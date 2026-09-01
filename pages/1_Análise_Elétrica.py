import streamlit as st
from utils.leitura import ler_dados
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
    render_grafico_multiserie,
    render_grafico_distribuicao_tensao,
    eh_tensao
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
    obter_escala_visual
)

from utils.unidades import remover_unidade_do_tipo
from utils.prodist import (
    CLASSES_PRODIST,
    obter_limites_prodist,
    inferir_classe_prodist,
    inferir_metadados_prodist
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


def render_controles_prodist(
    unidade_final,
    serie_tensao,
    variavel_info
):
    """
    Renderiza controles de limites PRODIST na unidade do gráfico.
    """

    mostrar_limites = st.checkbox(
        "Mostrar faixas e limites PRODIST nos gráficos",
        value=True
    )

    if not mostrar_limites:

        return False, None

    metadados_prodist = inferir_metadados_prodist(
        variavel_info,
        unidade_final
    )

    classe = metadados_prodist.get(
        "classe"
    )

    if classe is None:

        classe = inferir_classe_prodist(
            serie_tensao,
            unidade_final
        )

    classe_inferida_por_medida = inferir_classe_prodist(
        serie_tensao,
        unidade_final
    )

    serie_valida = serie_tensao.dropna()

    valor_referencia = 1.0

    if not serie_valida.empty:

        valor_referencia = float(
            serie_valida.abs().median()
        )

    if unidade_final == "pu":

        st.caption(
            "Valores em pu não permitem inferir automaticamente BT, MT ou AT "
            "sem uma tensão/base de referência externa. A série não é convertida; "
            "os limites proporcionais padrão são aplicados diretamente em pu."
        )

        classe = "Média tensão (> 2,3 kV a < 69 kV)"

    else:

        if classe is None:

            classe = classe_inferida_por_medida

        st.caption(
            f"Classe de tensão PRODIST inferida automaticamente: **{classe}**"
        )

    tensao_referencia = None

    if classe in CLASSES_PRODIST and unidade_final != "pu":

        tensao_referencia = st.number_input(
            f"TR para cálculo dos limites [{unidade_final}]",
            min_value=0.0,
            value=valor_referencia,
            step=0.1 if unidade_final == "kV" else 1.0
        )

    limites = obter_limites_prodist(
        classe=classe,
        tensao_referencia=tensao_referencia,
        unidade=unidade_final
    )

    editar_limites = st.checkbox(
        "Editar limites manualmente",
        value=False
    )

    if editar_limites:

        col_l1, col_l2, col_l3, col_l4 = st.columns(4)

        with col_l1:

            limites["critico_min"] = st.number_input(
                f"Crítico inf. [{unidade_final}]",
                value=float(limites["critico_min"]),
                format="%.6f"
            )

        with col_l2:

            limites["adequado_min"] = st.number_input(
                f"Adequado mín. [{unidade_final}]",
                value=float(limites["adequado_min"]),
                format="%.6f"
            )

        with col_l3:

            limites["adequado_max"] = st.number_input(
                f"Adequado máx. [{unidade_final}]",
                value=float(limites["adequado_max"]),
                format="%.6f"
            )

        with col_l4:

            limites["critico_max"] = st.number_input(
                f"Crítico sup. [{unidade_final}]",
                value=float(limites["critico_max"]),
                format="%.6f"
            )

    return True, limites

uploaded_file = render_upload(
    session_key="arquivo_eletrico",
    label="Carregue o arquivo CSV ou HDF5",
    file_types=["csv", "h5", "hdf5"]
)


if uploaded_file is not None:

    aba_temporal, aba_qee = st.tabs([

        "Análise Temporal",

        "Dados de Qualidade Energética"
    ])

    with aba_temporal:

        try:

            df = ler_dados(uploaded_file)

        except Exception as erro:

            st.error(
                f"Erro ao ler o arquivo: {erro}"
            )

            st.stop()

        df = processar_tempo(df)

        mapeamento = carregar_mapeamento()

        colunas_mapeadas = mapear_colunas(
            df.columns,
            mapeamento
        )

        estrutura = organizar_variaveis(
            colunas_mapeadas
        )

        if not colunas_mapeadas:

            st.warning(
                "Nenhuma coluna do arquivo foi reconhecida pelo mapeamento atual."
            )

            with st.expander(
                "Ver colunas encontradas no arquivo"
            ):

                st.write(
                    list(df.columns)
                )

            st.stop()

        if not estrutura:

            st.warning(
                "As colunas foram lidas, mas nenhuma variável pôde ser organizada."
            )

            st.stop()

        tipos_disponiveis = list(
            estrutura.keys()
        )

        if not tipos_disponiveis:

            st.warning(
                "Nenhum tipo de variável disponível para visualização."
            )

            st.stop()

        tipo_escolhido = st.selectbox(
            "Tipo de variável",
            tipos_disponiveis
        )

        elementos = list(
            estrutura[tipo_escolhido].keys()
        )

        if not elementos:

            st.warning(
                "Nenhum elemento encontrado para o tipo de variável selecionado."
            )

            st.stop()

        elemento_escolhido = st.selectbox(
            "Elemento",
            elementos
        )

        variaveis = estrutura[
            tipo_escolhido
        ][
            elemento_escolhido
        ]

        if not variaveis:

            st.warning(
                "Nenhuma variável encontrada para o elemento selecionado."
            )

            st.stop()

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

        unidade_final, fator_visual = (
            obter_escala_visual(

                df_plot["Valor"],

                unidade_original
            )
        )

        serie_escalada = (
            df_plot["Valor"] * fator_visual
        )

        df_plot = df_plot.copy()

        df_plot["Valor"] = serie_escalada

        tipo_variavel = remover_unidade_do_tipo(
            variavel_info["tipo"]
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

        mostrar_limites_prodist = False

        limites_prodist = None

        if eh_tensao(
            variavel_info
        ):

            mostrar_limites_prodist, limites_prodist = (
                render_controles_prodist(
                    unidade_final,
                    df_plot["Valor"],
                    variavel_info
                )
            )

        if len(opcoes_unicas) > 1:

            col_esquerda, col_direita = st.columns(2)

        else:

            col_esquerda = st.container()

        with col_esquerda:

            render_grafico_individual(
                df_plot,
                coluna_real,
                label_grafico,
                variavel_info,
                mostrar_limites_prodist,
                limites_prodist
            )

        if len(opcoes_unicas) > 1:

            df_multiserie = (
                preparar_multiplas_series(
                    df,
                    variaveis
                )
            )

            for coluna in df_multiserie.columns:

                if coluna != "Tempo":

                    df_multiserie[coluna] = (
                        df_multiserie[coluna]
                        * fator_visual
                    )

            with col_direita:

                render_grafico_multiserie(
                    df_multiserie,
                    label_grafico,
                    variavel_info,
                    mostrar_limites_prodist,
                    limites_prodist
                )

        if eh_tensao(
            variavel_info
        ):

            if df_multiserie is None:

                df_tensoes_distribuicao = df_plot.rename(
                    columns={
                        "Valor": coluna_real
                    }
                )

            else:

                df_tensoes_distribuicao = df_multiserie

            render_grafico_distribuicao_tensao(
                df_tensoes_distribuicao,
                label_grafico,
                mostrar_limites_prodist,
                limites_prodist
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

else:

    st.info(
        "Carregue um arquivo CSV para iniciar a análise elétrica."
    )
