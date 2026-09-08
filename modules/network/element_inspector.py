import re
from html import escape

import streamlit as st

from utils.estado_geracao import montar_estado_geracao_fv_medicoes
from utils.rotulos_medicoes import obter_rotulo_variavel


NODE_INFO = {
    "refbus": {
        "titulo": "Subestação / Fonte",
        "descricao": "Ponto de suprimento",
    },
    "load": {
        "titulo": "Carga",
        "descricao": "Consumo conectado",
    },
    "pv": {
        "titulo": "Geração Distribuída",
        "descricao": "Geração associada",
    },
    "regulator_bus": {
        "titulo": "Barramento Regulado",
        "descricao": "Regulação de tensão",
    },
    "virtual_bus": {
        "titulo": "Barramento Virtual",
        "descricao": "Nó intermediário",
    },
    "transformer_bus": {
        "titulo": "Conectado a Transformador",
        "descricao": "Ligação ao transformador",
    },
    "bus": {
        "titulo": "Barramento Comum",
        "descricao": "Interligação da rede",
    },
}


def _format_number(value):
    try:
        return f"{float(value):.6g}"
    except (TypeError, ValueError):
        return str(value)


def _format_measurement_value(measurement):
    unit = f" {measurement['unidade']}" if measurement.get("unidade") else ""
    return f"{_format_number(measurement['valor'])}{unit}"


def _measurement_source(measurement):
    return str(
        measurement.get("grupo")
        or measurement.get("target_id")
        or ""
    )


def _is_equipment_measurement(measurement):
    return measurement.get("target_kind") in {
        "pv",
        "pv_equipment",
    }


def _is_edge_measurement(measurement):
    return measurement.get("target_kind") == "edge"


def _is_power_measurement(measurement):
    variable = str(
        measurement.get("variavel", "")
    ).upper()
    unit = str(
        measurement.get("unidade") or ""
    ).lower()

    return (
        variable.startswith("P")
        or variable.startswith("Q")
        or unit in {"w", "kw", "mw", "var", "kvar", "mvar"}
    )


def _measurement_label(measurement):
    if measurement.get("rotulo_variavel"):
        return measurement["rotulo_variavel"]

    variable = str(
        measurement.get("variavel", "")
    )

    phase_match = re.match(
        r"^[A-Za-z]+([123ABC])$",
        variable,
        re.IGNORECASE,
    )

    if phase_match:
        return f"Fase {phase_match.group(1).upper()}"

    return obter_rotulo_variavel(
        variable
    )


def _measurement_context_label(measurement, category):
    label = _measurement_label(
        measurement
    )
    source = _measurement_source(
        measurement
    )

    if (
        _is_equipment_measurement(measurement)
        and source
    ):
        return measurement.get(
            "nome_curto_elemento",
            source,
        )

    if (
        _is_edge_measurement(measurement)
        and category.startswith("Fluxo")
        and source
    ):
        return f"{source} - {label}"

    return label


