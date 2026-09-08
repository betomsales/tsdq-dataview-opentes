import re

import pandas as pd
import streamlit as st

from components.graficos import (
    eh_tensao,
    render_grafico_distribuicao_tensao,
    render_grafico_individual,
    render_grafico_multiserie,
)
from components.tabelas import (
    render_codigo_variavel,
    render_tabela_dataset,
    render_tabela_serie,
)
from utils.escalas import obter_escala_visual
from utils.mapeamento import carregar_mapeamento
from utils.processamento import (
    preparar_multiplas_series,
    preparar_serie_temporal,
)
from utils.prodist import (
    CLASSES_PRODIST,
    inferir_classe_prodist,
    inferir_metadados_prodist,
    obter_limites_prodist,
)
from utils.unidades import (
    inferir_unidade_variavel,
    normalizar_unidade,
    remover_unidade_do_tipo,
)
from utils.rotulos_medicoes import (
    montar_rotulo_serie,
    obter_categoria_equipamento,
    obter_nome_curto_elemento,
    obter_rotulo_variavel,
    obter_unidade_configurada,
)


TIPO_TENSAO = "Tensão"
TIPO_CORRENTE = "Corrente (A)"
TIPO_ANGULO_CORRENTE = "Ângulo de Corrente (°)"
TIPO_TAP = "Taps dos Reguladores"
TIPO_POTENCIA_GERADOR = "Potência do Gerador (MW)"
TIPO_IRRADIANCIA = "Irradiância Solar (DNI)"
TIPO_POTENCIA_FV = "Potência Fotovoltaica"
TIPO_POTENCIA_ATIVA = "Potência Ativa da Rede (MW)"
TIPO_POTENCIA_REATIVA = "Potência Reativa da Rede (MVar)"
TIPO_TEMPERATURA_PV = "Temperatura do PV"


def preparar_dataframe_analise(
    results_df,
    time_values,
):
    df = results_df.copy()

    if time_values is None or time_values.isna().all():
        df["Tempo_EixoX"] = range(len(df))
    else:
        df["Tempo_EixoX"] = time_values

    return df


def _separar_variavel_unidade(variavel):
    unidades = {
        "pu": "pu",
        "a": "A",
        "ka": "kA",
        "ang": "°",
        "w": "W",
        "kw": "kW",
        "mw": "MW",
        "var": "Var",
        "kvar": "kVar",
        "mvar": "MVar",
        "v": "V",
        "kv": "kV",
        "wm2": "W/m²",
        "kwm2": "kW/m²",
        "dni": "DNI",
    }

    partes = str(variavel).rsplit("_", 1)

    if len(partes) == 2 and partes[1].lower() in unidades:
        return partes[0], unidades[partes[1].lower()]

    return str(variavel), None


def _fase_por_prefixo(variavel_base, prefixo):
    match = re.match(
        rf"^{prefixo}([A-Za-z0-9]+)$",
        variavel_base,
        re.IGNORECASE,
    )

    if not match:
        return None

    sufixo = match.group(1).upper()

    fases_tensao = {
        "1",
        "2",
        "3",
        "A",
        "B",
        "C",
        "AN",
        "BN",
        "CN",
        "AB",
        "BC",
        "CA",
        "12",
        "23",
        "31",
        "M",
    }
    fases_corrente = {
        "1",
        "2",
        "3",
        "A",
        "B",
        "C",
    }

    fases_validas = (
        fases_tensao
        if prefixo.lower() == "v"
        else fases_corrente
    )

    if sufixo not in fases_validas:
        return None

    return f"{prefixo.upper()}{sufixo}"


