"""Associa colunas DSS às identidades completas cadastradas na topologia."""

from .pv_binding import vincular_medicoes_pv
from .topology_adapter import EDGE_TYPES, ELEMENT_TYPES, LEGACY_ELEMENT_TYPES, normalize_id


def _entry(kind, name, target_kind, target_id, bus=None):
    return {
        "entity_type": kind, "entity_name": str(name), "entity_key": f"{kind}-{name}",
        "target_kind": target_kind, "target_id": target_id, "target_node_id": bus,
    }


def _registry(graph):
    entries = []
    for node in graph.nodes.values():
        for name in {node.id, node.metadata.get("topology_id_original", node.label)}:
            entries.append(_entry("Bus", name, "node", node.id))
    for edge in graph.edges.values():
        kind = EDGE_TYPES.get(normalize_id(edge.metadata.get("type") or edge.edge_type))
        if kind is None:
            continue
        name = edge.metadata.get("name")
        if not name:
            prefix = kind.lower() + "_"
            name = edge.id[len(prefix):] if normalize_id(edge.id).startswith(prefix) else edge.id
        entries.append(_entry(kind, name, "edge", edge.id))
        for control in edge.metadata.get("regcontrols", []):
            entries.append(_entry("RegControl", control["name"], "control", f"RegControl-{control['name']}", control["bus"]))
    for element in graph.metadata.get("elements") or []:
        kind = ELEMENT_TYPES.get(normalize_id(element.get("type")))
        kind = kind or LEGACY_ELEMENT_TYPES.get(normalize_id(element.get("element_type")))
        if kind is None:
            continue
        name = element.get("name") or element.get("id")
        if not name:
            continue
        aliases = {str(name)}
        if graph.metadata.get("topology_version") != 2 and element.get("id"):
            aliases.add(str(element["id"]))
        for alias in aliases:
            entry = _entry(kind, alias, "pv" if kind == "PVSystem" else "equipment", normalize_id(name), normalize_id(element.get("bus")))
            entry["csv_prefix"] = f"{kind}-{alias}"
            entry["entity_name"] = str(name)
            entry["entity_key"] = f"{kind}-{name}"
            entries.append(entry)
    return entries


def _unassociated(column, reason):
    return {
        "column": column, "variable": column, "group": "Não associado",
        "target_kind": "unassociated", "target_id": "", "target_node_id": None,
        "binding_error": reason,
    }


def _resolve_dss(column, graph, entries):
    simulator, separator, entity = str(column).partition(".")
    if not separator or not simulator.lower().startswith("dss-"):
        return None
    lower = entity.lower()
    candidates = []
    for entry in entries:
        prefix = f"{entry['entity_type']}-{entry['entity_name']}"
        # Legacy aliases may differ from the name preserved for presentation.
        if entry["entity_type"] != "Bus":
            prefix = entry.get("csv_prefix", prefix)
        explicit_bus = None
        if lower.startswith(prefix.lower() + "-"):
            variable = entity[len(prefix) + 1:]
        elif entry["target_kind"] in {"pv", "equipment"} and lower.startswith(prefix.lower() + "_bus"):
            suffix = entity[len(prefix) + 4:]
            matches = [bus for bus in graph.nodes if suffix.lower().startswith(bus + "-")]
            if matches:
                explicit_bus = max(matches, key=len)
                variable = suffix[len(explicit_bus) + 1:]
            elif "-" in suffix:
                explicit_bus, variable = suffix.rsplit("-", 1)
                explicit_bus = normalize_id(explicit_bus)
            else:
                continue
        else:
            continue
        if variable:
            candidates.append((len(prefix), entry, variable, explicit_bus))
    if not candidates:
        if graph.metadata.get("topology_version") != 2:
            return None
        return _unassociated(column, f"Entidade DSS não cadastrada na topologia: {entity}.")
    longest = max(item[0] for item in candidates)
    candidates = [item for item in candidates if item[0] == longest]
    identities = {
        (entry["target_kind"], entry["target_id"], entry["target_node_id"], entry["entity_key"].lower())
        for _, entry, _, _ in candidates
    }
    if len(identities) != 1:
        return _unassociated(column, "Identificador ambíguo: mais de uma entidade da topologia corresponde à coluna.")
    _, entry, variable, explicit_bus = candidates[0]
    if explicit_bus and explicit_bus not in graph.nodes:
        return _unassociated(column, "A barra declarada no CSV não existe na topologia.")
    if explicit_bus and entry["target_node_id"] and explicit_bus != entry["target_node_id"]:
        return _unassociated(column, "A barra declarada no CSV diverge da conexão do equipamento no JSON.")
    if entry["target_node_id"] and entry["target_node_id"] not in graph.nodes:
        return _unassociated(column, "O equipamento referencia uma barra inexistente na topologia.")
    item = dict(entry)
    item.update({
        "column": column, "variable": variable, "binding_source": "topology",
        "binding_error": None, "csv_target_node_id": explicit_bus,
        "group": "Barramento" if entry["target_kind"] == "node" else f"{entry['entity_type']} {entry['entity_name']}",
    })
    return item


def vincular_medicoes_rede(graph, measurement_columns):
    """Uma associação comum ao snapshot, às séries, ao QEE e ao D3."""
    entries = _registry(graph)
    # Store each legacy alias without changing the equipment's displayed name.
    for entry in entries:
        if entry["entity_type"] != "Bus":
            entry.setdefault("csv_prefix", entry["entity_key"])
    bound = []
    for original in measurement_columns:
        resolved = _resolve_dss(original["column"], graph, entries)
        bound.append(resolved if resolved is not None else dict(original))
    return vincular_medicoes_pv(graph, bound)
