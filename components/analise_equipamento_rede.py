"""Equipment-focused entry point to the existing inspector and analyses."""

import streamlit as st

from components.analise_eletrica_rede import (
    render_analise_eletrica_elemento,
    render_grandezas_derivadas,
)
from modules.network.element_inspector import _render_card, _render_measurements
from modules.network.equipment_view import equipment_measurements
from utils.estado_geracao import montar_estado_geracao_fv_medicoes


def render_equipment_analysis(graph, equipment, analysis_df, analysis_structure):
    st.subheader(equipment.label)
    st.caption(f"Barra conectada: {graph.nodes[equipment.bus].label}")
    inspector, temporal, derived = st.tabs(["Inspetor", "Análise Temporal", "Grandezas derivadas"])
    measurements = equipment_measurements(graph, equipment)
    with inspector:
        _render_card(equipment.label, [
            ("Tipo", equipment.kind), ("Barra", graph.nodes[equipment.bus].label),
            ("Fases", equipment.phases if equipment.phases is not None else "Não informado"),
            ("Terminais", ", ".join(map(str, equipment.terminals)) or "Não informados"),
        ], "#008000" if equipment.kind == "PVSystem" else "#0066CC")
        if equipment.kind == "PVSystem":
            state = montar_estado_geracao_fv_medicoes(measurements, renderizar_sem_dados=True)
            if state:
                _render_card(state["titulo"], state["rows"], state["cor"], "170px")
        if measurements:
            _render_measurements(measurements)
        else:
            st.info("Este equipamento não possui medições associadas no instante selecionado.")

    available = analysis_structure is not None and any(
        equipment.analysis_key in elements for elements in analysis_structure.values()
    )
    with temporal:
        if analysis_df is not None and available:
            render_analise_eletrica_elemento(
                analysis_df, analysis_structure, equipment.analysis_key,
                key_prefix=f"equipment_{equipment.id}",
            )
        else:
            st.info("Não há séries temporais associadas a este equipamento.")
    with derived:
        if analysis_df is not None and available:
            render_grandezas_derivadas(
                analysis_df, analysis_structure, equipment.analysis_key, equipment.label,
            )
        else:
            st.info("Não há medições P/Q disponíveis para este equipamento.")