def _classificar_variavel(item):
    variavel_base, unidade = _separar_variavel_unidade(
        item["variable"]
    )
    variavel_lower = variavel_base.lower()
    unidade = (
        normalizar_unidade(unidade)
        or obter_unidade_configurada(variavel_base)
        or inferir_unidade_variavel(
            variavel_base,
            item.get("target_kind"),
        )
    )
    unidade = normalizar_unidade(
        unidade
    )
    fase = None

    if variavel_lower in {"dni", "irradiance"}:
        return TIPO_IRRADIANCIA, None, unidade or "DNI"

    if variavel_lower in {"temperature", "temperatura"}:
        return TIPO_TEMPERATURA_PV, None, unidade

    if variavel_lower == "tap":
        return TIPO_TAP, None, unidade

    if variavel_lower.startswith("p_gen"):
        return TIPO_POTENCIA_FV, None, unidade

    match_p = re.match(
        r"^p([123abc])?$",
        variavel_lower,
    )

    if match_p:
        fase = (
            f"P{match_p.group(1).upper()}"
            if match_p.group(1)
            else None
        )

        if item["target_kind"] in {"pv", "pv_equipment"}:
            return TIPO_POTENCIA_FV, fase, unidade

        return TIPO_POTENCIA_ATIVA, fase, unidade

    if variavel_lower.startswith("p_"):
        if item["target_kind"] in {"pv", "pv_equipment"}:
            return TIPO_POTENCIA_FV, None, unidade

        return TIPO_POTENCIA_ATIVA, None, unidade

    match_q = re.match(
        r"^q([123abc])?$",
        variavel_lower,
    )

    if match_q:
        fase = (
            f"Q{match_q.group(1).upper()}"
            if match_q.group(1)
            else None
        )

        return TIPO_POTENCIA_REATIVA, fase, unidade

    if variavel_lower.startswith("q_"):
        return TIPO_POTENCIA_REATIVA, None, unidade

    fase = _fase_por_prefixo(
        variavel_base,
        "v",
    )

    if fase:
        return TIPO_TENSAO, fase, unidade

    fase = _fase_por_prefixo(
        variavel_base,
        "i",
    )

    if fase and unidade == "°":
        return TIPO_ANGULO_CORRENTE, fase, unidade

    if fase:
        return TIPO_CORRENTE, fase, unidade

    return variavel_base, None, unidade


def _pertence_ao_no(
    graph,
    item,
    node_id,
):
    pv_nodes = [
        node.id
        for node in graph.nodes.values()
        if node.node_type == "pv"
    ]

    if (
        item["target_kind"] == "node"
        and item["target_id"] == node_id
        and node_id in graph.nodes
    ):
        return True

    if (
        item["target_kind"] in {"pv", "pv_equipment"}
        and item.get("target_node_id") == node_id
        and node_id in graph.nodes
    ):
        return True

    return (
        item["target_kind"] in {"pv", "pv_equipment"}
        and len(pv_nodes) == 1
        and pv_nodes[0] == node_id
    )


def _elemento_da_medicao(item):
    if item["target_kind"] == "node":
        return item["target_id"]

    if item["target_kind"] == "edge":
        return item["target_id"]

    if item["target_kind"] == "pv":
        return f"pvsystem:{item['target_id']}"

    if item["target_kind"] == "pv_equipment":
        return f"equipamento:{item['target_id']}"

    return item["target_id"]


def _tipo_entidade(item):
    if item["target_kind"] == "node":
        return "Barra"

    if item["target_kind"] == "edge":
        return "Linha"

    if item["target_kind"] == "pv":
        return "PVSystem"

    if item["target_kind"] == "pv_equipment":
        return "Equipamento"

    return "Outro"


def montar_estrutura_analise_rede(
    graph,
    measurement_columns,
):
    estrutura = {}
    mapeamento = carregar_mapeamento()

    for item in measurement_columns:
        elemento = _elemento_da_medicao(
            item
        )
        variavel_base, _ = _separar_variavel_unidade(
            item["variable"]
        )
        tipo, fase, unidade = _classificar_variavel(
            item
        )

        variavel_info = {
            "tipo": tipo,
            "elemento": elemento,
            "fase": fase,
            "unidade_detectada": unidade,
            "variavel_base": variavel_base,
            "rotulo_variavel": obter_rotulo_variavel(
                variavel_base
            ),
            "coluna_original": item["column"],
            "metadados": mapeamento.get(tipo, {}),
            "tipo_entidade": _tipo_entidade(item),
            "origem_medicao": item["group"],
            "target_kind": item["target_kind"],
            "target_id": item["target_id"],
            "target_node_id": item.get("target_node_id"),
            "nome_curto_elemento": obter_nome_curto_elemento(
                item.get("target_id"),
                item.get("group"),
            ),
            "categoria_card": obter_categoria_equipamento(
                variavel_base,
                item.get("target_id"),
            ),
        }
        variavel_info["rotulo_serie"] = montar_rotulo_serie(
            variavel_info,
            incluir_origem=True,
        )
        variavel_info["rotulo_card"] = montar_rotulo_serie(
            variavel_info,
            incluir_origem=variavel_info["tipo_entidade"] in {
                "PVSystem",
                "Equipamento",
                "Linha",
            },
            incluir_unidade=False,
            compacto=variavel_info["tipo_entidade"] in {
                "PVSystem",
                "Equipamento",
            },
        )

        estrutura.setdefault(
            tipo,
            {},
        ).setdefault(
            elemento,
            [],
        ).append(
            variavel_info
        )

    return estrutura


