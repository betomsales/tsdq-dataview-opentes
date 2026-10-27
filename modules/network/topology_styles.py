from utils.prodist import classificar_tensao


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
        "storage": {"border": "#087E8B", "background": "#D9D9D9"},
        "generator": {"border": "#BC6C25", "background": "#D9D9D9"},
        "capacitor": {"border": "#5A638C", "background": "#D9D9D9"},
    }

    return styles.get(
        node.node_type,
        styles["bus"]
    )


def get_voltage_color(voltage_pu):
    """Cor do nó segundo as faixas de tensão usadas no painel QEE."""
    return {
        "adequado": "#2ECC71",
        "precario": "#F1C40F",
        "critico": "#E74C3C",
    }.get(classificar_tensao(voltage_pu))
