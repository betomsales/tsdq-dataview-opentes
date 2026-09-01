import pandas as pd


def organizar_variaveis(colunas_mapeadas):
    """
    Organiza variáveis por tipo e elemento.
    """

    estrutura = {}

    for coluna, info in colunas_mapeadas.items():

        tipo = info["tipo"]

        elemento = info["elemento"]

        if tipo not in estrutura:
            estrutura[tipo] = {}

        if elemento not in estrutura[tipo]:
            estrutura[tipo][elemento] = []

        estrutura[tipo][elemento].append(info)

    return estrutura


def preparar_serie_temporal(
    df,
    variavel_info
):
    """
    Prepara série temporal para visualização.
    """

    coluna_real = variavel_info[
        "coluna_original"
    ]

    df_plot = df[
        [
            "Tempo_EixoX",
            coluna_real
        ]
    ].copy()

    df_plot.columns = [
        "Tempo",
        "Valor"
    ]

    df_plot["Valor"] = pd.to_numeric(
        df_plot["Valor"],
        errors="coerce"
    )

    

    tipo = variavel_info["tipo"]

    unidade = variavel_info.get(
        "unidade_detectada"
    )

    label_y = variavel_info.get(
        "rotulo_variavel",
        tipo,
    )

    if unidade:
        label_y += f" [{unidade}]"

    return {

        "df_plot": df_plot,

        "label_y": label_y,

        "coluna_real": coluna_real
    }

def preparar_multiplas_series(
    df,
    variaveis
):
    """
    Prepara dataframe multivariável.
    """

    df_multiserie = pd.DataFrame()

    df_multiserie["Tempo"] = df[
        "Tempo_EixoX"
    ]

    for variavel in variaveis:

        coluna = variavel[
            "coluna_original"
        ]

        nome_coluna = variavel.get(
            "rotulo_serie"
        ) or variavel.get(
            "rotulo_card"
        ) or coluna

        df_multiserie[
            nome_coluna
        ] = pd.to_numeric(
            df[coluna],
            errors="coerce"
        )

    return df_multiserie
