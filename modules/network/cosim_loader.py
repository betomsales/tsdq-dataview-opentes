import json
import re

import pandas as pd

from .graph_model import NetworkEdge, NetworkGraph, NetworkNode


VOLTAGE_COLUMN_PATTERN = re.compile(
    r"(?:^|\.)Bus-(.+?)-V([123ABC])_pu$",
    re.IGNORECASE,
)

BUS_COLUMN_PATTERN = re.compile(
    r"^DSS-[^.]+\.Bus-(.+?)-(.+)$",
    re.IGNORECASE,
)
LINE_COLUMN_PATTERN = re.compile(
    r"^DSS-[^.]+\.Line-(.+?)-(.+)$",
    re.IGNORECASE,
)
PV_SYSTEM_COLUMN_PATTERN = re.compile(
    r"^DSS-[^.]+\.PVSystem-(.+?)-(.+)$",
    re.IGNORECASE,
)
EQUIPMENT_COLUMN_PATTERN = re.compile(
    r"^([^.]+)\.([^-]+)-(.+)$",
    re.IGNORECASE,
)


def _split_variable_unit(variable):
    """Separa somente unidades declaradas explicitamente no nome da coluna."""

    suffix_units = {
        "pu": "pu",
        "a": "A",
        "ka": "kA",
        "ang": "graus",
        "w": "W",
        "kw": "kW",
        "mw": "MW",
        "var": "var",
        "kvar": "kvar",
        "mvar": "Mvar",
        "v": "V",
        "kv": "kV",
    }

    parts = variable.rsplit("_", 1)

    if len(parts) == 2 and parts[1].lower() in suffix_units:
        return parts[0], suffix_units[parts[1].lower()]

    return variable, None


def _measurement(column, variable, value, group):
    variable_name, unit = _split_variable_unit(variable)

    return {
        "grupo": group,
        "variavel": variable_name,
        "unidade": unit,
        "valor": float(value),
        "coluna_original": column,
    }


def load_topology_json(uploaded_file):
    """Converte o JSON exportado pela co-simulacao em NetworkGraph."""

    uploaded_file.seek(0)
    raw = uploaded_file.read()

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")

    data = json.loads(raw)

    if not isinstance(data.get("nodes"), list) or not isinstance(
        data.get("edges"), list
    ):
        raise ValueError("O JSON deve conter as listas 'nodes' e 'edges'.")

    graph = NetworkGraph()

    for item in data["nodes"]:
        node_id = str(item["id"]).lower()
        graph.add_node(
            NetworkNode(
                id=node_id,
                label=str(item.get("label", item["id"])),
                node_type=item.get("node_type", "bus"),
                voltage_pu=item.get("voltage_pu"),
                metadata=item.get("metadata") or {},
            )
        )

    for item in data["edges"]:
        source = str(item["source"]).lower()
        target = str(item["target"]).lower()

        if source not in graph.nodes or target not in graph.nodes:
            raise ValueError(
                f"A conexao '{item.get('id', '')}' referencia um no inexistente."
            )

        graph.add_edge(
            NetworkEdge(
                id=str(item["id"]),
                source=source,
                target=target,
                edge_type=item.get("edge_type", "line"),
                metadata=item.get("metadata") or {},
            )
        )

    return graph


def load_cosim_results(uploaded_file):
    """Le o CSV e cataloga todas as series por elemento da co-simulacao."""

    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.astype(str).str.strip()

    if df.empty:
        raise ValueError("O CSV de resultados nao possui registros.")

    measurement_columns = []

    for column in df.columns:
        match = BUS_COLUMN_PATTERN.match(column)

        if match:
            measurement_columns.append({
                "column": column,
                "target_kind": "node",
                "target_id": match.group(1).lower(),
                "group": "Barramento",
                "variable": match.group(2),
            })
            continue

        match = LINE_COLUMN_PATTERN.match(column)

        if match:
            measurement_columns.append({
                "column": column,
                "target_kind": "edge",
                "target_id": f"line_{match.group(1).lower()}",
                "group": f"Linha {match.group(1)}",
                "variable": match.group(2),
            })
            continue

        match = PV_SYSTEM_COLUMN_PATTERN.match(column)

        if match:
            measurement_columns.append({
                "column": column,
                "target_kind": "pv",
                "target_id": match.group(1).lower(),
                "group": f"PVSystem {match.group(1)}",
                "variable": match.group(2),
            })
            continue

        match = EQUIPMENT_COLUMN_PATTERN.match(column)

        if match:
            measurement_columns.append({
                "column": column,
                "target_kind": "pv_equipment",
                "target_id": match.group(2).lower(),
                "group": f"{match.group(1)} / {match.group(2)}",
                "variable": match.group(3),
            })

    if not measurement_columns:
        raise ValueError(
            "Nenhuma coluna de medicao reconhecida foi encontrada no CSV."
        )

    time_column = df.columns[0]
    time_values = pd.to_datetime(
        df[time_column],
        format="mixed",
        errors="coerce",
    )

    return df, measurement_columns, time_column, time_values


