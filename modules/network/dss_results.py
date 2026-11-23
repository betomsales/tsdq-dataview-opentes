"""Adapt OpenDSS monitor samples to the existing network measurement catalog."""

from dataclasses import dataclass
from io import BytesIO
import hashlib
import math
import re
import tempfile

import numpy as np
import opendssdirect as dss
import pandas as pd

from .dss_loader import compile_circuit
from .graph_model import NetworkEdge, NetworkGraph
from .topology_builder import build_graph


@dataclass
class DSSResults:
    graph: NetworkGraph
    dataframe: pd.DataFrame
    catalog: list
    raw: pd.DataFrame
    monitors: list
    warnings: list
    master_file: str


def _monitor_graph(engine):
    graph = build_graph(engine)
    graph.metadata.update({"input_source": "opendss_zip", "time_unit": "h", "elements": []})
    for node in graph.nodes.values():
        engine.Circuit.SetActiveBus(node.id)
        node.metadata.update({"kv_base": engine.Bus.kVBase(), "nodes": [n for n in engine.Bus.Nodes() if n in (1, 2, 3)]})
        node.metadata["connected_elements"] = []
    for edge in graph.edges.values():
        if edge.edge_type == "line":
            edge.metadata.update({"type": "Line", "name": edge.id.removeprefix("line_")})
    # A separate identity for every transformer avoids merging parallel devices.
    graph.edges = {key: edge for key, edge in graph.edges.items() if edge.edge_type == "line"}
    if engine.Transformers.First():
        while True:
            name = engine.Transformers.Name()
            buses = [bus.split(".")[0].lower() for bus in engine.CktElement.BusNames()]
            for terminal, bus in enumerate(buses[1:], 2):
                key = f"transformer_{name}" + (f"_t{terminal}" if len(buses) > 2 else "")
                graph.add_edge(NetworkEdge(key, buses[0], bus, "transformer", metadata={"type": "Transformer", "name": name}))
            if not engine.Transformers.Next():
                break
    for kind, collection in (("Load", engine.Loads), ("PVSystem", engine.PVsystems),
                             ("Storage", engine.Storages), ("Generator", engine.Generators),
                             ("Capacitor", engine.Capacitors), ("Vsource", engine.Vsources)):
        if not collection.First():
            continue
        while True:
            bus = engine.CktElement.BusNames()[0].split(".")[0].lower()
            record = {"type": kind, "name": collection.Name(), "bus": bus,
                      "nodes": [n for n in engine.CktElement.NodeOrder()[:engine.CktElement.NumConductors()] if n in (1, 2, 3)],
                      "phases": engine.CktElement.NumPhases()}
            graph.metadata["elements"].append(record)
            if bus in graph.nodes:
                graph.nodes[bus].metadata["connected_elements"].append(record)
            if not collection.Next():
                break
    return graph


def _channel_quantities(headers, channels, mode):
    """Return conductor quantities; preserve units and decode complex pairs."""
    data = {header.strip().lower(): values for header, values in zip(headers, channels)}
    output = []
    used = set()
    for key, values in data.items():
        match = re.fullmatch(r"([vi])(\d+)(\.re)?", key) if mode == 0 else None
        if match:
            letter, conductor, rectangular = match.groups()
            stem = f"{letter}{conductor}"
            partner = f"{stem}.im" if rectangular else f"{letter}angle{conductor}"
            if partner not in data:
                continue
            other = data[partner]
            magnitude = np.hypot(values, other) if rectangular else values
            angle = np.degrees(np.arctan2(other, values)) if rectangular else other
            output.extend([(letter.upper(), int(conductor), magnitude, "V" if letter == "v" else "A"),
                           (letter.upper(), int(conductor), angle, "ang")])
            used.update((key, partner))
        match = re.fullmatch(r"([pq])(\d+) \((kw|kvar)\)", key) if mode == 1 else None
        if match:
            letter, conductor, unit = match.groups()
            if (letter, unit) not in {("p", "kw"), ("q", "kvar")}:
                continue
            output.append((letter.upper(), int(conductor), values, unit))
            used.add(key)
        match = re.fullmatch(r"s(\d+) \(kva\)", key) if mode == 1 else None
        if match and f"ang{match[1]}" in data:
            angle_key = f"ang{match[1]}"
            angle = np.radians(data[angle_key])
            output.extend([("P", int(match[1]), values * np.cos(angle), "kw"),
                           ("Q", int(match[1]), values * np.sin(angle), "kvar")])
            used.update((key, angle_key))
    return output, set(data) - used


