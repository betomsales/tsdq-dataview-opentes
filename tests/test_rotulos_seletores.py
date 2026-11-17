import ast
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from components.analise_eletrica_rede import render_analise_eletrica_elemento
from utils.escalas import obter_escala_visual
from utils.mapeamento import carregar_mapeamento
from utils.unidades import remover_unidade_do_tipo


ROOT = Path(__file__).resolve().parent.parent


class RotulosSeletoresTest(unittest.TestCase):
    def test_type_selectors_display_labels_but_return_original_keys(self):
        paths = (
            ROOT / "components" / "analise_eletrica_rede.py",
            ROOT / "pages" / "1_An\u00e1lise_El\u00e9trica.py",
        )
        types = [key for key in carregar_mapeamento() if not key.startswith("_")]
        labels = [remover_unidade_do_tipo(key) for key in types]
        self.assertIn("Pot\u00eancia Ativa da Rede", labels)
        self.assertIn("Pot\u00eancia Reativa da Rede", labels)
        self.assertIn("Pot\u00eancia do Gerador", labels)
        self.assertIn("Corrente", labels)
        self.assertIn("\u00c2ngulo de Corrente (\u00b0)", labels)
        self.assertIn("Irradi\u00e2ncia Solar (DNI)", labels)
        self.assertEqual(len(labels), len(set(labels)))

        for path in paths:
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                calls = [
                    node for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "selectbox"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "Tipo de vari\u00e1vel"
                ]
                self.assertEqual(len(calls), 1)
                # Exercise the actual selector expression without running page uploads.
                script = (
                    "import streamlit as st\n"
                    "from utils.unidades import remover_unidade_do_tipo\n"
                    f"tipos_disponiveis = {types!r}\n"
                    "indice_padrao = 0\n"
                    "key_prefix = 'test'\n"
                    f"selected = {ast.unparse(calls[0])}\n"
                    "st.write(selected)\n"
                )
                app = AppTest.from_string(script, default_timeout=30).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.selectbox[0].options, labels)
                for key in types:
                    app.selectbox[0].select(key).run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.selectbox[0].value, key)
                    self.assertEqual(app.markdown[0].value, key)

    def test_network_analysis_preserves_values_units_and_metadata(self):
        cases = (
            ("Pot\u00eancia Ativa da Rede (MW)", "P1", "W"),
            ("Pot\u00eancia Ativa da Rede (MW)", "P1", "kW"),
            ("Pot\u00eancia Ativa da Rede (MW)", "P1", "MW"),
            ("Pot\u00eancia Reativa da Rede (MVar)", "Q1", "Var"),
            ("Pot\u00eancia Reativa da Rede (MVar)", "Q1", "kVar"),
            ("Pot\u00eancia Reativa da Rede (MVar)", "Q1", "MVar"),
            ("Pot\u00eancia do Gerador (MW)", "P1", "W"),
            ("Corrente (A)", "I1", "A"),
            ("Corrente (A)", "I1", "kA"),
        )
        module = "components.analise_eletrica_rede"
        for category, phase, unit in cases:
            with self.subTest(category=category, unit=unit):
                df = pd.DataFrame({
                    "Tempo_EixoX": pd.date_range("2026-01-01", periods=3, freq="5min"),
                    "measurement": [0.0, -1.5, 2.5],
                })
                original_df = df.copy(deep=True)
                info = {
                    "tipo": category,
                    "fase": phase,
                    "unidade_detectada": unit,
                    "coluna_original": "measurement",
                }
                original_info = dict(info)
                structure = {category: {"element": [info]}}
                expected_unit, expected_factor = obter_escala_visual(df["measurement"], unit)
                with ExitStack() as stack:
                    st = stack.enter_context(patch(f"{module}.st"))
                    st.selectbox.return_value = category
                    chart = stack.enter_context(patch(f"{module}.render_grafico_individual"))
                    for name in ("render_tabela_serie", "render_tabela_dataset", "render_codigo_variavel"):
                        stack.enter_context(patch(f"{module}.{name}"))
                    render_analise_eletrica_elemento(df, structure, "element")

                chart.assert_called_once()
                data, column, label, metadata, *_ = chart.call_args.args
                self.assertEqual(column, "measurement")
                self.assertEqual(data["Valor"].tolist(), (df["measurement"] * expected_factor).tolist())
                self.assertEqual(label, f"{remover_unidade_do_tipo(category)} [{expected_unit}]")
                self.assertEqual(metadata, original_info)
                self.assertEqual(info, original_info)
                pd.testing.assert_frame_equal(df, original_df)
                formatter = st.selectbox.call_args.kwargs["format_func"]
                self.assertEqual(formatter(category), remover_unidade_do_tipo(category))


if __name__ == "__main__":
    unittest.main()
