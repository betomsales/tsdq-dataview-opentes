import streamlit as st
from utils.leitura import ler_csv
from utils.leitura import processar_tempo
from utils.mapeamento import carregar_mapeamento
from utils.mapeamento import mapear_colunas
from utils.processamento import (
    organizar_variaveis,
    preparar_serie_temporal,
    preparar_multiplas_series
)
from components.uploader import render_upload
from components.graficos import (
    render_grafico_individual,
    render_grafico_multiserie
)
from components.tabelas import (
    render_tabela_serie,
    render_tabela_dataset,
    render_codigo_variavel
)
from components.cards_qee import (
    render_cards_qee
)
from utils.escalas import (
    auto_scale_visual
)

st.set_page_config(
    page_title="Análise Elétrica",
    layout="wide"
)

st.title("Análise Elétrica")

st.markdown("""
Módulo para análise de resultados
provenientes de simulações elétricas.
""")

uploaded_file = render_upload(
    session_key="arquivo_eletrico",
    label="Carregue o arquivo CSV",
    file_types=["csv"]
)


if uploaded_file is not None:

    aba_temporal, aba_qee = st.tabs([

        "Análise Temporal",

        "Dados de Qualidade Energética"
    ])

    with aba_temporal:

        df = ler_csv(uploaded_file)

        df = processar_tempo(df)

        mapeamento = carregar_mapeamento()

        colunas_mapeadas = mapear_colunas(
            df.columns,
            mapeamento
        )

        estrutura = organizar_variaveis(
            colunas_mapeadas
        )

        tipos_disponiveis = list(
            estrutura.keys()
        )

        tipo_escolhido = st.selectbox(
            "Tipo de variável",
            tipos_disponiveis
        )

        elementos = list(
            estrutura[tipo_escolhido].keys()
        )

        elemento_escolhido = st.selectbox(
            "Elemento",
            elementos
        )

        variaveis = estrutura[
            tipo_escolhido
        ][
            elemento_escolhido
        ]

        opcoes_variaveis = []

        for variavel in variaveis:

            fase = variavel.get("fase")

            unidade = variavel.get(
                "unidade_detectada"
            )

            nome = ""

            if fase:
                nome += fase

            if unidade:

                if nome:
                    nome += " "

                nome += f"({unidade})"

            if not nome:
                nome = variavel["tipo"]

            opcoes_variaveis.append(nome)

        opcoes_unicas = list(
            dict.fromkeys(opcoes_variaveis)
        )

        if len(opcoes_unicas) == 1:

            variavel_info = variaveis[0]

        else:

            variavel_escolhida = st.selectbox(
                "Variável",
                opcoes_unicas
            )

            indice = opcoes_variaveis.index(
                variavel_escolhida
            )

            variavel_info = variaveis[indice]

        dados_plot = preparar_serie_temporal(
            df,
            variavel_info
        )

        df_multiserie = None

        df_plot = dados_plot["df_plot"]

        unidade_original = (
            variavel_info.get(
                "unidade_detectada"
            )
        )

        if unidade_original:

            unidade_original = (
                unidade_original
                .replace("Mvar", "MVar")
                .replace("kvar", "kVar")
                .replace("var", "Var")
            )

        serie_escalada, unidade_final = (
            auto_scale_visual(

                df_plot["Valor"],

                unidade_original
            )
        )

        df_plot = df_plot.copy()

        df_plot["Valor"] = serie_escalada

        tipo_variavel = variavel_info[
            "tipo"
        ]

        tipo_variavel = (
            tipo_variavel
            .replace("(MW)", "")
            .replace("(kW)", "")
            .replace("(W)", "")
            .replace("(MVar)", "")
            .replace("(kVar)", "")
            .replace("(Var)", "")
            .strip()
        )

        if unidade_final:

            label_grafico = (
                f"{tipo_variavel} "
                f"[{unidade_final}]"
            )

        else:

            label_grafico = tipo_variavel

        coluna_real = dados_plot[
            "coluna_real"
        ]   

        if len(opcoes_unicas) > 1:

            col_esquerda, col_direita = st.columns(2)

        else:

            col_esquerda = st.container()

        with col_esquerda:

            render_grafico_individual(
                df_plot,
                coluna_real,
                label_grafico,
                variavel_info
            )

        if len(opcoes_unicas) > 1:

            df_multiserie = (
                preparar_multiplas_series(
                    df,
                    variaveis
                )
            )    

            with col_direita:

                render_grafico_multiserie(
                    df_multiserie,
                    label_grafico,
                    variavel_info
                )

        render_tabela_serie(
            df_plot
        )

        render_tabela_dataset(
            df
        )

        render_codigo_variavel(
            variavel_info
        )

    variavel_qee = variavel_info

    with aba_qee:

        render_cards_qee(
            df,
            estrutura
        )