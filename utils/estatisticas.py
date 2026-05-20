import numpy as np

from utils.prodist import (
    classificar_tensao
)


def calcular_estatisticas(
    df_plot
):
    """
    Estatísticas básicas.
    """

    serie = df_plot[
        "Valor"
    ].dropna()

    return {

        "maximo": serie.max(),

        "minimo": serie.min(),

        "media": serie.mean(),

        "rms": np.sqrt(
            np.mean(
                serie ** 2
            )
        )
    }


def calcular_drp_drc(
    df_plot
):
    """
    Calcula DRP e DRC.
    """

    serie = df_plot[
        "Valor"
    ].dropna()

    total = len(serie)

    if total == 0:

        return {

            "drp": 0,

            "drc": 0,

            "violacoes": 0
        }

    precario = 0

    critico = 0

    for valor in serie:

        classificacao = (
            classificar_tensao(valor)
        )

        if classificacao == "precario":

            precario += 1

        elif classificacao == "critico":

            critico += 1

    drp = (
        precario / total
    ) * 100

    drc = (
        critico / total
    ) * 100

    return {

        "drp": drp,

        "drc": drc,

        "violacoes": (
            precario + critico
        )
    }


def calcular_desequilibrio(
    df_multiserie
):
    """
    Calcula desequilíbrio percentual.
    """

    colunas = [

        c

        for c in df_multiserie.columns

        if c != "Tempo"
    ]

    if len(colunas) < 3:

        return None

    medias = []

    for coluna in colunas[:3]:

        medias.append(
            df_multiserie[
                coluna
            ].mean()
        )

    media_total = np.mean(
        medias
    )

    desvio_max = max([

        abs(v - media_total)

        for v in medias
    ])

    desequilibrio = (
        desvio_max
        / media_total
    ) * 100

    return desequilibrio