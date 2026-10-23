"""Identidade visual compartilhada pelas páginas e componentes do ARGOS."""

import base64
from html import escape
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[1]
BRAND_DIR = BASE_DIR / "assets" / "grei"


@st.cache_data(show_spinner=False)
def asset_uri(relative_path: str) -> str:
    path = BRAND_DIR / relative_path
    media_type = "image/svg+xml" if path.suffix == ".svg" else "font/ttf"
    content = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{content}"


@st.cache_data(show_spinner=False)
def font_face_css() -> str:
    fonts = (
        ("Exo 2", 700, "exo2-bold.ttf"),
        ("Poppins", 400, "poppins-regular.ttf"),
        ("Poppins", 500, "poppins-medium.ttf"),
        ("Poppins", 600, "poppins-semibold.ttf"),
    )
    return "\n".join(
        f"@font-face {{font-family:'{family}';font-style:normal;"
        f"font-weight:{weight};font-display:swap;"
        f"src:url('{asset_uri('fonts/' + filename)}') format('truetype');}}"
        for family, weight, filename in fonts
    )


def apply_brand_style(*, workspace: bool = False) -> None:
    styles = (BRAND_DIR / "theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{font_face_css()}\n{styles}</style>", unsafe_allow_html=True)
    st.logo(str(BRAND_DIR / "logo-green.svg"), size="large")
    st.sidebar.markdown(
        '<div class="grei-sidebar-footer"><strong>ARGOS</strong><br>'
        'Grupo de Redes Elétricas Inteligentes<br>Universidade Federal do Ceará</div>',
        unsafe_allow_html=True,
    )

    # A shared template changes presentation while preserving explicit trace colors.
    template = go.layout.Template(pio.templates["plotly_white"])
    template.layout.update(
        font={"family": "Poppins, sans-serif", "size": 12, "color": "#23342d"},
        title={"font": {"family": "Exo 2, sans-serif", "size": 18}},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        xaxis={"gridcolor": "#e5ece7", "zerolinecolor": "#cbdcd0", "automargin": True},
        yaxis={"gridcolor": "#e5ece7", "zerolinecolor": "#cbdcd0", "automargin": True},
        hoverlabel={"font": {"family": "Poppins, sans-serif"}},
    )
    pio.templates["argos"] = template
    pio.templates.default = "argos"

    if workspace:
        st.markdown(
            """<style>
            [data-testid="stMainBlockContainer"] {padding:5rem 2.5rem 3rem;}
            @media(max-width:760px) {
                [data-testid="stMainBlockContainer"] {padding:4.5rem 1rem 2rem;}
            }
            </style>""",
            unsafe_allow_html=True,
        )


def style_plotly_figure(figure):
    # Explicit layout fonts take precedence over Streamlit's frontend defaults.
    return figure.update_layout(
        font_family="Poppins, sans-serif",
        title_font_family="Exo 2, sans-serif",
    )


def render_page_header(title: str, category: str, description: str) -> None:
    st.markdown(
        f"""
        <header class="grei-page-header">
            <div class="grei-page-heading">
                <p class="grei-page-category">ARGOS / {escape(category)}</p>
                <h1>{escape(title)}</h1>
                <p class="grei-page-description">{escape(description)}</p>
            </div>
            <img src="{asset_uri('logo-white.svg')}" alt="GREI" class="grei-page-logo">
        </header>
        """,
        unsafe_allow_html=True,
    )
