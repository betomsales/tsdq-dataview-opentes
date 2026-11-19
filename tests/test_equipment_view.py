import copy
import io
import json
import unittest
from unittest.mock import patch

import pandas as pd

from components.analise_eletrica_rede import montar_estrutura_analise_rede, preparar_dataframe_analise
from components.analise_equipamento_rede import render_equipment_analysis
from modules.network.cosim_loader import load_topology_json, load_cosim_results, apply_measurement_snapshot
from modules.network.d3_renderer import _graph_to_d3_payload, build_d3_temporal_frames, _graph_signature
from modules.network.equipment_view import connected_equipment, equipment_measurements
from modules.network.graph_model import NetworkNode
from modules.network.session_manager import aplicar_selecao_grafo, sincronizar_selecao_barramento
from modules.network.topology_renderer import render_graph


def fixture():
    data = {
        "version": 2,
        "nodes": [{"name": bus, "kv_base": 2.4, "nodes": [1, 2, 3], "x": i, "y": i}
                  for i, bus in enumerate(("634", "680"))],
        "edges": [{"type": "Line", "name": "main", "source": "634", "target": "680",
                   "phases": 3, "open": False, "regcontrols": []}],
        "elements": [{"type": kind, "name": name, "bus": bus, "nodes": [1, 2, 3], "phases": 3}
                     for kind, name, bus in (("PVSystem", "pv-3", "680"), ("PVSystem", "other", "680"),
                                             ("Load", "pv-3", "680"), ("Load", "house", "634"))],
    }
    graph = load_topology_json(io.StringIO(json.dumps(data)))
    raw = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=3, freq="5min"),
        "DSS-0.Bus-680-V1_pu": [0, 1, 1.01],
        "DSS-0.PVSystem-pv-3-P1": [0, 63.15, 70],
        "DSS-0.PVSystem-pv-3-Q1": [0, 2, 3],
        "DSS-0.PVSystem-other-P1": [0, 900, 1000],
        "DSS-0.Load-pv-3-P1": [10, 20, 30],
        "DSS-0.Load-pv-3-Q1": [1, 2, 3],
        "InverterSim-0.Inverter_2_bus680-P_ac": [0, 63, 69],
    })
    df, catalog, _, times = load_cosim_results(io.StringIO(raw.to_csv(index=False)), graph=graph)
    apply_measurement_snapshot(graph, df, catalog, 1)
    return graph, df, catalog, times


