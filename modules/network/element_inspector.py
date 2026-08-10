import re
from html import escape

import streamlit as st


NODE_INFO = {
    "refbus": {
        "titulo": "Subestação / Fonte",
        "descricao": "Representa o ponto de suprimento de energia do circuito.",
    },
    "load": {
        "titulo": "Carga",
        "descricao": "Barramento associado ao consumo de energia elétrica.",
    },
    "pv": {
        "titulo": "Geração Distribuída",
        "descricao": "Barramento com geração de energia associada.",
    },
    "regulator_bus": {
        "titulo": "Barramento Regulado",
        "descricao": "Associado a um regulador de tensão da rede.",
    },
    "virtual_bus": {
        "titulo": "Barramento Virtual",
        "descricao": "Criado pelo modelo para representar um ponto intermediário da rede.",
    },
    "transformer_bus": {
        "titulo": "Conectado a Transformador",
        "descricao": "Barramento conectado a transformadores.",
    },
    "bus": {
        "titulo": "Barramento Comum",
        "descricao": "Barramento utilizado para interligação dos elementos da rede.",
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


def _measurement_label(measurement):
    variable = str(
        measurement.get("variavel", "")
    )

    known_labels = {
        "P_meas": "Potência medida",
        "Q_meas": "Potência reativa medida",
        "P_ac": "Potência AC",
        "Q_ac": "Potência reativa AC",
        "P_dc": "Potência DC",
        "temperature": "Temperatura",
        "irradiance": "Irradiância",
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
        return (
            "Potência Ativa",
            "#e67e22",
            40,
        )

    if variable.startswith("Q") or unit in {"var", "kvar", "mvar"}:
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
    """
    Renderiza um card visualmente alinhado ao painel QEE.
    """

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
                _measurement_label(measurement),
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
            "Tensão",
            voltage_rows,
            "#f1c40f",
        )

    with col_neighbors:
        _render_card(
            "Conectado a",
            neighbor_rows,
            "#8e44ad",
        )

    _render_measurements(
        node.metadata.get("measurements", []),
        include_voltage=False,
    )
