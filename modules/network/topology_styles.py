def get_node_style(node):

    styles = {

        "refbus": {
            "background": "#D9D9D9",
            "border": "#000000",
        },

        "bus": {
            "background": "#D9D9D9",
            "border": "#808080",
        },

        "load": {
            "background": "#D9D9D9",
            "border": "#1E88E5",
        },

        "pv": {
            "background": "#D9D9D9",
            "border": "#4CAF50",
        },

    }

    return styles.get(
        node.node_type,
        styles["bus"],
    )