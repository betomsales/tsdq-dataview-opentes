def normalizar_unidade(unidade):
    """
    Padroniza unidades vindas do mapeamento.
    """

    if unidade is None:
        return None

    unidade = str(unidade).strip()

    mapa = {
        "w": "W",
        "kw": "kW",
        "mw": "MW",
        "gw": "GW",

        "var": "Var",
        "kvar": "kVar",
        "mvar": "MVar",

        "va": "VA",
        "kva": "kVA",
        "mva": "MVA",

        "v": "V",
        "kv": "kV",
        "pu": "pu",

        "a": "A",
        "ka": "kA",

        "hz": "Hz",
        "%": "%"
    }

    return mapa.get(
        unidade.lower(),
        unidade
    )


def remover_unidade_do_tipo(tipo_variavel):
    """
    Remove unidade textual do nome da variável.
    """

    if not tipo_variavel:
        return tipo_variavel

    unidades = [
        "(GW)",
        "(MW)",
        "(kW)",
        "(W)",
        "(MVar)",
        "(kVar)",
        "(Var)",
        "(MVA)",
        "(kVA)",
        "(VA)",
        "(kV)",
        "(V)",
        "(pu)",
        "(A)",
        "(kA)"
    ]

    resultado = tipo_variavel

    for unidade in unidades:
        resultado = resultado.replace(
            unidade,
            ""
        )

    return resultado.strip()