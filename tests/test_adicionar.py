"""O formulario `adicionar`: o que recusa, o que avisa e o que escreve.

As ligacoes sao as reais dadas pelo autor a 2026-09-29 e a 2026-10-12.
Nenhum teste faz um pedido de rede, e nenhum escreve no repositorio: a
curadoria e o dataset sao copias numa pasta temporaria.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

from ferramentas import adicionar
from recolha import armazem
from recolha.fontes.manual import ler_registo
from recolha.modelos import RAIZ

HOJE = date(2026, 10, 12)
# A linha de 2026-10-12 tal como ficou no `main`, e a mesma ligacao tal
# como sai de "partilhar" no telemovel: com a conta no caminho e o
# parametro de rasto.
ESCRITA = "https://www.instagram.com/p/DeZ6Klqlsyr/"
PARTILHADA = "https://www.instagram.com/andre_ventura_oficial/p/DeZ6Klqlsyr/?igsh=MTQ2b2x5"
WORKFLOW = RAIZ / ".github" / "workflows" / "adicionar.yml"

CURADORIA = """# cabecalho que tem de sobreviver
entrevistas:
  # comentario que tem de sobreviver
  - data: 2026-10-12
    canal: rtp3
    prova: https://www.instagram.com/p/DeZ6Klqlsyr/

remover:
  - prova: https://exemplo.pt/vetada
    motivo: e um resumo da entrevista da vespera

mesma_entrevista: []
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.pasta)
        self.curadoria = self.pasta / "curadoria.yml"
        self.curadoria.write_text(CURADORIA, encoding="utf-8", newline="\n")
        self.publicadas = self.pasta / "entrevistas.json"
        self.publicadas.write_text(json.dumps({"entrevistas": [
            {"data": "2026-09-22", "canal": "cnn-portugal", "transmissoes": [
                {"data": "2026-09-22", "canal": "cnn-portugal", "prova_url": "https://exemplo.pt/publicada"}]},
        ]}), encoding="utf-8")

    def correr(self, data, canal, prova):
        return adicionar.correr(data, canal, prova, curadoria=self.curadoria, publicadas=self.publicadas, hoje=HOJE)

    def linhas(self):
        return yaml.safe_load(self.curadoria.read_text(encoding="utf-8"))["entrevistas"]


class TestRecusa(Base):
    def test_a_mesma_publicacao_partilhada_do_telemovel_e_recusada(self):
        """A ligacao partilhada traz a conta no caminho e `?igsh=`, e e a
        mesma publicacao que ja esta escrita. Comparar enderecos por
        inteiro deixava-a entrar duas vezes, e contar uma entrevista duas
        vezes e o pior erro deste projeto."""
        codigo, relatorio = self.correr("2026-10-12", "rtp3", PARTILHADA)
        self.assertEqual(codigo, 1)
        self.assertIn("ja esta na curadoria", relatorio)
        self.assertEqual(self.curadoria.read_text(encoding="utf-8"), CURADORIA)

    def test_uma_prova_ja_publicada_por_outra_fonte_e_recusada(self):
        codigo, relatorio = self.correr("2026-09-22", "cnn-portugal", "https://exemplo.pt/publicada")
        self.assertEqual(codigo, 1)
        self.assertIn("ja esta publicada", relatorio)

    def test_uma_prova_vetada_nao_volta_pelo_formulario(self):
        """Um veto escrito e uma decisao de uma pessoa que leu a pagina. O
        formulario nao o pode contornar sem que alguem o decida."""
        codigo, relatorio = self.correr("2025-03-19", "rtp3", "https://exemplo.pt/vetada")
        self.assertEqual(codigo, 1)
        self.assertIn("vetada", relatorio)

    def test_canal_fora_da_tabela_e_recusado(self):
        """O canal nunca se adivinha: a KB pagou oito linhas erradas em oito
        por o deduzir. Um id que nao existe nao entra."""
        codigo, _ = self.correr("2026-10-05", "rtpn", "https://www.instagram.com/p/DeH9qyUCSZS/")
        self.assertEqual(codigo, 1)

    def test_uma_data_que_nao_existe_e_recusada(self):
        """Oito digitos ou a forma certa nao chegam: 30 de fevereiro so daria
        erro na publicacao, longe de quem preencheu o formulario."""
        for escrito in ("2026-02-30", "30-02-2026", "20260230", "2026-10-05 noite", "5 outubro"):
            with self.subTest(data=escrito):
                self.assertEqual(adicionar.normalizar_data(escrito), "")

    def test_as_escritas_do_telemovel_dao_iso(self):
        for escrito in ("2026-10-05", "20261005", "5-10-2026", "05/10/2026", "5.10.2026"):
            with self.subTest(data=escrito):
                self.assertEqual(adicionar.normalizar_data(escrito), "2026-10-05")


