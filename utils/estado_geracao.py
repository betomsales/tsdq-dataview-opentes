import pandas as pd

from utils.escalas import auto_scale
from utils.unidades import normalizar_unidade


EPSILON_POTENCIA = 1e-9

FONTES_ESTADO_GERACAO_FV = [
    {
        "categoria": "Potência Ativa do PVSystem",
        "base": "PVSystem",
        "grandeza": "P_meas",
        "regra": "P_meas > 0",
        "amostras": "Amostras com injeção",
        "positivo": "Injetando",
        "positivo_parcial": "Injetando em parte do período",
        "zero": "Sem injeção",
        "negativo": "Absorvendo",
        "negativo_parcial": "Absorvendo em parte do período",
        "misto": "Alternando sinal",
    },
    {
        "categoria": "Potência Ativa AC dos Inversores",
        "base": "Inversor",
        "grandeza": "P_ac",
        "regra": "P_ac > 0",
        "amostras": "Amostras com entrega AC",
        "positivo": "Entregando AC",
        "positivo_parcial": "Entregando AC em parte do período",
        "zero": "Sem entrega AC",
        "negativo": "Absorvendo AC",
        "negativo_parcial": "Absorvendo AC em parte do período",
        "misto": "Alternando sinal AC",
    },
    {
        "categoria": "Potência DC dos Painéis",
        "base": "Painel fotovoltaico",
        "grandeza": "P_dc",
        "regra": "P_dc > 0",
        "amostras": "Amostras com geração DC",
        "positivo": "Gerando DC",
        "positivo_parcial": "Gerando DC em parte do período",
        "zero": "Sem geração DC",
        "negativo": "Potência DC negativa",
        "negativo_parcial": "DC negativo em parte do período",
        "misto": "Alternando sinal DC",
    },
]


def _selecionar_fonte_prioritaria(itens):
    for fonte in FONTES_ESTADO_GERACAO_FV:
        selecionados = [
            item
            for item in itens
            if item.get("categoria_card") == fonte["categoria"]
        ]

        if selecionados:
            return fonte, selecionados

    return None, []


def _as_number(value):
    try:
        if pd.isna(value):
            return None

        return float(value)
    except (TypeError, ValueError):
        return None


def _converter_potencia_para_w(valor, unidade):
    unidade = normalizar_unidade(
        unidade
    ) or "W"
    fatores = {
        "W": 1.0,
        "kW": 1e3,
        "MW": 1e6,
        "GW": 1e9,
    }

    if unidade not in fatores:
        return valor, unidade

    return valor * fatores[unidade], "W"


def _formatar_valor(valor, unidade):
    valor = _as_number(
        valor
    )

    if valor is None:
        return "Não identificado"

    unidade = normalizar_unidade(
        unidade
    ) or ""

    if unidade in {"W", "Var", "VA", "V", "A"}:
        valor, unidade, _ = auto_scale(
            valor,
            unidade,
        )

    return f"{valor:.4f} {unidade}".strip()


def _cor_por_estado(valor):
    if valor is None:
        return "#7f8c8d"

    if valor > EPSILON_POTENCIA:
        return "#27ae60"

    if valor < -EPSILON_POTENCIA:
        return "#e67e22"

    return "#95a5a6"


def _classificar_valor(valor, fonte):
    valor = _as_number(
        valor
    )

    if valor is None:
        return "Não identificado", "#7f8c8d"

    if valor > EPSILON_POTENCIA:
        return fonte["positivo"], "#27ae60"

    if valor < -EPSILON_POTENCIA:
        return fonte["negativo"], "#e67e22"

    return fonte["zero"], "#95a5a6"


