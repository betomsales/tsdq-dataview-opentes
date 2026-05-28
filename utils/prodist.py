import re


CLASSES_PRODIST = {
    "Alta tensão (>= 230 kV)": {
        "adequado_min": 0.95,
        "adequado_max": 1.05,
        "critico_min": 0.93,
        "critico_max": 1.07,
    },
    "Alta tensão (69 kV a < 230 kV)": {
        "adequado_min": 0.95,
        "adequado_max": 1.05,
        "critico_min": 0.90,
        "critico_max": 1.07,
    },
    "Média tensão (> 2,3 kV a < 69 kV)": {
        "adequado_min": 0.93,
        "adequado_max": 1.05,
        "critico_min": 0.90,
        "critico_max": 1.05,
    },
}


LIMITES_BT_NOMINAIS = {
    "BT 220 V fase-fase": {
        "adequado_min": 202.0,
        "adequado_max": 231.0,
        "critico_min": 191.0,
        "critico_max": 233.0,
    },
    "BT 127 V fase-neutro": {
        "adequado_min": 117.0,
        "adequado_max": 133.0,
        "critico_min": 110.0,
        "critico_max": 135.0,
    },
    "BT 380 V fase-fase": {
        "adequado_min": 350.0,
        "adequado_max": 399.0,
        "critico_min": 331.0,
        "critico_max": 403.0,
    },
    "BT 220 V fase-neutro": {
        "adequado_min": 202.0,
        "adequado_max": 231.0,
        "critico_min": 191.0,
        "critico_max": 233.0,
    },
}


def converter_limites_para_unidade(
    limites,
    unidade
):
    """
    Converte limites absolutos em V para a unidade exibida no grafico.
    """

    if unidade == "kV":

        return {
            chave: valor / 1000
            for chave, valor in limites.items()
        }

    return limites


def obter_limites_prodist(
    classe="Média tensão (> 2,3 kV a < 69 kV)",
    tensao_referencia=None,
    unidade="pu",
    limites_customizados=None
):
    """
    Retorna limites PRODIST na mesma unidade da serie plotada.
    """

    if limites_customizados:

        return limites_customizados

    if classe in LIMITES_BT_NOMINAIS:

        return converter_limites_para_unidade(
            LIMITES_BT_NOMINAIS[classe],
            unidade
        )

    fatores = CLASSES_PRODIST.get(
        classe,
        CLASSES_PRODIST["Média tensão (> 2,3 kV a < 69 kV)"]
    )

    if unidade == "pu":

        return fatores.copy()

    if tensao_referencia is None:

        raise ValueError(
            "Informe a tensão de referência para limites PRODIST em V ou kV."
        )

    return {
        chave: fator * tensao_referencia
        for chave, fator in fatores.items()
    }


def inferir_classe_prodist(
    serie,
    unidade="pu"
):
    """
    Infere a classe PRODIST pela magnitude da tensao medida.
    """

    if unidade == "pu":

        return None

    valores = serie.dropna()

    if valores.empty:

        return "Média tensão (> 2,3 kV a < 69 kV)"

    valor_referencia = float(
        valores.abs().median()
    )

    if unidade == "V":

        valor_kv = valor_referencia / 1000

    else:

        valor_kv = valor_referencia

    if valor_kv <= 2.3:

        valor_v = valor_kv * 1000

        opcoes_bt = [
            (127, "BT 127 V fase-neutro"),
            (220, "BT 220 V fase-fase"),
            (380, "BT 380 V fase-fase"),
        ]

        _, classe_bt = min(
            opcoes_bt,
            key=lambda opcao: abs(valor_v - opcao[0])
        )

        return classe_bt

    if valor_kv >= 230:

        return "Alta tensão (>= 230 kV)"

    if valor_kv >= 69:

        return "Alta tensão (69 kV a < 230 kV)"

    return "Média tensão (> 2,3 kV a < 69 kV)"


def inferir_natureza_tensao(
    variavel_info
):
    """
    Infere se a medição é fase-neutro, fase-fase ou genérica.
    """

    fase = (
        variavel_info.get("fase")
        or
        ""
    ).upper()

    prodist_cfg = (
        variavel_info
        .get("metadados", {})
        .get("prodist", {})
    )

    fase_neutro = set(
        prodist_cfg.get(
            "fase_neutro",
            []
        )
    )

    fase_fase = set(
        prodist_cfg.get(
            "fase_fase",
            []
        )
    )

    if fase in fase_fase:

        return "fase-fase"

    if fase in fase_neutro:

        return "fase-neutro"

    if re.match(r"^V(AB|BC|CA|12|23|31)$", fase):

        return "fase-fase"

    if re.match(r"^V(AN|BN|CN|A|B|C|1|2|3|M)$", fase):

        return "fase-neutro"

    return "generica"