def _measurement_category(measurement):
    variable = str(
        measurement.get("variavel", "")
    ).upper()
    unit = str(
        measurement.get("unidade") or ""
    ).lower()
    is_current_phase = re.match(
        r"^I[123ABC]$",
        variable,
        re.IGNORECASE,
    )
    category_by_equipment = measurement.get(
        "categoria_card"
    )

    if _is_equipment_measurement(measurement) and category_by_equipment:
        equipment_cards = {
            "Potência DC dos Painéis": ("#e67e22", 40),
            "Potência Ativa AC dos Inversores": ("#d35400", 45),
            "Potência Reativa AC dos Inversores": ("#16a085", 50),
            "Potência Ativa do PVSystem": ("#f39c12", 55),
            "Potência Reativa do PVSystem": ("#1abc9c", 60),
            "Temperatura dos Painéis": ("#c0392b", 70),
            "Irradiância dos Painéis": ("#27ae60", 80),
            "Dados dos Painéis": ("#7f8c8d", 90),
            "Dados dos Inversores": ("#7f8c8d", 90),
            "Dados do PVSystem": ("#7f8c8d", 90),
        }
        color, order = equipment_cards.get(
            category_by_equipment,
            ("#7f8c8d", 90),
        )

        return (
            category_by_equipment,
            color,
            order,
        )

    if variable.startswith("V") or unit in {"pu", "v", "kv"}:
        return (
            "Tensão",
            "#f1c40f",
            10,
        )

    if "IRRADIANCE" in variable or "IRRADIÂNCIA" in variable:
        return (
            "Irradiância",
            "#27ae60",
            70,
        )

    if is_current_phase and unit == "graus":
        return (
            "Ângulo das Correntes",
            "#9b59b6",
            30,
        )

    if is_current_phase or unit in {"a", "ka"}:
        return (
            "Correntes",
            "#2980b9",
            20,
        )

    if variable.startswith("P") or unit in {"w", "kw", "mw"}:
        if _is_equipment_measurement(measurement):
            return (
                "Potência Ativa - Equipamentos Conectados",
                "#e67e22",
                40,
            )

        if _is_edge_measurement(measurement):
            return (
                "Fluxo de Potência Ativa",
                "#e67e22",
                40,
            )

        return (
            "Potência Ativa",
            "#e67e22",
            40,
        )

    if variable.startswith("Q") or unit in {"var", "kvar", "mvar"}:
        if _is_equipment_measurement(measurement):
            return (
                "Potência Reativa - Equipamentos Conectados",
                "#16a085",
                50,
            )

        if _is_edge_measurement(measurement):
            return (
                "Fluxo de Potência Reativa",
                "#16a085",
                50,
            )

        return (
            "Potência Reativa",
            "#16a085",
            50,
        )

    if "TEMPERATURE" in variable or "TEMPERATURA" in variable:
        return (
            "Temperatura",
            "#c0392b",
            60,
        )

    return (
        "Outras medições",
        "#7f8c8d",
        90,
    )


def _render_card(
    title,
    rows=None,
    color="#95a5a6",
    min_height="150px",
):
    if not rows:
        content = (
            '<p style="color:gray;margin:0;font-size:1rem;">'
            "Não identificado"
            "</p>"
        )
    else:
        lines = []

        for label, value in rows:
            lines.append(
                '<div style="display:flex;justify-content:space-between;'
                'gap:1rem;margin-bottom:0.35rem;align-items:flex-start;">'
                '<span style="font-size:1.05rem;color:#4b5563;">'
                f"{escape(str(label))}"
                "</span>"
                '<span style="font-size:1.15rem;font-weight:bold;'
                'color:#111827;text-align:right;white-space:nowrap;'
                'flex-shrink:0;">'
                f"{escape(str(value))}"
                "</span>"
                "</div>"
            )

        content = "".join(lines)

    st.markdown(
        '<div style="border-left:6px solid '
        f"{color};padding:1rem;border-radius:0.5rem;"
        "background-color:#f7f7f7;margin-bottom:1rem;"
        f'min-height:{min_height};">'
        '<h4 style="margin-top:0;margin-bottom:1rem;font-size:1.35rem;">'
        f"{escape(str(title))}"
        "</h4>"
        f"{content}"
        "</div>",
        unsafe_allow_html=True,
    )


def _has_equipment_power_measurements(measurements):
    return any(
        _is_equipment_measurement(measurement)
        and _is_power_measurement(measurement)
        for measurement in measurements
    )


