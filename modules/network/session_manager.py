"""Sincroniza selecoes do grafo com os controles da pagina."""


def normalizar_indice_instante(value, max_value):
    if max_value is None or max_value < 0:
        return 0
    try:
        index = int(value)
    except (TypeError, ValueError, OverflowError):
        index = 0
    return min(max(index, 0), max_value)


def sincronizar_selecao_barramento(state):
    state["network_selected_node"] = state.get("network_node_selector")


def aplicar_selecao_grafo(state, event, node_ids, *, max_row_index=None, renderer="D3/JavaScript"):
    if isinstance(event, dict):
        node_id = event.get("id") or event.get("selectedNodeId")
        frame_index = event.get("frameIndex")
        graph_id = event.get("graphId")
        event_id = event.get("eventId")
        token = (renderer, graph_id, event_id if event_id is not None else (node_id, frame_index))
    else:
        node_id, frame_index, graph_id = event, None, None
        token = (renderer, None, node_id)

    if not isinstance(node_id, str) or node_id not in node_ids:
        return False
    # Component values persist across reruns; each interaction is applied once.
    last_events = dict(state.get("network_last_graph_events", {}))
    if token == last_events.get(renderer):
        return False
    last_events[renderer] = token
    state["network_last_graph_events"] = last_events

    if isinstance(event, dict) and graph_id and isinstance(event.get("positions"), dict):
        state["network_d3_layout_state"] = {"graphId": graph_id, "positions": event["positions"]}

    changed = state.get("network_selected_node") != node_id
    changed = changed or state.get("network_node_selector") != node_id
    state["network_selected_node"] = node_id
    state["network_node_selector"] = node_id
    if frame_index is not None and max_row_index is not None:
        index = normalizar_indice_instante(frame_index, max_row_index)
        if index != state.get("network_selected_row"):
            state["network_selected_row"] = index
            state["network_sync_selected_row_slider"] = True
            changed = True
    return changed
