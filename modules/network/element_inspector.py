import streamlit as st


def get_neighbors(
    node_id,
    graph,
):

    neighbors = []

    for edge in graph.edges.values():

        if edge.source == node_id:

            neighbors.append(
                edge.target
            )

        elif edge.target == node_id:

            neighbors.append(
                edge.source
            )

    return sorted(
        neighbors
    )


def render_node_details(
    node_id,
    graph,
):

    st.subheader(
        "Inspetor"
    )

    if not node_id:

        st.info(
            "Selecione um barramento."
        )

        return

    node = graph.nodes.get(
        node_id
    )

    if node is None:

        st.warning(
            "Barramento não encontrado."
        )

        return

    st.markdown(
        f"### {node.label}"
    )

    st.write(
        f"Tipo: {node.node_type}"
    )

    neighbors = get_neighbors(
        node_id,
        graph,
    )

    st.write(
        f"Conexões: {len(neighbors)}"
    )

    st.markdown(
        "#### Conectado a"
    )

    for neighbor in neighbors:

        st.write(
            f"• {neighbor}"
        )