from streamlit_agraph import (
    agraph,
    Node,
    Edge,
    Config,
)

from .topology_styles import (
    get_node_style,
)


def render_graph(graph):

    nodes = []

    edges = []

    for node in graph.nodes.values():

        style = get_node_style(node)

        nodes.append(
            Node(
                id=node.id,
                label=node.label,
                size=20,
                color=style["background"],
            )
        )

    for edge in graph.edges.values():

        edges.append(
            Edge(
                source=edge.source,
                target=edge.target,
            )
        )

    config = Config(
        width="100%",
        height=700,
        directed=False,
        physics=True,
        hierarchical=False,
    )

    return agraph(
        nodes=nodes,
        edges=edges,
        config=config,
    )