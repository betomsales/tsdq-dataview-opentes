from html import escape

import streamlit as st

from utils.escalas import auto_scale
from utils.estado_geracao import montar_estado_geracao_fv_series
from utils.qee import (
    calcular_desequilibrio_global,
    calcular_drp_drc_global,
    calcular_indicadores_temporais,
    identificar_variaveis_qee,
    montar_card_fases,
)


def card_qee(
    titulo,
    dados=None,
    cor="#95a5a6",
):
    tamanho_titulo = "1.5rem"
    tamanho_fase = "1.2rem"
    tamanho_valor = "1.3rem"

    if not dados:
        conteudo = """
        <p style="
            color:gray;
            margin:0;
            font-size:1rem;
        ">
            Não identificado
        </p>
        """
        cor = "#7f8c8d"
    else:
        linhas = []

        for fase, info in dados.items():
            valor = info.get("valor")
            unidade = info.get("unidade")

            if (
                valor is not None
                and unidade in ["W", "Var", "V", "A"]
            ):
                valor, unidade, _ = auto_scale(
                    valor,
                    unidade,
                )

            if valor is None:
                valor_str = "Não identificado"
            else:
                valor_str = f"{valor:.4f}"

            linha = (
                f"<div style='display:flex;"
                f"justify-content:space-between;"
                f"gap:1rem;"
                f"margin-bottom:0.3rem;'>"
                f"<span style='font-size:{tamanho_fase};line-height:1.35;'>"
                f"{fase}"
                f"</span>"
                f"<span style='font-size:{tamanho_valor};font-weight:bold;"
                f"white-space:nowrap;flex-shrink:0;'>"
                f"{valor_str} "
                f"{unidade or ''}"
                f"</span>"
                f"</div>"
            )
            linhas.append(linha)

        conteudo = "".join(linhas)

    st.markdown(
        f"""
        <div style="
            border-left: 6px solid {cor};
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #f7f7f7;
            margin-bottom: 1rem;
            min-height: 180px;
        ">

        <h4 style="
            margin-top:0;
            margin-bottom:1rem;
            font-size:{tamanho_titulo};
        ">
            {titulo}
        </h4>

        {conteudo}

        </div>
        """,
        unsafe_allow_html=True,
    )


def card_qee_texto(
    titulo,
    dados=None,
    cor="#95a5a6",
):
    if not dados:
        conteudo = (
            '<p style="color:gray;margin:0;font-size:1rem;">'
            "Não identificado"
            "</p>"
        )
    else:
        linhas = []

        for rotulo, valor in dados:
            linhas.append(
                "<div style='display:flex;justify-content:space-between;"
                "gap:1rem;margin-bottom:0.3rem;align-items:flex-start;'>"
                "<span style='font-size:1.2rem;line-height:1.35;color:#4b5563;'>"
                f"{escape(str(rotulo))}"
                "</span>"
                "<span style='font-size:1.2rem;font-weight:bold;line-height:1.35;"
                "text-align:right;white-space:normal;overflow-wrap:anywhere;'>"
                f"{escape(str(valor))}"
                "</span>"
                "</div>"
            )

        conteudo = "".join(
            linhas
        )

    st.markdown(
        f"""
        <div style="
            border-left: 6px solid {cor};
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #f7f7f7;
            margin-bottom: 1rem;
            min-height: 180px;
        ">

        <h4 style="
            margin-top:0;
            margin-bottom:1rem;
            font-size:1.5rem;
        ">
            {escape(str(titulo))}
        </h4>

        {conteudo}

        </div>
        """,
        unsafe_allow_html=True,
    )


def _filtrar_por_elemento(
    variaveis,
    elemento_referencia,
):
    if elemento_referencia is None:
        return variaveis

    return [
        variavel
        for variavel in variaveis
        if (
            variavel["elemento"] == elemento_referencia
            or variavel.get("target_node_id") == elemento_referencia
        )
    ]


def _filtrar_por_categoria(
    variaveis,
    categoria,
):
    return [
        variavel
        for variavel in variaveis
        if variavel.get("categoria_card") == categoria
    ]


