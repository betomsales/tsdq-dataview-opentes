import streamlit as st

from components.graficos_comunicacao import (
    render_cards_comunicacao,
    render_grafico_confiabilidade,
    render_grafico_jitter,
    render_grafico_latencia,
    render_grafico_payload,
    render_tabela_mensagens
)
from components.uploader import render_upload
from utils.comunicacao import (
    calcular_kpis,
    expandir_mensagens,
    ler_resultados_comunicacao,
    listar_origens,
    preparar_tabela_temporal,
    validar_resultados_comunicacao
)


st.set_page_config(
    page_title="Comunicacao",
    layout="wide"
)

st.title("Comunicacao")

st.markdown(
    """
    Modulo para analise dos resultados de comunicacao
    provenientes da co-simulacao.
    """
)

uploaded_file = render_upload(
    session_key="arquivo_comunicacao",
    label="Carregue o arquivo results.csv",
    file_types=["csv"]
)


if uploaded_file is None:

    st.info(
        "Carregue o arquivo results.csv para iniciar a analise de comunicacao."
    )

    st.stop()


if uploaded_file.name.lower() != "results.csv":

    st.warning(
        "Esta pagina espera especificamente um arquivo chamado results.csv."
    )

    st.stop()


df = ler_resultados_comunicacao(
    uploaded_file
)

erros = validar_resultados_comunicacao(
    df
)

if erros:

    for erro in erros:

        st.error(
            erro
        )

    with st.expander(
        "Ver colunas encontradas"
    ):

        st.write(
            list(df.columns)
        )

    st.stop()


origens = listar_origens(
    df
)

if not origens:

    st.warning(
        "Nenhuma origem de comunicacao foi encontrada no arquivo."
    )

    st.stop()


origem_escolhida = st.selectbox(
    "Origem",
    origens,
    index=0
)

time_data = preparar_tabela_temporal(
    df,
    origem_escolhida
)

df_expandido = expandir_mensagens(
    time_data
)

if df_expandido.empty:

    st.warning(
        "Nenhuma mensagem FIPA-ACL foi identificada em val_out."
    )

    with st.expander(
        "Ver tabela temporal processada"
    ):

        st.dataframe(
            time_data,
            use_container_width=True
        )

    st.stop()


kpis = calcular_kpis(
    time_data,
    df_expandido
)

render_cards_comunicacao(
    kpis
)

aba_dashboard, aba_dados = st.tabs(
    [
        "Dashboard",
        "Dados processados"
    ]
)

with aba_dashboard:

    col1, col2 = st.columns(2)

    with col1:

        render_grafico_latencia(
            df_expandido
        )

        render_grafico_payload(
            df_expandido
        )

    with col2:

        render_grafico_jitter(
            df_expandido
        )

        render_grafico_confiabilidade(
            kpis
        )


with aba_dados:

    st.subheader(
        "Mensagens desempacotadas"
    )

    render_tabela_mensagens(
        df_expandido
    )

    with st.expander(
        "Tabela temporal pivotada"
    ):

        st.dataframe(
            time_data,
            use_container_width=True
        )
