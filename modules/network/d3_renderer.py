from pathlib import Path
import re

import pandas as pd
import streamlit.components.v1 as st_components

from .topology_styles import (
    get_node_style,
    get_voltage_color,
)


_COMPONENT_DIR = Path(__file__).parent / "d3_component"
_network_d3_component = st_components.declare_component(
    "network_d3",
    path=str(_COMPONENT_DIR),
)

VOLTAGE_VARIABLE_PATTERN = re.compile(
    r"^V([123ABC])_pu$",
    re.IGNORECASE,
)


def _as_number(value):

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def _get_phase_value(phases, keys):

    for key in keys:
        if key in phases:
            return _as_number(
                phases[key]
            )

    return None


def _graph_to_d3_payload(graph):

    nodes = []
    edges = []

    for node in graph.nodes.values():

        style = get_node_style(
            node
        )
        phases = node.metadata.get(
            "voltage_phases_pu",
            {},
        ) or {}
        voltage_pu = _as_number(
            node.voltage_pu
        )

        nodes.append({
            "id": node.id,
            "label": node.label,
            "type": node.node_type,
            "voltage": voltage_pu,
            "voltageColor": get_voltage_color(
                voltage_pu
            ),
            "baseColor": style["background"],
            "borderColor": style["border"],
            "measurements": len(
                node.metadata.get(
                    "measurements",
                    [],
                )
            ),
            "phases": {
                "A": _get_phase_value(
                    phases,
                    ["V1", "VA", "A"],
                ),
                "B": _get_phase_value(
                    phases,
                    ["V2", "VB", "B"],
                ),
                "C": _get_phase_value(
                    phases,
                    ["V3", "VC", "C"],
                ),
            },
        })

    for edge in graph.edges.values():

        edge_measurements = edge.metadata.get(
            "measurements",
            [],
        )

        edges.append({
            "id": edge.id,
            "source": edge.source,
            "target": edge.target,
            "type": edge.edge_type,
            "measurements": len(
                edge_measurements
            ),
        })

    return {
        "nodes": nodes,
        "edges": edges,
    }


def _phase_from_variable(variable):

    match = VOLTAGE_VARIABLE_PATTERN.match(
        str(variable).strip()
    )

    if not match:
        return None

    phase = match.group(1).upper()

    return {
        "1": "A",
        "2": "B",
        "3": "C",
    }.get(
        phase,
        phase,
    )


def _format_time_label(time_values, row_index):

    if time_values is None:
        return str(row_index)

    value = time_values.iloc[row_index]

    if pd.isna(value):
        return str(row_index)

    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y %H:%M:%S")

    return str(value)


def build_d3_temporal_frames(
    graph,
    results_df,
    measurement_columns,
    time_values=None,
):
    """Prepara frames de tensão para animação local no D3."""

    if results_df is None or measurement_columns is None:
        return []

    phase_series = []

    for item in measurement_columns:
        if item.get("target_kind") != "node":
            continue

        node_id = item.get("target_id")

        if node_id not in graph.nodes:
            continue

        column = item.get("column")

        if column not in results_df.columns:
            continue

        phase = _phase_from_variable(
            item.get("variable")
        )

        if phase is None:
            continue

        values = pd.to_numeric(
            results_df[column],
            errors="coerce",
        )
        phase_series.append(
            (
                node_id,
                phase,
                values,
            )
        )

    if not phase_series:
        return []

    frames = []

    for row_index in range(len(results_df)):
        values_by_node = {
            node_id: {
                "A": None,
                "B": None,
                "C": None,
            }
            for node_id in graph.nodes
        }

        for node_id, phase, values in phase_series:
            value = values.iloc[row_index]

            if pd.isna(value):
                continue

            values_by_node[node_id][phase] = float(value)

        frame_nodes = []

        for node_id, phases in values_by_node.items():
            measured_values = [
                value for value in phases.values()
                if value is not None
            ]
            voltage = None

            if measured_values:
                voltage = sum(measured_values) / len(measured_values)

            frame_nodes.append({
                "id": node_id,
                "phases": phases,
                "voltage": voltage,
                "measurements": len(measured_values),
            })

        frames.append({
            "index": row_index,
            "label": _format_time_label(
                time_values,
                row_index,
            ),
            "nodes": frame_nodes,
        })

    return frames


def render_graph_d3(
    graph,
    selected_node_id=None,
    height=640,
    results_df=None,
    measurement_columns=None,
    time_values=None,
    initial_frame_index=0,
    key="network_d3_graph",
):
    """Renderiza o mapa de rede em D3 e retorna o nó clicado."""

    payload = _graph_to_d3_payload(
        graph
    )
    temporal_frames = build_d3_temporal_frames(
        graph,
        results_df,
        measurement_columns,
        time_values,
    )
    payload["frames"] = temporal_frames
    payload["initialFrame"] = int(
        initial_frame_index or 0
    ) if temporal_frames else None

    return _network_d3_component(
        graph_data=payload,
        selected_node_id=selected_node_id,
        height=height,
        default=selected_node_id,
        key=key,
    )