import numpy as np

def auto_scale(
    valor,
    unidade
):
    """
    Realiza escalonamento automático.
    """

    if valor is None:

        return (
            valor,
            unidade,
            1
        )

    unidades_base = {

        "W": [

            ("W", 1),

            ("kW", 1e3),

            ("MW", 1e6),

            ("GW", 1e9)
        ],

        "Var": [

            ("Var", 1),

            ("kVar", 1e3),

            ("MVar", 1e6)
        ],

        "VA": [

            ("VA", 1),

            ("kVA", 1e3),

            ("MVA", 1e6)
        ],

        "V": [

            ("V", 1),

            ("kV", 1e3)
        ],

        "A": [

            ("A", 1),

            ("kA", 1e3)
        ]
    }

    # NÃO escalar unidades
    # que já possuem prefixo

    unidades_bloqueadas = [

        "kW",
        "MW",
        "GW",

        "kVar",
        "MVar",

        "kVA",
        "MVA",

        "kV",
        "kA"
    ]

    if unidade in unidades_bloqueadas:

        return (
            valor,
            unidade,
            1
        )

    if unidade not in unidades_base:

        return (
            valor,
            unidade,
            1
        )

    valor_abs = abs(valor)

    escala_escolhida = (
        unidade,
        1
    )

    for nome, fator in unidades_base[
        unidade
    ]:

        if valor_abs >= fator:

            escala_escolhida = (
                nome,
                fator
            )

    unidade_final = (
        escala_escolhida[0]
    )

    fator_final = (
        escala_escolhida[1]
    )

    valor_final = (
        valor / fator_final
    )

    return (

        valor_final,

        unidade_final,

        fator_final
    )

def auto_scale_visual(
    serie,
    unidade
):
    """
    Escalonamento visual multinível
    para gráficos.
    """

    if unidade is None:

        return (
            serie,
            unidade
        )

    escalas = {

        "GW": [

            ("MW", 1e3),

            ("kW", 1e6),

            ("W", 1e9)
        ],

        "MW": [

            ("kW", 1e3),

            ("W", 1e6)
        ],

        "kW": [

            ("W", 1e3)
        ],

        "MVar": [

            ("kVar", 1e3),

            ("Var", 1e6)
        ],

        "kVar": [

            ("Var", 1e3)
        ],

        "MVA": [

            ("kVA", 1e3),

            ("VA", 1e6)
        ],

        "kVA": [

            ("VA", 1e3)
        ]
    }

    if unidade not in escalas:

        return (
            serie,
            unidade
        )

    valor_maximo = (
        serie.abs().max()
    )

    if 1 <= valor_maximo < 1000:

        return (
            serie,
            unidade
        )

    melhor_serie = serie

    melhor_unidade = unidade

    serie_atual = serie.copy()

    for nova_unidade, fator in escalas[
        unidade
    ]:

        serie_atual = (
            serie_atual * 1e3
        )

        novo_maximo = (
            serie_atual
            .abs()
            .max()
        )

        melhor_serie = (
            serie_atual
        )

        melhor_unidade = (
            nova_unidade
        )

        if 1 <= novo_maximo < 1000:

            break

    return (
        melhor_serie,
        melhor_unidade
    )