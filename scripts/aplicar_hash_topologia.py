"""Aplica no JSON de topologia o hash SHA-256 de um arquivo CSV.

Este script e independente da interface Streamlit. Ele foi pensado para ser
executado manualmente quando for necessario vincular uma topologia aos
resultados temporais da co-simulacao.

Exemplo:
    python scripts/aplicar_hash_topologia.py --csv resultados.csv --json topologia.json

Por padrao, o script cria uma copia do JSON com o sufixo "_com_hash".
Use --sobrescrever para atualizar o arquivo JSON original.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def calcular_sha256(caminho_csv: Path) -> str:
    sha256 = hashlib.sha256()

    with caminho_csv.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            sha256.update(bloco)

    return sha256.hexdigest().upper()


def carregar_json(caminho_json: Path) -> dict:
    with caminho_json.open("r", encoding="utf-8-sig") as arquivo:
        dados = json.load(arquivo)

    if not isinstance(dados, dict):
        raise ValueError("O JSON de topologia precisa ter um objeto na raiz.")

    return dados


def aplicar_hash_no_json(
    topology_data: dict,
    caminho_csv: Path,
    caminho_json: Path,
    csv_hash: str,
) -> dict:
    metadata = topology_data.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    metadata.update(
        {
            "scenario_id": metadata.get("scenario_id", caminho_json.stem),
            "results_file": caminho_csv.name,
            "results_sha256": csv_hash,
            "hash_algorithm": "sha256",
            "hash_generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    topology_data["metadata"] = metadata

    return topology_data


def definir_saida(
    caminho_json: Path,
    caminho_saida: Path | None,
    sobrescrever: bool,
) -> Path:
    if sobrescrever:
        return caminho_json

    if caminho_saida is not None:
        return caminho_saida

    return caminho_json.with_name(f"{caminho_json.stem}_com_hash.json")


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calcula o SHA-256 de um CSV e grava esse vinculo no metadata "
            "do JSON de topologia."
        )
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Caminho do arquivo CSV de resultados da co-simulacao.",
    )
    parser.add_argument(
        "--json",
        required=True,
        type=Path,
        help="Caminho do arquivo JSON de topologia.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        help=(
            "Caminho do JSON de saida. Se omitido, cria uma copia com "
            "sufixo _com_hash."
        ),
    )
    parser.add_argument(
        "--sobrescrever",
        action="store_true",
        help="Atualiza o arquivo JSON original em vez de criar uma copia.",
    )

    return parser


def main() -> int:
    parser = criar_parser()
    args = parser.parse_args()

    caminho_csv = args.csv.resolve()
    caminho_json = args.json.resolve()
    caminho_saida = args.saida.resolve() if args.saida else None

    if args.sobrescrever and caminho_saida is not None:
        parser.error("Use --saida ou --sobrescrever, nao os dois juntos.")

    if not caminho_csv.is_file():
        parser.error(f"CSV nao encontrado: {caminho_csv}")

    if not caminho_json.is_file():
        parser.error(f"JSON nao encontrado: {caminho_json}")

    csv_hash = calcular_sha256(caminho_csv)
    topology_data = carregar_json(caminho_json)
    topology_data = aplicar_hash_no_json(
        topology_data,
        caminho_csv,
        caminho_json,
        csv_hash,
    )

    caminho_final = definir_saida(
        caminho_json,
        caminho_saida,
        args.sobrescrever,
    )
    caminho_final.parent.mkdir(parents=True, exist_ok=True)

    with caminho_final.open("w", encoding="utf-8") as arquivo:
        json.dump(
            topology_data,
            arquivo,
            ensure_ascii=False,
            indent=4,
        )
        arquivo.write("\n")

    print(f"CSV: {caminho_csv}")
    print(f"JSON gerado: {caminho_final}")
    print(f"results_sha256: {csv_hash}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
