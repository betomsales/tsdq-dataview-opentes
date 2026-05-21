import streamlit as st
import plotly.express as px

from utils.prodist import (
    obter_limites_prodist
)


def render_grafico_individual(
    df_plot,
    coluna_real,
    label_grafico,
    variavel_info
):
    """
    Renderiza gráfico individual.
    """

    fig = px.line(
        df_plot,
        x="Tempo",
        y="Valor",
        title=coluna_real
    )

    if (
        variavel_info["tipo"] == "Tensão"
        and
        variavel_info.get(
            "unidade_detectada"
        ) == "pu"
    ):

        limites = obter_limites_prodist()

        fig.add_hline(

            y=limites["adequado_max"],

            line_dash="dash",

            line_color="red",

            annotation_text="Limite Sup. PRODIST"
        )

        fig.add_hline(

            y=limites["adequado_min"],

            line_dash="dash",

            line_color="orange",

            annotation_text="Limite Inf. PRODIST"
        )

        fig.add_hline(

            y=limites["critico_min"],

            line_dash="dot",

            line_color="darkred",

            annotation_text="Limite Crítico PRODIST"
        )

    fig.update_layout(

        xaxis_title="Tempo",

        yaxis_title=label_grafico,

        hovermode="x unified"
    )

    st.subheader(
        "Série Temporal"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def render_grafico_multiserie(
    df_multiserie,
    label_grafico,
    variavel_info
):
    """
    Renderiza gráfico multivariável.
    """

    colunas_plot = [

        coluna

        for coluna in df_multiserie.columns

        if coluna != "Tempo"
    ]

    fig_multiserie = px.line(
        df_multiserie,
        x="Tempo",
        y=colunas_plot
    )

    if (
        variavel_info["tipo"] == "Tensão"
        and
        variavel_info.get(
            "unidade_detectada"
        ) == "pu"
    ):

        limites = obter_limites_prodist()

        fig_multiserie.add_hline(

            y=limites["adequado_max"],

            line_dash="dash",

            line_color="red",

            annotation_text="Limite Sup. PRODIST"
        )

        fig_multiserie.add_hline(

            y=limites["adequado_min"],

            line_dash="dash",

            line_color="orange",

            annotation_text="Limite Inf. PRODIST"
        )

        fig_multiserie.add_hline(

            y=limites["critico_min"],

            line_dash="dot",

            line_color="darkred",

            annotation_text="Limite Crítico PRODIST"
        )

    fig_multiserie.update_layout(

        title="Visualização conjunta",

        xaxis_title="Tempo",

        yaxis_title=label_grafico,

        hovermode="x unified"
    )

    st.subheader(
        "Visualização conjunta"
    )

    st.plotly_chart(
        fig_multiserie,
        use_container_width=True
    )