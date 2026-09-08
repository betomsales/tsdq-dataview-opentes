import json
import re

import pandas as pd

from utils.rotulos_medicoes import (
    obter_categoria_equipamento,
    obter_nome_curto_elemento,
    obter_rotulo_variavel,
    obter_unidade_configurada,
)
from utils.unidades import inferir_unidade_variavel, normalizar_unidade

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
BUS_SUFFIX_PATTERN = re.compile(
    r"^(.+)_bus(.+)$",
    re.IGNORECASE,
)


def _split_target_bus(identifier):
    match = BUS_SUFFIX_PATTERN.match(str(identifier).strip())

    if not match:
        return str(identifier), None

    return match.group(1), match.group(2).lower()


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
        "c": "°C",
        "celsius": "°C",
        "wm2": "W/m²",
        "w/m2": "W/m²",
        "kwm2": "kW/m²",
        "kw/m2": "kW/m²",
    }

    parts = variable.rsplit("_", 1)

    if len(parts) == 2 and parts[1].lower() in suffix_units:
        return parts[0], normalizar_unidade(
            suffix_units[parts[1].lower()]
        )

    return variable, None


def _measurement(
    column,
    variable,
    value,
    group,
    target_kind=None,
    target_id=None,
    target_node_id=None,
):
    variable_name, unit = _split_variable_unit(variable)
    unit = (
        normalizar_unidade(unit)
        or obter_unidade_configurada(variable_name)
        or inferir_unidade_variavel(
            variable_name,
            target_kind,
        )
    )
    unit = normalizar_unidade(
        unit
    )

    return {
        "grupo": group,
        "variavel": variable_name,
        "unidade": unit,
        "rotulo_variavel": obter_rotulo_variavel(
            variable_name
        ),
        "nome_curto_elemento": obter_nome_curto_elemento(
            target_id,
            group,
        ),
        "categoria_card": obter_categoria_equipamento(
            variable_name,
            target_id,
        ),
        "valor": float(value),
        "coluna_original": column,
        "target_kind": target_kind,
        "target_id": target_id,
        "target_node_id": target_node_id,
    }


def load_topology_json(uploaded_file):
    """Converte o JSON exportado pela co-simulação em NetworkGraph."""

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
                f"A conexão '{item.get('id', '')}' referencia um nó inexistente."
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
    """Lê o CSV e cataloga todas as séries por elemento da co-simulação."""

    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.astype(str).str.strip()

    if df.empty:
        raise ValueError("O CSV de resultados não possui registros.")

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
            pv_id, target_node_id = _split_target_bus(
                match.group(1)
            )
            group = f"PVSystem {pv_id}"

            if target_node_id:
                group = f"{group} (barra {target_node_id})"

            measurement_columns.append({
                "column": column,
                "target_kind": "pv",
                "target_id": pv_id.lower(),
                "target_node_id": target_node_id,
                "group": group,
                "variable": match.group(2),
            })
            continue

        match = EQUIPMENT_COLUMN_PATTERN.match(column)

        if match:
            equipment_id, target_node_id = _split_target_bus(
                match.group(2)
            )
            group = f"{match.group(1)} / {equipment_id}"

            if target_node_id:
                group = f"{group} (barra {target_node_id})"

            measurement_columns.append({
                "column": column,
                "target_kind": "pv_equipment",
                "target_id": equipment_id.lower(),
                "target_node_id": target_node_id,
                "group": group,
                "variable": match.group(3),
            })

    if not measurement_columns:
        raise ValueError(
            "Nenhuma coluna de medição reconhecida foi encontrada no CSV."
        )

    time_column = df.columns[0]
    time_values = pd.to_datetime(
        df[time_column],
        format="mixed",
        errors="coerce",
    )

    return df, measurement_columns, time_column, time_values


def apply_measurement_snapshot(graph, df, measurement_columns, row_index):
    """Aplica todas as medições reconhecidas aos seus elementos no grafo."""

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

        elif item["target_kind"] in {"pv", "pv_equipment"}:
            target_node_id = item.get("target_node_id")

            if target_node_id:
                target = graph.nodes.get(target_node_id)
            elif len(pv_nodes) == 1:
                target = pv_nodes[0]

        if target is None:
            unassociated.append({
                "coluna_original": item["column"],
                "valor": float(value),
                "motivo": "Elemento correspondente não encontrado na topologia",
            })
            continue

        measurement = _measurement(
            item["column"],
            item["variable"],
            value,
            item["group"],
            item["target_kind"],
            item["target_id"],
            item.get("target_node_id"),
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
    """Compatibilidade com chamadas anteriores; agora aplica todas as medições."""

    stats = apply_measurement_snapshot(
        graph,
        df,
        measurement_columns,
        row_index,
    )
    return stats["measured_nodes"]


def get_monitored_node_ids(graph, measurement_columns):
    """Retorna somente nós que possuem ao menos uma coluna real no CSV."""

    monitored = set()
    pv_nodes = [
        node.id for node in graph.nodes.values()
        if node.node_type == "pv"
    ]

    for item in measurement_columns:
        if item["target_kind"] == "node" and item["target_id"] in graph.nodes:
            monitored.add(item["target_id"])
        elif item["target_kind"] in {"pv", "pv_equipment"}:
            target_node_id = item.get("target_node_id")

            if target_node_id and target_node_id in graph.nodes:
                monitored.add(target_node_id)
            elif len(pv_nodes) == 1:
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
        belongs_to_explicit_bus = (
            item["target_kind"] in {"pv", "pv_equipment"}
            and item.get("target_node_id") == node_id
            and node_id in graph.nodes
        )

        if (
            not belongs_to_node
            and not belongs_to_single_pv
            and not belongs_to_explicit_bus
        ):
            continue

        variable, unit = _split_variable_unit(item["variable"])
        unit = (
            normalizar_unidade(unit)
            or obter_unidade_configurada(variable)
            or inferir_unidade_variavel(
                variable,
                item["target_kind"],
            )
        )
        unit = normalizar_unidade(
            unit
        )
        values = pd.to_numeric(df[item["column"]], errors="coerce")

        series.append({
            "grupo": item["group"],
            "variavel": variable,
            "unidade": unit,
            "rotulo_variavel": obter_rotulo_variavel(
                variable
            ),
            "coluna_original": item["column"],
            "tempo": time_values.copy(),
            "valores": values,
        })

    return series