def apply_measurement_snapshot(graph, df, measurement_columns, row_index):
    """Aplica todas as medicoes reconhecidas aos seus elementos no grafo."""

    row = df.iloc[row_index]
    measured_nodes = set()
    measured_edges = set()
    associated_columns = set()
    unassociated = []

    pv_nodes = [
        node for node in graph.nodes.values()
        if node.node_type == "pv"
    ]

    for node in graph.nodes.values():
        node.voltage_pu = None
        node.metadata.pop("voltage_phases_pu", None)
        node.metadata["measurements"] = []

    for edge in graph.edges.values():
        edge.metadata["measurements"] = []

    for item in measurement_columns:
        value = pd.to_numeric(row[item["column"]], errors="coerce")

        if pd.isna(value):
            continue

        target = None

        if item["target_kind"] == "node":
            target = graph.nodes.get(item["target_id"])

        elif item["target_kind"] == "edge":
            target = graph.edges.get(item["target_id"])

        elif item["target_kind"] in {"pv", "pv_equipment"} and len(pv_nodes) == 1:
            target = pv_nodes[0]

        if target is None:
            unassociated.append({
                "coluna_original": item["column"],
                "valor": float(value),
                "motivo": "Elemento correspondente nao encontrado na topologia",
            })
            continue

        measurement = _measurement(
            item["column"],
            item["variable"],
            value,
            item["group"],
        )
        target.metadata["measurements"].append(measurement)
        associated_columns.add(item["column"])

        if item["target_kind"] == "edge":
            measured_edges.add(target.id)
        else:
            measured_nodes.add(target.id)

        voltage_match = VOLTAGE_COLUMN_PATTERN.search(item["column"])

        if voltage_match and hasattr(target, "voltage_pu"):
            phase = f"V{voltage_match.group(2).upper()}"
            target.metadata.setdefault("voltage_phases_pu", {})[phase] = float(value)

    for node in graph.nodes.values():
        phases = node.metadata.get("voltage_phases_pu", {})

        if phases:
            node.voltage_pu = sum(phases.values()) / len(phases)

    graph.metadata["unassociated_measurements"] = unassociated

    return {
        "measured_nodes": len(measured_nodes),
        "measured_edges": len(measured_edges),
        "associated_columns": len(associated_columns),
        "unassociated_columns": len(unassociated),
    }


def apply_voltage_snapshot(graph, df, measurement_columns, row_index):
    """Compatibilidade com chamadas anteriores; agora aplica todas as medicoes."""

    stats = apply_measurement_snapshot(
        graph,
        df,
        measurement_columns,
        row_index,
    )
    return stats["measured_nodes"]


def get_monitored_node_ids(graph, measurement_columns):
    """Retorna somente nos que possuem ao menos uma coluna real no CSV."""

    monitored = set()
    pv_nodes = [
        node.id for node in graph.nodes.values()
        if node.node_type == "pv"
    ]

    for item in measurement_columns:
        if item["target_kind"] == "node" and item["target_id"] in graph.nodes:
            monitored.add(item["target_id"])
        elif item["target_kind"] in {"pv", "pv_equipment"} and len(pv_nodes) == 1:
            monitored.add(pv_nodes[0])

    return sorted(monitored)


def prepare_node_time_series(
    graph,
    df,
    measurement_columns,
    time_values,
    node_id,
):
    """Prepara curvas diretamente das colunas do CSV, sem criar valores."""

    pv_nodes = [
        node.id for node in graph.nodes.values()
        if node.node_type == "pv"
    ]
    series = []

    for item in measurement_columns:
        belongs_to_node = (
            item["target_kind"] == "node"
            and item["target_id"] == node_id
            and node_id in graph.nodes
        )
        belongs_to_single_pv = (
            item["target_kind"] in {"pv", "pv_equipment"}
            and len(pv_nodes) == 1
            and pv_nodes[0] == node_id
        )

        if not belongs_to_node and not belongs_to_single_pv:
            continue

        variable, unit = _split_variable_unit(item["variable"])
        values = pd.to_numeric(df[item["column"]], errors="coerce")

        series.append({
            "grupo": item["group"],
            "variavel": variable,
            "unidade": unit,
            "coluna_original": item["column"],
            "tempo": time_values.copy(),
            "valores": values,
        })

    return series
