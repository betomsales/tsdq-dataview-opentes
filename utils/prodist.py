def obter_limites_prodist():
    """
    Limites PRODIST MT.
    """

    return {

        "adequado_min": 0.93,

        "critico_min": 0.90,

        "adequado_max": 1.05
    }


def classificar_tensao(valor):
    """
    Classifica tensão conforme PRODIST.
    """

    limites = obter_limites_prodist()

    if (
        valor < limites["critico_min"]
        or
        valor > limites["critico_max"]
    ):

        return "critico"

    elif (
        valor < limites["adequado_min"]
        or
        valor > limites["adequado_max"]
    ):

        return "precario"

    return "adequado"