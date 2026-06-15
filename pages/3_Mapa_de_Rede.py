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
from modules.network.element_inspector import (
    render_node_details,
)
from modules.network.error_handler import (
    friendly_dss_error,
)
from io import BytesIO


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

if zip_file is not None:

    st.session_state["network_zip"] = (
        zip_file.getvalue()
    )

if (
    zip_file
    or
    "network_zip" in st.session_state
):

    try:

        uploaded_zip = BytesIO(
            st.session_state["network_zip"]
        )

        result = compile_circuit(
            uploaded_zip
        )

        dss = result["dss"]

        master_file = result["master_file"]

        warning_message = result["warning"]

        graph = build_graph(
            dss
        )

        st.write(
            "Barramentos encontrados:",
            graph.total_nodes
        )

        st.success(
            "Circuito carregado com sucesso"
        )

        if warning_message:

            st.warning(
                warning_message
            )

        st.caption(
            f"Arquivo principal detectado: {master_file}"
        )

        tab_simple, tab_complete = st.tabs(
            [
                "Rede Simplificada",
                "Rede Completa",
            ]
        )

        with tab_simple:

            # col_graph, col_info = st.columns(
            #     [4, 1]
            # )

            # with col_graph:

            #     selected_node = render_graph(
            #         graph,
            #         key="simple_graph",
            #     )
            
            # with col_info:

            #     render_node_details(
            #         selected_node,
            #         graph,
            #     )

            st.info(
                "Rede simplificada em desenvolvimento."
            )

        with tab_complete:

            col_graph, col_info = st.columns(
                [4, 1]
            )

            with col_graph:

                # selected_node = render_graph(
                #     graph,
                #     key="complete_graph",
                # )
                
                selected_node = render_graph(
                    graph
                )

            with col_info:

                render_node_details(
                    selected_node,
                    graph,
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

            tab1, tab2, tab3 = st.tabs(
                [
                    "Barramentos",
                    "Conexões",
                    "Tipos",
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

            with tab3:

                for node in graph.nodes.values():

                    st.write(
                        f"{node.label} → {node.node_type}"
                    )
    except Exception as e:

        st.error(
            friendly_dss_error(
                str(e)
            )
        )