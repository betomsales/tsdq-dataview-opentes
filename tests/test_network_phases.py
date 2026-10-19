import importlib.util
import math
import unittest

import pandas as pd

from modules.network.cosim_loader import (
    apply_measurement_snapshot,
    identificar_fases_ausentes,
)
from modules.network.graph_model import NetworkGraph, NetworkNode


def preparar_rede(valores, metadata=None, aliases=False):
    graph = NetworkGraph()
    graph.add_node(NetworkNode("611", "611", "bus", metadata=metadata or {}))
    fases = "ABC" if aliases else "123"
    catalogo = [
        {
            "column": f"DSS-0.Bus-611-V{fase}_pu",
            "variable": f"V{fase}_pu",
            "target_kind": "node",
            "target_id": "611",
            "group": "Barramento",
        }
        for fase in fases
    ]
    df = pd.DataFrame({item["column"]: serie for item, serie in zip(catalogo, valores)})
    return graph, df, catalogo


class FasesRedeTest(unittest.TestCase):
    def test_media_monofasica_preserva_leituras_originais_zeradas(self):
        graph, df, catalogo = preparar_rede([[0, 0], [0, 0], [0.96, 0.98]])
        original = df.copy(deep=True)
        for indice, esperado in enumerate((0.96, 0.98)):
            apply_measurement_snapshot(graph, df, catalogo, indice)
            node = graph.nodes["611"]
            self.assertEqual(node.metadata["absent_voltage_phases"], ["A", "B"])
            self.assertEqual(node.voltage_pu, esperado)
            self.assertEqual(node.metadata["voltage_phases_pu"]["V1"], 0)
            self.assertEqual(len(node.metadata["measurements"]), 3)
        pd.testing.assert_frame_equal(df, original)

    def test_media_bifasica_usa_somente_fases_existentes(self):
        graph, df, catalogo = preparar_rede([[1, 0.98], [0, 0], [0.96, 1]])
        for indice in range(2):
            apply_measurement_snapshot(graph, df, catalogo, indice)
            self.assertEqual(graph.nodes["611"].metadata["absent_voltage_phases"], ["B"])
            self.assertAlmostEqual(graph.nodes["611"].voltage_pu, (0.98, 0.99)[indice])

    def test_zero_pontual_em_fase_existente_nao_a_torna_ausente(self):
        graph, df, catalogo = preparar_rede([[0, 1], [0, 0], [0, 0]])
        for indice in range(2):
            apply_measurement_snapshot(graph, df, catalogo, indice)
            self.assertEqual(graph.nodes["611"].metadata["absent_voltage_phases"], ["B", "C"])
            self.assertEqual(graph.nodes["611"].voltage_pu, indice)

    def test_trifasico_explicitado_no_json_preserva_fase_desenergizada(self):
        graph, df, catalogo = preparar_rede([[0, 0], [1, 1], [1, 1]], {"nodes": [1, 2, 3]})
        apply_measurement_snapshot(graph, df, catalogo, 0)
        self.assertEqual(graph.nodes["611"].metadata["absent_voltage_phases"], [])
        self.assertAlmostEqual(graph.nodes["611"].voltage_pu, 2 / 3)

    def test_apenas_fases_ausentes_resultam_em_media_indisponivel(self):
        graph, df, catalogo = preparar_rede([[0, 0], [0, 0], [0, 0]])
        apply_measurement_snapshot(graph, df, catalogo, 0)
        self.assertEqual(graph.nodes["611"].metadata["absent_voltage_phases"], ["A", "B", "C"])
        self.assertIsNone(graph.nodes["611"].voltage_pu)

    def test_aliases_de_fase_sao_reconhecidos(self):
        graph, df, catalogo = preparar_rede([[1], [0], [1]], aliases=True)
        apply_measurement_snapshot(graph, df, catalogo, 0)
        self.assertEqual(graph.nodes["611"].metadata["absent_voltage_phases"], ["B"])
        self.assertEqual(graph.nodes["611"].voltage_pu, 1)

    def test_sem_amostras_validas_nao_e_fase_fisicamente_ausente(self):
        graph, df, catalogo = preparar_rede([[None, math.inf], [1, 1], [0, 0]])
        self.assertEqual(identificar_fases_ausentes(graph, df, catalogo)["611"], ["C"])

    def test_fases_sao_reavaliadas_ao_trocar_resultados(self):
        graph, df, catalogo = preparar_rede([[0], [0], [1]])
        apply_measurement_snapshot(graph, df, catalogo, 0)
        self.assertEqual(graph.nodes["611"].metadata["absent_voltage_phases"], ["A", "B"])
        df.loc[:, :] = 1
        apply_measurement_snapshot(graph, df, catalogo, 0)
        self.assertEqual(graph.nodes["611"].metadata["absent_voltage_phases"], [])
        self.assertEqual(graph.nodes["611"].voltage_pu, 1)


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit necessario")
class FasesD3Test(unittest.TestCase):
    def test_frames_preservam_zeros_e_ausencias_sem_mudar_o_tempo(self):
        from modules.network.d3_renderer import build_d3_temporal_frames, _graph_to_d3_payload

        graph, df, catalogo = preparar_rede([[0, 0], [0, 0], [0, 0.96]])
        tempos = pd.Series(pd.date_range("2026-01-01", periods=2, freq="5min"))
        apply_measurement_snapshot(graph, df, catalogo, 0)
        payload = _graph_to_d3_payload(graph)
        self.assertEqual(payload["nodes"][0]["absentPhases"], ["A", "B"])
        self.assertEqual(payload["nodes"][0]["phases"], {"A": 0, "B": 0, "C": 0})
        self.assertEqual(payload["nodes"][0]["voltage"], 0)

        frames = build_d3_temporal_frames(graph, df, catalogo, tempos)
        self.assertEqual([f["index"] for f in frames], [0, 1])
        self.assertEqual([f["label"] for f in frames], ["01/01/2026 00:00:00", "01/01/2026 00:05:00"])
        for frame, esperado in zip(frames, (0, 0.96)):
            node = frame["nodes"][0]
            self.assertEqual(node["absentPhases"], ["A", "B"])
            self.assertEqual(node["voltage"], esperado)
            self.assertEqual(node["phases"]["A"], 0)
            self.assertEqual(node["phases"]["B"], 0)
            self.assertEqual(node["measurements"], 1)

    def test_frames_separam_todas_ausentes_de_todas_sem_medicao(self):
        from modules.network.d3_renderer import build_d3_temporal_frames

        for valor, ausentes in ((0, ["A", "B", "C"]), (None, [])):
            with self.subTest(valor=valor):
                graph, df, catalogo = preparar_rede([[valor], [valor], [valor]])
                node = build_d3_temporal_frames(graph, df, catalogo)[0]["nodes"][0]
                self.assertEqual(node["absentPhases"], ausentes)
                self.assertIsNone(node["voltage"])


if __name__ == "__main__":
    unittest.main()
