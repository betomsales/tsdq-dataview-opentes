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

        "c": "°C",
        "°c": "°C",
        "celsius": "°C",
        "wm2": "W/m²",
        "w/m2": "W/m²",
        "w/m²": "W/m²",

        "hz": "Hz",
        "%": "%"
    }

    return mapa.get(
        unidade.lower(),
        unidade
    )


def inferir_unidade_variavel(
    variavel,
    target_kind=None,
):
    """
    Infere a unidade quando a coluna informa a grandeza, mas não a unidade.
    """

    if not variavel:
        return None

    variavel_normalizada = str(
        variavel
    ).strip().lower()

    unidades_por_variavel = {
        "p_meas": "W",
        "p_ac": "W",
        "p_dc": "W",
        "q_meas": "var",
        "q_ac": "var",
        "temperature": "°C",
        "temperatura": "°C",
        "irradiance": "W/m²",
        "irradiancia": "W/m²",
        "irradiância": "W/m²",
    }

    if variavel_normalizada in unidades_por_variavel:
        return unidades_por_variavel[variavel_normalizada]

    if (
        target_kind in {"pv", "pv_equipment"}
        and (
            variavel_normalizada.startswith("p_")
            or variavel_normalizada in {"p", "p1", "p2", "p3"}
        )
    ):
        return "W"

    if (
        target_kind in {"pv", "pv_equipment"}
        and (
            variavel_normalizada.startswith("q_")
            or variavel_normalizada in {"q", "q1", "q2", "q3"}
        )
    ):
        return "var"

    return None


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
