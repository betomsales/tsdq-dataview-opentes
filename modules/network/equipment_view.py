"""Projection of connected equipment, separate from the electrical graph."""

import base64
import json
from dataclasses import dataclass
from urllib.parse import quote

from .topology_adapter import normalize_id


@dataclass(frozen=True)
class EquipmentView:
    id: str
    name: str
    kind: str
    bus: str
    terminals: tuple
    phases: int | None

    @property
    def label(self):
        return f"PV {self.name}" if self.kind == "PVSystem" else f"Carga {self.name}"

    @property
    def analysis_key(self):
        name = normalize_id(self.name)
        return f"pvsystem:{name}" if self.kind == "PVSystem" else f"equipamento:load:{name}"


def connected_equipment(graph, *, show_pv=True, show_load=True):
    records = list(graph.metadata.get("elements") or [])
    for node in graph.nodes.values():
        records.extend(node.metadata.get("connected_elements") or [])
    equipment = {}
    seen = set()
    for record in records:
        kind = {"pvsystem": "PVSystem", "pv": "PVSystem", "load": "Load"}.get(
            normalize_id(record.get("type") or record.get("element_type"))
        )
        if kind is None or (kind == "PVSystem" and not show_pv) or (kind == "Load" and not show_load):
            continue
        name = str(record.get("name") or record.get("id") or "").strip()
        bus = normalize_id(record.get("bus"))
        identity = (kind, normalize_id(name), bus)
        if not name or bus not in graph.nodes or identity in seen:
            continue
        seen.add(identity)
        encoded = base64.urlsafe_b64encode(json.dumps(identity).encode("utf-8")).decode("ascii")
        visual_id = f"@equipment:{encoded}"
        while visual_id in graph.nodes or visual_id in equipment:
            visual_id = "@" + visual_id
        equipment[visual_id] = EquipmentView(
            visual_id, name, kind, bus,
            tuple(record.get("nodes") or []), record.get("phases"),
        )
    return equipment


def equipment_measurements(graph, equipment):
    result = []
    for measurement in graph.nodes[equipment.bus].metadata.get("measurements", []):
        kind = measurement.get("entity_type")
        name = measurement.get("entity_name")
        if kind and name:
            matches = kind == equipment.kind and normalize_id(name) == normalize_id(equipment.name)
        else:
            matches = (
                equipment.kind == "PVSystem" and measurement.get("target_kind") == "pv"
                and normalize_id(measurement.get("target_id")) == normalize_id(equipment.name)
            )
        if matches:
            result.append(measurement)
    return result


def equipment_icon(equipment):
    if equipment.kind == "PVSystem":
        glyph = '<path d="M5 6h22l2 17H3L5 6Zm-1 8h24M12 6l-1 17M20 6l1 17M16 23v5M10 28h12"/>'
        color = "#008000"
    else:
        glyph = '<path d="M4 5h24L16 28 4 5Z"/>'
        color = "#0066CC"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 32 32">'
        f'<g fill="#f7faf8" stroke="{color}" stroke-width="2" stroke-linejoin="round">{glyph}</g></svg>'
    )
    return "data:image/svg+xml," + quote(svg)
