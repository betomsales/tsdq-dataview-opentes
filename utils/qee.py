import unicodedata

import pandas as pd


def _normalizar_texto(texto):
    texto = str(texto or "")
    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )
    texto = texto.encode(
        "ascii",
        errors="ignore",
    ).decode(
        "ascii",
    )
    return texto.lower()


def identificar_variaveis_qee(
    estrutura
):
    resultado = {
        "tensao": [],
        "corrente": [],
        "potencia_ativa": [],
        "potencia_reativa": [],
        "potencia_fv": [],
        "potencia_gerador": [],
        "temperatura_pv": [],
        "irradiancia": [],
        "fp": [],
        "frequencia": [],
    }

    for tipo in estrutura:
        for elemento in estrutura[tipo]:
            variaveis = estrutura[tipo][elemento]

            for variavel in variaveis:
                nome_tipo = _normalizar_texto(
                    variavel["tipo"]
                )

                if "tensao" in nome_tipo:
                    resultado["tensao"].append(
                        variavel
                    )
                elif (
                    "angulo" in nome_tipo
                    and "corrente" in nome_tipo
                ):
                    continue
                elif "corrente" in nome_tipo:
                    resultado["corrente"].append(
                        variavel
                    )
                elif "potencia ativa" in nome_tipo:
                    resultado["potencia_ativa"].append(
                        variavel
                    )
                elif "potencia reativa" in nome_tipo:
                    resultado["potencia_reativa"].append(
                        variavel
                    )
                elif "fotovoltaica" in nome_tipo:
                    resultado["potencia_fv"].append(
                        variavel
                    )
                elif "temperatura" in nome_tipo:
                    resultado["temperatura_pv"].append(
                        variavel
                    )
                elif "irradiancia" in nome_tipo:
                    resultado["irradiancia"].append(
                        variavel
                    )
                elif "gerador" in nome_tipo:
                    resultado["potencia_gerador"].append(
                        variavel
                    )
                elif "fator de potencia" in nome_tipo:
                    resultado["fp"].append(
                        variavel
                    )
                elif "frequencia" in nome_tipo:
                    resultado["frequencia"].append(
                        variavel
                    )

    return resultado


def montar_card_fases(
    df,
    variaveis
):
    resultado = {}

    for variavel in variaveis:
        fase = variavel.get("fase")
        coluna = variavel["coluna_original"]
        unidade = variavel.get("unidade_detectada")

        if coluna not in df.columns:
            continue

        serie = pd.to_numeric(
            df[coluna],
            errors="coerce",
        )
        valor = serie.mean()

        if fase is None:
            fase = variavel.get(
                "rotulo_card",
                "Total",
            )
        elif (
            variavel.get("target_kind") in {"pv", "pv_equipment"}
            and variavel.get("rotulo_card")
        ):
            fase = f"{variavel['rotulo_card']} - {fase}"

        resultado[fase] = {
            "valor": valor,
            "unidade": unidade,
        }

    return resultado


def calcular_desequilibrio_global(
    dados_tensao
):
    fases = []

    for _, info in dados_tensao.items():
        valor = info.get("valor")

        if valor is None:
            continue

        fases.append(valor)

    if len(fases) < 3:
        return None

    media = sum(fases) / len(fases)

    if media == 0:
        return None

    desvio_max = max(
        abs(valor - media)
        for valor in fases
    )

    return (desvio_max / media) * 100


def classificar_tensao_prodist(
    valor
):
    if valor is None:
        return None

    if 0.93 <= valor <= 1.05:
        return "adequado"

    if (
        0.90 <= valor < 0.93
        or 1.05 < valor <= 1.08
    ):
        return "precario"

    return "critico"


def calcular_drp_drc_global(
    df,
    variaveis_tensao
):
    total = 0
    precario = 0
    critico = 0

    for variavel in variaveis_tensao:
        coluna = variavel["coluna_original"]

        if coluna not in df.columns:
            continue

        serie = pd.to_numeric(
            df[coluna],
            errors="coerce",
        )

        for valor in serie:
            if pd.isna(valor):
                continue

            classificacao = classificar_tensao_prodist(
                valor
            )
            total += 1

            if classificacao == "precario":
                precario += 1
            elif classificacao == "critico":
                critico += 1

    if total == 0:
        return None, None

    drp = (precario / total) * 100
    drc = (critico / total) * 100

    return drp, drc


def calcular_indicadores_temporais(
    df,
    variaveis
):
    valores = []

    for variavel in variaveis:
        coluna = variavel["coluna_original"]

        if coluna not in df.columns:
            continue

        serie = pd.to_numeric(
            df[coluna],
            errors="coerce",
        ).dropna()

        valores.extend(
            serie.tolist()
        )

    if len(valores) == 0:
        return None

    serie = pd.Series(valores)

    return {
        "minimo": serie.min(),
        "maximo": serie.max(),
        "media": serie.mean(),
        "desvio": serie.std(),
    }
