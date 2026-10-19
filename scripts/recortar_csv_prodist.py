"""Recorta sete dias de um CSV sem alterar suas amostras ou o arquivo original.

O PRODIST usa 1.008 leituras validas integralizadas a cada 10 minutos, com
periodo minimo de sete dias. Este utilitario apenas recorta o periodo:
nao integraliza tensoes, expurga leituras ou certifica uma medicao oficial.
Um CSV regular de cinco minutos mantem 2.016 registros em sete dias.

Referencia: https://www.gov.br/aneel/pt-br/assuntos/distribuicao/
qualidade-do-fornecimento-de-energia-eletrica

Exemplos:
    python scripts/recortar_csv_prodist.py --csv resultados.csv
    python scripts/recortar_csv_prodist.py --csv resultados.csv --inicio 2018-02-01

O intervalo inclui o inicio e exclui inicio + dias. O CSV deve ser UTF-8,
separado por virgulas, com tempos ISO 8601 em ordem estritamente crescente.
O processamento e linha a linha, sem carregar o CSV inteiro na memoria.
Depois do recorte, use aplicar_hash_topologia.py para vincular uma copia
do JSON ao novo CSV. Nenhum JSON e alterado por este script.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


DIAS_PRODIST = 7
LEITURAS_PRODIST = 1008
INTERVALO_PRODIST = timedelta(minutes=10)


@dataclass(frozen=True)
class ResultadoRecorte:
    saida: Path
    inicio: datetime
    fim_exclusivo: datetime
    ultima_amostra: datetime
    registros: int
    colunas: int
    intervalo: timedelta


def interpretar_data(valor: str) -> datetime:
    try:
        data = datetime.fromisoformat(valor.strip())
    except ValueError as erro:
        raise ValueError(
            f"Data invalida: {valor!r}. Use AAAA-MM-DD ou AAAA-MM-DD HH:MM:SS."
        ) from erro
    return data.astimezone(timezone.utc) if data.utcoffset() is not None else data


def recortar_csv(
    caminho_csv: Path,
    caminho_saida: Path | None = None,
    inicio: datetime | None = None,
    dias: int = DIAS_PRODIST,
    coluna_tempo: str | None = None,
) -> ResultadoRecorte:
    if not isinstance(dias, int) or dias <= 0:
        raise ValueError("A quantidade de dias deve ser um inteiro positivo.")

    entrada = Path(caminho_csv).resolve()
    saida = (
        Path(caminho_saida).resolve() if caminho_saida is not None
        else entrada.with_name(f"{entrada.stem}_{dias}dias.csv")
    )
    if not entrada.is_file():
        raise ValueError(f"CSV nao encontrado: {entrada}")
    if saida == entrada:
        raise ValueError("O CSV original nao pode ser usado como arquivo de saida.")
    if saida.exists():
        raise ValueError(f"A saida ja existe; escolha outro caminho: {saida}")

    if inicio is not None and inicio.utcoffset() is not None:
        inicio = inicio.astimezone(timezone.utc)

    duracao = timedelta(days=dias)
    criado = False
    registros = 0
    anterior = None
    primeira = None
    ultima = None
    intervalo = None
    irregular = False
    fim = None

    try:
        with entrada.open("r", encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.reader(arquivo, strict=True)
            cabecalho = next(leitor, None)
            if not cabecalho:
                raise ValueError("O CSV esta vazio ou nao possui cabecalho.")
            if len(cabecalho) != len(set(cabecalho)):
                raise ValueError("O CSV possui nomes de colunas repetidos.")
            if coluna_tempo is not None and coluna_tempo not in cabecalho:
                raise ValueError(f"Coluna de tempo nao encontrada: {coluna_tempo}")
            indice_tempo = cabecalho.index(coluna_tempo) if coluna_tempo is not None else 0

            saida.parent.mkdir(parents=True, exist_ok=True)
            with saida.open("x", encoding="utf-8", newline="") as destino:
                criado = True
                escritor = csv.writer(destino, lineterminator="\n")
                escritor.writerow(cabecalho)
                for linha in leitor:
                    if not linha:
                        continue
                    if len(linha) != len(cabecalho):
                        raise ValueError(f"Quantidade de campos incorreta na linha {leitor.line_num}.")
                    try:
                        tempo = interpretar_data(linha[indice_tempo])
                        if anterior is not None and tempo <= anterior:
                            raise ValueError("Os tempos devem ser crescentes, sem duplicatas.")
                        anterior = tempo
                        if inicio is None:
                            inicio = tempo
                        if fim is None:
                            fim = inicio + duracao
                        selecionada = inicio <= tempo < fim
                    except TypeError as erro:
                        raise ValueError(
                            "O inicio e os tempos do CSV devem usar fusos horarios compativeis."
                        ) from erro
                    except ValueError as erro:
                        raise ValueError(f"Linha {leitor.line_num}: {erro}") from erro

                    if not selecionada:
                        continue
                    if ultima is not None:
                        passo = tempo - ultima
                        if intervalo is None:
                            intervalo = passo
                        elif passo != intervalo:
                            irregular = True
                    if primeira is None:
                        primeira = tempo
                    ultima = tempo
                    registros += 1
                    escritor.writerow(linha)

                if primeira is None:
                    raise ValueError("Nenhum registro encontrado no periodo solicitado.")
                if primeira != inicio:
                    raise ValueError("Nao existe amostra no instante inicial solicitado.")
                if intervalo is None or irregular:
                    raise ValueError(
                        "O periodo nao possui uma sequencia regular de amostras. "
                        "Nenhuma lacuna foi preenchida ou leitura descartada."
                    )
                if duracao % intervalo or registros != duracao // intervalo or ultima + intervalo != fim:
                    raise ValueError(
                        f"Dados insuficientes ou incompletos para {dias} dias: "
                        f"{registros} registros encontrados. O recorte parcial nao foi mantido."
                    )
    except BaseException:
        if criado:
            saida.unlink(missing_ok=True)
        raise

    return ResultadoRecorte(saida, inicio, fim, ultima, registros, len(cabecalho), intervalo)


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", required=True, type=Path, help="CSV original de resultados.")
    parser.add_argument("--saida", type=Path, help="Novo CSV; por padrao, usa o sufixo _7dias.")
    parser.add_argument("--inicio", help="Inicio ISO 8601; por padrao, usa a primeira amostra.")
    parser.add_argument("--dias", type=int, default=DIAS_PRODIST, help="Duracao em dias (padrao: 7).")
    parser.add_argument("--coluna-tempo", help="Nome da coluna de tempo (padrao: primeira coluna).")
    return parser


def main() -> int:
    parser = criar_parser()
    args = parser.parse_args()
    try:
        resultado = recortar_csv(
            args.csv, args.saida,
            interpretar_data(args.inicio) if args.inicio else None,
            args.dias, args.coluna_tempo,
        )
    except (ValueError, OSError, csv.Error, UnicodeError, OverflowError) as erro:
        parser.error(str(erro))

    print(f"CSV gerado: {resultado.saida}")
    print(f"Janela: [{resultado.inicio.isoformat(sep=' ')}, {resultado.fim_exclusivo.isoformat(sep=' ')})")
    print(f"Ultima amostra: {resultado.ultima_amostra.isoformat(sep=' ')}")
    print(f"Registros: {resultado.registros} | Colunas: {resultado.colunas}")
    print(f"Intervalo original: {resultado.intervalo.total_seconds():g} segundos")
    print(f"Tamanho: {resultado.saida.stat().st_size / (1024 * 1024):.2f} MiB")
    print(f"Referencia PRODIST: minimo de {DIAS_PRODIST} dias e {LEITURAS_PRODIST} leituras validas de 10 minutos.")
    if resultado.intervalo != INTERVALO_PRODIST:
        print("ATENCAO: a cadencia original nao e de 10 minutos e foi preservada.")
    print("Este recorte de simulacao nao constitui uma medicao oficial ou certificada.")
    print("Gere um novo hash para vincular uma copia do JSON a este CSV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
