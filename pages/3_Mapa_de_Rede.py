import streamlit as st

from modules.network.dss_loader import (
    compile_circuit,
)

from modules.network.topology_builder import (
    build_graph,
)

from modules.network.topology_renderer import (
    render_graph,
    render_node_time_series,
)
from modules.network.element_inspector import (
    render_edge_details,
    render_node_details,
)
from modules.network.error_handler import (
    friendly_dss_error,
)
from modules.network.cosim_loader import (
    apply_measurement_snapshot,
    get_monitored_node_ids,
    load_cosim_results,
    load_topology_json,
    prepare_node_time_series,
)
from io import BytesIO


st.set_page_config(
    page_title="Mapa de Rede",
    layout="wide",
)

st.title(
    "Mapa de Rede"
)

input_mode = st.radio(
    "Fonte da rede",
    ["Resultados da co-simulacao", "Circuito OpenDSS (.zip)"],
    horizontal=True,
)

graph = None
master_file = None
warning_message = None
snapshot_caption = None
measured_nodes = 0
measurement_stats = None
results_df = None
measurement_columns = None
time_values = None

if input_mode == "Resultados da co-simulacao":

    topology_file = st.file_uploader(
        "Topologia da rede (.json)",
        type=["json"],
        key="network_topology_json",
    )

    results_file = st.file_uploader(
        "Resultados temporais da co-simulacao (.csv)",
        type=["csv"],
        key="network_results_csv",
    )

    if topology_file is not None and results_file is not None:

        try:

            graph = load_topology_json(
                topology_file
            )

            (
                results_df,
                measurement_columns,
                time_column,
                time_values,
            ) = load_cosim_results(
                results_file
            )

            selected_row = st.slider(
                "Instante da simulacao",
                min_value=0,
                max_value=len(results_df) - 1,
                value=0,
            )

            selected_time = time_values.iloc[selected_row]

            if selected_time is not None and not str(selected_time) == "NaT":
                snapshot_caption = selected_time.strftime("%d/%m/%Y %H:%M:%S")
            else:
                snapshot_caption = str(results_df.iloc[selected_row][time_column])

            measurement_stats = apply_measurement_snapshot(
                graph,
                results_df,
                measurement_columns,
                selected_row,
            )
            measured_nodes = measurement_stats["measured_nodes"]

        except Exception as e:

            st.error(str(e))

elif input_mode == "Circuito OpenDSS (.zip)":

    zip_file = st.file_uploader(
        "Selecione um circuito OpenDSS (.zip)",
        type=["zip"],
    )

    if zip_file is not None:

        st.session_state["network_zip"] = (
            zip_file.getvalue()
        )

    if zip_file or "network_zip" in st.session_state:

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

        except Exception as e:

            st.error(
                friendly_dss_error(
                    str(e)
                )
            )

if graph is not None:

        st.write(
            "Barramentos encontrados:",
            graph.total_nodes
        )

        if snapshot_caption:

            st.success(
                f"Topologia e resultados carregados - instante {snapshot_caption}"
            )

            st.caption(
                f"Nos com tensao: {measured_nodes} de {graph.total_nodes}. "
                "Verde: adequado; amarelo: precario; vermelho: critico; "
                "cinza: sem medicao."
            )

            st.caption(
                f"Colunas associadas: {measurement_stats['associated_columns']}; "
                f"arestas com dados: {measurement_stats['measured_edges']}; "
                f"nao associadas: {measurement_stats['unassociated_columns']}."
            )

        else:

            st.success(
                "Circuito carregado com sucesso"
            )

        if warning_message:

            st.warning(
                warning_message
            )

        if master_file:

            st.caption(
                f"Arquivo principal detectado: {master_file}"
            )

        col_graph, col_info = st.columns(
            [4, 1]
        )

        with col_graph:

            selected_node = render_graph(
                graph
            )

        with col_info:

            render_node_details(
                selected_node,
                graph,
            )

            measured_edge_ids = [
                edge.id
                for edge in graph.edges.values()
                if edge.metadata.get("measurements")
            ]

            if measured_edge_ids:

                st.divider()
                selected_edge = st.selectbox(
                    "Elemento de linha",
                    measured_edge_ids,
                )
                render_edge_details(
                    selected_edge,
                    graph,
                )

            unassociated = graph.metadata.get(
                "unassociated_measurements",
                [],
            )

            if unassociated:

                with st.expander("Medicoes nao associadas"):
                    st.json(unassociated)

        if (
            results_df is not None
            and measurement_columns is not None
            and time_values is not None
        ):

            monitored_node_ids = get_monitored_node_ids(
                graph,
                measurement_columns,
            )

            if monitored_node_ids:

                st.divider()
                temporal_node_id = st.selectbox(
                    "No monitorado para a serie temporal",
                    monitored_node_ids,
                    key="temporal_node_id",
                )
                node_series = prepare_node_time_series(
                    graph,
                    results_df,
                    measurement_columns,
                    time_values,
                    temporal_node_id,
                )
                render_node_time_series(
                    temporal_node_id,
                    node_series,
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
