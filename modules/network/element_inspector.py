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


def _render_measurements(measurements):
    if not measurements:
        st.caption("Sem medicoes associadas neste instante.")
        return

    groups = {}

    for measurement in measurements:
        groups.setdefault(measurement["grupo"], []).append(measurement)

    for group, items in groups.items():
        st.markdown(f"**{group}**")

        for item in items:
            unit = f" {item['unidade']}" if item.get("unidade") else ""
            st.write(f"{item['variavel']}: {item['valor']:.6g}{unit}")


def render_edge_details(edge_id, graph):
    edge = graph.edges.get(edge_id)

    if edge is None:
        return

    st.markdown(f"### {edge.id}")
    st.caption(f"{edge.source} -> {edge.target} | {edge.edge_type}")
    _render_measurements(edge.metadata.get("measurements", []))


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

    st.markdown(
        "#### Tensao"
    )

    voltage_phases = node.metadata.get(
        "voltage_phases_pu",
        {}
    )

    if voltage_phases:

        for phase in sorted(voltage_phases):

            st.metric(
                phase,
                f"{voltage_phases[phase]:.6f} pu"
            )

        st.caption(
            f"Media das fases: {node.voltage_pu:.6f} pu"
        )

    else:

        st.caption(
            "Sem medicao de tensao para este no."
        )

    st.markdown("#### Outras medicoes")
    _render_measurements(
        node.metadata.get("measurements", [])
    )

    if neighbors:

        st.markdown(
            "#### Conectado a"
        )

        for neighbor in neighbors:

            st.write(
                f"• {neighbor}"
            )
