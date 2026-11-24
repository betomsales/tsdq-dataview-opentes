import io
import json
import math
from pathlib import Path
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from components.graficos_comunicacao import criar_entrega, criar_jitter, criar_latencia, criar_mapa, criar_payload
from utils.comunicacao import (
    calcular_kpis, expandir_mensagens, extrair_remetente, ler_resultados_comunicacao,
    preparar_tabela_temporal, tabela_comparativa, validar_resultados_comunicacao,
)
from utils.comunicacao_metadados import MetadadosComunicacao, NAO_IDENTIFICADA, ler_metadado


def registros(messages=True):
    rows = []
    for time in (0, 1):
        for node, sent, received, dropped in (("a", 10, 6, 1), ("b", 20, 21, 2)):
            values = {"packets_sent": sent * time, "packets_received": received * time, "packets_dropped": dropped * time}
            if messages and time == 1:
                values.update(val_out=json.dumps({"sender": ("b" if node == "a" else "a") + "@host"}),
                              packet_sizes_out="100", latencies_out="0.002", jitters_out="0.000003")
            rows.extend({"Tempo": time, "Origem": "OmnetSim-0." + node, "Atributo": attr, "Valor": value} for attr, value in values.items())
    return pd.DataFrame(rows)


class ComunicacaoTest(unittest.TestCase):
    def test_csv_numeric_origin_preserved(self):
        raw = ler_resultados_comunicacao(io.BytesIO(b'Tempo,Origem,Atributo,Valor\n0,001,packets_sent,0\n'))
        self.assertEqual(raw.Origem.iloc[0], "001")
        self.assertFalse(validar_resultados_comunicacao(raw))
        self.assertEqual(len(preparar_tabela_temporal(raw, "001")), 1)

    def test_invalid_schema_time_and_duplicates(self):
        self.assertTrue(validar_resultados_comunicacao(pd.DataFrame()))
        for value in ("bad", float("inf"), -1):
            raw = registros().astype({"Tempo": object}); raw.loc[0, "Tempo"] = value
            self.assertTrue(validar_resultados_comunicacao(raw))
        raw = registros()
        self.assertTrue(validar_resultados_comunicacao(pd.concat([raw, raw.iloc[:1]])))

    def test_cumulative_totals_sum_nodes_not_samples(self):
        temporal = preparar_tabela_temporal(registros())
        kpis = calcular_kpis(temporal, expandir_mensagens(temporal))
        self.assertEqual(kpis["pacotes_enviados"], 30)
        self.assertEqual(kpis["pacotes_recebidos"], 27)
        self.assertEqual(kpis["pdr"], 90)
        self.assertEqual(kpis["taxa_drop"], 10)
        self.assertEqual(kpis["mensagens"], 2)

    def test_receiver_and_sender_are_distinct(self):
        expanded = expandir_mensagens(preparar_tabela_temporal(registros()))
        row = expanded[expanded.NodeId == "a"].iloc[0]
        self.assertEqual(row.Agente, "b")
        self.assertEqual(row.RemetenteId, "b")
        self.assertEqual(row.Latencia, .002)

    def test_missing_telemetry_is_nan_not_zero(self):
        raw = registros()
        raw = raw[~raw.Atributo.isin(["latencies_out", "jitters_out"])]
        expanded = expandir_mensagens(preparar_tabela_temporal(raw))
        self.assertTrue(expanded.Latencia.isna().all())
        self.assertTrue(expanded.attrs["avisos"])

    def test_zero_is_valid_telemetry(self):
        raw = registros(); raw.loc[raw.Atributo == "latencies_out", "Valor"] = "0"
        self.assertTrue(expandir_mensagens(preparar_tabela_temporal(raw)).Latencia.eq(0).all())

    def test_empty_messages_still_allow_counters(self):
        temporal = preparar_tabela_temporal(registros(False))
        expanded = expandir_mensagens(temporal)
        self.assertTrue(expanded.empty)
        kpis = calcular_kpis(temporal, expanded)
        self.assertEqual(kpis["pdr"], 90)
        self.assertTrue(math.isnan(kpis["latencia_media"]))

    def test_malformed_sender_does_not_crash(self):
        for message in ("[]", "null", "4", '{"sender": []}', "not-json"):
            self.assertEqual(extrair_remetente(message), "Não identificado")

    def test_unequal_lists_preserve_message_indices(self):
        temporal = pd.DataFrame([{"Tempo": 0, "Origem": "o", "NodeId": "n",
                                  "val_out": '{"sender":"a"}||||||{"sender":"c"}',
                                  "latencies_out": "0.01|||0.02|||0.03"}])
        expanded = expandir_mensagens(temporal)
        self.assertEqual(expanded.Latencia.tolist(), [.01, .03])

    def test_resets_missing_and_inconsistent_counters_disable_percentages(self):
        temporal = preparar_tabela_temporal(registros())
        temporal.loc[temporal.Tempo == 0, "packets_sent"] = 100
        self.assertTrue(math.isnan(calcular_kpis(temporal, expandir_mensagens(temporal))["pdr"]))
        temporal = preparar_tabela_temporal(registros())
        temporal.loc[0, "packets_sent"] = float("nan")
        self.assertTrue(math.isnan(calcular_kpis(temporal, expandir_mensagens(temporal))["pdr"]))
        temporal["packets_sent"] = 0
        kpis = calcular_kpis(temporal, expandir_mensagens(temporal))
        self.assertTrue(math.isnan(kpis["pdr"]))
        self.assertIn("excedem", " ".join(kpis["avisos"]))

    def test_comparison_exposes_units_and_valid_sample_count(self):
        messages = expandir_mensagens(preparar_tabela_temporal(registros()))
        summary = tabela_comparativa(messages, "NodeId")
        self.assertEqual(summary["Latência média (ms)"].tolist(), [2, 2])
        self.assertEqual(summary["Jitter médio (µs)"].tolist(), [3, 3])
        self.assertEqual(summary["Amostras de latência"].tolist(), [1, 1])


