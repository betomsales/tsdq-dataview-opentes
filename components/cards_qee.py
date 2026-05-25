import streamlit as st
from utils.escalas import auto_scale
from utils.qee import (

    identificar_variaveis_qee,

    montar_card_fases,

    calcular_desequilibrio_global,

    calcular_drp_drc_global,

    calcular_indicadores_temporais
)


def card_qee(
    titulo,
    dados=None,
    cor="#95a5a6"
):
    """
    Renderiza card QEE.
    """

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

            valor = info.get(
                "valor"
            )

            unidade = info.get(
                "unidade"
            )

            if (
                valor is not None
                and unidade in [
                    "W",
                    "Var",
                    "V",
                    "A"
                ]
            ):

                (
                    valor,
                    unidade,
                    _
                ) = auto_scale(
                    valor,
                    unidade
                )

            if valor is None:

                valor_str = (
                    "Não identificado"
                )

            else:

                valor_str = (
                    f"{valor:.4f}"
                )

            linha = (
                f"<div style='display:flex;"
                f"justify-content:space-between;"
                f"margin-bottom:0.3rem;'>"

                f"<span>{fase}</span>"

                f"<span>"
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
        ">
            {titulo}
        </h4>

        {conteudo}

        </div>
        """,
        unsafe_allow_html=True
    )


def render_cards_qee(
    df,
    estrutura,
):
    """
    Renderiza painel QEE.
    """

    variaveis_qee = (
        identificar_variaveis_qee(
            estrutura
        )
    )

    st.subheader(
        "Configuração QEE"
    )

    opcoes_tensao = []

    for variavel in variaveis_qee[
        "tensao"
    ]:

        elemento = variavel[
            "elemento"
        ]

        if elemento not in opcoes_tensao:

            opcoes_tensao.append(
                elemento
            )

    if not opcoes_tensao:

        st.warning(
            "Nenhuma variável de tensão foi identificada para cálculo de QEE."
        )

        st.stop()

    tensao_referencia = st.selectbox(

        "Tensão de referência",

        opcoes_tensao
    )

    variaveis_tensao_filtradas = []

    for variavel in variaveis_qee[
        "tensao"
    ]:

        if (
            variavel["elemento"]
            == tensao_referencia
        ):

            variaveis_tensao_filtradas.append(
                variavel
            )

    dados_tensao = (
        montar_card_fases(
            df,
            variaveis_tensao_filtradas
        )
    )

    dados_corrente = (
        montar_card_fases(
            df,
            variaveis_qee[
                "corrente"
            ]
        )
    )

    dados_potencia_ativa = (
        montar_card_fases(
            df,
            variaveis_qee[
                "potencia_ativa"
            ]
        )
    )

    dados_potencia_reativa = (
        montar_card_fases(
            df,
            variaveis_qee[
                "potencia_reativa"
            ]
        )
    )

    dados_potencia_fv = (
        montar_card_fases(
            df,
            variaveis_qee[
                "potencia_fv"
            ]
        )
    )

    dados_potencia_gerador = (
        montar_card_fases(
            df,
            variaveis_qee[
                "potencia_gerador"
            ]
        )
    )

    dados_fp = (
        montar_card_fases(
            df,
            variaveis_qee[
                "fp"
            ]
        )
    )

    dados_frequencia = (
        montar_card_fases(
            df,
            variaveis_qee[
                "frequencia"
            ]
        )
    )

    desequilibrio = (
        calcular_desequilibrio_global(
            dados_tensao
        )
    )

    drp, drc = (
        calcular_drp_drc_global(

            df,

            variaveis_tensao_filtradas
        )
    )

    indicadores_temporais = (
        calcular_indicadores_temporais(

            df,

            variaveis_tensao_filtradas
        )
    )

    st.subheader(
        "Barra Monitorada"
    )

    st.caption(
        f"Elemento monitorado: "
        f"{tensao_referencia}"
    )

    linha1_col1, linha1_col2 = st.columns(2)

    with linha1_col1:

        card_qee(
            "Tensão",
            dados_tensao,
            "#f1c40f"
        )

    with linha1_col2:

        card_qee(

            "Desequilíbrio (%) - Simplificado",

            (
                {
                    "Global": {

                        "valor": desequilibrio,

                        "unidade": "%"
                    }
                }

                if desequilibrio is not None

                else {
                    "Sistema": {

                        "valor": None,

                        "unidade": ""
                    }
                }
            ),

            "#9b59b6"
        )

    linha2_col1, linha2_col2 = st.columns(2)

    with linha2_col1:

        card_qee(

            "DRP",

            (
                {
                    "Global": {

                        "valor": drp,

                        "unidade": "%"
                    }
                }

                if drp is not None

                else None
            ),

            "#2ecc71"
        )

    with linha2_col2:

        card_qee(

            "DRC",

            (
                {
                    "Global": {

                        "valor": drc,

                        "unidade": "%"
                    }
                }

                if drc is not None

                else None
            ),

            "#e91e63"
        )

    if indicadores_temporais:

        st.subheader(
            "Indicadores Temporais"
        )

        col_t1, col_t2, col_t3, col_t4 = st.columns(4)

        with col_t1:

            card_qee(

                "Tensão Mínima",

                {
                    "Global": {

                        "valor": indicadores_temporais[
                            "minimo"
                        ],

                        "unidade": "pu"
                    }
                },

                "#2980b9"
            )

        with col_t2:

            card_qee(

                "Tensão Máxima",

                {
                    "Global": {

                        "valor": indicadores_temporais[
                            "maximo"
                        ],

                        "unidade": "pu"
                    }
                },

                "#27ae60"
            )

        with col_t3:

            card_qee(

                "Tensão Média",

                {
                    "Global": {

                        "valor": indicadores_temporais[
                            "media"
                        ],

                        "unidade": "pu"
                    }
                },

                "#f39c12"
            )

        with col_t4:

            card_qee(

                "Desvio Padrão",

                {
                    "Global": {

                        "valor": indicadores_temporais[
                            "desvio"
                        ],

                        "unidade": "pu"
                    }
                },

                "#8e44ad"
            )

    st.subheader(
        "Indicadores Globais do Sistema"
    )

    col_g1, col_g2, col_g3 = st.columns(3)

    with col_g1:

        card_qee(
            "Potência Ativa",
            dados_potencia_ativa,
            "#e67e22"
        )

        card_qee(
            "Potência Reativa",
            dados_potencia_reativa,
            "#16a085"
        )

    with col_g2:

        card_qee(
            "Potência FV",
            dados_potencia_fv,
            "#27ae60"
        )

        card_qee(
            "Potência do Gerador",
            dados_potencia_gerador,
            "#c0392b"
        )

    with col_g3:

        card_qee(
            "Fator de Potência",
            dados_fp,
            "#f39c12"
        )

        card_qee(
            "Frequência",
            dados_frequencia,
            "#8e44ad"
        )