import streamlit as st


NODE_INFO = {

    "refbus": {
        "titulo": "Subestação / Fonte",
        "descricao":
            "Representa o ponto de suprimento de energia do circuito."
    },

    "load": {
        "titulo": "Carga",
        "descricao":
            "Barramento associado ao consumo de energia elétrica."
    },

    "pv": {
        "titulo": "Geração Distribuída",
        "descricao":
            "Barramento com geração de energia associada."
    },

    "regulator_bus": {
        "titulo": "Barramento Regulado",
        "descricao":
            "Associado a um regulador de tensão da rede."
    },

    "virtual_bus": {
        "titulo": "Barramento Virtual",
        "descricao":
            "Criado pelo modelo para representar um ponto intermediário da rede."
    },

    "transformer_bus": {
        "titulo": "Conectado a Transformador",
        "descricao":
            "Barramento conectado a transformadores."
    },

    "bus": {
        "titulo": "Barramento Comum",
        "descricao":
            "Barramento utilizado para interligação dos elementos da rede."
    },
}


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

    node_info = NODE_INFO.get(
        node.node_type,
        NODE_INFO["bus"]
    )

    st.markdown(
        f"### {node.label}"
    )

    st.markdown(
        f"**Classe:** {node_info['titulo']}"
    )

    st.caption(
        node_info["descricao"]
    )

    neighbors = get_neighbors(
        node_id,
        graph,
    )

    st.write(
        f"Conexões: {len(neighbors)}"
    )

    if neighbors:

        st.markdown(
            "#### Conectado a"
        )

        for neighbor in neighbors:

            st.write(
                f"• {neighbor}"
            )