def extrair_tensao_nominal_kv(
    variavel_info
):
    """
    Extrai tensão nominal/base do nome da coluna ou elemento mapeado.
    """

    textos = [
        variavel_info.get("coluna_original", ""),
        variavel_info.get("elemento", ""),
    ]

    texto = " ".join(textos)

    padroes = [
        r"(\d+(?:[\.,]\d+)?)\s*kV",
        r"(\d+)\s*k\s*(\d+)",
        r"(\d+(?:[\.,]\d+)?)\s*V",
    ]

    for padrao in padroes:

        for match in re.finditer(
            padrao,
            texto,
            re.IGNORECASE
        ):

            if len(match.groups()) == 2:

                valor = float(
                    f"{match.group(1)}.{match.group(2)}"
                )

                return valor

            valor = float(
                match.group(1).replace(
                    ",",
                    "."
                )
            )

            if "kv" in match.group(0).lower() or "k" in match.group(0).lower():

                return valor

            return valor / 1000

    prodist_cfg = (
        variavel_info
        .get("metadados", {})
        .get("prodist", {})
    )

    nominais = prodist_cfg.get(
        "nominais_kv",
        []
    )

    for match in re.finditer(
        r"(?<!\d)(\d+(?:[\.,]\d+)?)(?!\d)",
        texto
    ):

        valor = float(
            match.group(1).replace(
                ",",
                "."
            )
        )

        for nominal in nominais:

            nominal = float(nominal)

            if (
                abs(valor - nominal) < 1e-9
                or
                abs((valor / 1000) - nominal) < 1e-9
            ):

                return nominal

    for nominal in nominais:

        nominal_txt = str(nominal).replace(
            ".",
            r"[\.,]"
        )

        if re.search(
            rf"(^|[^\d]){nominal_txt}($|[^\d])",
            texto
        ):

            return float(nominal)

    return None


def classe_por_tensao_nominal(
    tensao_nominal_kv,
    natureza="generica"
):
    """
    Determina a classe PRODIST a partir da tensão nominal explícita.
    """

    if tensao_nominal_kv is None:

        return None

    if tensao_nominal_kv <= 2.3:

        nominal_v = tensao_nominal_kv * 1000

        if natureza == "fase-fase":

            if abs(nominal_v - 380) < abs(nominal_v - 220):

                return "BT 380 V fase-fase"

            return "BT 220 V fase-fase"

        if natureza == "fase-neutro":

            if abs(nominal_v - 220) < abs(nominal_v - 127):

                return "BT 220 V fase-neutro"

            return "BT 127 V fase-neutro"

        if abs(nominal_v - 127) <= abs(nominal_v - 220):

            return "BT 127 V fase-neutro"

        return "BT 220 V fase-fase"

    if tensao_nominal_kv >= 230:

        return "Alta tensão (>= 230 kV)"

    if tensao_nominal_kv >= 69:

        return "Alta tensão (69 kV a < 230 kV)"

    return "Média tensão (> 2,3 kV a < 69 kV)"


def inferir_metadados_prodist(
    variavel_info,
    unidade_grafico
):
    """
    Consolida a inferência PRODIST usando o mapeamento sem alterar valores.
    """

    natureza = inferir_natureza_tensao(
        variavel_info
    )

    tensao_nominal_kv = extrair_tensao_nominal_kv(
        variavel_info
    )

    classe = classe_por_tensao_nominal(
        tensao_nominal_kv,
        natureza
    )

    aplicavel = classe is not None

    origem = [
        "mapeamento_unidade",
        "mapeamento_fase",
    ]

    if tensao_nominal_kv is not None:

        origem.append(
            "nome_coluna_ou_elemento"
        )

    return {
        "unidade": unidade_grafico,
        "natureza": natureza,
        "tensao_nominal_kv": tensao_nominal_kv,
        "classe": classe,
        "limites_aplicaveis": aplicavel,
        "origem": origem,
        "confianca": "alta" if aplicavel else "media",
    }


def classificar_tensao(
    valor,
    limites=None
):
    """
    Classifica tensão conforme limites PRODIST informados.
    """

    if limites is None:

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
