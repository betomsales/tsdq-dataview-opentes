import re
from html import escape

import streamlit as st


NODE_INFO = {
    "refbus": {
        "titulo": "Subestacao / Fonte",
        "descricao": "Representa o ponto de suprimento de energia do circuito.",
    },
    "load": {
        "titulo": "Carga",
        "descricao": "Barramento associado ao consumo de energia eletrica.",
    },
    "pv": {
        "titulo": "Geracao Distribuida",
        "descricao": "Barramento com geracao de energia associada.",
    },
    "regulator_bus": {
        "titulo": "Barramento Regulado",
        "descricao": "Associado a um regulador de tensao da rede.",
    },
    "virtual_bus": {
        "titulo": "Barramento Virtual",
        "descricao": "Criado pelo modelo para representar um ponto intermediario da rede.",
    },
    "transformer_bus": {
        "titulo": "Conectado a Transformador",
        "descricao": "Barramento conectado a transformadores.",
    },
    "bus": {
        "titulo": "Barramento Comum",
        "descricao": "Barramento utilizado para interligacao dos elementos da rede.",
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
    variable = str(
        measurement.get("variavel", "")
    )

    known_labels = {
        "P_meas": "Potencia medida",
        "Q_meas": "Potencia reativa medida",
        "P_ac": "Potencia AC",
        "Q_ac": "Potencia reativa AC",
        "P_dc": "Potencia DC",
        "temperature": "Temperatura",
        "irradiance": "Irradiancia",
    }

    if variable in known_labels:
        return known_labels[variable]

    phase_match = re.match(
        r"^[A-Za-z]+([123ABC])$",
        variable,
        re.IGNORECASE,
    )

    if phase_match:
        return f"Fase {phase_match.group(1).upper()}"

    return variable.replace(
        "_",
        " ",
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
        and _is_power_measurement(measurement)
        and source
    ):
        return f"{source} - {label}"

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

    if variable.startswith("V") or unit in {"pu", "v", "kv"}:
        return (
            "Tensao",
            "#f1c40f",
            10,
        )

    if "IRRADIANCE" in variable or "IRRADIANCIA" in variable:
        return (
            "Irradiancia",
            "#27ae60",
            70,
        )

    if is_current_phase and unit == "graus":
        return (
            "Angulo das Correntes",
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
                "Potencia Ativa - Equipamentos Conectados",
                "#e67e22",
                40,
            )

        if _is_edge_measurement(measurement):
            return (
                "Fluxo de Potencia Ativa",
                "#e67e22",
                40,
            )

        return (
            "Potencia Ativa",
            "#e67e22",
            40,
        )

    if variable.startswith("Q") or unit in {"var", "kvar", "mvar"}:
        if _is_equipment_measurement(measurement):
            return (
                "Potencia Reativa - Equipamentos Conectados",
                "#16a085",
                50,
            )

        if _is_edge_measurement(measurement):
            return (
                "Fluxo de Potencia Reativa",
                "#16a085",
                50,
            )

        return (
            "Potencia Reativa",
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
        "Outras medicoes",
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
            "Nao identificado"
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
                'color:#111827;text-align:right;overflow-wrap:anywhere;">'
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

        if not include_voltage and title == "Tensao":
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
            "Outras medicoes",
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
        st.warning("Barramento nao encontrado.")
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
        ("Descricao", node_info["descricao"]),
        ("Conexoes", len(neighbors)),
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
                "Media",
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
            "Tensao da Barra",
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
            "As potencias exibidas neste barramento pertencem aos equipamentos "
            "conectados a ele, nao a barra como grandeza propria. Valores "
            "positivos indicam injecao apenas se essa for a convencao adotada "
            "pela co-simulacao."
        )

    _render_measurements(
        measurements,
        include_voltage=False,
    )
