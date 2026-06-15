from streamlit_agraph import (
    agraph,
    Node,
    Edge,
    Config,
)

from .topology_styles import (
    get_node_style,
)


def render_graph(
    graph,
    key=None,
):

    nodes = []

    edges = []

    for node in graph.nodes.values():

        style = get_node_style(node)

        nodes.append(
            Node(
                id=node.id,
                label=node.label,
                size=10,

                color={
                    "background": style["background"],
                    "border": style["border"],
                },

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
        key=key,
    )