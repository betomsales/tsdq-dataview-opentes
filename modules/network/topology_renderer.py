from streamlit_agraph import (
    agraph,
    Node,
    Edge,
    Config,
)
import pandas as pd
import plotly.express as px
import streamlit as st

from .topology_styles import (
    get_node_style,
)


def get_voltage_color(voltage_pu):
    """Cor do no segundo as faixas de tensao usadas no painel QEE."""

    if voltage_pu is None:
        return None

    if 0.93 <= voltage_pu <= 1.05:
        return "#2ECC71"

    if 0.90 <= voltage_pu <= 1.08:
        return "#F1C40F"

    return "#E74C3C"


def render_graph(
    graph,
):

    nodes = []

    edges = []

    for node in graph.nodes.values():

        style = get_node_style(node)

        voltage_color = get_voltage_color(
            node.voltage_pu
        )

        label = node.label

        if node.voltage_pu is not None:
            label += f"\n{node.voltage_pu:.4f} pu"

        nodes.append(
            Node(
                id=node.id,
                label=label,
                size=10,

                color={
                    "background": voltage_color or style["background"],
                    "border": style["border"],
                },

                title=(
                    f"{node.label}: {node.voltage_pu:.6f} pu"
                    if node.voltage_pu is not None
                    else f"{node.label}: sem medicao"
                ),

                borderWidth=6,
            )
        )

    for edge in graph.edges.values():

        edges.append(
            Edge(
                source=edge.source,
                target=edge.target,
                width=4,
                color="#B8B8B8",
            )
        )

    config = Config(
        width="100%",
        height=600,
        directed=False,
        physics=True,
        hierarchical=False,
    )
    return agraph(
        nodes=nodes,
        edges=edges,
        config=config,
    )


def render_node_time_series(node_id, series):
    """Plota apenas amostras existentes nas colunas originais do CSV."""

    st.subheader(f"Serie temporal do no {node_id}")
    st.caption(
        "As curvas usam diretamente os registros do arquivo de entrada. "
        "Valores ausentes nao sao interpolados nem substituidos."
    )
    grouped = {}

    for item in series:
        separate_variable = item["variavel"] if item["unidade"] is None else None
        key = (item["grupo"], item["unidade"], separate_variable)
        grouped.setdefault(key, []).append(item)

    for (group, unit, separate_variable), items in grouped.items():
        frames = []

        for item in items:
            frame = pd.DataFrame({
                "Tempo": item["tempo"],
                "Valor": item["valores"],
                "Variavel": item["variavel"],
                "Coluna original": item["coluna_original"],
            }).dropna(subset=["Tempo", "Valor"])

            if not frame.empty:
                frames.append(frame)

        if not frames:
            continue

        plot_data = pd.concat(frames, ignore_index=True)
        axis_label = f"Valor [{unit}]" if unit else "Valor [unidade nao informada]"
        title = group

        if separate_variable:
            title = f"{group} - {separate_variable}"

        figure = px.line(
            plot_data,
            x="Tempo",
            y="Valor",
            color="Variavel",
            hover_data=["Coluna original"],
            title=title,
            labels={"Valor": axis_label},
        )
        figure.update_layout(hovermode="x unified")
        st.plotly_chart(figure, use_container_width=True)
