import json
import re

from pathlib import Path

from utils.unidades import normalizar_unidade

BASE_DIR = Path(__file__).resolve().parent.parent

def carregar_mapeamento():

    arquivo_mapeamento = (
        BASE_DIR
        / "configs"
        / "mapeamento.json"
    )

    with open(
        arquivo_mapeamento,
        "r",
        encoding="utf-8"
    ) as arquivo:

        return json.load(arquivo)


def mapear_colunas(colunas, mapeamento):
    """
    Mapeia semanticamente as colunas do CSV.
    """

    resultado = {}

    for coluna in colunas:

        coluna_limpa = coluna.strip()

        for tipo, dados in mapeamento.items():

            if tipo.startswith("_"):
                continue

            regex = dados.get("regex")

            if not regex:
                continue

            match = re.match(
                regex,
                coluna_limpa,
                re.IGNORECASE
            )

            if not match:
                continue

            grupos = match.groups()

            elemento = grupos[0].strip()

            fase = None
            unidade = None

            if dados.get("tem_fase") and len(grupos) >= 2:

                fase_raw = grupos[1]

                if fase_raw:

                    if not fase_raw.upper().startswith(
                        dados.get("prefixo", "").upper()
                    ):

                        fase = (
                            dados.get("prefixo", "")
                            + fase_raw.upper()
                        )

                    else:

                        fase = fase_raw.upper()

            if dados.get("tem_fase"):

                if len(grupos) >= 3:
                    unidade = grupos[2]

            else:

                if len(grupos) >= 2:
                    unidade = grupos[1]

            resultado[coluna] = {

                "tipo": tipo,

                "elemento": elemento,

                "fase": fase,

                "unidade_detectada": normalizar_unidade(
                    unidade
                ),

                "coluna_original": coluna,

                "metadados": dados
            }

            break

    return resultado