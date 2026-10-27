"""Normaliza topologias legadas e v2 para o modelo interno do ARGOS."""

from copy import deepcopy
import math


EDGE_TYPES = {name.lower(): name for name in ("Line", "Switch", "Transformer")}
ELEMENT_TYPES = {
    name.lower(): name
    for name in ("Vsource", "Load", "Capacitor", "PVSystem", "Storage", "Generator")
}
LEGACY_ELEMENT_TYPES = {
    "pv": "PVSystem", "storage": "Storage", "load": "Load",
    "generator": "Generator", "capacitor": "Capacitor", "vsource": "Vsource",
}
# Only the visual highlight uses precedence; all roles and devices are retained.
ROLE_PRECEDENCE = (
    "refbus", "regulator_bus", "pv", "storage", "generator", "load",
    "capacitor", "transformer_bus", "bus",
)
ELEMENT_ROLES = {
    "Vsource": "refbus", "PVSystem": "pv", "Storage": "storage",
    "Generator": "generator", "Load": "load", "Capacitor": "capacitor",
}


def normalize_id(value):
    return str(value).strip().lower() if value is not None else ""


def _identifier(value, context):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise ValueError(f"{context}: identificador ausente ou inválido.")
    return str(value).strip()


def _records(value, context):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{context} deve ser uma lista de objetos.")
    return value


def _required(item, fields, context):
    missing = [field for field in fields if field not in item]
    if missing:
        raise ValueError(f"{context}: campos obrigatórios ausentes: {', '.join(missing)}.")


