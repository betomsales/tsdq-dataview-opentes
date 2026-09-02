def get_node_style(node):

    styles = {

        "refbus": {
            "border": "#C00000",
            "background": "#D9D9D9",
        },

        "pv": {
            "border": "#008000",
            "background": "#D9D9D9",
        },

        "load": {
            "border": "#0066CC",
            "background": "#D9D9D9",
        },

        "regulator_bus": {
            "border": "#FF8C00",
            "background": "#D9D9D9",
        },

        "virtual_bus": {
            "border": "#D4AA00",
            "background": "#D9D9D9",
        },

        "transformer_bus": {
            "border": "#7B2CBF",
            "background": "#D9D9D9",
        },

        "bus": {
            "border": "#808080",
            "background": "#D9D9D9",
        },
    }

    return styles.get(
        node.node_type,
        styles["bus"]
    )


def get_voltage_color(voltage_pu):
    """Cor do nó segundo as faixas de tensão usadas no painel QEE."""

    if voltage_pu is None:
        return None

    if 0.93 <= voltage_pu <= 1.05:
        return "#2ECC71"

    if 0.90 <= voltage_pu <= 1.08:
        return "#F1C40F"

    return "#E74C3C"
