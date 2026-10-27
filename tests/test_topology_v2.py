from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import unittest

import pandas as pd

from modules.network.cosim_loader import (
    apply_measurement_snapshot, get_monitored_node_ids, load_cosim_results,
    load_topology_json, prepare_node_time_series,
)
from modules.network.measurement_binding import vincular_medicoes_rede
from modules.network.pv_binding import vincular_medicoes_pv
from scripts.aplicar_hash_topologia import aplicar_hash_no_json
from utils.vinculo_arquivos import (
    calcular_sha256_upload, carregar_json_upload, obter_hash_vinculado, validar_vinculo,
)


def topology_v2():
    return {
        "version": 2,
        "nodes": [
            {"name": name, "kv_base": 2.4, "nodes": nodes, "x": x, "y": y}
            for name, nodes, x, y in (
                ("grid-inlet", [1, 2, 3], 0, 0), ("rg60", [1, 2, 3], 100, 0),
                ("646", [2, 3], 200, 100), ("storage-bus", [1, 2, 3], 300, 100),
                ("load-only", [1, 2, 3], None, None),
            )
        ],
        "edges": [
            {"type": "Transformer", "name": "reg-one", "source": "grid-inlet", "target": "rg60",
             "phases": 1, "open": False, "regcontrols": [{"name": "creg1a", "bus": "rg60"}]},
            {"type": "Line", "name": "650632", "source": "rg60", "target": "646",
             "phases": 3, "open": False, "regcontrols": []},
            {"type": "Switch", "name": "650632", "source": "646", "target": "storage-bus",
             "phases": 3, "open": True, "regcontrols": []},
            {"type": "Transformer", "name": "650632", "source": "storage-bus", "target": "load-only",
             "phases": 3, "open": False, "regcontrols": []},
        ],
        "elements": [
            {"type": kind, "name": name, "bus": bus, "nodes": nodes, "phases": phases}
            for kind, name, bus, nodes, phases in (
                ("Vsource", "source", "grid-inlet", [1, 2, 3], 3),
                ("Load", "646", "646", [2, 3], 1),
                ("PVSystem", "pv-4", "646", [2], 1),
                ("PVSystem", "pv-5", "646", [3], 1),
                ("PVSystem", "pv20", "load-only", [1, 2, 3], 3),
                ("Storage", "bat1", "storage-bus", [1, 2, 3], 3),
                ("Generator", "g1", "load-only", [1, 2, 3], 3),
                ("Capacitor", "cap1", "646", [2, 3], 1),
            )
        ],
    }


def results_csv():
    frame = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=3, freq="5min"),
        "DSS-5.Bus-grid-inlet-V1_pu": [1, 1, 1],
        "DSS-5.Bus-rg60-V1_pu": [1, 1, 1],
        "DSS-5.Bus-646-V1_pu": [math.nan] * 3,
        "DSS-5.Bus-646-V2_pu": [0, 0.98, 0],
        "DSS-5.Bus-646-V3_pu": [1.07, 1, math.nan],
        "DSS-5.PVSystem-pv-4-P_meas": [1000, 0, -500],
        "DSS-5.PVSystem-pv-4-Q_meas": [100, 0, -50],
        "DSS-5.PVSystem-pv-4-P_pu": [0.5, 0, -0.25],
        "DSS-5.PVSystem-pv-5-P_meas": [2000, 2000, 2000],
        "DSS-5.PVSystem-pv20-P_meas": [3000, 3000, 3000],
        "DSS-5.Load-646-P_meas": [80, 81, 82],
        "DSS-5.Storage-bat1-P_act": [50, 0, -50],
        "DSS-5.RegControl-creg1a-tap": [1.01, 1.02, 1.03],
        "DSS-5.Line-650632-I1_A": [10, 11, 12],
        "DSS-5.Switch-650632-I1_A": [0, 0, 0],
        "DSS-5.Transformer-650632-I1_A": [5, 6, 7],
    })
    return frame.to_csv(index=False).encode("utf-8")


def load_case(data=None, csv=None, with_graph=True):
    graph = load_topology_json(io.StringIO(json.dumps(data or topology_v2())))
    df, catalog, _, times = load_cosim_results(io.BytesIO(csv or results_csv()), graph=graph if with_graph else None)
    return graph, df, catalog, times


