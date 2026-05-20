import streamlit as st


def card_qee(
    titulo,
    valor,
    unidade,
    cor
):
    """
    Card simples de QEE.
    """

    st.markdown(
        f"""
        <div style="
            border-left: 6px solid {cor};
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #f7f7f7;
            margin-bottom: 1rem;
        ">

        <h4 style="margin:0;">
            {titulo}
        </h4>

        <h2 style="margin:0;">
            {valor}
            <span style="
                font-size:1rem;
                color:gray;
            ">
                {unidade}
            </span>
        </h2>

        </div>
        """,
        unsafe_allow_html=True
    )


def render_cards_qee():
    """
    Renderiza painel QEE.
    """

    st.subheader(
        "Dados de Qualidade Energética"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        card_qee(
            "Tensão F-N",
            "219.754",
            "V",
            "#f1c40f"
        )

        card_qee(
            "THD Tensão",
            "2.327",
            "%",
            "#2ecc71"
        )

        card_qee(
            "Flutuação",
            "0.080",
            "pu",
            "#2ecc71"
        )

    with col2:

        card_qee(
            "Corrente",
            "0.284",
            "A",
            "#3498db"
        )

        card_qee(
            "THD Corrente",
            "8.317",
            "%",
            "#e91e63"
        )

        card_qee(
            "Desequilíbrio",
            "0.000",
            "%",
            "#9b59b6"
        )

    with col3:

        card_qee(
            "Potência Total",
            "0.062",
            "kW",
            "#e67e22"
        )

        card_qee(
            "Fator de Potência",
            "-0.997",
            "cap",
            "#f39c12"
        )

        card_qee(
            "Frequência",
            "60.024",
            "Hz",
            "#8e44ad"
        )