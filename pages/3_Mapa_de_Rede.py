import hashlib
import json

import streamlit as st
from pathlib import Path

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


def gerar_topologia_vinculada(
    topology_data,
    topology_name,
    results_name,
    results_hash,
):
    updated_topology = dict(topology_data)
    metadata = dict(
        updated_topology.get("metadata") or {}
    )

    metadata.update(
        {
            "scenario_id": metadata.get(
                "scenario_id",
                Path(topology_name).stem,
            ),
            "results_file": results_name,
            "results_sha256": results_hash,
            "hash_algorithm": "sha256",
        }
    )

    updated_topology["metadata"] = metadata

    return json.dumps(
        updated_topology,
        ensure_ascii=False,
        indent=4,
    ).encode("utf-8")


def render_validacao_vinculo(
    topology_data,
    topology_name,
    results_name,
    results_hash,
):
    expected_hash = obter_hash_vinculado(
        topology_data
    )

    if not expected_hash:
        st.warning(
            "Esta topologia ainda nao possui vinculo SHA-256 com o CSV carregado."
        )
        st.download_button(
            "Baixar topologia vinculada ao CSV",
            data=gerar_topologia_vinculada(
                topology_data,
                topology_name,
                results_name,
                results_hash,
            ),
            file_name=f"{Path(topology_name).stem}_vinculada.json",
            mime="application/json",
        )

        return

    if expected_hash == results_hash:
        st.success(
            "Vinculo validado: a topologia corresponde ao CSV carregado."
        )
        return

    st.error(
        "Vinculo invalido: o hash do CSV carregado nao corresponde ao "
        "hash registrado na topologia."
    )
    st.caption(
        f"Hash esperado: {expected_hash}"
    )
    st.caption(
        f"Hash do CSV carregado: {results_hash}"
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

            topology_data = carregar_json_upload(
                topology_file
            )

            results_hash = calcular_sha256_upload(
                results_file
            )

            render_validacao_vinculo(
                topology_data,
                topology_file.name,
                results_file.name,
                results_hash,
            )

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

        selected_node = render_graph(
            graph
        )

        st.divider()

        render_node_details(
            selected_node,
            graph,
        )

        if (
            results_df is not None
            and measurement_columns is not None
            and time_values is not None
        ):

            st.divider()

            if selected_node:

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
                        "O barramento selecionado nao possui serie temporal "
                        "associada no arquivo de resultados."
                    )

            else:

                st.info(
                    "Selecione um barramento no grafo para visualizar "
                    "a serie temporal correspondente."
                )

        unassociated = graph.metadata.get(
            "unassociated_measurements",
            [],
        )

        if unassociated:

            with st.expander("Medicoes nao associadas"):
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