class MetadadosComunicacaoTest(unittest.TestCase):
    def metadata(self, links):
        return MetadadosComunicacao(links=[{"origem": a, "destino": b, "tipo": tech} for a, b, tech in links])

    def message(self, sender="a", receiver="b"):
        return pd.DataFrame([{"NodeId": receiver, "RemetenteId": sender}])

    def test_metadata_schema_validation(self):
        for kind, value in (("config", []), ("links", {}), ("posicoes", [{"id": "a", "x": "nan", "y": 0}]),
                            ("links", [{"origem": "a", "destino": "b"}]), ("posicoes", [1])):
            with self.assertRaises(ValueError):
                ler_metadado(json.dumps(value).encode(), kind)

    def test_legacy_agent_alias_and_technology(self):
        links = ler_metadado(b'[{"origem":"AgenteCentral","destino":"AgenteP_1","tipo":"Link_5G"}]', "links")
        result = MetadadosComunicacao(links=links).associar(self.message("agent_central", "agent_p_1"))
        self.assertEqual(result.Tecnologia.iloc[0], "5G")

    def test_direct_link(self):
        result = self.metadata([("a", "b", "5G")]).associar(self.message())
        self.assertEqual(result.Tecnologia.iloc[0], "5G")
        self.assertEqual(result.Associação.iloc[0], "Enlace direto declarado")

    def test_multihop_is_explicit_estimate_of_last_hop(self):
        result = self.metadata([("a", "x", "5G"), ("x", "b", "Cabeada")]).associar(self.message())
        self.assertEqual(result.Tecnologia.iloc[0], "Cabeada")
        self.assertIn("estimado", result.Associação.iloc[0])
        self.assertEqual(result.Enlace.iloc[0], "x → b")

    def test_ambiguous_paths_and_parallel_links_are_not_invented(self):
        for links in ([('a', 'x', '5G'), ('x', 'b', '5G'), ('a', 'y', '4G'), ('y', 'b', '4G')],
                      [('a', 'b', '5G'), ('a', 'b', '4G')]):
            result = self.metadata(links).associar(self.message())
            self.assertEqual(result.Tecnologia.iloc[0], NAO_IDENTIFICADA)

    def test_no_metadata_keeps_messages_and_unknown_technology(self):
        result = MetadadosComunicacao().associar(self.message())
        self.assertEqual(len(result), 1)
        self.assertEqual(result.Tecnologia.iloc[0], NAO_IDENTIFICADA)