def _render_measurements(
    measurements,
    include_voltage=True,
):
    measurement_cards = {}

    for measurement in measurements:
        title, color, order = _measurement_category(
            measurement
        )

        if not include_voltage and title == "Tensão":
            continue

        measurement_cards.setdefault(
            title,
            {
                "color": color,
                "order": order,
                "rows": [],
            },
        )
        measurement_cards[title]["rows"].append(
            (
                _measurement_context_label(
                    measurement,
                    title,
                ),
                _format_measurement_value(measurement),
            )
        )

    if not measurement_cards:
        _render_card(
            "Outras medições",
            None,
            "#7f8c8d",
            "120px",
        )
        return

    cards = sorted(
        measurement_cards.items(),
        key=lambda item: item[1]["order"],
    )

    columns = st.columns(
        min(
            4,
            len(cards),
        )
    )

    for index, (title, card) in enumerate(cards):
        with columns[index % len(columns)]:
            _render_card(
                title,
                card["rows"],
                card["color"],
            )


def render_edge_details(edge_id, graph):
    edge = graph.edges.get(edge_id)

    if edge is None:
        return

    _render_card(
        "Elemento de linha",
        [
            ("ID", edge.id),
            ("Origem", edge.source),
            ("Destino", edge.target),
            ("Classe", edge.edge_type),
        ],
        "#34495e",
        "130px",
    )

    st.caption(
        "Correntes e P/Q exibidos neste bloco pertencem ao ramo selecionado, "
        "representando grandezas transportadas pela linha ou transformador."
    )

    _render_measurements(edge.metadata.get("measurements", []))


def get_neighbors(
    node_id,
    graph,
):
    neighbors = []

    for edge in graph.edges.values():
        if edge.source == node_id:
            neighbors.append(edge.target)

        elif edge.target == node_id:
            neighbors.append(edge.source)

    return sorted(neighbors)


def render_node_details(
    node_id,
    graph,
):
    st.subheader("Inspetor")

    if not node_id:
        st.info("Selecione um barramento.")
        return

    node = graph.nodes.get(node_id)

    if node is None:
        st.warning("Barramento não encontrado.")
        return

    node_info = NODE_INFO.get(
        node.node_type,
        NODE_INFO["bus"],
    )

    neighbors = get_neighbors(
        node_id,
        graph,
    )

    voltage_phases = node.metadata.get(
        "voltage_phases_pu",
        {},
    )

    info_rows = [
        ("Classe", node_info["titulo"]),
        ("Descrição", node_info["descricao"]),
        ("Conexões", len(neighbors)),
    ]

    voltage_rows = [
        (
            phase,
            f"{voltage_phases[phase]:.6f} pu",
        )
        for phase in sorted(voltage_phases)
    ]

    if node.voltage_pu is not None:
        voltage_rows.append(
            (
                "Média",
                f"{node.voltage_pu:.6f} pu",
            )
        )

    neighbor_rows = [
        (
            "Barramento",
            neighbor,
        )
        for neighbor in neighbors
    ]

    col_info, col_voltage, col_neighbors = st.columns(3)

    with col_info:
        _render_card(
            node.label,
            info_rows,
            "#2980b9",
        )

    with col_voltage:
        _render_card(
            "Tensão da Barra",
            voltage_rows,
            "#f1c40f",
        )

    with col_neighbors:
        _render_card(
            "Conectado a",
            neighbor_rows,
            "#8e44ad",
        )

    measurements = node.metadata.get("measurements", [])

    if _has_equipment_power_measurements(measurements):
        st.caption(
            "As potências exibidas neste barramento pertencem aos equipamentos "
            "conectados a ele, não à barra como grandeza própria. O card de "
            "estado fotovoltaico usa apenas a potência ativa do PVSystem, do "
            "inversor ou do painel, nessa ordem de prioridade."
        )

    estado_geracao_fv = montar_estado_geracao_fv_medicoes(
        measurements,
        renderizar_sem_dados=node.node_type == "pv",
    )

    if estado_geracao_fv:
        _render_card(
            estado_geracao_fv["titulo"],
            estado_geracao_fv["rows"],
            estado_geracao_fv["cor"],
            "170px",
        )

    _render_measurements(
        measurements,
        include_voltage=False,
    )