class EquipmentViewTest(unittest.TestCase):
    def setUp(self):
        self.graph, self.df, self.catalog, self.times = fixture()
        self.equipment = connected_equipment(self.graph)
        self.pv = next(e for e in self.equipment.values() if e.kind == "PVSystem" and e.name == "pv-3")
        self.load = next(e for e in self.equipment.values() if e.kind == "Load" and e.name == "pv-3")

    def test_projection_does_not_mutate_graph_or_duplicate_equipment(self):
        before = copy.deepcopy(self.graph.__dict__)
        payload = _graph_to_d3_payload(self.graph)
        self.assertEqual(self.graph.__dict__, before)
        self.assertEqual((self.graph.total_nodes, self.graph.total_edges), (2, 1))
        self.assertEqual(len(self.equipment), 4)
        self.assertEqual(len(payload["nodes"]), 6)
        self.assertEqual(len(payload["edges"]), 5)
        self.assertNotEqual(self.pv.id, self.load.id)
        self.assertTrue(all(e.id not in self.graph.nodes for e in self.equipment.values()))
        for node in payload["nodes"]:
            if node.get("equipment"):
                self.assertNotIn("phases", node)
                self.assertNotIn("voltage", node)
                self.assertTrue(node["icon"].startswith("data:image/svg+xml,"))

    def test_visibility_filters_never_change_the_electrical_network(self):
        signature = _graph_signature(self.graph)
        hidden = _graph_to_d3_payload(self.graph, show_pv=False, show_load=False)
        self.assertEqual(len(hidden["nodes"]), 2)
        self.assertEqual(len(hidden["edges"]), 1)
        self.assertEqual(len(connected_equipment(self.graph, show_pv=False)), 2)
        self.assertEqual(len(connected_equipment(self.graph, show_load=False)), 2)
        self.assertEqual(_graph_signature(self.graph), signature)

    def test_identity_is_stable_and_cannot_collide_with_bus_id(self):
        self.assertEqual(self.equipment, connected_equipment(self.graph))
        self.graph.add_node(NetworkNode(self.pv.id, "collision", "bus"))
        projected = connected_equipment(self.graph)
        replacement = next(e for e in projected.values() if e.kind == "PVSystem" and e.name == "pv-3")
        self.assertNotEqual(replacement.id, self.pv.id)
        self.assertNotIn(replacement.id, self.graph.nodes)

    def test_measurements_are_filtered_by_class_and_full_name_not_bus_alone(self):
        pv = equipment_measurements(self.graph, self.pv)
        load = equipment_measurements(self.graph, self.load)
        self.assertEqual([m["valor"] for m in pv], [63.15, 2])
        self.assertEqual([m["valor"] for m in load], [20, 2])
        self.assertTrue(all("PVSystem-pv-3-" in m["coluna_original"] for m in pv))
        structure = montar_estrutura_analise_rede(self.graph, self.catalog)
        self.assertTrue(any(self.pv.analysis_key in elements for elements in structure.values()))
        self.assertTrue(any(self.load.analysis_key in elements for elements in structure.values()))

    def test_temporal_frames_still_contain_only_buses_and_preserve_zero(self):
        frames = build_d3_temporal_frames(self.graph, self.df, self.catalog, self.times)
        self.assertEqual(len(frames), 3)
        self.assertTrue(all({n["id"] for n in f["nodes"]} == {"634", "680"} for f in frames))
        self.assertEqual(next(n for n in frames[0]["nodes"] if n["id"] == "680")["phases"]["A"], 0)

    def test_equipment_and_bus_selections_keep_time_and_consume_events_once(self):
        state = {"network_selected_node": "680", "network_node_selector": "680", "network_selected_row": 1}
        event = {"id": self.pv.id, "graphId": "one", "frameIndex": 2, "eventId": 1, "playing": True}
        def apply(value, **kwargs):
            return aplicar_selecao_grafo(state, value, self.graph.nodes, equipment=self.equipment,
                                         max_row_index=2, **kwargs)
        self.assertTrue(apply(event))
        self.assertEqual(state["network_selected_equipment"], self.pv.id)
        self.assertEqual(state["network_selected_node"], "680")
        self.assertEqual(state["network_node_selector"], "680")
        self.assertEqual(state["network_selected_row"], 2)
        self.assertFalse(apply(event))
        self.assertTrue(apply({**event, "id": self.load.id, "eventId": 2}))
        self.assertTrue(apply({**event, "id": "680", "eventId": 3}))
        self.assertIsNone(state["network_selected_equipment"])
        self.assertEqual(state["network_selected_row"], 2)
        self.assertTrue(apply(self.pv.id, renderer="Agraph"))
        state["network_node_selector"] = "634"
        sincronizar_selecao_barramento(state)
        self.assertFalse(apply(self.pv.id, renderer="Agraph"))
        self.assertIsNone(state["network_selected_equipment"])

    def test_direct_entry_reuses_existing_analysis_with_exact_equipment_key(self):
        module = "components.analise_equipamento_rede"
        structure = montar_estrutura_analise_rede(self.graph, self.catalog)
        df = preparar_dataframe_analise(self.df, self.times)
        with patch(f"{module}.st") as st, patch(f"{module}._render_card"), \
             patch(f"{module}._render_measurements") as cards, \
             patch(f"{module}.render_analise_eletrica_elemento") as analysis, \
             patch(f"{module}.render_grandezas_derivadas") as derived:
            st.tabs.return_value = [st.container() for _ in range(3)]
            render_equipment_analysis(self.graph, self.load, df, structure)
            analysis.assert_called_once()
            self.assertEqual(analysis.call_args.args[2], self.load.analysis_key)
            self.assertEqual(derived.call_args.args[2], self.load.analysis_key)
            self.assertEqual([m["valor"] for m in cards.call_args.args[0]], [20, 2])

    def test_agraph_uses_the_same_visual_identities_and_attachment_edges(self):
        with patch("modules.network.topology_renderer.agraph", return_value=self.pv.id) as renderer:
            self.assertEqual(render_graph(self.graph), self.pv.id)
            nodes = renderer.call_args.kwargs["nodes"]
            self.assertEqual({n.id for n in nodes}, set(self.graph.nodes) | set(self.equipment))
            self.assertEqual(len(renderer.call_args.kwargs["edges"]), 5)
            for node in nodes:
                if node.id in self.equipment:
                    self.assertEqual(node.shape, "image")
            render_graph(self.graph, show_pv=False, show_load=False)
            self.assertEqual(len(renderer.call_args.kwargs["nodes"]), 2)
            self.assertEqual(len(renderer.call_args.kwargs["edges"]), 1)


if __name__ == "__main__":
    unittest.main()
