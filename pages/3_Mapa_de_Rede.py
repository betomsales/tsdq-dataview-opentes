import streamlit as st

from modules.network.dss_loader import (
    compile_circuit,
)

from modules.network.topology_builder import (
    build_graph,
)

from modules.network.topology_renderer import (
    render_graph,
)


st.set_page_config(
    page_title="Mapa de Rede",
    layout="wide",
)

st.title(
    "Mapa de Rede"
)

zip_file = st.file_uploader(
    "Selecione um circuito OpenDSS (.zip)",
    type=["zip"],
)

if zip_file:

    try:

        dss = compile_circuit(
            zip_file
        )

        graph = build_graph(
            dss
        )

        st.success(
            "Circuito carregado com sucesso"
        )

        render_graph(
            graph
        )

        with st.expander(
            "Diagnóstico da Rede",
            expanded=False,
        ):

            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    "Barramentos",
                    graph.total_nodes,
                )

            with col2:

                st.metric(
                    "Conexões",
                    graph.total_edges,
                )

            st.divider()

            tab1, tab2 = st.tabs(
                [
                    "Barramentos",
                    "Conexões",
                ]
            )

            with tab1:

                st.write(
                    sorted(
                        graph.nodes.keys()
                    )
                )

            with tab2:

                for edge in graph.edges.values():

                    st.write(
                        f"{edge.source} → {edge.target}"
                    )
    except Exception as e:

        st.error(
            str(e)
        )