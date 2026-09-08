import hashlib
import json

import streamlit as st

from modules.network.dss_loader import (
    compile_circuit,
)

from modules.network.topology_builder import (
    build_graph,
)

from modules.network.topology_renderer import (
    render_graph,
    render_graph_d3,
    render_node_time_series,
)
from modules.network.element_inspector import (
    render_edge_details,
    render_node_details,
)
from components.analise_eletrica_rede import (
    montar_estrutura_analise_rede,
    preparar_dataframe_analise,
    render_analise_eletrica_contexto,
)
from components.cards_qee import (
    render_cards_qee,
)
from modules.network.error_handler import (
    friendly_dss_error,
)
from modules.network.cosim_loader import (
    apply_measurement_snapshot,
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


def calcular_sha256_upload(uploaded_file):
    uploaded_file.seek(0)
    file_hash = hashlib.sha256(
        uploaded_file.read()
    ).hexdigest().upper()
    uploaded_file.seek(0)

    return file_hash


def carregar_json_upload(uploaded_file):
    uploaded_file.seek(0)
    raw = uploaded_file.read()
    uploaded_file.seek(0)

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")

    return json.loads(raw)


def obter_hash_vinculado(topology_data):
    metadata = topology_data.get(
        "metadata",
        {},
    ) or {}

    hash_value = metadata.get(
        "results_sha256",
        "",
    )

    return str(hash_value).strip().upper()


def render_validacao_vinculo(
    topology_data,
    results_hash,
):
    expected_hash = obter_hash_vinculado(
        topology_data
    )

    if not expected_hash:
        st.error(
            "Topologia sem vínculo SHA-256 com o arquivo CSV. "
            "Solicite à equipe da co-simulação um JSON gerado com "
            "metadata.results_sha256."
        )

        return False

    if expected_hash == results_hash:
        st.success(
            "Vínculo validado: a topologia corresponde ao CSV carregado."
        )
        return True

    st.error(
        "Vínculo inválido: o hash do CSV carregado não corresponde ao "
        "hash registrado na topologia."
    )
    st.caption(
        f"Hash esperado: {expected_hash}"
    )
    st.caption(
        f"Hash do CSV carregado: {results_hash}"
    )

    return False


def normalizar_indice_instante(value, max_value):
    if max_value is None or max_value < 0:
        return 0

    try:
        index = int(value)
    except (TypeError, ValueError):
        index = 0

    return min(
        max(index, 0),
        max_value,
    )


def extrair_evento_d3(evento):
    if not isinstance(evento, dict):
        return evento, None, None

    node_id = evento.get("id") or evento.get("selectedNodeId")
    frame_index = evento.get("frameIndex")
    positions = evento.get("positions")
    graph_id = evento.get("graphId")
    layout_state = None

    if graph_id and isinstance(positions, dict):
        layout_state = {
            "graphId": graph_id,
            "positions": positions,
        }

    return node_id, frame_index, layout_state


input_mode = st.radio(
    "Fonte da rede",
    ["Resultados da co-simulação", "Circuito OpenDSS (.zip)"],
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
selected_row = None
analysis_df = None
analysis_structure = None

if input_mode == "Resultados da co-simulação":

    topology_file = st.file_uploader(
        "Topologia da rede (.json)",
        type=["json"],
        key="network_topology_json",
    )

    results_file = st.file_uploader(
        "Resultados temporais da co-simulação (.csv)",
        type=["csv"],
        key="network_results_csv",
    )

    if topology_file is not None and results_file is not None:

        try:

            topology_data = carregar_json_upload(
                topology_file
            )

            results_hash = calcular_sha256_upload(
                results_file
            )

            vinculo_valido = render_validacao_vinculo(
                topology_data,
                results_hash,
            )

            if vinculo_valido:

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

                max_row_index = len(results_df) - 1
                stored_row = normalizar_indice_instante(
                    st.session_state.get("network_selected_row", 0),
                    max_row_index,
                )
                slider_key = "network_selected_row_slider"
                sincronizar_slider = st.session_state.pop(
                    "network_sync_selected_row_slider",
                    False,
                )
                slider_value = st.session_state.get(
                    slider_key
                )

                try:
                    slider_value = int(slider_value)
                except (TypeError, ValueError):
                    slider_value = None

                if (
                    sincronizar_slider
                    or slider_value is None
                    or slider_value < 0
                    or slider_value > max_row_index
                ):
                    st.session_state[slider_key] = stored_row

                selected_row = st.slider(
                    "Instante da simulação",
                    min_value=0,
                    max_value=max_row_index,
                    key=slider_key,
                )
                selected_row = normalizar_indice_instante(
                    selected_row,
                    max_row_index,
                )
                st.session_state["network_selected_row"] = selected_row

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
                analysis_df = preparar_dataframe_analise(
                    results_df,
                    time_values,
                )
                analysis_structure = montar_estrutura_analise_rede(
                    graph,
                    measurement_columns,
                )

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
                f"Nós com tensão: {measured_nodes} de {graph.total_nodes}. "
                "Verde: adequado; amarelo: precário; vermelho: crítico; "
                "cinza: sem medição."
            )

            st.caption(
                f"Colunas associadas: {measurement_stats['associated_columns']}; "
                f"arestas com dados: {measurement_stats['measured_edges']}; "
                f"não associadas: {measurement_stats['unassociated_columns']}."
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

        highlighted_node = st.session_state.get(
            "network_selected_node"
        )

        if highlighted_node not in graph.nodes:
            highlighted_node = None

        graph_renderer = st.radio(
            "Visualização do grafo",
            ["D3/JavaScript", "Agraph"],
            horizontal=True,
            key="network_graph_renderer",
        )

        if graph_renderer == "D3/JavaScript":
            clicked_node = render_graph_d3(
                graph,
                selected_node_id=highlighted_node,
                results_df=results_df,
                measurement_columns=measurement_columns,
                time_values=time_values,
                initial_frame_index=selected_row,
                layout_state=st.session_state.get(
                    "network_d3_layout_state"
                ),
            )

        else:
            clicked_node = render_graph(
                graph
            )

        st.divider()

        (
            clicked_node,
            clicked_frame_index,
            layout_state,
        ) = extrair_evento_d3(
            clicked_node
        )
        should_rerun = False

        if layout_state:
            st.session_state["network_d3_layout_state"] = layout_state

        if clicked_frame_index is not None and results_df is not None:
            frame_index = normalizar_indice_instante(
                clicked_frame_index,
                len(results_df) - 1,
            )

            if frame_index != st.session_state.get("network_selected_row"):
                st.session_state["network_selected_row"] = frame_index
                st.session_state["network_sync_selected_row_slider"] = True
                should_rerun = True

        if clicked_node in graph.nodes:
            st.session_state["network_selected_node"] = clicked_node

        if should_rerun:
            st.rerun()

        node_options = sorted(
            graph.nodes.keys()
        )
        current_node = st.session_state.get(
            "network_selected_node"
        )

        if current_node not in graph.nodes:
            current_node = None

        selection_options = [
            None,
            *node_options,
        ]
        selection_index = selection_options.index(
            current_node
        )

        def format_node_option(node_id):

            if node_id is None:
                return "Selecione um barramento"

            node = graph.nodes[node_id]

            if node.label == node_id:
                return node_id

            return f"{node.label} ({node_id})"

        selected_node = st.selectbox(
            "Barramento analisado",
            selection_options,
            index=selection_index,
            format_func=format_node_option,
        )

        if selected_node:
            st.session_state["network_selected_node"] = selected_node

            aba_inspetor, aba_temporal, aba_qee = st.tabs(
                [
                    "Inspetor",
                    "Análise Temporal",
                    "Dados de Qualidade Energética",
                ]
            )

            with aba_inspetor:

                render_node_details(
                    selected_node,
                    graph,
                )

            with aba_temporal:

                if (
                    analysis_df is not None
                    and analysis_structure is not None
                ):

                    render_analise_eletrica_contexto(
                        analysis_df,
                        analysis_structure,
                        graph,
                        selected_node,
                        key_prefix=f"analise_rede_{selected_node}",
                    )

                elif (
                    results_df is not None
                    and measurement_columns is not None
                    and time_values is not None
                ):

                    node_series = prepare_node_time_series(
                        graph,
                        results_df,
                        measurement_columns,
                        time_values,
                        selected_node,
                    )

                    if node_series:

                        render_node_time_series(
                            selected_node,
                            node_series,
                        )

                    else:

                        st.info(
                            "O barramento selecionado não possui série temporal "
                            "associada no arquivo de resultados."
                        )

                else:

                    st.info(
                        "A análise temporal está disponível para entradas "
                        "JSON + CSV validadas por hash."
                    )

            with aba_qee:

                if (
                    analysis_df is not None
                    and analysis_structure is not None
                ):

                    render_cards_qee(
                        analysis_df,
                        analysis_structure,
                        elemento_referencia=selected_node,
                        permitir_selecao=False,
                        key_prefix=f"qee_rede_{selected_node}",
                    )

                else:

                    st.info(
                        "Os dados de qualidade energética estão disponíveis "
                        "para entradas JSON + CSV validadas por hash."
                    )

        else:

            st.info(
                "Selecione um barramento no grafo ou na barra para visualizar "
                "o inspetor e a análise elétrica correspondente."
            )

        unassociated = graph.metadata.get(
            "unassociated_measurements",
            [],
        )

        if unassociated:

            with st.expander("Medições não associadas"):
                st.json(unassociated)

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
