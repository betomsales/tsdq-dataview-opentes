import math
import unittest

import pandas as pd

from modules.network.topology_styles import get_voltage_color
from utils.prodist import classificar_tensao, obter_limites_prodist
from utils.qee import (
    calcular_drp_drc_global,
    calcular_drp_drc_por_fase,
    classificar_tensao_prodist,
    identificar_variaveis_qee,
)


LIMITES = {
    "critico_min": 0.90,
    "adequado_min": 0.93,
    "adequado_max": 1.05,
    "critico_max": 1.08,
}


def tensao(coluna, fase="V1", unidade="pu", **campos):
    return {
        "tipo": "Tensão",
        "elemento": "634",
        "fase": fase,
        "unidade_detectada": unidade,
        "coluna_original": coluna,
        **campos,
    }


class IndicadoresTensaoTest(unittest.TestCase):
    def test_limites_inclusivos_e_decomposicao(self):
        df = pd.DataFrame({
            "va": [0.89, 0.90, 0.9299, 0.93, 1, 1.05, 1.0501, 1.08, 1.0801, 0],
        })
        resultado = calcular_drp_drc_por_fase(df, [tensao("va")], LIMITES)
        fase = resultado["fases"][0]

        self.assertEqual(fase["amostras_validas"], 10)
        self.assertEqual(fase["contagens"], {
            "drp_sub": 2, "drp_sobre": 2, "drc_sub": 2, "drc_sobre": 1,
        })
        self.assertEqual(fase["drp"], {"total": 40, "subtensao": 20, "sobretensao": 20})
        self.assertEqual(fase["drc"], {"total": 30, "subtensao": 20, "sobretensao": 10})
        for indicador in ("drp", "drc"):
            self.assertAlmostEqual(
                fase[indicador]["total"],
                fase[indicador]["subtensao"] + fase[indicador]["sobretensao"],
            )

    def test_resumo_nao_combina_contribuicoes_de_fases_diferentes(self):
        df = pd.DataFrame({
            "va": [0.91, 0.91, 0.91, 1],
            "vb": [0.89, 1.09, 1, 1],
            "vc": [1.06, 1.06, 1, 1],
        })
        variaveis = [tensao("va"), tensao("vb", "V2"), tensao("vc", "V3")]
        resultado = calcular_drp_drc_por_fase(df, variaveis, LIMITES)

        self.assertEqual(resultado["resumo"]["drp"]["fase"], "Fase A")
        self.assertEqual(resultado["resumo"]["drp"]["drp"], {
            "total": 75, "subtensao": 75, "sobretensao": 0,
        })
        self.assertEqual(resultado["resumo"]["drc"]["fase"], "Fase B")
        self.assertEqual(resultado["resumo"]["drc"]["drc"], {
            "total": 50, "subtensao": 25, "sobretensao": 25,
        })
        self.assertEqual(calcular_drp_drc_global(df, variaveis, LIMITES), (75, 50))

    def test_zero_permanece_e_ausencias_nao_entram_no_denominador(self):
        df = pd.DataFrame({"va": [0, None, "", math.inf, -math.inf, "texto", 1]})
        resultado = calcular_drp_drc_por_fase(df, [tensao("va")])
        fase = resultado["fases"][0]

        self.assertEqual(fase["amostras_validas"], 2)
        self.assertEqual(fase["amostras_invalidas"], 5)
        self.assertEqual(fase["drc"]["subtensao"], 50)
        self.assertEqual(df["va"].iloc[0], 0)
        self.assertEqual(df["va"].iloc[5], "texto")

    def test_denominador_individual_e_fase_sem_dados(self):
        df = pd.DataFrame({"va": [0, None], "vb": [None, None], "vc": [0, 1]})
        resultado = calcular_drp_drc_por_fase(
            df, [
                tensao(coluna, fase, fases_presentes=[1, 2, 3])
                for coluna, fase in (("va", "VA"), ("vb", "VB"), ("vc", "VC"))
            ],
        )
        a, b, c = resultado["fases"]

        self.assertEqual(a["drc"]["total"], 100)
        self.assertIsNone(b["drp"]["total"])
        self.assertIsNone(b["drc"]["total"])
        self.assertEqual(c["drc"]["total"], 50)
        self.assertEqual(resultado["resumo"]["drc"]["fase"], "Fase A")

    def test_fases_zeradas_ausentes_em_barras_mono_e_bifasicas(self):
        variaveis = [tensao("va"), tensao("vb", "V2"), tensao("vc", "V3")]
        for dados, presentes, ausentes in (
            ({"va": [1, 0.91], "vb": [0, 0], "vc": [0, 0]}, ["Fase A"], ["Fase B", "Fase C"]),
            ({"va": [1, 1], "vb": [0, 0], "vc": [1, 1.06]}, ["Fase A", "Fase C"], ["Fase B"]),
            ({"va": [0, 0], "vb": [0, 0], "vc": [1, 1]}, ["Fase C"], ["Fase A", "Fase B"]),
        ):
            with self.subTest(presentes=presentes):
                df = pd.DataFrame(dados)
                original = df.copy(deep=True)
                resultado = calcular_drp_drc_por_fase(df, variaveis)
                self.assertEqual([fase["fase"] for fase in resultado["fases"]], presentes)
                self.assertEqual([fase["fase"] for fase in resultado["fases_ausentes"]], ausentes)
                self.assertLess(resultado["resumo"]["drc"]["drc"]["total"], 100)
                self.assertEqual(len(resultado["dados_pu"].columns), len(presentes))
                self.assertEqual(len(resultado["variaveis"]), len(presentes))
                pd.testing.assert_frame_equal(df, original)

    def test_fases_do_json_prevalecem_sobre_os_valores_do_csv(self):
        df = pd.DataFrame({"va": [0, 0], "vb": [1.10, 1.10], "vc": [1, 1]})
        variaveis = [
            tensao(coluna, fase, fases_presentes=[1, 3])
            for coluna, fase in (("va", "V1"), ("vb", "V2"), ("vc", "V3"))
        ]
        resultado = calcular_drp_drc_por_fase(df, variaveis)
        self.assertEqual([fase["fase"] for fase in resultado["fases"]], ["Fase A", "Fase C"])
        self.assertEqual(resultado["fases_ausentes"][0]["fase"], "Fase B")
        self.assertEqual(resultado["fases_ausentes"][0]["motivo"], "Fase não conectada no JSON")
        self.assertEqual(resultado["resumo"]["drc"]["fase"], "Fase A")
        self.assertEqual(resultado["resumo"]["drc"]["drc"]["subtensao"], 100)

    def test_trifasico_declarado_mantem_fase_desenergizada(self):
        df = pd.DataFrame({"va": [1, 1], "vb": [0, 0], "vc": [1, 1]})
        variaveis = [
            tensao(coluna, fase, fases_presentes=[1, 2, 3])
            for coluna, fase in (("va", "V1"), ("vb", "V2"), ("vc", "V3"))
        ]
        resultado = calcular_drp_drc_por_fase(df, variaveis)
        self.assertEqual(resultado["fases_ausentes"], [])
        self.assertEqual(resultado["resumo"]["drc"]["fase"], "Fase B")
        self.assertEqual(resultado["resumo"]["drc"]["drc"]["total"], 100)

    def test_apenas_fases_ausentes_nao_resultam_em_drc_ou_drp_zero(self):
        resultado = calcular_drp_drc_por_fase(pd.DataFrame({"va": [0, 0]}), [tensao("va")])
        self.assertEqual(resultado["fases"], [])
        self.assertEqual(len(resultado["fases_ausentes"]), 1)
        self.assertEqual(resultado["resumo"], {"drp": None, "drc": None})

    def test_fase_inexistente_em_tensao_absoluta_nao_exige_referencia(self):
        resultado = calcular_drp_drc_por_fase(
            pd.DataFrame({"vb": [0, 0]}), [tensao("vb", "V2", "V")],
        )
        self.assertEqual(resultado["descartadas"], [])
        self.assertEqual(len(resultado["fases_ausentes"]), 1)

    def test_fases_com_neutro_e_tensoes_fase_fase(self):
        for fase in ("V2", "VB", "VBN", "V12", "VAB"):
            with self.subTest(fase=fase):
                resultado = calcular_drp_drc_por_fase(
                    pd.DataFrame({"v": [1]}),
                    [tensao("v", fase, fases_presentes=["1", "3", "0"])],
                )
                self.assertEqual(resultado["fases"], [])
                self.assertEqual(len(resultado["fases_ausentes"]), 1)
        resultado = calcular_drp_drc_por_fase(
            pd.DataFrame({"v": [0, 0]}), [tensao("v", "VAC", fases_presentes=[1, 3])],
        )
        self.assertEqual(resultado["fases"][0]["drc"]["total"], 100)

    def test_sem_dados_validos_nao_e_fase_ausente(self):
        resultado = calcular_drp_drc_por_fase(
            pd.DataFrame({"va": [None, math.inf, "texto"]}), [tensao("va")],
        )
        self.assertEqual(resultado["fases_ausentes"], [])
        self.assertEqual(resultado["fases"][0]["amostras_validas"], 0)

    def test_dados_vazios_nao_representam_indicador_zero(self):
        for df in (pd.DataFrame({"va": []}), pd.DataFrame({"va": [None]})):
            with self.subTest(linhas=len(df)):
                self.assertEqual(calcular_drp_drc_global(df, [tensao("va")]), (None, None))
        resultado = calcular_drp_drc_por_fase(pd.DataFrame(), [])
        self.assertEqual(resultado["fases"], [])
        self.assertEqual(resultado["resumo"], {"drp": None, "drc": None})

    def test_magnitudes_sao_separadas_de_angulos_e_unidades_invalidas(self):
        variaveis = [
            tensao("va"),
            tensao("DSS-0.Bus-634-V1_ang", unidade="°"),
            tensao("angulo_pu", variavel_base="V1_ang"),
            tensao("corrente", unidade="A"),
            tensao("sem_unidade", unidade=None),
        ]
        estrutura = {"Tensão": {"634": variaveis}}
        self.assertEqual(identificar_variaveis_qee(estrutura)["tensao"], [variaveis[0]])
        df = pd.DataFrame({variavel["coluna_original"]: [1] for variavel in variaveis})
        resultado = calcular_drp_drc_por_fase(df, variaveis)
        self.assertEqual(len(resultado["fases"]), 1)
        self.assertEqual(len(resultado["descartadas"]), 4)

    def test_tensoes_absolutas_exigem_referencia_explicita(self):
        df = pd.DataFrame({"va_v": [0, 90, 93, 105, 106], "vb_kv": [0, 0.90, 0.93, 1.05, 1.06]})
        variaveis = [tensao("va_v", unidade="V"), tensao("vb_kv", "VB", "kV")]
        sem_base = calcular_drp_drc_por_fase(df, variaveis)
        self.assertEqual(len(sem_base["descartadas"]), 2)
        self.assertIsNone(sem_base["resumo"]["drc"])

        resultado = calcular_drp_drc_por_fase(
            df, variaveis, referencias_tensao={"va_v": 100, "vb_kv": 1},
        )
        for fase in resultado["fases"]:
            self.assertEqual(fase["drp"]["total"], 20)
            self.assertEqual(fase["drc"]["subtensao"], 20)
            self.assertEqual(fase["drc"]["sobretensao"], 20)

    def test_referencias_nulas_negativas_ou_nao_finitas_nao_sao_usadas(self):
        df = pd.DataFrame({"va": [100]})
        for referencia in (0, -1, None, math.nan, math.inf, "texto"):
            with self.subTest(referencia=referencia):
                resultado = calcular_drp_drc_por_fase(
                    df, [tensao("va", unidade="V")], referencias_tensao={"va": referencia},
                )
                self.assertEqual(len(resultado["descartadas"]), 1)
                self.assertIsNone(resultado["resumo"]["drp"])

    def test_conversao_na_fronteira_nao_produz_critico_por_arredondamento(self):
        df = pd.DataFrame({"va": [0.09, 0.093, 0.105]})
        resultado = calcular_drp_drc_por_fase(
            df, [tensao("va", unidade="kV")], referencias_tensao={"va": 0.1},
        )
        fase = resultado["fases"][0]
        self.assertEqual(fase["contagens"]["drp_sub"], 1)
        self.assertEqual(fase["drc"]["total"], 0)

    def test_conversao_nao_inclui_resultado_nao_finito(self):
        df = pd.DataFrame({"va": [1e308]})
        resultado = calcular_drp_drc_por_fase(
            df, [tensao("va", unidade="V")], referencias_tensao={"va": 1e-308},
        )
        self.assertEqual(resultado["fases"][0]["amostras_validas"], 0)
        self.assertIsNone(resultado["resumo"]["drp"])

    def test_colunas_duplicadas_no_catalogo_nao_sao_contadas_duas_vezes(self):
        df = pd.DataFrame({"va": [0.91, 1]})
        variavel = tensao("va")
        resultado = calcular_drp_drc_por_fase(df, [variavel, variavel.copy()])
        self.assertEqual(len(resultado["fases"]), 1)
        self.assertEqual(resultado["fases"][0]["amostras_validas"], 2)

    def test_coluna_inexistente_tem_diagnostico(self):
        resultado = calcular_drp_drc_por_fase(pd.DataFrame(), [tensao("ausente")])
        self.assertEqual(resultado["descartadas"][0]["motivo"], "Coluna ausente no arquivo")

    def test_limites_invalidos_sao_rejeitados(self):
        for limites in (
            {**LIMITES, "critico_min": 2},
            {**LIMITES, "critico_max": math.inf},
        ):
            with self.assertRaises(ValueError):
                calcular_drp_drc_por_fase(pd.DataFrame(), [], limites)

    def test_faixas_padrao_compartilhadas_com_graficos_e_mapa(self):
        limites = obter_limites_prodist()
        self.assertEqual(limites["critico_max"], 1.05)
        for valor, classe, cor in (
            (0, "critico", "#E74C3C"),
            (0.90, "precario", "#F1C40F"),
            (0.93, "adequado", "#2ECC71"),
            (1.05, "adequado", "#2ECC71"),
            (1.06, "critico", "#E74C3C"),
            (None, None, None),
            (math.nan, None, None),
        ):
            with self.subTest(valor=valor):
                self.assertEqual(classificar_tensao_prodist(valor), classe)
                self.assertEqual(classificar_tensao(valor), classe)
                self.assertEqual(get_voltage_color(valor), cor)


if __name__ == "__main__":
    unittest.main()
