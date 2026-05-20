import streamlit as st

from utils.qee import (

    identificar_variaveis_qee,

    montar_card_fases,

    calcular_desequilibrio_global
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
    estrutura
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

    st.subheader(
        "Grandezas"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        card_qee(
            "Tensão",
            dados_tensao,
            "#f1c40f"
        )

        card_qee(
            "DRP",
            None
        )

        card_qee(
            "Flutuação",
            None
        )

    with col2:

        card_qee(
            "Corrente",
            dados_corrente,
            "#3498db"
        )

        card_qee(
            "DRC",
            None
        )

        card_qee(

            "Desequilíbrio",

            (
                {
                    "Global": {

                        "valor": desequilibrio,

                        "unidade": "%"
                    }
                }

                if desequilibrio is not None

                else None
            ),

            "#9b59b6"
        )

    with col3:

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

        card_qee(
            "Potência FV",
            dados_potencia_fv,
            "#27ae60"
        )

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