import importlib.util
import io
import json
from pathlib import Path
import unittest

import pandas as pd


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit necessario")
class CardsQeeTest(unittest.TestCase):
    def app_qee(self, unidade="pu", contextual=True, sem_dados=False, dados=None, fases_presentes=None):
        from streamlit.testing.v1 import AppTest

        script = f'''
import pandas as pd
from components.cards_qee import render_cards_qee

unidade = {unidade!r}
if {dados!r} is not None:
    dados = {dados!r}
elif {sem_dados!r}:
    dados = {{"va": [None, None], "vb": [None, None], "vc": [None, None]}}
elif unidade == "pu":
    dados = {{"va": [0.91, 0.91, 0.91, 1], "vb": [0, 1.06, 1, 1], "vc": [1, 1, 1, 1]}}
else:
    dados = {{"va": [0, 90, 93, 105, 106]}}
df = pd.DataFrame(dados)
variaveis = [
    {{"tipo": "Tensão", "elemento": "634", "fase": f"V{{i + 1}}",
      "unidade_detectada": unidade, "coluna_original": coluna,
      "fases_presentes": {fases_presentes!r}}}
    for i, coluna in enumerate(df.columns)
]
estrutura = {{"Tensão": {{"634": variaveis}}}}
render_cards_qee(
    df, estrutura,
    elemento_referencia="634" if {contextual!r} else None,
    permitir_selecao=not {contextual!r},
)
'''
        return AppTest.from_string(script, default_timeout=30).run()

    def indicadores(self, app):
        for tabela in app.dataframe:
            if "DRP total (%)" in tabela.value.columns:
                return tabela.value.set_index("Fase")
        self.fail("Tabela por fase ausente")

    def test_seis_cartoes_e_tabela_nas_duas_selecoes(self):
        for contextual in (True, False):
            with self.subTest(contextual=contextual):
                app = self.app_qee(contextual=contextual)
                self.assertEqual(len(app.exception), 0)
                html = "\n".join(elemento.value for elemento in app.markdown)
                for indicador in ("DRP", "DRC"):
                    for parcela in ("total", "subtensão", "sobretensão"):
                        self.assertIn(f"{indicador} - {parcela}", html)
                tabela = self.indicadores(app)
                self.assertEqual(tabela.loc["Fase A", "DRP total (%)"], 75)
                self.assertEqual(tabela.loc["Fase B", "DRC subtensão (%)"], 25)
                self.assertEqual(tabela.loc["Fase B", "DRC sobretensão (%)"], 25)
                self.assertEqual(len(app.selectbox), 0 if contextual else 1)

    def test_referencia_absoluta_recalcula_os_cartoes(self):
        app = self.app_qee(unidade="V")
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.number_input), 1)
        self.assertTrue(any("Coluna não apurada" in tabela.value.columns for tabela in app.dataframe))

        app.number_input[0].set_value(100.0).run()
        self.assertEqual(len(app.exception), 0)
        tabela = self.indicadores(app)
        self.assertEqual(tabela.loc["Fase A", "DRP total (%)"], 20)
        self.assertEqual(tabela.loc["Fase A", "DRC total (%)"], 40)

    def test_ausencia_de_dados_nao_exibe_nan(self):
        app = self.app_qee(sem_dados=True)
        self.assertEqual(len(app.exception), 0)
        html = "\n".join(elemento.value for elemento in app.markdown)
        self.assertNotIn("nan", html.lower())
        self.assertIn("Não identificado", html)

    def test_fases_ausentes_nao_aparecem_como_drc_nos_cartoes(self):
        for contextual in (True, False):
            with self.subTest(contextual=contextual):
                app = self.app_qee(
                    contextual=contextual,
                    dados={"va": [1, 0.91], "vb": [None, None], "vc": [None, None]},
                )
                self.assertEqual(len(app.exception), 0)
                tabela = self.indicadores(app)
                self.assertEqual(tabela.loc["Fase A", "DRC total (%)"], 0)
                for fase in ("Fase B", "Fase C"):
                    self.assertEqual(tabela.loc[fase, "Situação"], "Fase ausente")
                    self.assertTrue(pd.isna(tabela.loc[fase, "DRC total (%)"]))
                self.assertTrue(any("Fases ausentes: Fase B, Fase C" in c.value for c in app.caption))

    def test_todas_as_fases_ausentes_mantem_tabela_sem_indicador(self):
        app = self.app_qee(sem_dados=True)
        self.assertEqual(len(app.exception), 0)
        tabela = self.indicadores(app)
        self.assertTrue(tabela["DRC total (%)"].isna().all())
        self.assertTrue(tabela["Situação"].eq("Fase ausente").all())

    def test_fases_zeradas_aparecem_como_subtensao_critica_nos_cartoes(self):
        for contextual in (True, False):
            with self.subTest(contextual=contextual):
                app = self.app_qee(
                    contextual=contextual,
                    dados={"va": [0, 0], "vb": [None, None], "vc": [1, 1]},
                )
                self.assertEqual(len(app.exception), 0)
                tabela = self.indicadores(app)
                self.assertEqual(tabela.loc["Fase A", "DRC subtensão (%)"], 100)
                self.assertEqual(tabela.loc["Fase A", "DRC total (%)"], 100)
                self.assertNotEqual(tabela.loc["Fase A", "Situação"], "Fase ausente")
                self.assertEqual(tabela.loc["Fase B", "Situação"], "Fase ausente")
                self.assertEqual(tabela.loc["Fase C", "DRC total (%)"], 0)

    def test_metadados_de_fase_do_json_chegam_ao_calculo_qee(self):
        from components.analise_eletrica_rede import montar_estrutura_analise_rede
        from modules.network.cosim_loader import load_cosim_results, load_topology_json
        from utils.qee import calcular_drp_drc_por_fase, identificar_variaveis_qee

        csv = io.BytesIO(
            b"time,DSS-0.Bus-634-V1_pu,DSS-0.Bus-634-V2_pu,DSS-0.Bus-634-V3_pu\n"
            b"2026-01-01 00:00:00,0,1.10,1\n"
            b"2026-01-01 00:05:00,0,1.10,1\n"
        )
        for fases in ([1, 3], None):
            with self.subTest(fases=fases):
                metadata = {"nodes": fases} if fases is not None else {}
                topologia = {
                    "nodes": [{"id": "634", "metadata": metadata}, {"id": "650"}],
                    "edges": [{"id": "l1", "source": "650", "target": "634"}],
                }
                graph = load_topology_json(io.BytesIO(json.dumps(topologia).encode()))
                df, catalogo, _, _ = load_cosim_results(csv)
                estrutura = montar_estrutura_analise_rede(graph, catalogo)
                variaveis = identificar_variaveis_qee(estrutura)["tensao"]
                if fases is not None:
                    self.assertTrue(all(v["fases_presentes"] == fases for v in variaveis))
                else:
                    self.assertTrue(all("fases_presentes" not in v for v in variaveis))
                resultado = calcular_drp_drc_por_fase(df, variaveis)
                if fases is not None:
                    self.assertEqual(resultado["fases_ausentes"][0]["fase"], "Fase B")
                else:
                    self.assertEqual(resultado["fases_ausentes"], [])
                self.assertEqual(resultado["resumo"]["drc"]["fase"], "Fase A")

    def test_pagina_analise_eletrica_com_csv_carregado(self):
        from streamlit.testing.v1 import AppTest

        pagina = Path(__file__).resolve().parents[1] / "pages" / "1_Análise_Elétrica.py"
        csv = io.BytesIO(
            b"time,DSS-0.Bus-634-V1_pu,DSS-0.Bus-634-V2_pu\n"
            b"2026-01-01 00:00:00,0.91,0\n"
            b"2026-01-01 00:05:00,1,1.06\n"
        )
        csv.name = "qee_test.csv"
        app = AppTest.from_file(str(pagina), default_timeout=30)
        app.session_state["arquivo_eletrico"] = csv
        app.run()

        self.assertEqual(len(app.exception), 0)
        tabela = self.indicadores(app)
        self.assertEqual(tabela.loc["Fase A", "DRP total (%)"], 50)
        self.assertEqual(tabela.loc["Fase B", "DRC total (%)"], 100)


if __name__ == "__main__":
    unittest.main()
