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