def _elemento_tem_variaveis(
    estrutura,
    elemento,
):
    return any(
        elemento in elementos
        for elementos in estrutura.values()
    )


def _variaveis_do_elemento(
    estrutura,
    elemento,
):
    variaveis = []

    for elementos in estrutura.values():
        variaveis.extend(
            elementos.get(
                elemento,
                [],
            )
        )

    return variaveis


def _linhas_conectadas(
    graph,
    node_id,
):
    return [
        edge
        for edge in graph.edges.values()
        if node_id in {edge.source, edge.target}
    ]


def _equipamentos_vinculados(
    graph,
    estrutura,
    node_id,
):
    pv_nodes = [
        node.id
        for node in graph.nodes.values()
        if node.node_type == "pv"
    ]

    equipamentos = []

    for elementos in estrutura.values():
        for elemento, variaveis in elementos.items():
            if not variaveis:
                continue

            tipo_entidade = variaveis[0].get(
                "tipo_entidade"
            )
            target_node_id = variaveis[0].get(
                "target_node_id"
            )

            if (
                tipo_entidade in {"PVSystem", "Equipamento"}
                and target_node_id == node_id
            ):
                equipamentos.append(
                    elemento
                )
                continue

            if (
                tipo_entidade in {"PVSystem", "Equipamento"}
                and not target_node_id
                and len(pv_nodes) == 1
                and pv_nodes[0] == node_id
            ):
                equipamentos.append(
                    elemento
                )

    return sorted(
        set(equipamentos)
    )


def _rotulo_elemento(
    graph,
    estrutura,
    elemento,
):
    if elemento in graph.nodes:
        node = graph.nodes[elemento]

        if node.label == elemento:
            return elemento

        return f"{node.label} ({elemento})"

    if elemento in graph.edges:
        edge = graph.edges[elemento]
        return f"{edge.id}: {edge.source} -> {edge.target}"

    variaveis = _variaveis_do_elemento(
        estrutura,
        elemento,
    )

    if variaveis:
        return variaveis[0].get(
            "origem_medicao",
            elemento,
        )

    return elemento


def _metric_card(
    titulo,
    valor,
):
    st.metric(
        titulo,
        valor,
    )