def _classificar_serie(serie, fonte):
    valores = serie.dropna()

    if valores.empty:
        return "Não identificado", "#7f8c8d", None

    positivos = int(
        (valores > EPSILON_POTENCIA).sum()
    )
    negativos = int(
        (valores < -EPSILON_POTENCIA).sum()
    )
    total = len(
        valores
    )
    percentual_positivo = (
        positivos / total
    ) * 100

    if positivos and negativos:
        return fonte["misto"], "#f39c12", percentual_positivo

    if positivos:
        estado = (
            fonte["positivo"]
            if positivos == total
            else fonte["positivo_parcial"]
        )
        return estado, "#27ae60", percentual_positivo

    if negativos:
        estado = (
            fonte["negativo"]
            if negativos == total
            else fonte["negativo_parcial"]
        )
        return estado, "#e67e22", percentual_positivo

    return fonte["zero"], "#95a5a6", percentual_positivo


def montar_estado_geracao_fv_medicoes(
    medicoes,
    renderizar_sem_dados=False,
):
    fonte, selecionados = _selecionar_fonte_prioritaria(
        medicoes
    )

    if fonte is None:
        if not renderizar_sem_dados:
            return None

        return {
            "titulo": "Estado da Geração FV",
            "cor": "#7f8c8d",
            "rows": [
                ("Base", "Não identificada"),
                ("Estado", "Sem medição ativa"),
            ],
        }

    valores = []

    for medicao in selecionados:
        valor = _as_number(
            medicao.get("valor")
        )

        if valor is None:
            continue

        valor_w, unidade_base = _converter_potencia_para_w(
            valor,
            medicao.get("unidade"),
        )
        valores.append(
            (valor_w, unidade_base)
        )

    if not valores:
        valor_total = None
        unidade_total = "W"
    else:
        unidade_total = valores[0][1]
        valor_total = sum(
            valor
            for valor, _ in valores
        )

    estado, cor = _classificar_valor(
        valor_total,
        fonte,
    )

    return {
        "titulo": "Estado da Geração FV",
        "cor": cor,
        "rows": [
            ("Base", fonte["base"]),
            ("Grandeza", fonte["grandeza"]),
            ("Potência", _formatar_valor(valor_total, unidade_total)),
            ("Estado", estado),
            ("Regra", fonte["regra"]),
        ],
    }


def montar_estado_geracao_fv_series(
    df,
    variaveis,
):
    fonte, selecionadas = _selecionar_fonte_prioritaria(
        variaveis
    )

    if fonte is None:
        return None

    series = []

    for variavel in selecionadas:
        coluna = variavel.get(
            "coluna_original"
        )

        if coluna not in df.columns:
            continue

        serie = pd.to_numeric(
            df[coluna],
            errors="coerce",
        )
        fator = 1.0
        unidade = normalizar_unidade(
            variavel.get("unidade_detectada")
        ) or "W"

        if unidade == "kW":
            fator = 1e3
        elif unidade == "MW":
            fator = 1e6
        elif unidade == "GW":
            fator = 1e9

        series.append(
            serie * fator
        )

    if not series:
        return {
            "titulo": "Estado da Geração FV",
            "cor": "#7f8c8d",
            "rows": [
                ("Base", fonte["base"]),
                ("Grandeza", fonte["grandeza"]),
                ("Estado", "Sem série ativa"),
                ("Regra", fonte["regra"]),
            ],
        }

    serie_total = pd.concat(
        series,
        axis=1,
    ).sum(
        axis=1,
        min_count=1,
    )
    valores_validos = serie_total.dropna()
    media = (
        valores_validos.mean()
        if not valores_validos.empty
        else None
    )
    estado, cor, percentual_positivo = _classificar_serie(
        serie_total,
        fonte,
    )
    percentual_texto = (
        "Não identificado"
        if percentual_positivo is None
        else f"{percentual_positivo:.1f}%"
    )

    return {
        "titulo": "Estado da Geração FV",
        "cor": cor,
        "rows": [
            ("Base", fonte["base"]),
            ("Grandeza", fonte["grandeza"]),
            ("P médio", _formatar_valor(media, "W")),
            (fonte["amostras"], percentual_texto),
            ("Estado", estado),
            ("Regra", fonte["regra"]),
        ],
    }