class TopologyV2Test(unittest.TestCase):
    def test_flat_fields_and_classification_preserve_all_attachments(self):
        graph, _, _, _ = load_case()
        self.assertEqual(graph.metadata["topology_version"], 2)
        self.assertEqual(graph.nodes["grid-inlet"].node_type, "refbus")
        self.assertEqual(graph.nodes["rg60"].node_type, "regulator_bus")
        node = graph.nodes["646"]
        self.assertEqual(node.node_type, "pv")
        self.assertEqual(node.metadata["roles"], ["pv", "load", "capacitor"])
        self.assertEqual(node.metadata["nodes"], [2, 3])
        load = next(e for e in node.metadata["connected_elements"] if e["type"] == "Load")
        self.assertEqual((load["phases"], load["nodes"]), (1, [2, 3]))
        self.assertEqual(len(node.metadata["connected_elements"]), 4)
        self.assertIsNone(node.voltage_pu)
        self.assertEqual(node.metadata["kv_base"], 2.4)

    def test_class_and_name_are_compound_identities(self):
        graph, _, _, _ = load_case()
        self.assertEqual(len(graph.edges), 4)
        self.assertTrue({"Line-650632", "Switch-650632", "Transformer-650632"} <= graph.edges.keys())
        self.assertTrue(graph.edges["Switch-650632"].metadata["open"])

    def test_same_name_across_equipment_classes_remains_distinct(self):
        data = topology_v2()
        data["elements"][1]["name"] = "pv-4"
        graph, df, catalog, _ = load_case(data)
        extra = "DSS-5.Load-pv-4-P_meas"
        df[extra] = 7
        catalog.append({"column": extra})
        apply_measurement_snapshot(graph, df, catalog, 0)
        node = graph.nodes["646"]
        values = {m["entity_type"]: m for m in node.metadata["measurements"] if m["entity_name"] == "pv-4" and m["variavel"] == "P_meas"}
        self.assertEqual(values["Load"]["valor"], 7)
        self.assertEqual(values["PVSystem"]["valor"], 1000)
        self.assertIsNone(values["Load"]["categoria_card"])

    def test_names_hyphens_simulator_and_pvs_are_bound_consistently(self):
        for with_graph in (True, False):
            with self.subTest(with_graph=with_graph):
                graph, df, catalog, times = load_case(with_graph=with_graph)
                bound = {item["column"]: item for item in vincular_medicoes_rede(graph, catalog)}
                pv = bound["DSS-5.PVSystem-pv-4-P_meas"]
                self.assertEqual((pv["target_id"], pv["variable"], pv["target_node_id"]), ("pv-4", "P_meas", "646"))
                self.assertEqual(bound["DSS-5.Bus-grid-inlet-V1_pu"]["target_id"], "grid-inlet")
                apply_measurement_snapshot(graph, df, catalog, 0)
                pvs = {m["target_id"] for m in graph.nodes["646"].metadata["measurements"] if m["target_kind"] == "pv"}
                self.assertEqual(pvs, {"pv-4", "pv-5"})
                curves = prepare_node_time_series(graph, df, catalog, times, "646")
                self.assertTrue(any("pv-4-P_meas" in curve["coluna_original"] for curve in curves))
                self.assertFalse(any("pv20" in curve["coluna_original"] for curve in curves))
                self.assertIn("646", get_monitored_node_ids(graph, catalog))
                self.assertEqual(next(m for m in graph.nodes["646"].metadata["measurements"] if m["variavel"] == "P_meas" and m["target_id"] == "pv-4")["unidade"], "W")

    def test_lines_switches_transformers_and_controls_keep_their_owner(self):
        graph, df, catalog, _ = load_case()
        apply_measurement_snapshot(graph, df, catalog, 0)
        for edge, value in (("Line-650632", 10), ("Switch-650632", 0), ("Transformer-650632", 5)):
            self.assertEqual(graph.edges[edge].metadata["measurements"][0]["valor"], value)
        control = graph.nodes["rg60"].metadata["measurements"][1]
        self.assertEqual(control["entity_type"], "RegControl")
        self.assertEqual(control["valor"], 1.01)
        self.assertEqual(graph.metadata["unassociated_measurements"], [])

    def test_coordinates_zero_null_and_partial(self):
        data = topology_v2()
        data["nodes"][1]["y"] = None
        graph, _, _, _ = load_case(data)
        self.assertTrue(graph.nodes["grid-inlet"].metadata["coord_defined"])
        self.assertEqual(graph.nodes["grid-inlet"].metadata["x"], 0)
        self.assertFalse(graph.nodes["load-only"].metadata["coord_defined"])
        self.assertFalse(graph.nodes["rg60"].metadata["coord_defined"])

    def test_unknown_and_nan_columns_are_not_silently_discarded(self):
        graph, df, catalog, _ = load_case()
        unknown = ["DSS-5.PVSystem-unknown-P_meas", "unrecognized_column"]
        for column in unknown:
            df[column] = math.nan
            catalog.append({"column": column, "target_kind": "unassociated", "binding_error": "Não reconhecida"})
        apply_measurement_snapshot(graph, df, catalog, 0)
        diagnostics = graph.metadata["unassociated_measurements"]
        self.assertEqual({item["coluna_original"] for item in diagnostics}, set(unknown))
        self.assertTrue(all(item["valor"] is None and item["motivo"] for item in diagnostics))

    def test_bus_suffix_validates_explicit_connection(self):
        graph, _, _, _ = load_case()
        for bus, valid in (("646", True), ("rg60", False), ("missing", False)):
            item = vincular_medicoes_rede(graph, [{"column": f"DSS-5.PVSystem-pv-4_bus{bus}-P_meas"}])[0]
            self.assertEqual(item.get("binding_error") is None, valid)

    def test_v2_does_not_guess_single_pv(self):
        graph, _, _, _ = load_case()
        graph.metadata["elements"] = [e for e in graph.metadata["elements"] if e["type"] != "PVSystem" or e["name"] == "pv-4"]
        item = {"column": "DSS-0.PVSystem-unknown-P_meas", "target_kind": "pv", "target_id": "unknown", "group": "PVSystem unknown", "variable": "P_meas"}
        self.assertIsNone(vincular_medicoes_pv(graph, [item])[0]["target_node_id"])
        self.assertTrue(vincular_medicoes_rede(graph, [item])[0]["binding_error"])

    def test_legacy_and_explicit_version_one_keep_layout_and_ids(self):
        for version in (None, 1):
            data = {"nodes": [{"id": "A", "node_type": "pv", "metadata": {"nodes": [1], "x": 0, "y": 0}}, {"id": "b"}],
                    "links": [{"id": "line_ab", "source": "A", "target": "b"}]}
            if version is not None:
                data["version"] = version
            graph = load_topology_json(io.StringIO(json.dumps(data)))
            self.assertEqual(graph.nodes["a"].label, "A")
            self.assertEqual(graph.nodes["a"].node_type, "pv")
            self.assertTrue(graph.nodes["a"].metadata["coord_defined"])
            self.assertIn("line_ab", graph.edges)

    def test_empty_edges_are_valid_in_both_formats(self):
        for data in ({"nodes": [{"id": "a"}], "edges": []}, {"version": 2, "nodes": [topology_v2()["nodes"][0]], "edges": [], "elements": []}):
            graph = load_topology_json(io.StringIO(json.dumps(data)))
            self.assertEqual(graph.total_edges, 0)
            self.assertEqual(graph.total_nodes, 1)

    def test_legacy_explicit_coordinate_flag_and_zero_edge_id_are_preserved(self):
        data = {"nodes": [{"id": "a", "metadata": {"x": 0, "y": 0, "coord_defined": False}}],
                "edges": [{"id": 0, "source": "a", "target": "a"}]}
        graph = load_topology_json(io.StringIO(json.dumps(data)))
        self.assertFalse(graph.nodes["a"].metadata["coord_defined"])
        self.assertIn("0", graph.edges)

    def test_source_and_regulation_highlights_do_not_hide_pvs(self):
        data = topology_v2()
        data["elements"][2]["bus"] = "rg60"
        data["elements"][4]["bus"] = "grid-inlet"
        graph, df, catalog, _ = load_case(data)
        self.assertEqual(graph.nodes["rg60"].node_type, "regulator_bus")
        self.assertIn("pv", graph.nodes["rg60"].metadata["roles"])
        self.assertEqual(graph.nodes["grid-inlet"].node_type, "refbus")
        self.assertIn("pv", graph.nodes["grid-inlet"].metadata["roles"])
        apply_measurement_snapshot(graph, df, catalog, 0)
        self.assertTrue(any(item["target_id"] == "pv-4" for item in graph.nodes["rg60"].metadata["measurements"]))

    def test_invalid_versions_and_structures_fail_clearly(self):
        for version in (3, "2", None, True):
            data = topology_v2()
            data["version"] = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "Versão"):
                load_topology_json(io.StringIO(json.dumps(data)))
        for field in ("nodes", "edges", "elements"):
            data = topology_v2()
            data[field] = {}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "lista"):
                load_topology_json(io.StringIO(json.dumps(data)))

    def test_duplicates_and_missing_references_are_rejected(self):
        for field in ("nodes", "edges", "elements"):
            data = topology_v2()
            data[field].append(deepcopy(data[field][0]))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "duplicado"):
                load_topology_json(io.StringIO(json.dumps(data)))
        for target in ("edge", "element", "control"):
            data = topology_v2()
            if target == "edge":
                data["edges"][0]["source"] = "missing"
            elif target == "element":
                data["elements"][0]["bus"] = "missing"
            else:
                data["edges"][0]["regcontrols"][0]["bus"] = "missing"
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "inexistente"):
                load_topology_json(io.StringIO(json.dumps(data)))

    def test_conflicting_legacy_aliases_are_reported(self):
        data = {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [], "elements": [
            {"id": "pv_1", "name": "same", "element_type": "pv", "bus": "a"},
            {"id": "pv_2", "name": "same", "element_type": "pv", "bus": "b"},
        ]}
        graph = load_topology_json(io.StringIO(json.dumps(data)))
        item = vincular_medicoes_rede(graph, [{"column": "DSS-0.PVSystem-same-P_meas"}])[0]
        self.assertIn("ambíguo", item["binding_error"])

    def test_d3_and_qee_keep_zero_nan_open_edges_and_timestamps(self):
        from components.analise_eletrica_rede import montar_estrutura_analise_rede
        from modules.network.d3_renderer import _graph_to_d3_payload, build_d3_temporal_frames
        from utils.qee import calcular_drp_drc_por_fase

        graph, df, catalog, times = load_case()
        apply_measurement_snapshot(graph, df, catalog, 0)
        self.assertEqual(graph.nodes["646"].metadata["absent_voltage_phases"], ["A"])
        self.assertEqual(graph.nodes["646"].metadata["voltage_phases_pu"]["V2"], 0)
        frames = build_d3_temporal_frames(graph, df, catalog, times)
        self.assertEqual([frame["index"] for frame in frames], [0, 1, 2])
        self.assertEqual(frames[0]["label"], "01/01/2026 00:00:00")
        self.assertEqual(next(node for node in frames[0]["nodes"] if node["id"] == "646")["phases"]["B"], 0)
        payload = _graph_to_d3_payload(graph)
        self.assertTrue(next(edge for edge in payload["edges"] if edge["type"] == "switch")["open"])
        self.assertTrue(next(node for node in payload["nodes"] if node["id"] == "grid-inlet")["coord"]["defined"])
        structure = montar_estrutura_analise_rede(graph, catalog)
        indicators = calcular_drp_drc_por_fase(df, structure["Tensão"]["646"])
        self.assertEqual(len(indicators["fases_ausentes"]), 1)
        phase_b = next(item for item in indicators["fases"] if item["fase"] == "Fase B")
        self.assertAlmostEqual(phase_b["drc"]["subtensao"], 200 / 3)

    def test_longest_registered_name_wins_and_input_is_not_modified(self):
        data = topology_v2()
        data["nodes"].append({"name": "grid", "kv_base": None, "nodes": [1], "x": None, "y": None})
        original = deepcopy(data)
        graph, _, catalog, _ = load_case(data)
        bound = vincular_medicoes_rede(graph, catalog)
        item = next(item for item in bound if "Bus-grid-inlet" in item["column"])
        self.assertEqual(item["target_id"], "grid-inlet")
        self.assertEqual(item["variable"], "V1_pu")
        self.assertEqual(data, original)

    def test_invalid_field_types_and_regcontrol_duplicates_are_rejected(self):
        for field, value in (("phases", 0), ("open", "false"), ("regcontrols", {})):
            data = topology_v2()
            data["edges"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                load_topology_json(io.StringIO(json.dumps(data)))
        for field, value in (("x", math.inf), ("kv_base", -1), ("nodes", [2, 2])):
            data = topology_v2()
            data["nodes"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                load_topology_json(io.StringIO(json.dumps(data)))
        data = topology_v2()
        data["edges"][3]["regcontrols"] = deepcopy(data["edges"][0]["regcontrols"])
        with self.assertRaisesRegex(ValueError, "duplicado"):
            load_topology_json(io.StringIO(json.dumps(data)))

    def test_legacy_duplicate_ids_are_rejected(self):
        for data in (
            {"nodes": [{"id": "a"}, {"id": "A"}], "edges": []},
            {"nodes": [{"id": "a"}], "edges": [{"id": "x", "source": "a", "target": "a"}] * 2},
        ):
            with self.assertRaisesRegex(ValueError, "duplicado"):
                load_topology_json(io.StringIO(json.dumps(data)))


class HashTopologyTest(unittest.TestCase):
    def test_hash_uses_original_bytes_and_rewinds_upload(self):
        raw = b'date,value\r\n2026-01-01,0\r\n'
        upload = io.BytesIO(raw)
        upload.seek(3)
        actual = calcular_sha256_upload(upload)
        self.assertEqual(actual, hashlib.sha256(raw).hexdigest().upper())
        self.assertNotEqual(actual, hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest().upper())
        self.assertEqual(upload.tell(), 0)

    def test_legacy_and_v2_hash_fields_are_supported(self):
        digest = calcular_sha256_upload(io.BytesIO(results_csv()))
        for data in ({"results_sha256": digest.lower()}, {"metadata": {"results_sha256": digest}}, {"hash": {"results_sha256": digest}}, {"metadata": {"hash": {"results_sha256": digest}}}):
            self.assertEqual(validar_vinculo(data, digest), digest)
        for data in ({}, {"results_sha256": "0" * 64}):
            with self.assertRaises(ValueError):
                validar_vinculo(data, digest)

    def test_script_writes_root_for_v2_and_metadata_for_legacy(self):
        for data in ({"version": 2}, {}):
            result = aplicar_hash_no_json(data, Path("results.csv"), Path("network.json"), "A" * 64)
            self.assertEqual(obter_hash_vinculado(result), "A" * 64)
            if data.get("version") == 2:
                self.assertNotIn("metadata", result)
                self.assertEqual(result["results_sha256"], "A" * 64)
            else:
                self.assertEqual(result["metadata"]["results_sha256"], "A" * 64)

    def test_script_aligns_preexisting_aliases_when_explicitly_run(self):
        data = {"version": 2, "metadata": {"csv_sha256": "OLD"}, "sha256": "OLD"}
        aplicar_hash_no_json(data, Path("r.csv"), Path("t.json"), "NEW")
        self.assertEqual(obter_hash_vinculado(data), "NEW")

    def test_json_upload_bom_and_root_validation(self):
        upload = io.BytesIO(b'\xef\xbb\xbf{"version":2}')
        self.assertEqual(carregar_json_upload(upload), {"version": 2})
        self.assertEqual(upload.tell(), 0)
        with self.assertRaisesRegex(ValueError, "objeto"):
            carregar_json_upload(io.BytesIO(b'[]'))


class TopologyV2InterfaceTest(unittest.TestCase):
    def test_inspector_preserves_load_and_pv_without_invented_measurements(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_string('''
from test_topology_v2 import load_case
from modules.network.cosim_loader import apply_measurement_snapshot
from modules.network.element_inspector import render_node_details
graph, df, catalog, _ = load_case()
apply_measurement_snapshot(graph, df, catalog, 0)
render_node_details("646", graph)
''', default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        equipment = next(table.value for table in app.dataframe if "Tipo" in table.value.columns)
        self.assertEqual(set(equipment["Tipo"]), {"Load", "PVSystem", "Capacitor"})
        html = "\n".join(item.value for item in app.markdown)
        self.assertIn("PVSystem pv-4", html)
        self.assertNotIn("PVSystem pv20", html)
        self.assertNotIn("Temperatura dos Painéis", html)
        self.assertNotIn("Irradiância dos Painéis", html)
        self.assertNotIn("Potência Ativa Normalizada", html)


if __name__ == "__main__":
    unittest.main()
