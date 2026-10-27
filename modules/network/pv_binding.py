"""Resolve vinculos de medicoes fotovoltaicas sem depender da apresentacao."""


def _normalizar(valor):
    return str(valor).strip().lower() if valor is not None else ""


def _indice_pvs(graph):
    anexos = {}
    for node in graph.nodes.values():
        attached = node.metadata.get("attached") or {}
        if not isinstance(attached, dict):
            continue
        for referencia in attached.get("pv") or []:
            chave = _normalizar(referencia)
            if chave:
                anexos.setdefault(chave, set()).add(node.id)

    indice = {}
    declarados = set()
    possui_cadastro = graph.metadata.get("topology_version") == 2 or bool(anexos)
    for elemento in graph.metadata.get("elements") or []:
        if not isinstance(elemento, dict) or (
            _normalizar(elemento.get("element_type")) != "pv"
            and _normalizar(elemento.get("type")) != "pvsystem"
        ):
            continue
        possui_cadastro = True
        aliases = {_normalizar(elemento.get(campo)) for campo in ("id", "name")} - {""}
        identidade = _normalizar(elemento.get("id") or elemento.get("name"))
        barras = {_normalizar(elemento.get("bus"))} - {""}
        for alias in aliases:
            barras.update(anexos.get(alias, set()))
        declarados.update(aliases)
        for alias in aliases:
            indice.setdefault(alias, set()).update(
                (identidade, barra) for barra in barras or {""}
            )

    for referencia, barras in anexos.items():
        if referencia not in declarados:
            indice.setdefault(referencia, set()).update((referencia, barra) for barra in barras)
    return indice, possui_cadastro


def vincular_medicoes_pv(graph, measurement_columns):
    """Retorna um catalogo associado, preservando o catalogo CSV original."""
    indice, possui_cadastro = _indice_pvs(graph)
    legados = [node.id for node in graph.nodes.values() if node.node_type == "pv"]
    resultado = []

    for original in measurement_columns:
        item = dict(original)
        resultado.append(item)
        if item.get("target_kind") not in {"pv", "pv_equipment"}:
            continue

        explicita = _normalizar(item.get("csv_target_node_id", item.get("target_node_id")))
        grupo_csv = item.get("csv_group", item["group"])
        item["csv_target_node_id"] = explicita or None
        item["csv_group"] = grupo_csv
        candidatos = indice.get(_normalizar(item.get("target_id")), set()) if item["target_kind"] == "pv" else set()
        erro = None
        barra_json = None
        if len(candidatos) > 1:
            erro = "Identificador PV ambiguo ou conexoes conflitantes no JSON"
        elif candidatos:
            _, barra_json = next(iter(candidatos))
            if barra_json not in graph.nodes:
                erro = "O PV referencia uma barra ausente na topologia"
            elif explicita and explicita != barra_json:
                erro = "A barra declarada no CSV diverge da conexao do PV no JSON"

        # Classes DSS nao reconhecidas nao sao paineis nem inversores.
        equipamento_dss = (
            item["target_kind"] == "pv_equipment"
            and str(item.get("column", "")).lower().startswith("dss-")
        )
        barra = None
        origem = None
        if equipamento_dss:
            erro = "Classe DSS ainda nao vinculada como equipamento fotovoltaico"
        elif not erro and explicita:
            if explicita in graph.nodes:
                barra, origem = explicita, "csv_bus"
            else:
                erro = "A barra declarada no CSV nao existe na topologia"
        elif not erro and barra_json:
            barra, origem = barra_json, "elements"
        elif not erro and not possui_cadastro and len(legados) == 1:
            barra, origem = legados[0], "legacy_single_pv"
        elif not erro:
            erro = "Equipamento sem vinculo inequivoco com uma barra no JSON"

        item["target_node_id"] = barra
        item["binding_source"] = origem
        item["binding_error"] = erro
        item["group"] = grupo_csv
        if barra and not explicita:
            item["group"] = f"{grupo_csv} (barra {barra})"

    return resultado