def _number(value, context, nonnegative=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{context} deve ser um número finito ou null.")
    if nonnegative and value < 0:
        raise ValueError(f"{context} não pode ser negativo.")
    return value


def _node_numbers(value, context):
    if not isinstance(value, list) or any(type(node) is not int or node < 0 for node in value):
        raise ValueError(f"{context} deve listar números de nós não negativos.")
    if len(value) != len(set(value)):
        raise ValueError(f"{context} contém números de nós duplicados.")
    return list(value)


def _phases(value, context):
    if type(value) is not int or value < 1:
        raise ValueError(f"{context} deve ser um inteiro positivo.")
    return value


def _unique(seen, identity, context):
    key = normalize_id(identity)
    if key in seen:
        raise ValueError(f"{context}: identificador duplicado '{identity}'.")
    seen.add(key)


def _first(item, fields):
    return next((item[field] for field in fields if item.get(field) is not None), None)


def _metadata(item):
    value = item.get("metadata")
    return deepcopy(value) if isinstance(value, dict) else {}


def _global_metadata(data, version):
    metadata = _metadata(data)
    metadata["topology_version"] = version
    metadata["topology_schema_keys"] = sorted(data)
    return metadata


def _adapt_legacy(data):
    nodes = _records(data.get("nodes"), "nodes")
    edges = _first(data, ("edges", "links", "branches"))
    edges = _records(edges, "edges/links/branches")
    metadata = _global_metadata(data, 1)
    metadata["elements"] = deepcopy(data.get("elements", metadata.get("elements", [])) or [])
    _records(metadata["elements"], "elements")
    result = {"nodes": [], "edges": [], "metadata": metadata}
    seen_nodes, seen_edges, seen_elements = set(), set(), set()

    for item in nodes:
        original = _identifier(_first(item, ("id", "name", "bus", "label")), "Barra")
        _unique(seen_nodes, original, "Barra")
        fields = _metadata(item)
        for name in ("kv_base", "nodes", "x", "y", "attached"):
            if name in item:
                fields[name] = deepcopy(item[name])
        fields.setdefault("topology_id_original", original)
        if "x" in fields or "y" in fields:
            fields["coord_defined"] = bool(fields.get("coord_defined", True)) and all(
                isinstance(fields.get(axis), (int, float))
                and not isinstance(fields[axis], bool) and math.isfinite(fields[axis])
                for axis in ("x", "y")
            )
        result["nodes"].append({
            "id": normalize_id(original), "label": str(item.get("label", original)),
            "node_type": str(item.get("node_type") or item.get("type") or fields.get("node_type") or "bus"),
            "voltage_pu": _first(item, ("voltage_pu", "voltage", "v_pu")), "metadata": fields,
        })

    for item in edges:
        source = normalize_id(_identifier(_first(item, ("source", "from", "from_bus", "bus1")), "Origem do ramo"))
        target = normalize_id(_identifier(_first(item, ("target", "to", "to_bus", "bus2")), "Destino do ramo"))
        raw_id = _first(item, ("id", "name"))
        original = _identifier(raw_id if raw_id is not None else f"{source}_{target}", "Ramo")
        _unique(seen_edges, original, "Ramo")
        if source not in seen_nodes or target not in seen_nodes:
            raise ValueError(f"O ramo '{original}' referencia uma barra inexistente.")
        fields = _metadata(item)
        for name in ("name", "phases", "open", "regcontrols"):
            if name in item:
                fields[name] = deepcopy(item[name])
        fields.setdefault("topology_id_original", original)
        result["edges"].append({
            "id": original, "source": source, "target": target,
            "edge_type": str(item.get("edge_type") or item.get("type") or fields.get("edge_type") or "line"),
            "metadata": fields,
        })
    for item in metadata["elements"]:
        identity = item.get("id")
        if identity is None and item.get("name"):
            identity = f"{item.get('element_type', item.get('type', ''))}:{item['name']}"
        if identity is not None:
            _unique(seen_elements, identity, "Equipamento")
    return result


def _adapt_v2(data):
    _required(data, ("nodes", "edges", "elements"), "Topologia v2")
    nodes = _records(data["nodes"], "nodes")
    edges = _records(data["edges"], "edges")
    elements = _records(data["elements"], "elements")
    if not nodes:
        raise ValueError("A topologia v2 deve conter ao menos uma barra.")
    metadata = _global_metadata(data, 2)
    metadata["elements"] = []
    result = {"nodes": [], "edges": [], "metadata": metadata}
    by_bus, seen_edges, seen_elements, seen_controls = {}, set(), set(), set()
    roles = {}

    for item in nodes:
        _required(item, ("name", "kv_base", "nodes", "x", "y"), "Barra v2")
        name = _identifier(item["name"], "Barra")
        node_id = normalize_id(name)
        if node_id in by_bus:
            raise ValueError(f"Barra: identificador duplicado '{name}'.")
        fields = {
            "topology_id_original": name,
            "kv_base": _number(item["kv_base"], f"Barra {name}: kv_base", nonnegative=True),
            "nodes": _node_numbers(item["nodes"], f"Barra {name}: nodes"),
            "x": _number(item["x"], f"Barra {name}: x"),
            "y": _number(item["y"], f"Barra {name}: y"),
            "connected_elements": [], "regcontrols": [],
        }
        fields["coord_defined"] = fields["x"] is not None and fields["y"] is not None
        node = {"id": node_id, "label": name, "node_type": "bus", "voltage_pu": None, "metadata": fields}
        by_bus[node_id] = node
        roles[node_id] = set()
        result["nodes"].append(node)

    for item in elements:
        _required(item, ("type", "name", "bus", "nodes", "phases"), "Equipamento v2")
        kind = ELEMENT_TYPES.get(normalize_id(item["type"]))
        if kind is None:
            raise ValueError(f"Tipo de equipamento v2 não suportado: {item['type']}.")
        name = _identifier(item["name"], "Equipamento")
        identity = f"{kind}-{name}"
        _unique(seen_elements, identity, "Equipamento")
        bus = normalize_id(_identifier(item["bus"], f"{identity}: bus"))
        if bus not in by_bus:
            raise ValueError(f"O equipamento '{identity}' referencia a barra inexistente '{item['bus']}'.")
        record = {
            "id": identity, "name": name, "type": kind, "bus": bus,
            "nodes": _node_numbers(item["nodes"], f"{identity}: nodes"),
            "phases": _phases(item["phases"], f"{identity}: phases"),
        }
        metadata["elements"].append(record)
        by_bus[bus]["metadata"]["connected_elements"].append(record)
        roles[bus].add(ELEMENT_ROLES[kind])

    for item in edges:
        _required(item, ("type", "name", "source", "target", "phases", "open", "regcontrols"), "Ramo v2")
        kind = EDGE_TYPES.get(normalize_id(item["type"]))
        if kind is None:
            raise ValueError(f"Tipo de ramo v2 não suportado: {item['type']}.")
        name = _identifier(item["name"], "Ramo")
        identity = f"{kind}-{name}"
        _unique(seen_edges, identity, "Ramo")
        source = normalize_id(_identifier(item["source"], f"{identity}: source"))
        target = normalize_id(_identifier(item["target"], f"{identity}: target"))
        if source not in by_bus or target not in by_bus:
            raise ValueError(f"O ramo '{identity}' referencia uma barra inexistente.")
        if type(item["open"]) is not bool:
            raise ValueError(f"{identity}: open deve ser true ou false.")
        fields = {
            "topology_id_original": identity, "name": name, "type": kind,
            "phases": _phases(item["phases"], f"{identity}: phases"),
            "open": item["open"], "regcontrols": [],
        }
        controls = _records(item["regcontrols"], f"{identity}: regcontrols")
        if controls and kind != "Transformer":
            raise ValueError(f"{identity}: regcontrols deve estar associado a um Transformer.")
        for control in controls:
            _required(control, ("name", "bus"), f"{identity}: RegControl")
            control_name = _identifier(control["name"], "RegControl")
            _unique(seen_controls, control_name, "RegControl")
            bus = normalize_id(_identifier(control["bus"], f"RegControl {control_name}: bus"))
            if bus not in by_bus:
                raise ValueError(f"RegControl '{control_name}' referencia uma barra inexistente.")
            record = {"name": control_name, "bus": bus, "edge_id": identity}
            fields["regcontrols"].append(record)
            by_bus[bus]["metadata"]["regcontrols"].append(record)
            roles[bus].add("regulator_bus")
        if kind == "Transformer":
            roles[source].add("transformer_bus")
            roles[target].add("transformer_bus")
        result["edges"].append({
            "id": identity, "source": source, "target": target,
            "edge_type": kind.lower(), "metadata": fields,
        })

    for node_id, node in by_bus.items():
        ordered = [role for role in ROLE_PRECEDENCE if role in roles[node_id]] or ["bus"]
        node["node_type"] = ordered[0]
        node["metadata"]["roles"] = ordered
    return result


def adapt_topology(data):
    if not isinstance(data, dict):
        raise ValueError("O JSON de topologia deve ter um objeto na raiz.")
    version = data.get("version", 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError(f"Versão de topologia não suportada: {version!r}. Versões aceitas: 1 (legado) e 2.")
    return _adapt_v2(data) if version == 2 else _adapt_legacy(data)
