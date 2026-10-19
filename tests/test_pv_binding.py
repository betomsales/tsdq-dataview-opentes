from copy import deepcopy
import importlib.util
import io
import unittest

import pandas as pd

from modules.network.cosim_loader import (
    apply_measurement_snapshot,
    get_monitored_node_ids,
    load_cosim_results,
    prepare_node_time_series,
)
from modules.network.graph_model import NetworkGraph, NetworkNode
from modules.network.pv_binding import vincular_medicoes_pv
from utils.estado_geracao import montar_estado_geracao_fv_medicoes
from utils.qee import montar_card_fases


def preparar_caso():
    graph = NetworkGraph()
    for barra in ("675", "680"):
        graph.add_node(NetworkNode(barra, barra, "pv", metadata={"nodes": [1, 2, 3]}))
    graph.add_node(NetworkNode("671", "671", "storage"))
    graph.metadata["elements"] = [
        {"id": "pv_pv1", "name": "pv1", "element_type": "pv", "bus": "675"},
        {"id": "pv_pv2", "name": "pv2", "element_type": "pv", "bus": "680"},
        {"id": "storage_bat1", "name": "bat1", "element_type": "storage", "bus": "671"},
    ]
    dados = {"date": ["2018-01-01 00:00:00", "2018-01-01 00:05:00"]}
    for barra in ("675", "680"):
        for fase in (1, 2, 3):
            dados[f"DSS-0.Bus-{barra}-V{fase}_pu"] = [0.98, 1.0]
    for pv, p, q in (("pv1", [10, 20], [1, 2]), ("pv2", [30, 40], [-1, -2])):
        dados[f"DSS-0.PVSystem-{pv}-P_meas"] = p
        dados[f"DSS-0.PVSystem-{pv}-P_pu"] = [valor / 100 for valor in p]
        dados[f"DSS-0.PVSystem-{pv}-Q_meas"] = q
    return graph, *load_cosim_results(io.StringIO(pd.DataFrame(dados).to_csv(index=False)))