def render_cards_qee(
    df,
    estrutura,
    elemento_referencia=None,
    permitir_selecao=True,
    key_prefix="qee",
):
    variaveis_qee = identificar_variaveis_qee(
        estrutura
    )

    st.subheader(
        "Configuração QEE"
    )

    opcoes_tensao = []

    for variavel in variaveis_qee["tensao"]:
        elemento = variavel["elemento"]

        if elemento not in opcoes_tensao:
            opcoes_tensao.append(elemento)

    if not opcoes_tensao:
        st.warning(
            "Nenhuma variável de tensão foi identificada para cálculo de QEE."
        )
        return

    if elemento_referencia in opcoes_tensao:
        tensao_referencia = elemento_referencia
    elif permitir_selecao:
        tensao_referencia = st.selectbox(
            "Tensão de referência",
            opcoes_tensao,
            key=f"{key_prefix}_tensao_referencia",
        )
    else:
        st.info(
            "O barramento selecionado não possui tensões reconhecidas para QEE."
        )
        return

    filtro_elemento = (
        elemento_referencia
        if elemento_referencia is not None
        else None
    )

    variaveis_tensao_filtradas = [
        variavel
        for variavel in variaveis_qee["tensao"]
        if variavel["elemento"] == tensao_referencia
    ]

    dados_tensao = montar_card_fases(
        df,
        variaveis_tensao_filtradas,
    )
    dados_corrente = montar_card_fases(
        df,
        _filtrar_por_elemento(
            variaveis_qee["corrente"],
            filtro_elemento,
        ),
    )
    variaveis_potencia_ativa = _filtrar_por_elemento(
        variaveis_qee["potencia_ativa"],
        filtro_elemento,
    )
    variaveis_potencia_reativa = _filtrar_por_elemento(
        variaveis_qee["potencia_reativa"],
        filtro_elemento,
    )
    variaveis_potencia_fv = _filtrar_por_elemento(
        variaveis_qee["potencia_fv"],
        filtro_elemento,
    )
    variaveis_temperatura_pv = _filtrar_por_elemento(
        variaveis_qee["temperatura_pv"],
        filtro_elemento,
    )
    variaveis_irradiancia = _filtrar_por_elemento(
        variaveis_qee["irradiancia"],
        filtro_elemento,
    )
    dados_potencia_ativa = montar_card_fases(
        df,
        variaveis_potencia_ativa,
    )
    dados_potencia_reativa = montar_card_fases(
        df,
        variaveis_potencia_reativa,
    )
    dados_potencia_fv = montar_card_fases(
        df,
        variaveis_potencia_fv,
    )
    dados_potencia_dc_paineis = montar_card_fases(
        df,
        _filtrar_por_categoria(
            variaveis_potencia_fv,
            "Potência DC dos Painéis",
        ),
    )
    dados_potencia_ativa_ac_inversores = montar_card_fases(
        df,
        _filtrar_por_categoria(
            variaveis_potencia_fv,
            "Potência Ativa AC dos Inversores",
        ),
    )
    dados_potencia_ativa_pvsystem = montar_card_fases(
        df,
        _filtrar_por_categoria(
            variaveis_potencia_fv,
            "Potência Ativa do PVSystem",
        ),
    )
    dados_potencia_reativa_ac_inversores = montar_card_fases(
        df,
        _filtrar_por_categoria(
            variaveis_potencia_reativa,
            "Potência Reativa AC dos Inversores",
        ),
    )
    dados_potencia_reativa_pvsystem = montar_card_fases(
        df,
        _filtrar_por_categoria(
            variaveis_potencia_reativa,
            "Potência Reativa do PVSystem",
        ),
    )
    dados_temperatura_pv = montar_card_fases(
        df,
        variaveis_temperatura_pv,
    )
    dados_irradiancia = montar_card_fases(
        df,
        variaveis_irradiancia,
    )
    dados_potencia_gerador = montar_card_fases(
        df,
        _filtrar_por_elemento(
            variaveis_qee["potencia_gerador"],
            filtro_elemento,
        ),
    )
    dados_fp = montar_card_fases(
        df,
        _filtrar_por_elemento(
            variaveis_qee["fp"],
            filtro_elemento,
        ),
    )
    dados_frequencia = montar_card_fases(
        df,
        _filtrar_por_elemento(
            variaveis_qee["frequencia"],
            filtro_elemento,
        ),
    )
    estado_geracao_fv = montar_estado_geracao_fv_series(
        df,
        variaveis_potencia_fv,
    )

    desequilibrio = calcular_desequilibrio_global(
        dados_tensao
    )
    drp, drc = calcular_drp_drc_global(
        df,
        variaveis_tensao_filtradas,
    )
    indicadores_temporais = calcular_indicadores_temporais(
        df,
        variaveis_tensao_filtradas,
    )

    st.subheader(
        "Barra Monitorada"
    )
    st.caption(
        f"Elemento monitorado: {tensao_referencia}"
    )

    linha1_col1, linha1_col2 = st.columns(2)

    with linha1_col1:
        card_qee(
            "Tensão Média",
            dados_tensao,
            "#f1c40f",
        )

    with linha1_col2:
        card_qee(
            "Desequilíbrio",
            (
                {
                    "Global": {
                        "valor": desequilibrio,
                        "unidade": "%",
                    }
                }
                if desequilibrio is not None
                else {
                    "Sistema": {
                        "valor": None,
                        "unidade": "",
                    }
                }
            ),
            "#9b59b6",
        )

    linha2_col1, linha2_col2 = st.columns(2)

    with linha2_col1:
        card_qee(
            "DRP",
            (
                {
                    "Global": {
                        "valor": drp,
                        "unidade": "%",
                    }
                }
                if drp is not None
                else None
            ),
            "#2ecc71",
        )

    with linha2_col2:
        card_qee(
            "DRC",
            (
                {
                    "Global": {
                        "valor": drc,
                        "unidade": "%",
                    }
                }
                if drc is not None
                else None
            ),
            "#e91e63",
        )

    if indicadores_temporais:
        st.subheader(
            "Indicadores Temporais"
        )

        col_t1, col_t2, col_t3, col_t4 = st.columns(4)

        with col_t1:
            card_qee(
                "Tensão Mínima Trifásica",
                {
                    "Global": {
                        "valor": indicadores_temporais["minimo"],
                        "unidade": "pu",
                    }
                },
                "#2980b9",
            )

        with col_t2:
            card_qee(
                "Tensão Máxima Trifásica",
                {
                    "Global": {
                        "valor": indicadores_temporais["maximo"],
                        "unidade": "pu",
                    }
                },
                "#27ae60",
            )

        with col_t3:
            card_qee(
                "Tensão Média Trifásica",
                {
                    "Global": {
                        "valor": indicadores_temporais["media"],
                        "unidade": "pu",
                    }
                },
                "#f39c12",
            )

        with col_t4:
            card_qee(
                "Desvio Padrão",
                {
                    "Global": {
                        "valor": indicadores_temporais["desvio"],
                        "unidade": "pu",
                    }
                },
                "#8e44ad",
            )

    st.subheader(
        "Indicadores do Elemento"
    )

    col_g1, col_g2, col_g3 = st.columns(3)

    with col_g1:
        if estado_geracao_fv:
            card_qee_texto(
                estado_geracao_fv["titulo"],
                estado_geracao_fv["rows"],
                estado_geracao_fv["cor"],
            )

        card_qee(
            "Potência DC dos Painéis",
            dados_potencia_dc_paineis,
            "#e67e22",
        )
        card_qee(
            "Potência Ativa AC dos Inversores",
            dados_potencia_ativa_ac_inversores,
            "#d35400",
        )

    with col_g2:
        card_qee(
            "Potência Reativa AC dos Inversores",
            dados_potencia_reativa_ac_inversores,
            "#16a085",
        )
        card_qee(
            "Potência Ativa do PVSystem",
            dados_potencia_ativa_pvsystem,
            "#f39c12",
        )
        card_qee(
            "Potência Reativa do PVSystem",
            dados_potencia_reativa_pvsystem,
            "#1abc9c",
        )

    with col_g3:
        card_qee(
            "Temperatura dos Painéis",
            dados_temperatura_pv,
            "#c0392b",
        )
        card_qee(
            "Irradiância dos Painéis",
            dados_irradiancia,
            "#27ae60",
        )
        card_qee(
            "Corrente",
            dados_corrente,
            "#3498db",
        )
        card_qee(
            "Fator de Potência",
            dados_fp,
            "#f39c12",
        )
        card_qee(
            "Frequência",
            dados_frequencia,
            "#8e44ad",
        )

