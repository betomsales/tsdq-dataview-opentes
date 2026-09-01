import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.comunicacao import classificar_agente


def render_cards_comunicacao(kpis):
    """
    Renderiza indicadores principais da comunicação.
    """

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Pacotes enviados",
            f"{kpis['pacotes_enviados']:.0f}"
        )

    with col2:
        st.metric(
            "Pacotes recebidos",
            f"{kpis['pacotes_recebidos']:.0f}"
        )

    with col3:
        st.metric(
            "Pacotes dropados",
            f"{kpis['pacotes_dropados']:.0f}"
        )

    with col4:
        st.metric(
            "Taxa de drop",
            f"{kpis['taxa_drop']:.1f}%"
        )

    col5, col6, col7, col8 = st.columns(4)

    with col5:
        st.metric(
            "Mensagens",
            f"{kpis['mensagens']:.0f}"
        )

    with col6:
        st.metric(
            "Agentes",
            f"{kpis['agentes']:.0f}"
        )

    with col7:
        st.metric(
            "Latência média",
            f"{kpis['latencia_media']:.4f} s"
        )

    with col8:
        st.metric(
            "Jitter médio",
            f"{kpis['jitter_medio']:.4f} s"
        )


def _preparar_classes(df_expandido):
    """
    Adiciona classificação visual dos agentes.
    """

    df_plot = df_expandido.copy()

    df_plot["Classe"] = (
        df_plot["Agente"]
        .apply(classificar_agente)
    )

    return df_plot


def render_grafico_latencia(df_expandido):
    """
    Renderiza latência por mensagem.
    """

    df_plot = _preparar_classes(
        df_expandido
    )

    fig = px.scatter(
        df_plot,
        x="Tempo",
        y="Latencia",
        color="Classe",
        symbol="Classe",
        hover_data=[
            "Agente",
            "Tamanho do pacote",
            "Jitter"
        ],
        labels={
            "Latencia": "Latência (s)"
        },
        title="Latência temporal por pacote"
    )

    resumo = (
        df_expandido
        .groupby("Tempo", as_index=False)
        .agg(
            Latencia_media=("Latencia", "mean"),
            Jitter_medio=("Jitter", "mean")
        )
    )

    if not resumo.empty:

        fig.add_trace(
            go.Scatter(
                x=resumo["Tempo"],
                y=resumo["Latencia_media"],
                mode="lines",
                name="Média",
                line={
                    "color": "gray",
                    "dash": "dash"
                }
            )
        )

    fig.update_layout(
        hovermode="closest"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def render_grafico_jitter(df_expandido):
    """
    Renderiza jitter por pacote.
    """

    df_plot = _preparar_classes(
        df_expandido
    )

    fig = px.scatter(
        df_plot,
        x="Tempo",
        y="Jitter",
        color="Classe",
        hover_data=[
            "Agente",
            "Latencia"
        ],
        labels={
            "Jitter": "Jitter (s)"
        },
        title="Jitter distribuído por pacote"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def render_grafico_payload(df_expandido):
    """
    Renderiza tamanho dos pacotes.
    """

    df_plot = _preparar_classes(
        df_expandido
    )

    fig = px.scatter(
        df_plot,
        x="Tempo",
        y="Tamanho do pacote",
        color="Classe",
        symbol="Classe",
        hover_data=[
            "Agente",
            "Latencia",
            "Jitter"
        ],
        labels={
            "Tamanho do pacote": "Tamanho (bytes)"
        },
        title="Tamanho das mensagens FIPA-ACL"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def render_grafico_confiabilidade(kpis):
    """
    Renderiza distribuição de pacotes.
    """

    labels = [
        "Entregues",
        "Dropados",
        "Em trânsito"
    ]

    valores = [
        kpis["pacotes_recebidos"],
        kpis["pacotes_dropados"],
        kpis["pacotes_em_transito"]
    ]

    dados = [
        (label, valor)
        for label, valor in zip(labels, valores)
        if valor > 0
    ]

    if not dados:

        st.info(
            "Não há dados suficientes para calcular a confiabilidade."
        )

        return

    fig = go.Figure(
        data=[
            go.Pie(
                labels=[
                    item[0]
                    for item in dados
                ],
                values=[
                    item[1]
                    for item in dados
                ],
                hole=0.35
            )
        ]
    )

    fig.update_layout(
        title="Confiabilidade global da rede"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


def render_tabela_mensagens(df_expandido):
    """
    Renderiza tabela de mensagens desempacotadas.
    """

    st.dataframe(
        df_expandido,
        use_container_width=True
    )
