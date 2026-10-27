import json
import re

import pandas as pd

from utils.qee import motivo_fase_ausente
from utils.rotulos_medicoes import (
    obter_categoria_equipamento,
    obter_nome_curto_elemento,
    obter_rotulo_variavel,
    obter_unidade_configurada,
)
from utils.unidades import inferir_unidade_variavel, normalizar_unidade

from .graph_model import NetworkEdge, NetworkGraph, NetworkNode
from .measurement_binding import vincular_medicoes_rede
from .topology_adapter import adapt_topology


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
    entity_type=None,
    entity_name=None,
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

    result = {
        "grupo": group,
        "variavel": variable_name,
        "unidade": unit,
        "rotulo_variavel": obter_rotulo_variavel(
            variable_name, unit,
        ),
        "nome_curto_elemento": obter_nome_curto_elemento(
            target_id,
            group,
        ),
        "categoria_card": obter_categoria_equipamento(
            variable_name,
            target_id,
            unit,
        ),
        "valor": float(value),
        "coluna_original": column,
        "target_kind": target_kind,
        "target_id": target_id,
        "target_node_id": target_node_id,
        "entity_type": entity_type,
        "entity_name": entity_name,
    }
    if target_kind in {"equipment", "control"}:
        result["categoria_card"] = None
        result["nome_curto_elemento"] = f"{entity_type} {entity_name}"
    return result


def _valor_numerico(value):
    try:
        return None if value is None or pd.isna(value) else float(value)
    except (TypeError, ValueError):
        return None


def load_topology_json(uploaded_file):
    """Lê o formato de origem e instancia o grafo após sua normalização."""
    uploaded_file.seek(0)
    raw = uploaded_file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    topology = adapt_topology(json.loads(raw))
    graph = NetworkGraph()
    graph.metadata = topology["metadata"]
    for item in topology["nodes"]:
        item["voltage_pu"] = _valor_numerico(item["voltage_pu"])
        graph.add_node(NetworkNode(**item))
    for item in topology["edges"]:
        graph.add_edge(NetworkEdge(**item))
    return graph

def load_cosim_results(uploaded_file, graph=None):
    """Lê o CSV e cataloga todas as séries por elemento da co-simulação."""

    uploaded_file.seek(0)
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.astype(str).str.strip()

    if df.empty:
        raise ValueError("O CSV de resultados não possui registros.")

    measurement_columns = []

    for column in df.columns[1:]:
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
            continue

        measurement_columns.append({
            "column": column, "variable": column, "target_kind": "unassociated",
            "target_id": "", "group": "Não associado",
            "binding_error": "Coluna não reconhecida pelo catálogo de medições.",
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

    if graph is not None:
        measurement_columns = vincular_medicoes_rede(graph, measurement_columns)
    return df, measurement_columns, time_column, time_values


def identificar_fases_ausentes(graph, df, measurement_columns):
    """Identifica fases ausentes pela topologia ou pela serie inteira NaN."""
    ausentes = {node_id: set() for node_id in graph.nodes}
    nomes_fase = {"1": "A", "2": "B", "3": "C"}

    for item in vincular_medicoes_rede(graph, measurement_columns):
        if item.get("target_kind") != "node":
            continue
        node = graph.nodes.get(item.get("target_id"))
        coluna = item.get("column")
        match = VOLTAGE_COLUMN_PATTERN.search(str(coluna))
        if node is None or coluna not in df.columns or match is None:
            continue

        fase = match.group(2).upper()
        if motivo_fase_ausente({
            "fase": f"V{fase}",
            "fases_presentes": node.metadata.get("nodes"),
        }, df[coluna]):
            ausentes[node.id].add(nomes_fase.get(fase, fase))

    return {node_id: sorted(fases) for node_id, fases in ausentes.items()}


def apply_measurement_snapshot(graph, df, measurement_columns, row_index):
    """Aplica todas as medições reconhecidas aos seus elementos no grafo."""

    row = df.iloc[row_index]
    fases_ausentes = identificar_fases_ausentes(graph, df, measurement_columns)
    measured_nodes = set()
    measured_edges = set()
    associated_columns = set()
    unassociated = []

    for node in graph.nodes.values():
        node.voltage_pu = None
        node.metadata.pop("voltage_phases_pu", None)
        node.metadata["absent_voltage_phases"] = fases_ausentes[node.id]
        node.metadata["measurements"] = []

    for edge in graph.edges.values():
        edge.metadata["measurements"] = []

    for item in vincular_medicoes_rede(graph, measurement_columns):
        value = pd.to_numeric(row[item["column"]], errors="coerce")

        target = None

        if item["target_kind"] == "node":
            target = graph.nodes.get(item["target_id"])

        elif item["target_kind"] == "edge":
            target = graph.edges.get(item["target_id"])

        elif item["target_kind"] in {"pv", "pv_equipment", "equipment", "control"}:
            target_node_id = item.get("target_node_id")

            if target_node_id:
                target = graph.nodes.get(target_node_id)

        if target is None or item.get("binding_error"):
            unassociated.append({
                "coluna_original": item["column"],
                "valor": None if pd.isna(value) else float(value),
                "motivo": item.get("binding_error") or "Elemento correspondente não encontrado na topologia",
            })
            continue

        if pd.isna(value):
            continue

        measurement = _measurement(
            item["column"],
            item["variable"],
            value,
            item["group"],
            item["target_kind"],
            item["target_id"],
            item.get("target_node_id"),
            item.get("entity_type"),
            item.get("entity_name"),
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
        valores = [
            value for fase, value in phases.items()
            if {"V1": "A", "V2": "B", "V3": "C"}.get(fase, fase.removeprefix("V"))
            not in fases_ausentes[node.id]
        ]

        if valores:
            node.voltage_pu = sum(valores) / len(valores)

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
    for item in vincular_medicoes_rede(graph, measurement_columns):
        if item.get("binding_error"):
            continue
        if item["target_kind"] == "node" and item["target_id"] in graph.nodes:
            monitored.add(item["target_id"])
        elif item["target_kind"] in {"pv", "pv_equipment", "equipment", "control"}:
            target_node_id = item.get("target_node_id")

            if target_node_id and target_node_id in graph.nodes:
                monitored.add(target_node_id)

    return sorted(monitored)


def prepare_node_time_series(
    graph,
    df,
    measurement_columns,
    time_values,
    node_id,
):
    """Prepara curvas diretamente das colunas do CSV, sem criar valores."""

    series = []

    for item in vincular_medicoes_rede(graph, measurement_columns):
        if item.get("binding_error"):
            continue
        belongs_to_node = (
            item["target_kind"] == "node"
            and item["target_id"] == node_id
            and node_id in graph.nodes
        )
        belongs_to_explicit_bus = (
            item["target_kind"] in {"pv", "pv_equipment", "equipment", "control"}
            and item.get("target_node_id") == node_id
            and node_id in graph.nodes
        )

        if (
            not belongs_to_node
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
                variable, unit,
            ),
            "coluna_original": item["column"],
            "tempo": time_values.copy(),
            "valores": values,
        })

    return series
