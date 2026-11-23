"""ZIP-only preparation and controls; JSON/CSV loading remains independent."""

import hashlib

import streamlit as st

from components.analise_eletrica_rede import montar_estrutura_analise_rede, preparar_dataframe_analise
from modules.network.cosim_loader import apply_measurement_snapshot
from modules.network.dss_results import load_dss_zip, select_branch_terminals
from modules.network.session_manager import normalizar_indice_instante


@st.cache_data(show_spinner=False, max_entries=3)
def cached_zip_results(content):
    return load_dss_zip(content)


def render_zip_results(content):
    with st.spinner("Lendo circuito e monitores OpenDSS..."):
        result = cached_zip_results(content)
    graph = result.graph
    selections = {}
    options = {}
    for item in result.catalog:
        if item["target_kind"] == "edge":
            options.setdefault(item["target_id"], set()).add(item["terminal"])
    digest = hashlib.sha256(content).hexdigest()[:16]
    if any(len(terminals) > 1 for terminals in options.values()):
        with st.popover("Terminais dos ramos"):
            for edge_id, terminals in options.items():
                edge = graph.edges[edge_id]
                selections[edge_id] = st.selectbox(
                    f"{edge.metadata.get('type', edge.edge_type)} {edge.metadata.get('name', edge.id)}",
                    sorted(terminals), format_func=lambda terminal: f"Terminal {terminal}",
                    key=f"zip_terminal_{digest}_{edge_id}",
                )
    else:
        selections = {edge_id: min(terminals) for edge_id, terminals in options.items()}
    catalog = select_branch_terminals(result.catalog, selections)
    with st.expander("Monitores e dados OpenDSS", expanded=bool(result.warnings)):
        st.dataframe(result.monitors, use_container_width=True, hide_index=True)
        if not result.raw.empty:
            st.dataframe(result.raw, use_container_width=True, hide_index=True)
        for warning in result.warnings:
            st.warning(warning)
    if result.dataframe.empty:
        st.info("O circuito não forneceu séries temporais compatíveis. O grafo permanece disponível; nenhuma simulação adicional foi executada.")
        return {"graph": graph, "master_file": result.master_file}

    frame = result.dataframe
    times = frame["Tempo (h)"]
    maximum = len(frame) - 1
    slider_key = f"network_zip_row_{digest}"
    stored = normalizar_indice_instante(st.session_state.get("network_selected_row", 0), maximum)
    sync = st.session_state.pop("network_sync_selected_row_slider", False)
    if sync or slider_key not in st.session_state:
        st.session_state[slider_key] = stored
    if maximum > 0:
        selected = st.slider("Instante da simulação", min_value=0, max_value=maximum, key=slider_key)
    else:
        selected = 0
    st.session_state["network_selected_row"] = selected
    stats = apply_measurement_snapshot(graph, frame, catalog, selected)
    analysis_frame = preparar_dataframe_analise(frame, times)
    structure = montar_estrutura_analise_rede(graph, catalog)
    st.caption(f"Tempo decorrido em horas: {times.iloc[0]:g} a {times.iloc[-1]:g}; {len(times)} instantes. Dados obtidos dos monitores da execução do circuito, não dos CSVs previamente exportados.")
    st.caption("Os indicadores descrevem as amostras disponíveis e não certificam uma campanha regulamentar de medição.")
    if any(item["target_kind"] == "pv" for item in catalog):
        st.caption("P/Q dos PVs usam sinal positivo para injeção; o sinal original do OpenDSS é preservado na tabela bruta dos monitores.")
    return {"graph": graph, "master_file": result.master_file, "results_df": frame,
            "measurement_columns": catalog, "time_values": times, "selected_row": selected,
            "snapshot_caption": f"{times.iloc[selected]:g} h", "measurement_stats": stats,
            "analysis_df": analysis_frame, "analysis_structure": structure}
