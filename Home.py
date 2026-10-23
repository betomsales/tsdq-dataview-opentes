"""Tela inicial do ARGOS, com identidade GREI e acesso aos módulos existentes."""

from datetime import date
from html import escape
from pathlib import Path
import tomllib

import streamlit as st

from components.identidade import apply_brand_style, asset_uri


BASE_DIR = Path(__file__).resolve().parent

MODULES = (
    {
        "key": "network",
        "title": "Mapa de Rede",
        "category": "TOPOLOGIA E RESULTADOS",
        "description": "Explore as barras e conexões da rede e acompanhe as medições ao longo do tempo.",
        "details": "Grafo interativo · Inspetor · Séries temporais",
        "icon": "network.svg",
        "page": "pages/3_Mapa_de_Rede.py",
        "action": "Abrir mapa de rede",
    },
    {
        "key": "electrical",
        "title": "Análise Elétrica",
        "category": "GRANDEZAS E QUALIDADE",
        "description": "Examine tensões, correntes e potências e avalie os indicadores de qualidade da energia.",
        "details": "Gráficos · Tabelas · Indicadores DRP e DRC",
        "icon": "chart-no-axes-combined.svg",
        "page": "pages/1_Análise_Elétrica.py",
        "action": "Abrir análise elétrica",
    },
    {
        "key": "communication",
        "title": "Comunicação",
        "category": "MENSAGENS E DESEMPENHO",
        "description": "Analise as mensagens da co-simulação e os resultados de latência, jitter e confiabilidade.",
        "details": "Latência · Jitter · Tráfego de mensagens",
        "icon": "radio-tower.svg",
        "page": "pages/2_Comunicação.py",
        "action": "Abrir comunicação",
    },
)


