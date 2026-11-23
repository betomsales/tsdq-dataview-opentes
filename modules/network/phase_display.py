"""View-only phase presence and voltage coverage, without changing QEE rules."""

import math


PHASES = ("A", "B", "C")


def present_phases(node):
    terminals = node.metadata.get("nodes")
    if not isinstance(terminals, (list, tuple, set)):
        return None
    aliases = {"1": "A", "2": "B", "3": "C", "A": "A", "B": "B", "C": "C"}
    found = {aliases[str(value).upper()] for value in terminals if str(value).upper() in aliases}
    return [phase for phase in PHASES if phase in found] or None


def phase_configuration(node):
    phases = present_phases(node)
    return {1: "Monofásica", 2: "Bifásica", 3: "Trifásica"}.get(len(phases or []), "Não informada")


def phase_details(node):
    declared = present_phases(node)
    values = node.metadata.get("voltage_phases_pu") or {}
    inferred = node.metadata.get("absent_voltage_phases") or []
    result = []
    for index, phase in enumerate(PHASES, 1):
        value = next((values[key] for key in (f"V{index}", f"V{phase}", phase) if key in values), None)
        absent = phase not in declared if declared is not None else phase in inferred
        if absent:
            text = "Fase inexistente" if declared is not None else "Ausência inferida pela série NaN"
        elif value is not None and math.isfinite(value):
            text = f"{value:.6f} pu"
        elif declared is not None:
            text = "Existente - sem medição em pu"
        else:
            text = "Sem medição em pu; presença não informada"
        result.append((f"Fase {phase}", text))
    return result
