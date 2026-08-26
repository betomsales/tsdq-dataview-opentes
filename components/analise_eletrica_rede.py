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
    normalizar_unidade,
    remover_unidade_do_tipo,
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
    unidade = normalizar_unidade(unidade)
    fase = None

    if variavel_lower == "dni":
        return TIPO_IRRADIANCIA, None, unidade or "DNI"

    if variavel_lower == "tap":
        return TIPO_TAP, None, unidade

    if variavel_lower.startswith("p_gen"):
        return TIPO_POTENCIA_FV, None, unidade

    if variavel_lower == "p":
        if item["target_kind"] in {"pv", "pv_equipment"}:
            return TIPO_POTENCIA_FV, None, unidade

        return TIPO_POTENCIA_ATIVA, None, unidade

    if variavel_lower == "q":
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

    return (
        item["target_kind"] in {"pv", "pv_equipment"}
        and len(pv_nodes) == 1
        and pv_nodes[0] == node_id
    )


def montar_estrutura_analise_rede(
    graph,
    measurement_columns,
):
    estrutura = {}
    mapeamento = carregar_mapeamento()

    for node_id in graph.nodes:
        for item in measurement_columns:
            if not _pertence_ao_no(
                graph,
                item,
                node_id,
            ):
                continue

            tipo, fase, unidade = _classificar_variavel(
                item
            )

            variavel_info = {
                "tipo": tipo,
                "elemento": node_id,
                "fase": fase,
                "unidade_detectada": unidade,
                "coluna_original": item["column"],
                "metadados": mapeamento.get(tipo, {}),
            }

            estrutura.setdefault(
                tipo,
                {},
            ).setdefault(
                node_id,
                [],
            ).append(
                variavel_info
            )

    return estrutura


def render_controles_prodist_rede(
    unidade_final,
    serie_tensao,
    variavel_info,
    key_prefix,
):
    mostrar_limites = st.checkbox(
        "Mostrar faixas e limites PRODIST nos graficos",
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
            "Valores em pu usam os limites proporcionais padrao diretamente "
            "na serie, sem conversao de base."
        )
        classe = "Média tensão (> 2,3 kV a < 69 kV)"
    else:
        if classe is None:
            classe = classe_inferida_por_medida

        st.caption(
            f"Classe de tensao PRODIST inferida automaticamente: **{classe}**"
        )

    tensao_referencia = None

    if classe in CLASSES_PRODIST and unidade_final != "pu":
        tensao_referencia = st.number_input(
            f"TR para calculo dos limites [{unidade_final}]",
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
                f"Critico inf. [{unidade_final}]",
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
                f"Critico sup. [{unidade_final}]",
                value=float(limites["critico_max"]),
                format="%.6f",
                key=f"{key_prefix}_critico_max",
            )

    return True, limites


def _montar_opcoes_variaveis(variaveis):
    opcoes = []

    for variavel in variaveis:
        fase = variavel.get("fase")
        unidade = variavel.get("unidade_detectada")
        nome = ""

        if fase:
            nome += fase

        if unidade:
            if nome:
                nome += " "

            nome += f"({unidade})"

        if not nome:
            nome = variavel["tipo"]

        opcoes.append(nome)

    return opcoes


def render_analise_eletrica_elemento(
    df,
    estrutura,
    elemento_selecionado,
    key_prefix="analise_rede",
):
    tipos_disponiveis = [
        tipo
        for tipo, elementos in estrutura.items()
        if elemento_selecionado in elementos
    ]

    if not tipos_disponiveis:
        st.info(
            "O barramento selecionado nao possui variaveis reconhecidas "
            "para analise eletrica."
        )
        return

    indice_padrao = 0

    if TIPO_TENSAO in tipos_disponiveis:
        indice_padrao = tipos_disponiveis.index(
            TIPO_TENSAO
        )

    tipo_escolhido = st.selectbox(
        "Tipo de variavel",
        tipos_disponiveis,
        index=indice_padrao,
        key=f"{key_prefix}_tipo_variavel",
    )

    variaveis = estrutura[tipo_escolhido][
        elemento_selecionado
    ]

    if not variaveis:
        st.warning(
            "Nenhuma variavel encontrada para o barramento selecionado."
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
            "Variavel",
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

    if unidade_final:
        label_grafico = f"{tipo_variavel} [{unidade_final}]"
    else:
        label_grafico = tipo_variavel

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
