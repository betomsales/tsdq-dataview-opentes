import pandas as pd


def identificar_variaveis_qee(
    estrutura
):
    """
    Identifica variáveis úteis para QEE.
    """

    resultado = {

        "tensao": [],

        "corrente": [],

        "potencia_ativa": [],

        "potencia_reativa": [],

        "potencia_fv": [],

        "potencia_gerador": [],

        "fp": [],

        "frequencia": []
    }

    for tipo in estrutura:

        for elemento in estrutura[tipo]:

            variaveis = estrutura[
                tipo
            ][
                elemento
            ]

            for variavel in variaveis:

                nome_tipo = (
                    variavel["tipo"]
                    .lower()
                )

                if "tensão" in nome_tipo:

                    resultado[
                        "tensao"
                    ].append(
                        variavel
                    )

                elif "corrente" in nome_tipo:

                    resultado[
                        "corrente"
                    ].append(
                        variavel
                    )

                elif (
                    "potência ativa"
                    in nome_tipo
                ):

                    resultado[
                        "potencia_ativa"
                    ].append(
                        variavel
                    )

                elif (
                    "potência reativa"
                    in nome_tipo
                ):

                    resultado[
                        "potencia_reativa"
                    ].append(
                        variavel
                    )

                elif (
                    "fotovoltaica"
                    in nome_tipo
                ):

                    resultado[
                        "potencia_fv"
                    ].append(
                        variavel
                    )

                elif (
                    "gerador"
                    in nome_tipo
                ):

                    resultado[
                        "potencia_gerador"
                    ].append(
                        variavel
                    )

                elif (
                    "fator de potência"
                    in nome_tipo
                ):

                    resultado[
                        "fp"
                    ].append(
                        variavel
                    )

                elif (
                    "frequência"
                    in nome_tipo
                ):

                    resultado[
                        "frequencia"
                    ].append(
                        variavel
                    )

    return resultado


def montar_card_fases(
    df,
    variaveis
):
    """
    Monta estrutura trifásica.
    """

    resultado = {}

    for variavel in variaveis:

        fase = variavel.get(
            "fase"
        )

        coluna = variavel[
            "coluna_original"
        ]

        unidade = variavel.get(
            "unidade_detectada"
        )

        if coluna not in df.columns:
            continue

        serie = pd.to_numeric(
            df[coluna],
            errors="coerce"
        )

        valor = serie.mean()

        if fase is None:
            fase = "Total"

        resultado[fase] = {

            "valor": valor,

            "unidade": unidade
        }

    return resultado


def calcular_desequilibrio_global(
    dados_tensao
):
    """
    Calcula desequilíbrio percentual.
    """

    fases = []

    for fase, info in dados_tensao.items():

        valor = info.get(
            "valor"
        )

        if valor is None:
            continue

        fases.append(valor)

    if len(fases) < 3:

        return None

    media = sum(fases) / len(fases)

    desvio_max = max([

        abs(v - media)

        for v in fases
    ])

    desequilibrio = (
        desvio_max
        / media
    ) * 100

    return desequilibrio