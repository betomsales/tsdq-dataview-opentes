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
from .pv_binding import vincular_medicoes_pv


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
    }


def _normalizar_id(value):
    return str(value).strip().lower()


def _metadata_item(item):
    metadata = item.get("metadata")

    if isinstance(metadata, dict):
        return metadata.copy()

    return {}


def _primeiro_valor(item, nomes):
    for nome in nomes:
        if nome in item and item[nome] is not None:
            return item[nome]

    return None


def _valor_numerico(value):
    try:
        if value is None or pd.isna(value):
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def _metadata_global_topologia(data):
    metadata = data.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}
    else:
        metadata = metadata.copy()

    if "elements" in data:
        metadata["elements"] = data.get("elements") or []

    metadata["topology_schema_keys"] = sorted(
        str(key)
        for key in data.keys()
    )

    return metadata


def load_topology_json(uploaded_file):
    """Converte o JSON de topologia da co-simulacao em NetworkGraph.

    O loader aceita o formato legado nodes/edges e o formato mais novo com
    metadados topologicos por no, como coordenadas x/y e lista elements.
    """

    uploaded_file.seek(0)
    raw = uploaded_file.read()

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")

    data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError("O JSON de topologia deve ter um objeto na raiz.")

    nodes = data.get("nodes")
    edges = data.get("edges") or data.get("links") or data.get("branches")

    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError(
            "O JSON deve conter as listas 'nodes' e 'edges' "
            "ou campos equivalentes 'links'/'branches'."
        )

    graph = NetworkGraph()
    graph.metadata = _metadata_global_topologia(
        data
    )

    for item in nodes:
        if not isinstance(item, dict):
            continue

        raw_id = _primeiro_valor(
            item,
            ["id", "name", "bus", "label"],
        )

        if raw_id is None:
            raise ValueError("Um no da topologia nao possui identificador.")

        node_id = _normalizar_id(
            raw_id
        )
        metadata = _metadata_item(
            item
        )
        metadata.setdefault(
            "topology_id_original",
            str(raw_id),
        )

        voltage_pu = _primeiro_valor(
            item,
            ["voltage_pu", "voltage", "v_pu"],
        )
        voltage_pu = _valor_numerico(
            voltage_pu
        )

        graph.add_node(
            NetworkNode(
                id=node_id,
                label=str(item.get("label", raw_id)),
                node_type=str(
                    item.get("node_type")
                    or item.get("type")
                    or metadata.get("node_type")
                    or "bus"
                ),
                voltage_pu=voltage_pu,
                metadata=metadata,
            )
        )

    for item in edges:
        if not isinstance(item, dict):
            continue

        source_raw = _primeiro_valor(
            item,
            ["source", "from", "from_bus", "bus1"],
        )
        target_raw = _primeiro_valor(
            item,
            ["target", "to", "to_bus", "bus2"],
        )

        if source_raw is None or target_raw is None:
            raise ValueError("Uma conexao da topologia nao possui origem/destino.")

        source = _normalizar_id(
            source_raw
        )
        target = _normalizar_id(
            target_raw
        )

        edge_id = _primeiro_valor(
            item,
            ["id", "name"],
        )

        if edge_id is None:
            edge_id = f"{source}_{target}"

        if source not in graph.nodes or target not in graph.nodes:
            raise ValueError(
                f"A conexao '{edge_id}' referencia um no inexistente."
            )

        metadata = _metadata_item(
            item
        )
        metadata.setdefault(
            "topology_id_original",
            str(edge_id),
        )

        graph.add_edge(
            NetworkEdge(
                id=str(edge_id),
                source=source,
                target=target,
                edge_type=str(
                    item.get("edge_type")
                    or item.get("type")
                    or metadata.get("edge_type")
                    or "line"
                ),
                metadata=metadata,
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


def identificar_fases_ausentes(graph, df, measurement_columns):
    """Identifica fases ausentes pela topologia ou pela serie inteira NaN."""
    ausentes = {node_id: set() for node_id in graph.nodes}
    nomes_fase = {"1": "A", "2": "B", "3": "C"}

    for item in measurement_columns:
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

    for item in vincular_medicoes_pv(graph, measurement_columns):
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

        if target is None:
            unassociated.append({
                "coluna_original": item["column"],
                "valor": float(value),
                "motivo": item.get("binding_error") or "Elemento correspondente não encontrado na topologia",
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
    for item in vincular_medicoes_pv(graph, measurement_columns):
        if item["target_kind"] == "node" and item["target_id"] in graph.nodes:
            monitored.add(item["target_id"])
        elif item["target_kind"] in {"pv", "pv_equipment"}:
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

    for item in vincular_medicoes_pv(graph, measurement_columns):
        belongs_to_node = (
            item["target_kind"] == "node"
            and item["target_id"] == node_id
            and node_id in graph.nodes
        )
        belongs_to_explicit_bus = (
            item["target_kind"] in {"pv", "pv_equipment"}
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