def read_monitor_results(engine, graph):
    catalog, series, raw, reports, warnings = [], {}, {}, [], []
    voltage_sources = {}
    engine.Monitors.SaveAll()
    for monitor in engine.Monitors.AllNames():
        engine.Monitors.Name(monitor)
        count = engine.Monitors.SampleCount()
        element, terminal, mode = engine.Monitors.Element(), engine.Monitors.Terminal(), engine.Monitors.Mode()
        report = {"Monitor": monitor, "Elemento": element, "Terminal": terminal, "Modo": mode, "Amostras": count}
        reports.append(report)
        if not count:
            report["Estado"] = "Sem amostras; nenhuma simulação adicional foi executada."
            continue
        hours = np.asarray(engine.Monitors.dblHour(), dtype=float)
        if len(hours) != count or not np.isfinite(hours).all() or np.any(np.diff(hours) <= 0):
            report["Estado"] = "Eixo temporal ausente, repetido ou não crescente."
            warnings.append(f"Monitor {monitor}: {report['Estado']}")
            continue
        headers = list(engine.Monitors.Header())
        channels = [np.asarray(engine.Monitors.Channel(i + 1), dtype=float) for i in range(len(headers))]
        if any(len(values) != count for values in channels):
            report["Estado"] = "Número de amostras incompatível com os canais."
            warnings.append(f"Monitor {monitor}: {report['Estado']}")
            continue
        for index, (header, values) in enumerate(zip(headers, channels)):
            raw[f"{monitor} | {index + 1}: {header}"] = pd.Series(values, index=hours)
        if mode not in (0, 1):
            report["Estado"] = "Modo não integrado às análises; canais preservados na tabela bruta."
            warnings.append(f"Monitor {monitor}: {report['Estado']}")
            continue
        engine.Circuit.SetActiveElement(element)
        buses = engine.CktElement.BusNames()
        n = engine.CktElement.NumConductors()
        if terminal < 1 or terminal > len(buses):
            report["Estado"] = "Terminal inválido."
            continue
        bus = buses[terminal - 1].split(".")[0].lower()
        nodes = engine.CktElement.NodeOrder()[(terminal - 1) * n:terminal * n]
        kind, _, name = element.partition(".")
        name = name.lower()
        entity_type = {"line": "Line", "transformer": "Transformer", "load": "Load", "pvsystem": "PVSystem",
                       "storage": "Storage", "generator": "Generator", "capacitor": "Capacitor", "vsource": "Vsource"}.get(kind.lower())
        edges = [edge for edge in graph.edges.values() if edge.metadata.get("type") == entity_type and edge.metadata.get("name") == name]
        quantities, unused = _channel_quantities(headers, channels, mode)
        accepted, neutral = 0, 0
        for letter, conductor, values, unit in quantities:
            if conductor > len(nodes) or conductor < 1:
                continue
            phase = nodes[conductor - 1]
            if phase not in (1, 2, 3):
                neutral += 1
                continue
            if bus not in graph.nodes:
                continue
            if letter == "V":
                target_kind, target_id = "node", bus
                base = graph.nodes[bus].metadata.get("kv_base")
                if unit == "V" and base is not None and math.isfinite(base) and base > 0:
                    values, unit = values / (1000 * base), "pu"
                elif unit == "V":
                    warnings.append(f"Barra {bus}: tensão mantida em volts; base válida não disponível.")
                variable = f"V{phase}_{unit}"
                column = f"DSS-zip.Bus-{bus}-{variable}"
                candidate = pd.Series(values, index=hours)
                if column in series:
                    if not series[column].equals(candidate):
                        warnings.append(f"{column}: monitores divergentes; usado {voltage_sources[column]}, sem média ou mistura com {monitor}.")
                    continue
                voltage_sources[column] = monitor
                group = f"Barra {bus} - monitor {monitor}"
            else:
                if entity_type in {"Line", "Transformer"}:
                    if len(edges) != 1:
                        warnings.append(f"Monitor {monitor}: ramo com mais de dois terminais ou associação ambígua; consulte os canais brutos.")
                        continue
                    target_kind, target_id = "edge", edges[0].id
                elif entity_type:
                    target_kind = "pv" if entity_type == "PVSystem" else "equipment"
                    target_id = name
                else:
                    continue
                variable = f"{letter}{phase}_{unit}"
                column = f"OpenDSS.{monitor}-T{terminal}-{variable}"
                group = f"{entity_type} {name} - terminal {terminal} - monitor {monitor}"
                if target_kind == "pv" and letter in {"P", "Q"}:
                    values = -values
            identity = (target_kind, target_id, terminal if target_kind == "edge" else None, variable)
            previous = next((item for item in catalog if item.get("monitor_identity") == identity), None)
            if previous:
                warnings.append(f"Monitor {monitor}: canal {variable} duplicado; usado {previous['monitor']} nas análises.")
                continue
            series[column] = pd.Series(values, index=hours)
            catalog.append({"column": column, "variable": variable, "group": group,
                            "target_kind": target_kind, "target_id": target_id,
                            "target_node_id": bus if target_kind in {"pv", "equipment"} else None,
                            "entity_type": entity_type, "entity_name": name,
                            "terminal": terminal, "monitor": monitor, "monitor_identity": identity})
            accepted += 1
        report.update({"Estado": "Integrado" if accepted else "Sem novos canais compatíveis",
                       "Canais integrados": accepted, "Canais de neutro separados": neutral,
                       "Canais não interpretados": ", ".join(sorted(unused))})
    def table(columns):
        if not columns:
            return pd.DataFrame()
        frame = pd.DataFrame(columns).sort_index()
        frame.index.name = "Tempo (h)"
        return frame.reset_index()
    return table(series), catalog, table(raw), reports, list(dict.fromkeys(warnings))


def select_branch_terminals(catalog, selections):
    defaults = {}
    for item in catalog:
        if item["target_kind"] == "edge":
            defaults[item["target_id"]] = min(defaults.get(item["target_id"], item["terminal"]), item["terminal"])
    return [item for item in catalog if item["target_kind"] != "edge"
            or item["terminal"] == selections.get(item["target_id"], defaults[item["target_id"]])]


def load_dss_zip(content):
    engine = dss.NewContext()
    engine.Basic.AllowChangeDir(False)
    with tempfile.TemporaryDirectory(prefix="argos-opendss-") as directory:
        engine.Basic.DataPath(directory)
        try:
            result = compile_circuit(BytesIO(content), engine=engine, directory=directory)
            graph = _monitor_graph(engine)
            graph.metadata["timeline_id"] = hashlib.sha256(content).hexdigest()
            frame, catalog, raw, reports, warnings = read_monitor_results(engine, graph)
            if result["warning"]:
                warnings.insert(0, result["warning"])
            if not engine.Solution.Converged():
                warnings.insert(0, "O último Solve do circuito não convergiu; os resultados exigem conferência.")
            return DSSResults(graph, frame, catalog, raw, reports, warnings, result["master_file"])
        finally:
            engine.Basic.ClearAll()