def apply_home_style() -> None:
    apply_brand_style()
    st.markdown(
        """<style>
        [data-testid="stMainBlockContainer"] {
            max-width: none; padding: 3.75rem 0 0;
        }
        [data-testid="stHeader"] { background: #f7f9f7; }
        [data-testid="stDecoration"] { display: none; }
        .stElementContainer:has(style) { display: none; }
        .st-key-home_page { gap: 0; }
        .argos-hero {
            background: var(--grei-ink); color: white;
            border-bottom: 4px solid var(--grei-accent);
        }
        .argos-hero-inner { max-width: 1200px; padding: 30px 40px 38px; margin: 0 auto; }
        .argos-masthead {
            display: flex; justify-content: space-between; align-items: center;
            gap: 24px; margin-bottom: 28px;
        }
        .argos-grei-white { width: 84px; height: 60px; object-fit: contain; }
        .argos-institution { text-align: right; color: #d8e5dc; font-size: 12px; line-height: 1.8; }
        .argos-institution strong { color: white; font-weight: 500; }
        .argos-hero h1 {
            font-family: 'Exo 2', sans-serif; font-size: 58px; line-height: 1.05;
            font-weight: 700; color: white; padding: 0; margin: 0 0 12px;
        }
        .argos-hero .argos-subtitle {
            color: #f4ffeb; font-size: 23px; font-weight: 500;
            line-height: 1.5; margin: 0 0 6px;
        }
        .argos-hero .argos-description { color: #c4d4c9; font-size: 14px; line-height: 1.8; margin: 0; }
        .argos-tags { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
        .argos-tags span {
            color: #e8f3eb; border: 1px solid #52695b; border-radius: 4px;
            padding: 4px 10px; font-size: 11px; line-height: 1.6;
        }
        .argos-tags .argos-tag-primary { border-color: #2e8963; color: #7df0b3; }
        .st-key-home_content { width: 100%; max-width: 1200px; margin: 0 auto; padding: 32px 40px 38px; }
        .st-key-home_content > [data-testid="stElementContainer"] { width: 100%; min-width: 0; }
        /* Override inline widths measured before the section's max-width applies. */
        .st-key-home_content > [data-testid="stElementContainer"] [data-testid="stMarkdown"],
        .st-key-home_content > [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"] { width: 100% !important; min-width: 0; }
        .argos-section-heading {
            display: flex; align-items: baseline; justify-content: space-between;
            gap: 16px; margin: 0 0 20px;
        }
        .argos-section-heading h2 {
            font-family: 'Exo 2', sans-serif; font-size: 24px;
            color: var(--grei-ink); padding: 0; margin: 0;
        }
        .argos-section-heading span { color: var(--grei-muted); font-size: 12px; }
        .st-key-home_content [data-testid="stHorizontalBlock"] { gap: 20px; }
        /* Apply the card border only to the innermost Streamlit wrapper. */
        .st-key-home_content [data-testid="stVerticalBlockBorderWrapper"]:has(.argos-module):not(:has([data-testid="stVerticalBlockBorderWrapper"])) {
            background: white; border: 1px solid var(--grei-border); border-radius: 8px;
            padding: 24px; box-shadow: 0 3px 12px #23342d06;
            transition: border-color 160ms ease, box-shadow 160ms ease;
        }
        .st-key-home_content [data-testid="stVerticalBlockBorderWrapper"]:has(.argos-module):not(:has([data-testid="stVerticalBlockBorderWrapper"])):hover {
            border-color: #83ad96; box-shadow: 0 6px 20px #23342d0c;
        }
        .argos-module { min-height: 224px; }
        .argos-module-icon {
            width: 46px; height: 46px; display: grid; place-items: center;
            background: #edf5ef; border-radius: 6px; margin-bottom: 18px;
        }
        .argos-module-icon img { width: 25px; height: 25px; opacity: 0.78; }
        .argos-module .argos-module-category { color: var(--grei-green); font-size: 10px; font-weight: 600; margin: 0 0 6px; }
        .argos-module h3 {
            font-family: 'Exo 2', sans-serif; font-size: 24px; line-height: 1.3;
            color: var(--grei-ink); padding: 0; margin: 0 0 12px;
        }
        .argos-module .argos-module-description { color: var(--grei-muted); font-size: 13px; line-height: 1.8; margin: 0; }
        .argos-module .argos-module-details { color: #6a7a71; font-size: 10px; line-height: 1.8; margin: 14px 0 0; }
        .st-key-home_content [data-testid="stButton"] button {
            width: 100%; min-height: 43px; border: 1px solid #cbdcd0; border-radius: 5px;
            background: #f4f8f4; color: var(--grei-forest); box-shadow: none;
            transition: background 160ms ease, border-color 160ms ease;
        }
        .st-key-home_content [data-testid="stButton"] button p { font-size: 12px; font-weight: 500; line-height: 1.5; }
        .st-key-home_content [data-testid="stButton"] button:hover { background: #e8f2eb; border-color: var(--grei-green); color: var(--grei-forest); }
        .st-key-home_module_network [data-testid="stButton"] button { background: var(--grei-forest); border-color: var(--grei-forest); color: white; }
        .st-key-home_module_network [data-testid="stButton"] button:hover { background: #244b3b; border-color: #244b3b; color: white; }
        .st-key-home_content [data-testid="stButton"] button:focus-visible { outline: 3px solid #00de81; outline-offset: 3px; }
        .argos-footer { background: white; border-top: 1px solid var(--grei-border); }
        .argos-footer-inner {
            max-width: 1200px; padding: 26px 40px; margin: 0 auto;
            display: flex; align-items: center; justify-content: space-between; gap: 24px;
        }
        .argos-footer-brand { display: flex; align-items: center; gap: 22px; }
        .argos-grei-green { width: 74px; height: 53px; object-fit: contain; }
        .argos-footer-text { border-left: 1px solid var(--grei-border); padding-left: 22px; }
        .argos-footer-text p { color: var(--grei-muted); font-size: 11px; margin: 0; line-height: 1.8; }
        .argos-footer-text strong { color: var(--grei-forest); font-weight: 500; }
        .argos-version { color: #6a7a71; font-size: 10px; text-align: right; line-height: 1.8; }
        @media (prefers-reduced-motion: reduce) { .st-key-home_content * { transition: none !important; } }
        @media (max-width: 1000px) {
            .st-key-home_content { padding: 28px 24px 32px; }
            .argos-hero-inner { padding: 26px 24px 32px; }
            .st-key-home_content [data-testid="stHorizontalBlock"] { gap: 14px; }
            .st-key-home_content [data-testid="stVerticalBlockBorderWrapper"]:has(.argos-module):not(:has([data-testid="stVerticalBlockBorderWrapper"])) { padding: 20px; }
            .argos-module { min-height: 264px; }
            .argos-module h3 { font-size: 22px; }
        }
        @media (max-width: 900px) {
            .st-key-home_content [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
            .st-key-home_content [data-testid="stColumn"] { min-width: 100%; flex: 1 1 100%; }
            .argos-module { min-height: 0; }
            .argos-section-heading { flex-wrap: wrap; gap: 4px; }
            .argos-section-heading span { font-size: 11px; }
            .argos-hero h1 { font-size: 46px; }
            .argos-hero .argos-subtitle { font-size: 20px; }
            .argos-hero .argos-description { font-size: 13px; }
            .argos-institution { font-size: 10px; }
            .argos-grei-white { width: 72px; height: 52px; }
            .argos-footer-inner { flex-wrap: wrap; padding: 24px; gap: 20px; }
            .argos-footer-brand { gap: 16px; }
            .argos-footer-text { padding-left: 16px; }
            .argos-version { width: 100%; text-align: left; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown(
        f"""
        <section class="argos-hero" aria-label="ARGOS">
            <div class="argos-hero-inner">
                <div class="argos-masthead">
                    <img class="argos-grei-white" src="{asset_uri('logo-white.svg')}" alt="GREI">
                    <div class="argos-institution">
                        <strong>Grupo de Redes Elétricas Inteligentes</strong><br>
                        Universidade Federal do Ceará
                    </div>
                </div>
                <h1>ARGOS</h1>
                <p class="argos-subtitle">Análise de resultados de co-simulação</p>
                <p class="argos-description">Redes elétricas, qualidade da energia e comunicação.</p>
                <div class="argos-tags" aria-label="Contexto da aplicação">
                    <span class="argos-tag-primary">Redes elétricas inteligentes</span>
                    <span>OpenDSS</span>
                    <span>Co-simulação</span>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_modules() -> None:
    with st.container(key="home_content"):
        st.markdown(
            '<div class="argos-section-heading"><h2>Áreas de análise</h2>'
            '<span>Resultados sob diferentes perspectivas</span></div>',
            unsafe_allow_html=True,
        )
        for column, module in zip(st.columns(3), MODULES):
            with column, st.container(border=True, key=f"home_module_{module['key']}"):
                st.markdown(
                    f"""
                    <article class="argos-module" aria-label="{escape(module['title'])}">
                        <div class="argos-module-icon">
                            <img src="{asset_uri('icons/' + module['icon'])}" alt="" aria-hidden="true">
                        </div>
                        <p class="argos-module-category">{escape(module['category'])}</p>
                        <h3>{escape(module['title'])}</h3>
                        <p class="argos-module-description">{escape(module['description'])}</p>
                        <p class="argos-module-details">{escape(module['details'])}</p>
                    </article>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    module["action"], key=f"open_{module['key']}",
                    icon=":material/arrow_forward:", use_container_width=True,
                ):
                    st.switch_page(module["page"])


def render_footer() -> None:
    with (BASE_DIR / "pyproject.toml").open("rb") as project_file:
        version = escape(tomllib.load(project_file)["project"]["version"])
    st.markdown(
        f"""
        <footer class="argos-footer">
            <div class="argos-footer-inner">
                <div class="argos-footer-brand">
                    <img class="argos-grei-green" src="{asset_uri('logo-green.svg')}"
                         alt="GREI - Grupo de Redes Elétricas Inteligentes">
                    <div class="argos-footer-text">
                        <p><strong>Grupo de Redes Elétricas Inteligentes</strong></p>
                        <p>Universidade Federal do Ceará</p>
                    </div>
                </div>
                <div class="argos-version">ARGOS · v{version}<br>&copy; {date.today().year} GREI / UFC</div>
            </div>
        </footer>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="ARGOS | GREI",
        page_icon=str(BASE_DIR / "imagens" / "logo.png"),
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_home_style()
    with st.container(key="home_page"):
        render_header()
        render_modules()
        render_footer()


if __name__ == "__main__":
    main()
