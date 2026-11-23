from streamlit_agraph import (
    agraph,
    Node,
    Edge,
    Config,
)
import pandas as pd
import plotly.express as px
import streamlit as st

from components.identidade import style_plotly_figure
from .topology_styles import (
    get_node_style,
    get_voltage_color,
)
from .d3_renderer import (
    render_graph_d3,
)
from .equipment_view import connected_equipment, equipment_icon
from .phase_display import phase_configuration, phase_details


def render_graph(
    graph,
    *, show_pv=True, show_load=True,
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
                    else f"{node.label}: sem medição"
                ) + "\nConfiguração: " + phase_configuration(node) + "\n" + "\n".join(
                    f"{phase}: {text}" for phase, text in phase_details(node)
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
                dashes=edge.metadata.get("open") is True,
                title=f"{edge.id}" + (
                    f" - {'Aberto' if edge.metadata['open'] else 'Fechado'}"
                    if "open" in edge.metadata else ""
                ),
            )
        )

    for item in connected_equipment(graph, show_pv=show_pv, show_load=show_load).values():
        nodes.append(Node(
            id=item.id, label=item.label, size=18, shape="image", image=equipment_icon(item),
            title=f"{item.label} - Barra {graph.nodes[item.bus].label}",
        ))
        edges.append(Edge(
            source=item.bus, target=item.id, width=1.5, dashes=True, color="#8796a5",
            title="Conexão do equipamento à barra",
        ))

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

    st.subheader(f"Série temporal do nó {node_id}")
    st.caption(
        "As curvas usam diretamente os registros do arquivo de entrada. "
        "Valores ausentes não são interpolados nem substituídos."
    )
    grouped = {}

    for item in series:
        rotulo_variavel = item.get(
            "rotulo_variavel",
            item["variavel"],
        )
        separate_variable = rotulo_variavel if item["unidade"] is None else None
        key = (item["grupo"], item["unidade"], separate_variable)
        grouped.setdefault(key, []).append(item)

    for (group, unit, separate_variable), items in grouped.items():
        frames = []

        for item in items:
            frame = pd.DataFrame({
                "Tempo": item["tempo"],
                "Valor": item["valores"],
                "Variável": item.get(
                    "rotulo_variavel",
                    item["variavel"],
                ),
                "Coluna original": item["coluna_original"],
            }).dropna(subset=["Tempo", "Valor"])

            if not frame.empty:
                frames.append(frame)

        if not frames:
            continue

        plot_data = pd.concat(frames, ignore_index=True)
        axis_label = f"Valor [{unit}]" if unit else "Valor [unidade não informada]"
        title = group

        if separate_variable:
            title = f"{group} - {separate_variable}"

        figure = px.line(
            plot_data,
            x="Tempo",
            y="Valor",
            color="Variável",
            hover_data=["Coluna original"],
            title=title,
            labels={"Valor": axis_label},
        )
        figure.update_layout(hovermode="x unified")
        st.plotly_chart(style_plotly_figure(figure), theme=None, use_container_width=True)
