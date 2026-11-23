import copy
import math
import unittest

import pandas as pd

from modules.network.cosim_loader import apply_measurement_snapshot
from modules.network.d3_renderer import _graph_to_d3_payload, build_d3_temporal_frames
from modules.network.graph_model import NetworkGraph, NetworkNode
from modules.network.phase_display import phase_configuration, phase_details, present_phases


class PhaseDisplayTest(unittest.TestCase):
    def test_triphase_topology_with_only_one_monitor_is_not_monophase(self):
        node = NetworkNode("c", "c", "load", metadata={"nodes": [1, 2, 3, 4], "voltage_phases_pu": {"V1": 1.0088}})
        self.assertEqual(present_phases(node), ["A", "B", "C"])
        self.assertEqual(phase_configuration(node), "Trif\u00e1sica")
        rows = dict(phase_details(node))
        self.assertEqual(rows["Fase A"], "1.008800 pu")
        self.assertEqual(rows["Fase B"], "Existente - sem medi\u00e7\u00e3o em pu")
        self.assertEqual(rows["Fase C"], rows["Fase B"])

    def test_missing_columns_do_not_hide_topologically_absent_phases(self):
        node = NetworkNode("n", "n", "bus", metadata={"nodes": [3], "voltage_phases_pu": {"V3": 0}})
        self.assertEqual(phase_configuration(node), "Monof\u00e1sica")
        rows = dict(phase_details(node))
        self.assertEqual(rows["Fase A"], "Fase inexistente")
        self.assertEqual(rows["Fase B"], "Fase inexistente")
        self.assertEqual(rows["Fase C"], "0.000000 pu")

    def test_unknown_topology_does_not_infer_presence_from_monitor_count(self):
        node = NetworkNode("n", "n", "bus", metadata={"voltage_phases_pu": {"VA": 1}})
        self.assertIsNone(present_phases(node))
        self.assertEqual(phase_configuration(node), "N\u00e3o informada")
        self.assertIn("presen\u00e7a n\u00e3o informada", dict(phase_details(node))["Fase B"])
        node.metadata["absent_voltage_phases"] = ["C"]
        self.assertEqual(dict(phase_details(node))["Fase C"], "Aus\u00eancia inferida pela s\u00e9rie NaN")

    def test_visual_presence_does_not_modify_nan_rules_or_average(self):
        graph = NetworkGraph()
        graph.add_node(NetworkNode("n", "n", "bus", metadata={"nodes": [1, 2, 3]}))
        df = pd.DataFrame({f"DSS-0.Bus-n-V{i}_pu": values for i, values in enumerate(([0, 1], [math.nan]*2, [1, 1]), 1)})
        catalog = [{"column": column, "variable": column.rsplit("-", 1)[1], "target_kind": "node",
                    "target_id": "n", "group": "Barramento"} for column in df]
        apply_measurement_snapshot(graph, df, catalog, 0)
        original = copy.deepcopy(graph.nodes["n"])
        frame = build_d3_temporal_frames(graph, df, catalog)[0]["nodes"][0]
        payload = _graph_to_d3_payload(graph)["nodes"][0]
        self.assertEqual(graph.nodes["n"], original)
        self.assertEqual(frame["absentPhases"], ["B"])
        self.assertEqual(frame["voltage"], 0.5)
        self.assertEqual(payload["presentPhases"], ["A", "B", "C"])
        self.assertEqual(dict(phase_details(original))["Fase B"], "Existente - sem medi\u00e7\u00e3o em pu")
        self.assertEqual(payload["phases"]["A"], 0)

    def test_aliases_neutral_unknown_and_nonfinite_values(self):
        node = NetworkNode("n", "n", "bus", metadata={"nodes": ["A", "C", 0, 4], "voltage_phases_pu": {"VA": math.inf}})
        self.assertEqual(present_phases(node), ["A", "C"])
        self.assertEqual(phase_configuration(node), "Bif\u00e1sica")
        self.assertIn("sem medi\u00e7\u00e3o", dict(phase_details(node))["Fase A"])
        node.metadata["nodes"] = []
        self.assertIsNone(present_phases(node))


if __name__ == "__main__":
    unittest.main()