class GraficosComunicacaoTest(unittest.TestCase):
    def test_comparative_figures_and_unit_conversion(self):
        temporal = preparar_tabela_temporal(registros())
        messages = MetadadosComunicacao().associar(expandir_mensagens(temporal))
        latency = criar_latencia(messages, "NodeId")
        self.assertEqual(list(latency.data[2].y), [2])
        self.assertEqual(latency.layout.yaxis.title.text, "Latência (ms)")
        self.assertTrue(all(trace.type == "box" for trace in criar_jitter(messages, "NodeId").data))
        self.assertTrue(all(trace.type == "bar" for trace in criar_payload(messages, "NodeId").data))
        delivery = criar_entrega(calcular_kpis(temporal, messages))
        self.assertAlmostEqual(sum(trace.x[0] for trace in delivery.data), 100)

    def test_map_does_not_create_coordinates_or_zero_latency(self):
        messages = MetadadosComunicacao().associar(expandir_mensagens(preparar_tabela_temporal(registros())))
        metadata = MetadadosComunicacao(posicoes=[{"id": "a", "x": 0, "y": 1}, {"id": "z", "x": 2, "y": 3}])
        fig = criar_mapa(messages, metadata)
        self.assertEqual(len(fig.data), 2)
        self.assertEqual(fig.data[0].marker.color, "#CBD2CF")
        self.assertEqual(list(fig.data[1].marker.color), [2])

    def test_empty_page_renders_without_exceptions(self):
        path = Path(__file__).resolve().parents[1] / "pages" / "2_Comunicação.py"
        app = AppTest.from_file(str(path), default_timeout=30).run()
        self.assertFalse(app.exception)

    def loaded_page(self, raw, metadata=None):
        path = Path(__file__).resolve().parents[1] / "pages" / "2_Comunicação.py"
        files = {"Resultados de comunicação (CSV)": raw.to_csv(index=False).encode()}
        if metadata:
            files.update({label: json.dumps(value).encode() for label, value in metadata.items()})
        script = f'''
from io import BytesIO
import runpy
from unittest.mock import patch
files = {files!r}
def upload(label, **kwargs):
    if label not in files:
        return None
    result = BytesIO(files[label])
    result.name = label
    return result
with patch("streamlit.file_uploader", side_effect=upload):
    runpy.run_path({str(path)!r}, run_name="__main__")
'''
        return AppTest.from_string(script, default_timeout=45).run()

    def test_page_with_csv_only_and_empty_filter(self):
        app = self.loaded_page(registros())
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "30")
        self.assertEqual(app.metric[3].value, "90.0%")
        app.toggle[0].set_value(False).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "30")

    def test_page_with_counters_only(self):
        app = self.loaded_page(registros(False))
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[3].value, "90.0%")
        self.assertEqual(app.metric[5].value, "N/D")

    def test_page_with_metadata_and_technology_comparison(self):
        app = self.loaded_page(registros(), {
            "Configuração · config.json": {"topologia": "malha"},
            "Enlaces · links.json": [{"origem": "a", "destino": "b", "tipo": "Link_5G"}],
            "Coordenadas · posicoes.json": [{"id": "a", "x": 0, "y": 0, "camada": "med"}, {"id": "b", "x": 1, "y": 1}],
        })
        self.assertFalse(app.exception)
        app.selectbox[0].set_value("Tecnologia do enlace / último salto estimado").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect[0].value, ["5G"])

    def test_invalid_metadata_does_not_block_csv(self):
        app = self.loaded_page(registros(), {"Enlaces · links.json": {"bad": 1}})
        self.assertFalse(app.exception)
        self.assertTrue(app.warning)
        self.assertEqual(app.metric[0].value, "30")


if __name__ == "__main__":
    unittest.main()
