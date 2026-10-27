import unittest

from modules.network.session_manager import (
    aplicar_selecao_grafo,
    normalizar_indice_instante,
    sincronizar_selecao_barramento,
)


class NetworkSelectionTest(unittest.TestCase):
    def setUp(self):
        self.state = {"network_selected_node": "611", "network_node_selector": "611", "network_selected_row": 3}
        self.nodes = {"611", "634", "680"}

    def event(self, node="680", event_id=1, frame=3):
        return {"id": node, "eventId": event_id, "frameIndex": frame, "graphId": "graph-one"}

    def apply(self, event, **kwargs):
        return aplicar_selecao_grafo(self.state, event, self.nodes, max_row_index=23, **kwargs)

    def test_change_of_node_requires_rerun_even_at_same_frame(self):
        self.assertTrue(self.apply(self.event()))
        self.assertEqual(self.state["network_selected_node"], "680")
        self.assertEqual(self.state["network_node_selector"], "680")
        self.assertEqual(self.state["network_selected_row"], 3)
        self.assertFalse(self.apply(self.event()))

    def test_stale_component_value_does_not_undo_manual_selection(self):
        event = self.event()
        self.apply(event)
        self.state["network_node_selector"] = "634"
        sincronizar_selecao_barramento(self.state)
        self.assertFalse(self.apply(event))
        self.assertEqual(self.state["network_selected_node"], "634")
        self.assertEqual(self.state["network_node_selector"], "634")
        self.assertTrue(self.apply(self.event(event_id=2)))
        self.assertEqual(self.state["network_selected_node"], "680")

    def test_stale_event_cannot_rewind_manual_time_change(self):
        event = self.event(frame=8)
        self.assertTrue(self.apply(event))
        self.assertTrue(self.state.pop("network_sync_selected_row_slider"))
        self.state["network_selected_row"] = 12
        self.assertFalse(self.apply(event))
        self.assertEqual(self.state["network_selected_row"], 12)
        self.assertNotIn("network_sync_selected_row_slider", self.state)

    def test_successive_nodes_and_frames_are_kept_in_sync(self):
        for event_id, node in enumerate(("680", "634", "611", "680")):
            with self.subTest(node=node):
                self.assertTrue(self.apply(self.event(node, event_id, frame=event_id + 5)))
                self.assertEqual(self.state["network_selected_node"], node)
                self.assertEqual(self.state["network_node_selector"], node)
                self.assertEqual(self.state["network_selected_row"], event_id + 5)

    def test_same_node_can_apply_a_new_instant(self):
        self.assertTrue(self.apply(self.event("611", frame=7)))
        self.assertEqual(self.state["network_selected_row"], 7)

    def test_invalid_nodes_and_default_values_do_not_modify_state(self):
        original = dict(self.state)
        for event in (None, {}, {"id": []}, self.event("missing"), ["611"]):
            with self.subTest(event=event):
                self.assertFalse(self.apply(event))
                self.assertEqual(self.state, original)

    def test_manual_deselection_survives_a_stale_event(self):
        event = self.event()
        self.apply(event)
        self.state["network_node_selector"] = None
        sincronizar_selecao_barramento(self.state)
        self.assertFalse(self.apply(event))
        self.assertIsNone(self.state["network_selected_node"])

    def test_agraph_and_legacy_events_are_consumed_once(self):
        self.assertTrue(self.apply("680", renderer="Agraph"))
        self.state["network_node_selector"] = "634"
        sincronizar_selecao_barramento(self.state)
        self.assertFalse(self.apply("680", renderer="Agraph"))
        self.assertEqual(self.state["network_selected_node"], "634")
        self.assertTrue(self.apply({"selectedNodeId": "611", "frameIndex": 5}))

    def test_layout_and_graph_identity_are_preserved(self):
        event = self.event()
        event["positions"] = {"680": {"x": 0, "y": 10}}
        self.apply(event)
        self.assertEqual(self.state["network_d3_layout_state"], {"graphId": "graph-one", "positions": event["positions"]})
        event["graphId"] = "graph-two"
        event["id"] = "634"
        self.assertTrue(self.apply(event))

    def test_switching_renderers_cannot_replay_an_old_d3_selection(self):
        event = self.event()
        self.apply(event)
        self.apply("634", renderer="Agraph")
        self.assertFalse(self.apply(event))
        self.assertEqual(self.state["network_selected_node"], "634")

    def test_time_index_is_bounded(self):
        for value, expected in ((-5, 0), (100, 23), ("7", 7), (None, 0), (float("inf"), 0)):
            self.assertEqual(normalizar_indice_instante(value, 23), expected)
        self.assertEqual(normalizar_indice_instante(4, None), 0)
        self.assertEqual(normalizar_indice_instante(4, -1), 0)


if __name__ == "__main__":
    unittest.main()
