import json
import re
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def carregar_rotulos_medicoes():
    arquivo_rotulos = (
        BASE_DIR
        / "configs"
        / "rotulos_medicoes.json"
    )

    with open(
        arquivo_rotulos,
        "r",
        encoding="utf-8",
    ) as arquivo:
        return json.load(arquivo)


def obter_config_variavel(variavel):
    dados = carregar_rotulos_medicoes()
    variaveis = dados.get(
        "variaveis",
        {},
    )

    chave = str(variavel or "")

    if chave in variaveis:
        return variaveis[chave]

    chave_normalizada = chave.lower()

    for nome_variavel, config in variaveis.items():
        if nome_variavel.lower() == chave_normalizada:
            return config

    return {}


def obter_rotulo_variavel(variavel):
    config = obter_config_variavel(
        variavel
    )

    if config.get("rotulo"):
        return config["rotulo"]

    return str(
        variavel or ""
    ).replace(
        "_",
        " ",
    )


def obter_unidade_configurada(variavel):
    config = obter_config_variavel(
        variavel
    )

    return config.get(
        "unidade"
    )


def obter_nome_curto_elemento(
    target_id,
    origem=None,
):
    target = str(
        target_id or ""
    ).strip()
    target_lower = target.lower()
    origem_lower = str(
        origem or ""
    ).lower()

    match = re.search(
        r"pvpanel[_-]?(\d+)",
        target_lower,
    )

    if match:
        return f"Painel {match.group(1)}"

    match = re.search(
        r"inverter[_-]?(\d+)",
        target_lower,
    )

    if match:
        return f"Inversor {match.group(1)}"

    if target_lower.startswith("pv"):
        return f"PVSystem {target}"

    if "pvpanel" in origem_lower:
        return "Painel"

    if "inverter" in origem_lower:
        return "Inversor"

    return target or str(
        origem or ""
    )


def obter_categoria_equipamento(
    variavel,
    target_id=None,
):
    variavel_normalizada = str(
        variavel or ""
    ).strip().lower()
    target_normalizado = str(
        target_id or ""
    ).strip().lower()

    if variavel_normalizada == "p_dc":
        return "Potência DC dos Painéis"

    if variavel_normalizada == "p_ac":
        return "Potência Ativa AC dos Inversores"

    if variavel_normalizada == "q_ac":
        return "Potência Reativa AC dos Inversores"

    if variavel_normalizada == "temperature":
        return "Temperatura dos Painéis"

    if variavel_normalizada == "irradiance":
        return "Irradiância dos Painéis"

    if variavel_normalizada == "p_meas":
        return "Potência Ativa do PVSystem"

    if variavel_normalizada == "q_meas":
        return "Potência Reativa do PVSystem"

    if (
        target_normalizado.startswith("pv")
        and re.match(r"^p[123abc]?$", variavel_normalizada)
    ):
        return "Potência Ativa do PVSystem"

    if (
        target_normalizado.startswith("pv")
        and re.match(r"^q[123abc]?$", variavel_normalizada)
    ):
        return "Potência Reativa do PVSystem"

    if target_normalizado.startswith("pvpanel"):
        return "Dados dos Painéis"

    if target_normalizado.startswith("inverter"):
        return "Dados dos Inversores"

    if target_normalizado.startswith("pv"):
        return "Dados do PVSystem"

    return None


def montar_rotulo_serie(
    variavel_info,
    incluir_origem=False,
    incluir_unidade=True,
    compacto=False,
):
    if compacto:
        return obter_nome_curto_elemento(
            variavel_info.get("target_id"),
            variavel_info.get("origem_medicao"),
        )

    rotulo = variavel_info.get(
        "rotulo_variavel"
    ) or obter_rotulo_variavel(
        variavel_info.get("variavel_base")
        or variavel_info.get("variavel")
        or variavel_info.get("tipo")
    )

    fase = variavel_info.get(
        "fase"
    )

    if fase:
        rotulo = f"{rotulo} - {fase}"

    unidade = variavel_info.get(
        "unidade_detectada"
    )

    if incluir_unidade and unidade:
        rotulo = f"{rotulo} [{unidade}]"

    origem = variavel_info.get(
        "origem_medicao"
    )

    if incluir_origem and origem:
        rotulo = f"{origem} - {rotulo}"

    return rotulo
