import math
import re
import unicodedata

import pandas as pd

from utils.prodist import classificar_tensao, obter_limites_prodist
from utils.unidades import normalizar_unidade


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


def eh_magnitude_tensao(variavel):
    tipo = _normalizar_texto(variavel.get("tipo"))
    unidade = normalizar_unidade(variavel.get("unidade_detectada"))
    nome = _normalizar_texto(
        variavel.get("variavel_base")
        or variavel.get("coluna_original", "")
    )

    return (
        "tensao" in tipo
        and "angulo" not in tipo
        and unidade in {"pu", "V", "kV"}
        and not re.search(r"(?:_|-)(?:ang|angle|angulo|graus)(?:_|$)", nome)
    )


def _codigo_fase_tensao(fase):
    fase = str(fase if fase is not None else "").strip().upper()
    fase = fase.removeprefix("V")
    return {
        "1": "A", "2": "B", "3": "C",
        "AN": "A", "BN": "B", "CN": "C",
        "12": "AB", "23": "BC", "31": "CA",
        "21": "BA", "32": "CB", "13": "AC",
    }.get(fase, fase)


def rotulo_fase_tensao(variavel):
    fase = _codigo_fase_tensao(variavel.get("fase"))
    return f"Fase {fase}" if fase else "Sem fase"


def motivo_fase_ausente(variavel, valores):
    """Usa a topologia ou uma serie nao vazia inteiramente NaN, nunca zeros."""
    fase = _codigo_fase_tensao(variavel.get("fase"))
    if fase not in {"A", "B", "C", "AB", "BA", "AC", "CA", "BC", "CB"}:
        return None

    fases_presentes = variavel.get("fases_presentes")
    if isinstance(fases_presentes, (list, tuple, set)):
        fases_json = {_codigo_fase_tensao(item) for item in fases_presentes}
        if fases_json <= {"A", "B", "C", "0"}:
            if not set(fase) <= fases_json:
                return "Fase não conectada no JSON"

    if not valores.empty and valores.isna().all():
        return "Ausência inferida pela série inteiramente NaN"

    return None


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
                    if eh_magnitude_tensao(variavel):
                        resultado["tensao"].append(variavel)
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
        ).replace([math.inf, -math.inf], float("nan"))
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

        if valor is None or not math.isfinite(valor):
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
    valor,
    limites=None,
):
    return classificar_tensao(valor, limites)


def _preparar_tensoes_pu(df, variaveis_tensao, referencias_tensao):
    dados = pd.DataFrame(index=df.index)
    variaveis = []
    descartadas = []
    fases_ausentes = []
    colunas_vistas = set()

    for variavel in variaveis_tensao:
        coluna = variavel.get("coluna_original")

        if coluna in colunas_vistas:
            continue
        colunas_vistas.add(coluna)

        if coluna not in df.columns:
            motivo = "Coluna ausente no arquivo"
        elif not eh_magnitude_tensao(variavel):
            motivo = "Grandeza ou unidade incompatível com tensão"
        else:
            motivo = None

        if motivo is None:
            valores = pd.to_numeric(df[coluna], errors="coerce").replace(
                [math.inf, -math.inf], float("nan"),
            )
            motivo_ausencia = motivo_fase_ausente(variavel, df[coluna])
            if motivo_ausencia:
                fases_ausentes.append({
                    "fase": rotulo_fase_tensao(variavel),
                    "coluna": coluna,
                    "motivo": motivo_ausencia,
                })
                continue

        unidade = normalizar_unidade(variavel.get("unidade_detectada"))
        referencia = 1.0

        if motivo is None and unidade != "pu":
            try:
                referencia = float(referencias_tensao.get(coluna))
            except (TypeError, ValueError):
                referencia = 0.0

            if not math.isfinite(referencia) or referencia <= 0:
                motivo = "Tensão de referência não definida"

        if motivo:
            descartadas.append({"coluna": coluna, "motivo": motivo})
            continue

        dados[coluna] = (valores / referencia).replace(
            [math.inf, -math.inf], float("nan"),
        )
        variaveis.append({
            **variavel,
            "unidade_original": unidade,
            "unidade_detectada": "pu",
        })

    return dados, variaveis, descartadas, fases_ausentes


def calcular_drp_drc_por_fase(
    df,
    variaveis_tensao,
    limites=None,
    referencias_tensao=None,
):
    """Decompõe os indicadores e resume cada um pela fase de maior total."""
    limites = dict(obter_limites_prodist() if limites is None else limites)
    chaves = ("critico_min", "adequado_min", "adequado_max", "critico_max")
    valores_limite = [float(limites[chave]) for chave in chaves]

    if (
        not all(math.isfinite(valor) for valor in valores_limite)
        or valores_limite != sorted(valores_limite)
    ):
        raise ValueError("Os limites de tensão devem ser finitos e ordenados.")
    limites = dict(zip(chaves, valores_limite))

    dados, variaveis, descartadas, fases_ausentes = _preparar_tensoes_pu(
        df, variaveis_tensao, referencias_tensao or {},
    )
    fases = []

    for variavel in variaveis:
        coluna = variavel["coluna_original"]
        serie = dados[coluna].dropna()
        total = len(serie)

        if variavel["unidade_original"] != "pu":
            # Evita trocar de faixa pelo arredondamento da conversao a pu.
            for limite in valores_limite:
                proximas = (serie - limite).abs() <= 4 * math.ulp(limite)
                serie = serie.mask(proximas, limite)

        contagens = {
            "drp_sub": int(
                ((serie >= limites["critico_min"]) & (serie < limites["adequado_min"])).sum()
            ),
            "drp_sobre": int(
                ((serie > limites["adequado_max"]) & (serie <= limites["critico_max"])).sum()
            ),
            "drc_sub": int((serie < limites["critico_min"]).sum()),
            "drc_sobre": int((serie > limites["critico_max"]).sum()),
        }
        resultado = {
            "fase": rotulo_fase_tensao(variavel),
            "coluna": coluna,
            "amostras_validas": total,
            "amostras_invalidas": len(df) - total,
            "contagens": contagens,
        }

        for indicador in ("drp", "drc"):
            sub = contagens[f"{indicador}_sub"]
            sobre = contagens[f"{indicador}_sobre"]
            resultado[indicador] = {
                "total": (sub + sobre) / total * 100 if total else None,
                "subtensao": sub / total * 100 if total else None,
                "sobretensao": sobre / total * 100 if total else None,
            }

        fases.append(resultado)

    fases.sort(key=lambda fase: (fase["fase"], fase["coluna"]))
    com_dados = [fase for fase in fases if fase["amostras_validas"]]
    resumo = {
        indicador: max(com_dados, key=lambda fase: fase[indicador]["total"])
        if com_dados else None
        for indicador in ("drp", "drc")
    }

    return {
        "fases": fases,
        "fases_ausentes": sorted(
            fases_ausentes, key=lambda fase: (fase["fase"], fase["coluna"]),
        ),
        "resumo": resumo,
        "limites": limites,
        "dados_pu": dados,
        "variaveis": variaveis,
        "descartadas": descartadas,
    }


def calcular_drp_drc_global(
    df,
    variaveis_tensao,
    limites=None,
    referencias_tensao=None,
):
    """Mantém o retorno DRP/DRC para consumidores da API anterior."""
    resultado = calcular_drp_drc_por_fase(
        df, variaveis_tensao, limites, referencias_tensao,
    )
    return tuple(
        resultado["resumo"][indicador][indicador]["total"]
        if resultado["resumo"][indicador] else None
        for indicador in ("drp", "drc")
    )


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