def render_resumo_contexto_eletrico(
    graph,
    estrutura,
    node_id,
):
    linhas = [
        edge
        for edge in _linhas_conectadas(
            graph,
            node_id,
        )
        if _elemento_tem_variaveis(
            estrutura,
            edge.id,
        )
    ]
    equipamentos = _equipamentos_vinculados(
        graph,
        estrutura,
        node_id,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        _metric_card(
            "Medições da barra",
            len(
                _variaveis_do_elemento(
                    estrutura,
                    node_id,
                )
            ),
        )

    with col2:
        _metric_card(
            "Linhas conectadas",
            len(linhas),
        )

    with col3:
        _metric_card(
            "Equipamentos vinculados",
            len(equipamentos),
        )

    st.caption(
        "Tensões são apresentadas na barra; correntes e fluxos P/Q são "
        "apresentados nos ramos; geração/injeção aparece nos equipamentos "
        "vinculados ao barramento."
    )


def render_controles_prodist_rede(
    unidade_final,
    serie_tensao,
    variavel_info,
    key_prefix,
):
    mostrar_limites = st.checkbox(
        "Mostrar faixas e limites PRODIST nos gráficos",
        value=True,
        key=f"{key_prefix}_mostrar_limites_prodist",
    )

    if not mostrar_limites:
        return False, None

    metadados_prodist = inferir_metadados_prodist(
        variavel_info,
        unidade_final,
    )

    classe = metadados_prodist.get("classe")

    if classe is None:
        classe = inferir_classe_prodist(
            serie_tensao,
            unidade_final,
        )

    classe_inferida_por_medida = inferir_classe_prodist(
        serie_tensao,
        unidade_final,
    )

    serie_valida = serie_tensao.dropna()
    valor_referencia = 1.0

    if not serie_valida.empty:
        valor_referencia = float(
            serie_valida.abs().median()
        )

    if unidade_final == "pu":
        st.caption(
            "Valores em pu usam os limites proporcionais padrão diretamente "
            "na série, sem conversão de base."
        )
        classe = "Média tensão (> 2,3 kV a < 69 kV)"
    else:
        if classe is None:
            classe = classe_inferida_por_medida

        st.caption(
            f"Classe de tensão PRODIST inferida automaticamente: **{classe}**"
        )

    tensao_referencia = None

    if classe in CLASSES_PRODIST and unidade_final != "pu":
        tensao_referencia = st.number_input(
            f"TR para cálculo dos limites [{unidade_final}]",
            min_value=0.0,
            value=valor_referencia,
            step=0.1 if unidade_final == "kV" else 1.0,
            key=f"{key_prefix}_tensao_referencia_prodist",
        )

    limites = obter_limites_prodist(
        classe=classe,
        tensao_referencia=tensao_referencia,
        unidade=unidade_final,
    )

    editar_limites = st.checkbox(
        "Editar limites manualmente",
        value=False,
        key=f"{key_prefix}_editar_limites_prodist",
    )

    if editar_limites:
        col_l1, col_l2, col_l3, col_l4 = st.columns(4)

        with col_l1:
            limites["critico_min"] = st.number_input(
                f"Crítico inf. [{unidade_final}]",
                value=float(limites["critico_min"]),
                format="%.6f",
                key=f"{key_prefix}_critico_min",
            )

        with col_l2:
            limites["adequado_min"] = st.number_input(
                f"Adequado min. [{unidade_final}]",
                value=float(limites["adequado_min"]),
                format="%.6f",
                key=f"{key_prefix}_adequado_min",
            )

        with col_l3:
            limites["adequado_max"] = st.number_input(
                f"Adequado max. [{unidade_final}]",
                value=float(limites["adequado_max"]),
                format="%.6f",
                key=f"{key_prefix}_adequado_max",
            )

        with col_l4:
            limites["critico_max"] = st.number_input(
                f"Crítico sup. [{unidade_final}]",
                value=float(limites["critico_max"]),
                format="%.6f",
                key=f"{key_prefix}_critico_max",
            )

    return True, limites


def _montar_opcoes_variaveis(variaveis):
    opcoes = []

    for variavel in variaveis:
        nome = montar_rotulo_serie(
            variavel,
            incluir_origem=False,
        )

        opcoes.append(nome)

    return opcoes


def render_analise_eletrica_elemento(
    df,
    estrutura,
    elemento_selecionado,
    key_prefix="analise_rede",
):
    variaveis_elemento = _variaveis_do_elemento(
        estrutura,
        elemento_selecionado,
    )

    if variaveis_elemento:
        tipo_entidade = variaveis_elemento[0].get(
            "tipo_entidade",
            "Elemento",
        )
        origem = variaveis_elemento[0].get(
            "origem_medicao",
            elemento_selecionado,
        )

        st.caption(
            f"Origem da medição: {tipo_entidade} - {origem}"
        )

    tipos_disponiveis = [
        tipo
        for tipo, elementos in estrutura.items()
        if elemento_selecionado in elementos
    ]

    if not tipos_disponiveis:
        st.info(
            "O barramento selecionado não possui variáveis reconhecidas "
            "para análise elétrica."
        )
        return

    indice_padrao = 0

    if TIPO_TENSAO in tipos_disponiveis:
        indice_padrao = tipos_disponiveis.index(
            TIPO_TENSAO
        )

    tipo_escolhido = st.selectbox(
        "Tipo de variável",
        tipos_disponiveis,
        index=indice_padrao,
        key=f"{key_prefix}_tipo_variavel",
    )

    variaveis = estrutura[tipo_escolhido][
        elemento_selecionado
    ]

    if not variaveis:
        st.warning(
            "Nenhuma variável encontrada para o barramento selecionado."
        )
        return

    opcoes_variaveis = _montar_opcoes_variaveis(
        variaveis
    )
    opcoes_unicas = list(
        dict.fromkeys(opcoes_variaveis)
    )

    if len(opcoes_unicas) == 1:
        variavel_info = variaveis[0]
    else:
        variavel_escolhida = st.selectbox(
            "Variável",
            opcoes_unicas,
            key=f"{key_prefix}_variavel",
        )
        indice = opcoes_variaveis.index(
            variavel_escolhida
        )
        variavel_info = variaveis[indice]

    dados_plot = preparar_serie_temporal(
        df,
        variavel_info,
    )

    df_multiserie = None
    df_plot = dados_plot["df_plot"]

    unidade_original = variavel_info.get(
        "unidade_detectada"
    )
    unidade_final, fator_visual = obter_escala_visual(
        df_plot["Valor"],
        unidade_original,
    )

    df_plot = df_plot.copy()
    df_plot["Valor"] = df_plot["Valor"] * fator_visual

    tipo_variavel = remover_unidade_do_tipo(
        variavel_info["tipo"]
    )
    rotulo_variavel = variavel_info.get(
        "rotulo_variavel"
    ) or tipo_variavel

    if unidade_final:
        label_grafico = f"{rotulo_variavel} [{unidade_final}]"
    else:
        label_grafico = rotulo_variavel

    coluna_real = dados_plot["coluna_real"]
    mostrar_limites_prodist = False
    limites_prodist = None

    if eh_tensao(
        variavel_info
    ):
        mostrar_limites_prodist, limites_prodist = render_controles_prodist_rede(
            unidade_final,
            df_plot["Valor"],
            variavel_info,
            key_prefix,
        )

    if len(opcoes_unicas) > 1:
        col_esquerda, col_direita = st.columns(2)
    else:
        col_esquerda = st.container()

    with col_esquerda:
        render_grafico_individual(
            df_plot,
            coluna_real,
            label_grafico,
            variavel_info,
            mostrar_limites_prodist,
            limites_prodist,
        )

    if len(opcoes_unicas) > 1:
        df_multiserie = preparar_multiplas_series(
            df,
            variaveis,
        )

        for coluna in df_multiserie.columns:
            if coluna != "Tempo":
                df_multiserie[coluna] = (
                    df_multiserie[coluna]
                    * fator_visual
                )

        with col_direita:
            render_grafico_multiserie(
                df_multiserie,
                label_grafico,
                variavel_info,
                mostrar_limites_prodist,
                limites_prodist,
            )

    if eh_tensao(
        variavel_info
    ):
        if df_multiserie is None:
            df_tensoes_distribuicao = df_plot.rename(
                columns={
                    "Valor": coluna_real
                }
            )
        else:
            df_tensoes_distribuicao = df_multiserie

        render_grafico_distribuicao_tensao(
            df_tensoes_distribuicao,
            label_grafico,
            mostrar_limites_prodist,
            limites_prodist,
        )

    render_tabela_serie(
        df_plot
    )
    render_tabela_dataset(
        df
    )
    render_codigo_variavel(
        variavel_info
    )


def _series_potencia_por_fase(
    df,
    estrutura,
    elemento,
    prefixo_fase,
):
    series = {}

    for variavel in _variaveis_do_elemento(
        estrutura,
        elemento,
    ):
        fase = variavel.get("fase")

        if not fase or not fase.startswith(prefixo_fase):
            continue

        coluna = variavel["coluna_original"]

        if coluna not in df.columns:
            continue

        chave_fase = fase[1:] or "total"
        series[chave_fase] = {
            "coluna": coluna,
            "valores": pd.to_numeric(
                df[coluna],
                errors="coerce",
            ),
        }

    return series


def render_grandezas_derivadas(
    df,
    estrutura,
    elemento,
    rotulo_elemento,
):
    potencias_p = _series_potencia_por_fase(
        df,
        estrutura,
        elemento,
        "P",
    )
    potencias_q = _series_potencia_por_fase(
        df,
        estrutura,
        elemento,
        "Q",
    )
    fases = sorted(
        set(potencias_p)
        & set(potencias_q)
    )

    if not fases:
        st.info(
            "Não há pares P/Q suficientes para calcular potência aparente "
            "neste elemento."
        )
        return

    resumo = []
    series_s = pd.DataFrame()
    series_s["Tempo"] = df["Tempo_EixoX"]

    for fase in fases:
        valores_s = (
            potencias_p[fase]["valores"] ** 2
            + potencias_q[fase]["valores"] ** 2
        ) ** 0.5

        nome_fase = f"S{fase}"
        series_s[nome_fase] = valores_s

        resumo.append(
            {
                "Elemento": rotulo_elemento,
                "Grandeza derivada": nome_fase,
                "P de origem": potencias_p[fase]["coluna"],
                "Q de origem": potencias_q[fase]["coluna"],
                "Média": valores_s.mean(),
                "Mínimo": valores_s.min(),
                "Máximo": valores_s.max(),
            }
        )

    st.subheader(
        "Potência Aparente Calculada"
    )
    st.caption(
        "A potência aparente S não foi lida diretamente do arquivo CSV; "
        "ela foi calculada por fase a partir dos pares correspondentes "
        "de potência ativa P e potência reativa Q associados ao próprio "
        "elemento selecionado."
    )

    st.line_chart(
        series_s.set_index("Tempo")
    )
    st.dataframe(
        pd.DataFrame(resumo),
        use_container_width=True,
    )


def render_analise_eletrica_contexto(
    df,
    estrutura,
    graph,
    node_id,
    key_prefix="analise_contexto",
):
    render_resumo_contexto_eletrico(
        graph,
        estrutura,
        node_id,
    )

    aba_barra, aba_linhas, aba_equipamentos, aba_derivadas = st.tabs(
        [
            "Barramento",
            "Linhas conectadas",
            "Equipamentos conectados",
            "Grandezas derivadas",
        ]
    )

    with aba_barra:
        st.caption(
            "Medições próprias da barra selecionada, como tensões por fase."
        )

        if _elemento_tem_variaveis(
            estrutura,
            node_id,
        ):
            render_analise_eletrica_elemento(
                df,
                estrutura,
                node_id,
                key_prefix=f"{key_prefix}_barra_{node_id}",
            )
        else:
            st.info(
                "Esta barra não possui medições próprias reconhecidas no CSV."
            )

    with aba_linhas:
        linhas = [
            edge
            for edge in _linhas_conectadas(
                graph,
                node_id,
            )
            if _elemento_tem_variaveis(
                estrutura,
                edge.id,
            )
        ]

        if not linhas:
            st.info(
                "Não há linhas conectadas com medições reconhecidas no CSV."
            )
        else:
            linha_escolhida = st.selectbox(
                "Linha analisada",
                linhas,
                format_func=lambda edge: (
                    f"{edge.id}: {edge.source} -> {edge.target}"
                ),
                key=f"{key_prefix}_linha",
            )

            st.caption(
                "Correntes e P/Q exibidos aqui pertencem ao ramo selecionado, "
                "representando fluxo na linha."
            )

            render_analise_eletrica_elemento(
                df,
                estrutura,
                linha_escolhida.id,
                key_prefix=f"{key_prefix}_linha_{linha_escolhida.id}",
            )

    with aba_equipamentos:
        equipamentos = _equipamentos_vinculados(
            graph,
            estrutura,
            node_id,
        )

        if not equipamentos:
            st.info(
                "Não há equipamentos vinculados a este barramento com "
                "medições reconhecidas no CSV."
            )
        else:
            equipamento_escolhido = st.selectbox(
                "Equipamento analisado",
                equipamentos,
                format_func=lambda elemento: _rotulo_elemento(
                    graph,
                    estrutura,
                    elemento,
                ),
                key=f"{key_prefix}_equipamento",
            )

            st.caption(
                "P/Q exibidos aqui pertencem ao equipamento, como geração "
                "fotovoltaica, inversor ou painel."
            )

            render_analise_eletrica_elemento(
                df,
                estrutura,
                equipamento_escolhido,
                key_prefix=f"{key_prefix}_equipamento_{equipamento_escolhido}",
            )

    with aba_derivadas:
        opcoes_derivadas = []

        for edge in _linhas_conectadas(
            graph,
            node_id,
        ):
            if _elemento_tem_variaveis(
                estrutura,
                edge.id,
            ):
                opcoes_derivadas.append(
                    edge.id
                )

        opcoes_derivadas.extend(
            _equipamentos_vinculados(
                graph,
                estrutura,
                node_id,
            )
        )

        if not opcoes_derivadas:
            st.info(
                "Não há elementos conectados com P/Q para cálculos derivados."
            )
        else:
            elemento_derivado = st.selectbox(
                "Elemento para cálculo",
                opcoes_derivadas,
                format_func=lambda elemento: _rotulo_elemento(
                    graph,
                    estrutura,
                    elemento,
                ),
                key=f"{key_prefix}_derivado",
            )

            render_grandezas_derivadas(
                df,
                estrutura,
                elemento_derivado,
                _rotulo_elemento(
                    graph,
                    estrutura,
                    elemento_derivado,
                ),
            )