class VinculoPvTest(unittest.TestCase):
    def setUp(self):
        self.graph, self.df, self.catalogo, _, self.tempos = preparar_caso()

    def pv(self, nome="pv2", barra=None, kind="pv", coluna=None):
        return {
            "target_kind": kind, "target_id": nome, "target_node_id": barra,
            "column": coluna or f"DSS-0.PVSystem-{nome}-P_meas",
            "variable": "P_meas", "group": f"PVSystem {nome}",
        }

    def resolver(self, item):
        return vincular_medicoes_pv(self.graph, [item])[0]

    def test_dois_pvs_sao_associados_pelo_nome_sem_modificar_catalogo(self):
        original = deepcopy(self.catalogo)
        vinculadas = vincular_medicoes_pv(self.graph, self.catalogo)
        for item in vinculadas:
            if item["target_kind"] == "pv":
                self.assertEqual(item["target_node_id"], {"pv1": "675", "pv2": "680"}[item["target_id"]])
                self.assertEqual(item["binding_source"], "elements")
                self.assertIsNone(item["binding_error"])
        self.assertEqual(self.catalogo, original)
        self.assertEqual(vincular_medicoes_pv(self.graph, vinculadas), vinculadas)

    def test_id_e_nome_personalizados_sao_aliases_exatos(self):
        self.graph.metadata["elements"][1].update(id="pv_beto_fotovoltaico", name="beto_fotovoltaico")
        for nome in ("beto_fotovoltaico", "PV_BETO_FOTOVOLTAICO"):
            self.assertEqual(self.resolver(self.pv(nome))["target_node_id"], "680")
        self.assertIsNone(self.resolver(self.pv("beto"))["target_node_id"])

    def test_nao_confunde_pv2_com_pv20(self):
        self.assertIsNone(self.resolver(self.pv("pv20"))["target_node_id"])

    def test_bus_explicito_compativel_e_conflitante(self):
        self.assertEqual(self.resolver(self.pv(barra="680"))["target_node_id"], "680")
        item = self.resolver(self.pv(barra="675"))
        self.assertIsNone(item["target_node_id"])
        self.assertIn("diverge", item["binding_error"])

    def test_alias_ambiguo_nao_e_associado(self):
        self.graph.metadata["elements"].append({"id": "outro", "name": "pv2", "element_type": "pv", "bus": "675"})
        item = self.resolver(self.pv())
        self.assertIsNone(item["target_node_id"])
        self.assertIn("ambiguo", item["binding_error"])

    def test_barramento_inexistente_nao_e_associado(self):
        self.graph.metadata["elements"][1]["bus"] = "999"
        item = self.resolver(self.pv())
        self.assertIsNone(item["target_node_id"])
        self.assertIn("ausente", item["binding_error"])

    def test_attached_complementa_o_cadastro_e_detecta_conflitos(self):
        self.graph.nodes["680"].metadata["attached"] = {"pv": ["pv_pv2"]}
        self.assertEqual(self.resolver(self.pv())["target_node_id"], "680")
        self.graph.nodes["675"].metadata["attached"] = {"pv": ["pv_pv2"]}
        self.assertIsNone(self.resolver(self.pv())["target_node_id"])

    def test_attached_sem_elements_resolve_id_exato(self):
        self.graph.metadata["elements"] = []
        self.graph.nodes["680"].metadata["attached"] = {"pv": ["pv_pv2"]}
        self.assertEqual(self.resolver(self.pv("pv_pv2"))["target_node_id"], "680")

    def test_legado_com_um_unico_pv_permanece_compativel(self):
        self.graph.metadata["elements"] = []
        self.graph.nodes["675"].node_type = "bus"
        self.assertEqual(self.resolver(self.pv("pv_antigo"))["target_node_id"], "680")
        self.assertEqual(self.resolver(self.pv("pv_antigo"))["binding_source"], "legacy_single_pv")

    def test_nao_aplica_fallback_quando_ha_cadastro_explicito(self):
        self.graph.nodes["675"].node_type = "bus"
        self.assertIsNone(self.resolver(self.pv("desconhecido"))["target_node_id"])

    def test_paineis_legados_e_bus_explicito_permanecem_compativeis(self):
        item = self.pv("PVPanel_0", "675", "pv_equipment", "PVSimulator-0.PVPanel_0_bus675-temperature")
        self.assertEqual(self.resolver(item)["target_node_id"], "675")
        self.graph.metadata["elements"] = []
        self.graph.nodes["675"].node_type = "bus"
        item["target_node_id"] = None
        self.assertEqual(self.resolver(item)["target_node_id"], "680")

    def test_storage_circuit_e_switch_nao_sao_atribuidos_ao_pv_legado(self):
        self.graph.metadata["elements"] = []
        self.graph.nodes["675"].node_type = "bus"
        for classe in ("Storage", "Circuit", "Switch"):
            with self.subTest(classe=classe):
                item = self.pv(classe.lower(), kind="pv_equipment", coluna=f"DSS-0.{classe}-bat1-P_act")
                self.assertIsNone(self.resolver(item)["target_node_id"])

    def test_pvs_distintos_na_mesma_barra_continuam_identificados(self):
        self.graph.metadata["elements"][0]["bus"] = "680"
        apply_measurement_snapshot(self.graph, self.df, self.catalogo, 1)
        pvs = {m["target_id"] for m in self.graph.nodes["680"].metadata["measurements"] if m["target_kind"] == "pv"}
        self.assertEqual(pvs, {"pv1", "pv2"})

    def test_snapshot_series_e_monitoramento_usam_mesmo_vinculo(self):
        apply_measurement_snapshot(self.graph, self.df, self.catalogo, 1)
        for barra, pv, p, q in (("675", "pv1", 20, 2), ("680", "pv2", 40, -2)):
            medidas = [m for m in self.graph.nodes[barra].metadata["measurements"] if m["target_kind"] == "pv"]
            self.assertEqual({m["target_id"] for m in medidas}, {pv})
            medidas = {m["categoria_card"]: m for m in medidas}
            self.assertEqual(medidas["Potência Ativa do PVSystem"]["valor"], p)
            self.assertEqual(medidas["Potência Ativa do PVSystem"]["unidade"], "W")
            self.assertEqual(medidas["Potência Reativa do PVSystem"]["valor"], q)
            self.assertEqual(medidas["Potência Reativa do PVSystem"]["unidade"], "Var")
            self.assertEqual(medidas["Potência Ativa Normalizada"]["unidade"], "pu")
            curvas = prepare_node_time_series(self.graph, self.df, self.catalogo, self.tempos, barra)
            self.assertEqual(len(curvas), 6)
            self.assertTrue(all(f"PVSystem-{pv}-" in s["coluna_original"] for s in curvas if ".PVSystem-" in s["coluna_original"]))
        self.assertEqual(get_monitored_node_ids(self.graph, [c for c in self.catalogo if c["target_kind"] == "pv"]), ["675", "680"])

    def test_pu_nao_e_somado_a_potencia_medida_no_estado(self):
        apply_measurement_snapshot(self.graph, self.df, self.catalogo, 1)
        estado = montar_estado_geracao_fv_medicoes(self.graph.nodes["680"].metadata["measurements"])
        self.assertEqual(dict(estado["rows"])["Potência"], "40.0000 W")


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit necessario")
class VinculoPvInterfaceTest(unittest.TestCase):
    def test_estrutura_de_analise_e_medias_separam_pu_e_w(self):
        from components.analise_eletrica_rede import montar_estrutura_analise_rede, _equipamentos_vinculados
        from utils.qee import identificar_variaveis_qee

        graph, df, catalogo, _, _ = preparar_caso()
        estrutura = montar_estrutura_analise_rede(graph, catalogo)
        self.assertEqual(_equipamentos_vinculados(graph, estrutura, "680"), ["pvsystem:pv2"])
        variaveis = [v for v in identificar_variaveis_qee(estrutura)["potencia_fv"] if v["target_node_id"] == "680"]
        for categoria, esperado, unidade in (("Potência Ativa do PVSystem", 35, "W"), ("Potência Ativa Normalizada", 0.35, "pu")):
            dados = montar_card_fases(df, [v for v in variaveis if v["categoria_card"] == categoria])
            self.assertAlmostEqual(dados["PVSystem pv2"]["valor"], esperado)
            self.assertEqual(dados["PVSystem pv2"]["unidade"], unidade)

    def test_cards_contextuais_exibem_apenas_o_pv_da_barra(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string('''
from test_pv_binding import preparar_caso
from components.analise_eletrica_rede import montar_estrutura_analise_rede
from components.cards_qee import render_cards_qee
from modules.network.cosim_loader import apply_measurement_snapshot
from modules.network.element_inspector import render_node_details
graph, df, catalogo, _, _ = preparar_caso()
apply_measurement_snapshot(graph, df, catalogo, 1)
render_node_details("680", graph)
render_cards_qee(df, montar_estrutura_analise_rede(graph, catalogo), elemento_referencia="680", permitir_selecao=False)
''', default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        html = "\n".join(m.value for m in app.markdown)
        self.assertIn("PVSystem pv2", html)
        self.assertNotIn("PVSystem pv1", html)
        self.assertIn("40.0000 W", html)
        self.assertIn("35.0000 W", html)
        self.assertNotIn("0.3500 pu", html)
        self.assertNotIn("Potência Ativa Normalizada", html)
        self.assertNotIn("Potência ativa normalizada", html)


if __name__ == "__main__":
    unittest.main()
