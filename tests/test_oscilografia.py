import io
import math
import unittest
from unittest.mock import patch

import pandas as pd

from components.analise_eletrica_rede import montar_estrutura_analise_rede, preparar_dataframe_analise
from components.oscilografia import _variaveis_tensao_no, render_oscilografia_no
from modules.network.cosim_loader import load_cosim_results
from modules.network.graph_model import NetworkGraph, NetworkNode


def fixture():
    graph = NetworkGraph()
    graph.add_node(NetworkNode("611", "611", "bus", metadata={"nodes": [1, 2, 3]}))
    graph.add_node(NetworkNode("634", "634", "bus", metadata={"nodes": [1, 2, 3]}))
    columns = {}
    for node in ("611", "634"):
        for phase, angle in ((1, 0), (2, -120), (3, 120)):
            columns[f"DSS-0.Bus-{node}-V{phase}_pu"] = [0 if phase == 1 else 1, 0.98, 1.01]
            columns[f"DSS-0.Bus-{node}-V{phase}_ang"] = [angle] * 3
    original = pd.DataFrame({"time": pd.date_range("2026-01-01", periods=3, freq="5min"), **columns})
    df, catalog, _, times = load_cosim_results(io.StringIO(original.to_csv(index=False)), graph=graph)
    return preparar_dataframe_analise(df, times), montar_estrutura_analise_rede(graph, catalog)


class OscilografiaTest(unittest.TestCase):
    def setUp(self):
        self.df, self.structure = fixture()

    def render(self, node="611", structure=None, **kwargs):
        with patch("components.oscilografia.st") as streamlit:
            streamlit.selectbox.return_value = "pu"
            render_oscilografia_no(self.df, structure or self.structure, node, **kwargs)
            return streamlit.plotly_chart.call_args.args[0], streamlit

    def test_angles_are_cataloged_separately_from_voltage_magnitudes(self):
        self.assertEqual(len(self.structure["Tensão"]["611"]), 3)
        self.assertEqual(len(self.structure["Ângulo de Tensão (°)"]["611"]), 3)
        for node in ("611", "634"):
            variables = _variaveis_tensao_no(self.structure, node)
            self.assertEqual(len(variables), 3)
            self.assertTrue(all(v["unidade_detectada"] == "pu" for v in variables))
            self.assertTrue(all(f"Bus-{node}-" in v["coluna_original"] for v in variables))

    def test_legacy_angle_classification_cannot_enter_oscillography(self):
        legacy = {"Tensão": {"611": [
            {"tipo": "Tensão", "fase": "V1", "unidade_detectada": "pu", "coluna_original": "v1"},
            {"tipo": "Tensão", "fase": "V1", "unidade_detectada": "°", "coluna_original": "v1_angle"},
            {"tipo": "Tensão", "fase": "V2", "unidade_detectada": "pu", "variavel_base": "V2_ang", "coluna_original": "legacy_angle"},
        ]}}
        self.assertEqual([v["coluna_original"] for v in _variaveis_tensao_no(legacy, "611")], ["v1"])

    def test_graph_has_three_magnitudes_preserves_zero_and_current_time(self):
        fig, st = self.render(frame_index=0)
        lines = [trace for trace in fig.data if trace.mode == "lines"]
        self.assertEqual([trace.name for trace in lines], ["V1", "V2", "V3"])
        self.assertEqual(lines[0].y[0], 0)
        self.assertTrue(all(0 <= value < 2 for trace in lines for value in trace.y))
        self.assertEqual(fig.layout.yaxis.title.text, "Tensão [pu]")
        self.assertIsNone(fig.layout.title.text)
        self.assertEqual([a.text for a in fig.layout.annotations], ["Instante do grafo"])
        marker = next(shape for shape in fig.layout.shapes if shape.type == "line" and shape.x0 == shape.x1)
        self.assertEqual(marker.x0, self.df["Tempo_EixoX"].iloc[0])
        st.selectbox.assert_not_called()

    def test_nan_is_not_replaced_by_zero_or_interpolated(self):
        self.df.loc[1, "DSS-0.Bus-611-V2_pu"] = math.nan
        fig, _ = self.render(frame_index=1)
        trace = next(t for t in fig.data if t.name == "V2")
        self.assertTrue(math.isnan(trace.y[1]))
        self.assertFalse(trace.connectgaps)
        self.assertNotIn("V2 no instante", [trace.name for trace in fig.data])

    def test_mixed_magnitude_units_are_not_drawn_on_one_axis(self):
        other = dict(self.structure["Tensão"]["611"][0], unidade_detectada="kV", coluna_original="voltage_kv")
        self.df["voltage_kv"] = [2.4] * len(self.df)
        self.structure["Tensão"]["611"].append(other)
        fig, st = self.render()
        self.assertEqual([t.name for t in fig.data if t.mode == "lines"], ["V1", "V2", "V3"])
        st.selectbox.assert_called_once()

    def test_empty_node_has_no_chart(self):
        with patch("components.oscilografia.st") as streamlit:
            render_oscilografia_no(self.df, self.structure, "missing")
            streamlit.plotly_chart.assert_not_called()
            streamlit.info.assert_called_once()


if __name__ == "__main__":
    unittest.main()
