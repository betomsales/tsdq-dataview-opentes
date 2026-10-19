import csv
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts.recortar_csv_prodist import interpretar_data, recortar_csv


class RecortarCsvProdistTest(unittest.TestCase):
    def setUp(self):
        self.temporario = TemporaryDirectory()
        self.addCleanup(self.temporario.cleanup)
        self.pasta = Path(self.temporario.name)
        self.entrada = self.pasta / "resultados.csv"
        self.saida = self.pasta / "recorte.csv"

    def gravar(self, linhas, cabecalho=None, bom=False):
        with self.entrada.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow(cabecalho or ["date", "DSS-0.Bus-611-V1_pu", "observacao"])
            escritor.writerows(linhas)

    def gerar(self, dias=9, minutos=5):
        inicio = datetime(2018, 1, 1)
        passo = timedelta(minutes=minutos)
        self.gravar([
            [(inicio + i * passo).isoformat(sep=" "), "0.000000", "valor, entre aspas"]
            for i in range(dias * 24 * 60 // minutos)
        ])

    def ler(self, caminho):
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            return list(csv.reader(arquivo))

    def test_sete_dias_mantem_2016_amostras_e_o_original(self):
        self.gerar()
        original = hashlib.sha256(self.entrada.read_bytes()).digest()
        resultado = recortar_csv(self.entrada)
        linhas = self.ler(resultado.saida)
        self.assertEqual(resultado.registros, 2016)
        self.assertEqual(resultado.saida.name, "resultados_7dias.csv")
        self.assertEqual(resultado.intervalo, timedelta(minutes=5))
        self.assertEqual(resultado.fim_exclusivo, datetime(2018, 1, 8))
        self.assertEqual(linhas[1], ["2018-01-01 00:00:00", "0.000000", "valor, entre aspas"])
        self.assertEqual(linhas[-1][0], "2018-01-07 23:55:00")
        self.assertEqual(len(linhas), 2017)
        self.assertEqual(hashlib.sha256(self.entrada.read_bytes()).digest(), original)

    def test_dez_minutos_produz_1008_registros_sem_agregar(self):
        self.gerar(minutos=10)
        resultado = recortar_csv(self.entrada, self.saida)
        self.assertEqual(resultado.registros, 1008)
        self.assertEqual(resultado.ultima_amostra, datetime(2018, 1, 7, 23, 50))

    def test_inicio_personalizado_e_fim_exclusivo(self):
        self.gerar()
        inicio = interpretar_data("2018-01-02 12:00:00")
        resultado = recortar_csv(self.entrada, self.saida, inicio=inicio)
        self.assertEqual(resultado.inicio, inicio)
        self.assertEqual(resultado.fim_exclusivo, datetime(2018, 1, 9, 12))
        self.assertEqual(resultado.ultima_amostra, datetime(2018, 1, 9, 11, 55))
        self.assertEqual(resultado.registros, 2016)

    def test_duracao_personalizada_e_coluna_de_tempo(self):
        self.gravar([
            ["0.0", (datetime(2018, 1, 1) + timedelta(minutes=5 * i)).isoformat(sep=" "), "x"]
            for i in range(288)
        ], cabecalho=["valor", "instante", "observacao"], bom=True)
        resultado = recortar_csv(self.entrada, self.saida, dias=1, coluna_tempo="instante")
        self.assertEqual(resultado.registros, 288)
        self.assertEqual(self.ler(self.saida)[0], ["valor", "instante", "observacao"])

    def test_aceita_sete_dias_sem_exigir_amostra_do_oitavo(self):
        self.gerar(dias=7)
        self.assertEqual(recortar_csv(self.entrada, self.saida).registros, 2016)

    def test_periodo_incompleto_nao_deixa_recorte_parcial(self):
        self.gerar(dias=6)
        with self.assertRaisesRegex(ValueError, "insuficientes ou incompletos"):
            recortar_csv(self.entrada, self.saida)
        self.assertFalse(self.saida.exists())

    def test_lacuna_nao_e_preenchida_automaticamente(self):
        self.gerar()
        linhas = self.ler(self.entrada)
        self.gravar(linhas[1:20] + linhas[21:])
        with self.assertRaisesRegex(ValueError, "sequencia regular"):
            recortar_csv(self.entrada, self.saida)
        self.assertFalse(self.saida.exists())

    def test_tempos_duplicados_ou_desordenados_sao_rejeitados(self):
        for tempos in (
            ["2018-01-01", "2018-01-01"],
            ["2018-01-02", "2018-01-01"],
        ):
            with self.subTest(tempos=tempos):
                self.gravar([[tempo, "0", "x"] for tempo in tempos])
                with self.assertRaisesRegex(ValueError, "crescentes"):
                    recortar_csv(self.entrada, self.saida)
                self.assertFalse(self.saida.exists())

    def test_nao_sobrescreve_saida_existente(self):
        self.gerar()
        self.saida.write_bytes(b"preservar")
        with self.assertRaisesRegex(ValueError, "saida ja existe"):
            recortar_csv(self.entrada, self.saida)
        self.assertEqual(self.saida.read_bytes(), b"preservar")

    def test_nao_sobrescreve_original(self):
        self.gerar()
        original = self.entrada.read_bytes()
        with self.assertRaisesRegex(ValueError, "original nao pode"):
            recortar_csv(self.entrada, self.entrada)
        self.assertEqual(self.entrada.read_bytes(), original)

    def test_inicio_fora_do_periodo_ou_sem_amostra(self):
        self.gerar()
        for inicio, mensagem in (
            (datetime(2019, 1, 1), "Nenhum registro"),
            (datetime(2018, 1, 1, 0, 1), "instante inicial"),
        ):
            with self.subTest(inicio=inicio):
                with self.assertRaisesRegex(ValueError, mensagem):
                    recortar_csv(self.entrada, self.saida, inicio=inicio)
                self.assertFalse(self.saida.exists())

    def test_rejeita_fusos_incompativeis(self):
        self.gerar()
        with self.assertRaisesRegex(ValueError, "fusos horarios"):
            recortar_csv(self.entrada, self.saida, inicio=interpretar_data("2018-01-01T00:00:00Z"))
        self.assertFalse(self.saida.exists())

    def test_csv_invalido_nao_deixa_saida(self):
        for linhas, mensagem in (
            ([["nao-e-data", "0", "x"]], "Data invalida"),
            ([["2018-01-01", "0"]], "campos incorreta"),
            ([], "Nenhum registro"),
        ):
            with self.subTest(mensagem=mensagem):
                self.gravar(linhas)
                with self.assertRaisesRegex(ValueError, mensagem):
                    recortar_csv(self.entrada, self.saida)
                self.assertFalse(self.saida.exists())

    def test_coluna_inexistente_e_cabecalhos_duplicados(self):
        self.gerar()
        with self.assertRaisesRegex(ValueError, "Coluna de tempo"):
            recortar_csv(self.entrada, self.saida, coluna_tempo="ausente")
        self.gravar([], cabecalho=["date", "date"])
        with self.assertRaisesRegex(ValueError, "repetidos"):
            recortar_csv(self.entrada, self.saida)
        self.assertFalse(self.saida.exists())

    def test_dias_invalidos(self):
        for dias in (0, -1, 1.5):
            with self.subTest(dias=dias), self.assertRaisesRegex(ValueError, "inteiro positivo"):
                recortar_csv(self.entrada, self.saida, dias=dias)

    def test_linha_de_comando(self):
        self.gerar()
        script = Path(__file__).resolve().parents[1] / "scripts" / "recortar_csv_prodist.py"
        processo = subprocess.run([
            sys.executable, "-B", str(script), "--csv", str(self.entrada),
            "--saida", str(self.saida), "--dias", "1",
        ], capture_output=True, text=True)
        self.assertEqual(processo.returncode, 0, processo.stderr)
        self.assertIn("Registros: 288", processo.stdout)
        self.assertIn("cadencia original nao e de 10 minutos", processo.stdout)
        self.assertIn("nao constitui uma medicao oficial", processo.stdout)


if __name__ == "__main__":
    unittest.main()
