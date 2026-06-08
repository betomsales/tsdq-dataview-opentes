import streamlit as st
import os

from pathlib import Path
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent

icone = Image.open(
    BASE_DIR / "imagens" / "logo.png"
)
import os
from PIL import Image
# 1. Configuração da página (Sempre o primeiro comando)

icone = Image.open("imagens/logo.png")

st.set_page_config(
    page_title="OpenTES - TSDQ",
    page_icon=icone,
    layout="wide"
)

# 2. Renderização do Cabeçalho
# Criamos uma estrutura de colunas para centralizar a imagem local
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    # Caminho local conforme sua estrutura de pastas
    caminho_logo = (
        BASE_DIR
        / "imagens"
        / "OpenTES.png"
    )
    
    if caminho_logo.exists():
        st.image(
            str(caminho_logo),
            use_container_width=True,
        )
    else:
        # Fallback caso a imagem não seja encontrada (ajuda no debug)
        st.warning(f"⚠️ Arquivo {caminho_logo} não encontrado.")

# 3. Título e Linha Divisória
st.markdown("<h1 style='text-align: center;'>OpenTES - TSDQ</h1>", unsafe_allow_html=True)
st.markdown("<hr style='margin-top: 0; margin-bottom: 20px;'>", unsafe_allow_html=True)

# 4. Conteúdo Principal
st.markdown("""
<div style='text-align: center; font-size: 1.2rem; color: #9ca3af; margin-bottom: 30px;'>
    Sistema multidomínio para análise técnica e supervisão de dados.
</div>
""", unsafe_allow_html=True)

# Organizando os domínios em colunas para um visual mais "Dashboard"
c1, c2, c3 = st.columns(3)

with c1:
    st.info("### ⚡ Co-simulação\nSimulação de rede.")

with c2:
    st.info("### 📡 Comunicação\nAnálise de latência e tráfego de dados.")

with c3:
    st.info("### 🗺️ Qualidade\nAnálise da qualidade energética.")

st.write("")
st.success("**Universidade Federal do Ceará.**")