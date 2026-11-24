"""Metadados opcionais da rede de comunicacao; nao utiliza a topologia eletrica."""

from collections import deque
from dataclasses import dataclass, field
import json
import math

from utils.comunicacao import normalizar_agente


TECNOLOGIAS = {"Link_Wired": "Cabeada", "Link_5G": "5G", "Link_Wireless": "Wireless", "Link_4G": "4G", "Link_2G": "2G"}
NAO_IDENTIFICADA = "Não identificada"


def ler_metadado(content, kind):
    parsed = json.loads(content.decode("utf-8-sig"))
    if kind == "config":
        if not isinstance(parsed, dict):
            raise ValueError("config.json deve conter um objeto JSON.")
        return parsed
    if not isinstance(parsed, list):
        raise ValueError(f"{kind}.json deve conter uma lista de objetos.")
    result, seen = [], set()
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError(f"{kind}.json contém um registro que não é um objeto.")
        if kind == "posicoes":
            identifier = item.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError("Posição sem id textual.")
            identifier = normalizar_agente(identifier)
            if identifier in seen:
                raise ValueError(f"Posição duplicada para {identifier}.")
            seen.add(identifier)
            try:
                x, y = float(item["x"]), float(item["y"])
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"Coordenadas inválidas para {identifier}.") from None
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError(f"Coordenadas não finitas para {identifier}.")
            layer = item.get("camada")
            result.append({"id": identifier, "x": x, "y": y, "camada": layer if isinstance(layer, str) and layer.strip() else "Não informada"})
        elif kind == "links":
            source, target = item.get("origem", item.get("src")), item.get("destino", item.get("dst"))
            technology = item.get("tipo")
            if not all(isinstance(value, str) and value.strip() for value in (source, target, technology)):
                raise ValueError("Enlace sem origem, destino ou tipo textual.")
            result.append({"origem": normalizar_agente(source), "destino": normalizar_agente(target), "tipo": TECNOLOGIAS.get(technology, technology)})
        else:
            raise ValueError("Tipo de metadado desconhecido.")
    return result


@dataclass
class MetadadosComunicacao:
    config: dict = field(default_factory=dict)
    posicoes: list = field(default_factory=list)
    links: list = field(default_factory=list)

    def associar(self, messages):
        result = messages.copy()
        positions = {item["id"]: item for item in self.posicoes}
        adjacency = {}
        for link in self.links:
            source, target = link["origem"], link["destino"]
            # Parallel links with conflicting technologies cannot identify a sample.
            for a, b in ((source, target), (target, source)):
                neighbors = adjacency.setdefault(a, {})
                previous = neighbors.get(b)
                neighbors[b] = link["tipo"] if previous in (None, link["tipo"]) else NAO_IDENTIFICADA
        cache = {}

        def classify(sender, receiver):
            key = sender, receiver
            if key in cache:
                return cache[key]
            outcome = (NAO_IDENTIFICADA, "Sem associação", "")
            if sender in adjacency and receiver in adjacency and sender != receiver:
                distances, queue = {sender: 0}, deque([sender])
                while queue:
                    node = queue.popleft()
                    for neighbor in adjacency[node]:
                        if neighbor not in distances:
                            distances[neighbor] = distances[node] + 1
                            queue.append(neighbor)
                if receiver in distances:
                    candidates = [node for node in adjacency[receiver] if distances.get(node) == distances[receiver] - 1]
                    if len(candidates) == 1:
                        previous = candidates[0]
                        technology = adjacency[receiver][previous]
                        method = "Enlace direto declarado" if previous == sender else "Último salto estimado (caminho mínimo)"
                        outcome = (technology, method, f"{previous} → {receiver}")
                    elif candidates:
                        outcome = (NAO_IDENTIFICADA, "Rotas mínimas ambíguas", "")
            cache[key] = outcome
            return outcome

        associations = [classify(row.RemetenteId, row.NodeId) for row in result.itertuples()]
        for index, column in enumerate(("Tecnologia", "Associação", "Enlace")):
            result[column] = [item[index] for item in associations]
        result["Camada"] = result["NodeId"].map(lambda node: positions.get(node, {}).get("camada", "Não informada"))
        return result

    def diagnosticar(self, temporal, messages):
        warnings = []
        nodes = set(temporal["NodeId"])
        positions = {item["id"] for item in self.posicoes}
        if positions and nodes - positions:
            warnings.append(f"{len(nodes - positions)} nó(s) do CSV sem coordenadas; não aparecem no mapa.")
        if positions - nodes:
            warnings.append(f"{len(positions - nodes)} posição(ões) sem registros no CSV; permanecem sem medição no mapa.")
        if not messages.empty and self.links and messages["Tecnologia"].eq(NAO_IDENTIFICADA).any():
            warnings.append("Há mensagens sem tecnologia identificável; elas permanecem na visão geral e na tabela de dados.")
        if not messages.empty and messages["Associação"].str.startswith("Último salto").any():
            warnings.append("Parte das tecnologias representa o último salto estimado por caminho mínimo, não o percurso medido. A latência do CSV é fim a fim.")
        return warnings