class TestData(Base):
    def test_a_hora_da_publicacao_reproduz_as_linhas_reais(self):
        """O metodo dos identificadores, contra as quatro publicacoes reais
        cujo dia o autor leu. A de 2026-09-28 ja estava publicada e bate ao
        minuto."""
        reais = {"Dd14rXcoAi6": "2026-09-28 20:00", "DeH9qyUCSZS": "2026-10-05 20:30",
                 "DePnmSHjbR0": "2026-10-08 19:51", "DeZ6Klqlsyr": "2026-10-12 19:45"}
        for codigo, esperado in reais.items():
            with self.subTest(codigo=codigo):
                self.assertEqual(f"{adicionar.hora_da_publicacao(codigo):%Y-%m-%d %H:%M}", esperado)

    def test_a_data_escrita_ganha_a_deduzida_e_so_avisa(self):
        """O identificador diz quando a publicacao saiu, nao quando a
        entrevista passou. Um anuncio de vespera fica no dia que quem leu
        escreveu, com um aviso. Deduzir a data teria posto quatro de vinte
        e quatro linhas no dia errado (KB, licao vigesima sexta)."""
        codigo, relatorio = self.correr("2026-10-06", "now", "https://www.instagram.com/p/DeH9qyUCSZS/")
        self.assertEqual(codigo, 0)
        self.assertIn("a publicacao e de 2026-10-05 20:30", relatorio)
        self.assertEqual(str(self.linhas()[-1]["data"]), "2026-10-06")

    def test_o_mesmo_canal_a_um_dia_avisa_e_nao_trava(self):
        """Duas entrevistas em dias seguidos existem; a mesma contada duas
        vezes tambem. So quem leu as duas sabe, por isso avisa."""
        codigo, relatorio = self.correr("2026-10-11", "rtp3", "https://exemplo.pt/outra")
        self.assertEqual(codigo, 0)
        self.assertIn("ja tem uma entrevista a 2026-10-12", relatorio)


class TestEscrita(Base):
    def test_a_linha_entra_na_lista_certa_e_o_resto_fica_igual(self):
        """A curadoria e o registo de porque cada linha esta ali. Escrever
        por yaml.dump apagava os comentarios todos."""
        codigo, _ = self.correr("5-10-2026", "now", "https://www.instagram.com/p/DeH9qyUCSZS/?igsh=x")
        self.assertEqual(codigo, 0)
        novo = self.curadoria.read_text(encoding="utf-8")
        for linha in CURADORIA.splitlines():
            self.assertIn(linha, novo)
        self.assertNotIn("\r", novo)
        ultima = self.linhas()[-1]
        self.assertEqual((str(ultima["data"]), ultima["canal"], ultima["prova"]),
                         ("2026-10-05", "now", "https://www.instagram.com/p/DeH9qyUCSZS/"))
        self.assertEqual(len(yaml.safe_load(novo)["remover"]), 1)

    def test_a_curadoria_real_continua_legivel_pelo_coletor(self):
        """Contra o ficheiro real do repositorio, copiado: o coletor tem de
        ler uma linha a mais e nada a menos."""
        shutil.copy(RAIZ / "config" / "curadoria.yml", self.curadoria)
        antes = len(ler_registo(self.curadoria))
        codigo, relatorio = self.correr("2026-10-13", "cmtv", "https://exemplo.pt/nova-entrevista")
        self.assertEqual(codigo, 0, relatorio)
        self.assertEqual(len(ler_registo(self.curadoria)), antes + 1)


class TestFormulario(unittest.TestCase):
    def setUp(self):
        self.texto = WORKFLOW.read_text(encoding="utf-8")
        self.workflow = yaml.safe_load(self.texto)

    def test_o_formulario_tem_os_canais_da_tabela(self):
        """A lista do formulario e uma copia de config/porquinho.yml. Um
        canal novo so na tabela nao se podia escolher, e um so no
        formulario seria recusado depois de preenchido."""
        gatilho = self.workflow.get("on") or self.workflow.get(True)
        opcoes = gatilho["workflow_dispatch"]["inputs"]["canal"]["options"]
        tabela = yaml.safe_load((RAIZ / "config" / "porquinho.yml").read_text(encoding="utf-8"))["canais"]
        self.assertEqual(opcoes, [c["id"] for c in tabela])

    def test_os_campos_nunca_sao_colados_no_shell(self):
        """Um `${{ inputs.x }}` dentro de `run` e texto colado no script: uma
        ligacao com `$(...)` correria como comando com permissao de escrita
        no repositorio. Os campos entram por variaveis de ambiente."""
        for passo in self.workflow["jobs"]["adicionar"]["steps"]:
            with self.subTest(passo=passo.get("name", passo.get("uses"))):
                self.assertIsNone(re.search(r"\$\{\{\s*(inputs|github\.event)", passo.get("run", "")))

    def test_o_formulario_nao_partilha_o_grupo_da_recolha(self):
        """Um grupo de concorrencia guarda uma so corrida pendente e cancela
        a anterior: tres formularios seguidos perdiam o do meio."""
        self.assertNotIn("concurrency", self.workflow)
        self.assertNotIn("concurrency", self.workflow["jobs"]["adicionar"])


class TestQuarentena(unittest.TestCase):
    def test_a_corrida_de_uma_fonte_nao_apaga_a_quarentena_das_outras(self):
        """Medido a 2026-10-12: a corrida so da curadoria punha a quarentena
        publicada de 66 entradas a zero, e a pagina de Fontes perdia o
        diagnostico das outras fontes sem ninguem o decidir."""
        outra = {"fonte": "busca-exemplo", "motivo": "sem_sujeito", "titulo": "a", "url": "https://exemplo.pt/a"}
        veto = {"fonte": "registo-exemplo", "motivo": "vetada_a_mao (resumo)", "titulo": "b", "url": "https://exemplo.pt/b"}
        velha = {"fonte": "curadoria", "motivo": "fragmento_ou_repetido", "titulo": "c", "url": "https://exemplo.pt/c"}
        fundida = armazem.fundir_quarentena([outra, veto, velha], [veto], "curadoria")
        self.assertIn(outra, fundida)
        self.assertNotIn(velha, fundida)
        self.assertEqual(fundida.count(veto), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
