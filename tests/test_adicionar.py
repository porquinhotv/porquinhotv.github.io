"""Os formularios `adicionar` e `remover`: o que recusam, o que avisam e
o que escrevem.

As ligacoes sao as reais dadas pelo autor a 2026-09-29 e a 2026-10-12, e
as provas publicadas sao reais. Nenhum teste faz um pedido de rede, e
nenhum escreve no repositorio: a curadoria e o dataset sao copias numa
pasta temporaria.
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

from ferramentas import adicionar, remover
from recolha import armazem
from recolha.curadoria import ler_remocoes
from recolha.fontes.manual import ler_registo
from recolha.modelos import RAIZ

HOJE = date(2026, 10, 12)
# A linha de 2026-10-12 tal como ficou no `main`, e a mesma ligacao tal
# como sai de "partilhar" no telemovel: com a conta no caminho e o
# parametro de rasto.
PARTILHADA = "https://www.instagram.com/andre_ventura_oficial/p/DeZ6Klqlsyr/?igsh=MTQ2b2x5"
CNN = "https://cnnportugal.iol.pt/videos/a-entrevista-a-andre-ventura-na-integra/6ab2e9290cf22b9f8904c709"
RTP1 = "https://www.rtp.pt/play/p10324/e938640/grande-entrevista"
RTP3 = "https://www.rtp.pt/play/p16214/e938491/grande-entrevista"
SO_NO_TESTE = "https://exemplo.pt/so-existe-neste-teste"
WORKFLOWS = {nome: RAIZ / ".github" / "workflows" / f"{nome}.yml" for nome in ("adicionar", "remover")}

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

# Tres entrevistas reais do dataset de 2026-10-12: uma so na CNN, e o
# par do servico publico de 2026-06-24, uma entrevista com duas provas.
PUBLICADAS = {"entrevistas": [
    {"id": "a", "data": "2026-09-22", "canal": "cnn-portugal", "transmissoes": [
        {"data": "2026-09-22", "canal": "cnn-portugal", "prova_url": CNN}]},
    {"id": "b", "data": "2026-06-24", "canal": "rtp3", "transmissoes": [
        {"data": "2026-06-24", "canal": "rtp1", "prova_url": RTP1},
        {"data": "2026-06-24", "canal": "rtp3", "prova_url": RTP3}]},
    # So existe aqui. Os testes que correm sobre a curadoria real do
    # repositorio usam esta, e nunca uma prova real: um veto ou uma linha
    # legitima no ficheiro real partia o teste, e com ele o formulario
    # seguinte, que corre a suite antes de publicar.
    {"id": "c", "data": "2026-10-01", "canal": "now", "transmissoes": [
        {"data": "2026-10-01", "canal": "now", "prova_url": SO_NO_TESTE}]},
]}


class Base(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.pasta)
        self.curadoria = self.pasta / "curadoria.yml"
        self.curadoria.write_text(CURADORIA, encoding="utf-8", newline="\n")
        self.publicadas = self.pasta / "entrevistas.json"
        self.publicadas.write_text(json.dumps(PUBLICADAS), encoding="utf-8")

    def adicionar(self, entradas):
        return adicionar.correr(entradas, curadoria=self.curadoria, publicadas=self.publicadas, hoje=HOJE)

    def remover(self, provas, motivo="prova substituida"):
        return remover.correr(provas, motivo, curadoria=self.curadoria, publicadas=self.publicadas, hoje=HOJE)

    def ficheiro(self):
        return yaml.safe_load(self.curadoria.read_text(encoding="utf-8"))

    def intacto(self):
        self.assertEqual(self.curadoria.read_text(encoding="utf-8"), CURADORIA)


class TestAdicionarRecusa(Base):
    def test_a_mesma_publicacao_partilhada_do_telemovel_e_recusada(self):
        """A ligacao partilhada traz a conta no caminho e `?igsh=`, e e a
        mesma publicacao que ja esta escrita. Comparar enderecos por
        inteiro deixava-a entrar duas vezes, e contar uma entrevista duas
        vezes e o pior erro deste projeto."""
        codigo, relatorio = self.adicionar(f"2026-10-12 RTPN {PARTILHADA}")
        self.assertEqual(codigo, 1)
        self.assertIn("ja esta na curadoria", relatorio)
        self.intacto()

    def test_um_lote_com_uma_entrada_ma_nao_escreve_nenhuma(self):
        """Escrever as boas e calar as mas deixava o lote meio entrado, sem
        quem o preencheu saber quais faltam."""
        codigo, relatorio = self.adicionar(
            "2026-10-05 NOW https://www.instagram.com/p/DeH9qyUCSZS/ ; 2026-10-08 RTPX https://exemplo.pt/b")
        self.assertEqual(codigo, 1)
        self.assertIn("NADA FOI ESCRITO: 1 de 2", relatorio)
        self.intacto()

    def test_duas_entradas_coladas_sem_separador_sao_recusadas(self):
        """A caixa do formulario e de uma linha: um lote colado com mudancas
        de linha chega sem elas. Sem o `;`, duas entradas viravam uma com o
        canal "now cmtv", e o erro tem de dizer o que fazer."""
        codigo, relatorio = self.adicionar(
            "2026-10-05 now https://www.instagram.com/p/DeH9qyUCSZS/ 2026-10-08 cmtv https://www.instagram.com/p/DePnmSHjbR0/")
        self.assertEqual(codigo, 1)
        self.assertIn("separar as entradas com ';'", relatorio)

    def test_a_mesma_prova_duas_vezes_no_lote_e_recusada(self):
        codigo, relatorio = self.adicionar(
            "2026-10-05 now https://www.instagram.com/p/DeH9qyUCSZS/; 2026-10-06 now https://www.instagram.com/p/DeH9qyUCSZS/?igsh=x")
        self.assertEqual(codigo, 1)
        self.assertIn("na entrada 1 deste lote", relatorio)

    def test_uma_prova_ja_publicada_por_outra_fonte_e_recusada(self):
        codigo, relatorio = self.adicionar(f"2026-09-22 cnn {CNN}")
        self.assertEqual(codigo, 1)
        self.assertIn("ja esta publicada", relatorio)

    def test_uma_prova_vetada_nao_volta_pelo_formulario(self):
        """Um veto escrito e uma decisao de uma pessoa que leu a pagina. O
        formulario nao o pode contornar sem que alguem o decida."""
        codigo, relatorio = self.adicionar("2025-03-19 rtp3 https://exemplo.pt/vetada")
        self.assertEqual(codigo, 1)
        self.assertIn("vetada", relatorio)

    def test_uma_data_que_nao_existe_e_recusada(self):
        """Oito digitos ou a forma certa nao chegam: 30 de fevereiro so daria
        erro na publicacao, longe de quem preencheu o formulario."""
        for escrito in ("2026-02-30", "30-02-2026", "20260230", "5 outubro"):
            with self.subTest(data=escrito):
                self.assertEqual(adicionar.normalizar_data(escrito), "")

    def test_as_escritas_do_telemovel_dao_iso(self):
        for escrito in ("2026-10-05", "20261005", "5-10-2026", "05/10/2026", "5.10.2026"):
            with self.subTest(data=escrito):
                self.assertEqual(adicionar.normalizar_data(escrito), "2026-10-05")


class TestCanais(unittest.TestCase):
    def setUp(self):
        canais = yaml.safe_load((RAIZ / "config" / "porquinho.yml").read_text(encoding="utf-8"))["canais"]
        self.nomes = adicionar.nomes_de_canal(canais)

    def test_os_nomes_que_o_autor_escreveu_dao_o_canal_certo(self):
        """As formas da mensagem do autor de 2026-10-12, e as do site. RTPN
        e o nome antigo da RTP3, e nunca a RTP1."""
        for escrito, canal in {"NOW": "now", "CMTV": "cmtv", "RTPN": "rtp3", "RTP3": "rtp3", "RTP Noticias": "rtp3",
                               "rtp notícias": "rtp3", "SIC Notícias": "sic-noticias", "sic-noticias": "sic-noticias",
                               "SIC": "sic", "CNN": "cnn-portugal", "RTP1": "rtp1"}.items():
            with self.subTest(escrito=escrito):
                self.assertEqual(self.nomes.get(adicionar._simples(escrito)), canal)

    def test_um_sinonimo_que_desse_dois_canais_falha_ao_ler(self):
        """O canal nunca se adivinha: a KB pagou oito linhas erradas em oito
        por o deduzir."""
        with self.assertRaises(ValueError):
            adicionar.nomes_de_canal([{"id": "a", "nome": "A", "sinonimos": ["X"]}, {"id": "b", "nome": "B", "sinonimos": ["x"]}])


class TestAdicionarData(Base):
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
        entrevista passou. Deduzir a data teria posto quatro de vinte e
        quatro linhas no dia errado (KB, licao vigesima sexta)."""
        codigo, relatorio = self.adicionar("2026-10-06 now https://www.instagram.com/p/DeH9qyUCSZS/")
        self.assertEqual(codigo, 0)
        self.assertIn("a publicacao e de 2026-10-05 20:30", relatorio)
        self.assertEqual(str(self.ficheiro()["entrevistas"][-1]["data"]), "2026-10-06")

    def test_o_mesmo_canal_a_um_dia_avisa_e_nao_trava(self):
        codigo, relatorio = self.adicionar("2026-10-11 rtp3 https://exemplo.pt/outra")
        self.assertEqual(codigo, 0)
        self.assertIn("ja tem uma entrevista a 2026-10-12", relatorio)


class TestAdicionarEscrita(Base):
    def test_o_lote_da_mensagem_do_autor_entra_inteiro_e_o_resto_fica_igual(self):
        """As tres entradas de 2026-10-12, escritas como o autor as escreveu,
        em qualquer ordem. A curadoria e o registo de porque cada linha esta
        ali: escrever por yaml.dump apagava os comentarios todos."""
        self.curadoria.write_text(CURADORIA.replace("DeZ6Klqlsyr", "OutraCoisa1"), encoding="utf-8")
        antes = self.curadoria.read_text(encoding="utf-8")
        codigo, relatorio = self.adicionar(
            "NOW, 5-10-2026 https://www.instagram.com/p/DeH9qyUCSZS/;"
            "https://www.instagram.com/p/DePnmSHjbR0/?igsh=x CMTV 08-10-2026; "
            f"RTPN 12-10-2026 {PARTILHADA}")
        self.assertEqual(codigo, 0, relatorio)
        novo = self.curadoria.read_text(encoding="utf-8")
        for linha in antes.splitlines():
            self.assertIn(linha, novo)
        self.assertNotIn("\r", novo)
        escritas = [(str(l["data"]), l["canal"], l["prova"]) for l in self.ficheiro()["entrevistas"][1:]]
        self.assertEqual(escritas, [
            ("2026-10-05", "now", "https://www.instagram.com/p/DeH9qyUCSZS/"),
            ("2026-10-08", "cmtv", "https://www.instagram.com/p/DePnmSHjbR0/"),
            ("2026-10-12", "rtp3", "https://www.instagram.com/p/DeZ6Klqlsyr/"),
        ])
        self.assertEqual(len(self.ficheiro()["remover"]), 1)

    def test_a_curadoria_real_continua_legivel_pelo_coletor(self):
        """Contra o ficheiro real do repositorio, copiado: o coletor tem de
        ler as linhas novas e nada a menos."""
        shutil.copy(RAIZ / "config" / "curadoria.yml", self.curadoria)
        antes = len(ler_registo(self.curadoria))
        codigo, relatorio = self.adicionar("2026-10-13 cmtv https://exemplo.pt/so-no-teste-a; 2026-10-14 now https://exemplo.pt/so-no-teste-b")
        self.assertEqual(codigo, 0, relatorio)
        self.assertEqual(len(ler_registo(self.curadoria)), antes + 2)


class TestRemover(Base):
    def test_uma_ligacao_que_nao_esta_no_site_trava_o_lote(self):
        """Um erro de copia num veto que nao veta nada deixava quem
        preencheu convencido de que a linha saiu."""
        codigo, relatorio = self.remover(f"{CNN} https://exemplo.pt/nao-existe")
        self.assertEqual(codigo, 1)
        self.assertIn("nao esta no site", relatorio)
        self.intacto()

    def test_o_motivo_e_obrigatorio(self):
        codigo, _ = self.remover(CNN, motivo="  ")
        self.assertEqual(codigo, 1)
        self.intacto()

    def test_retirar_uma_prova_de_simulcast_avisa_que_a_entrevista_fica(self):
        """Retira-se uma prova, nao uma entrevista. A de 2026-06-24 passou
        nos dois canais do servico publico, e sem a prova da RTP1 continua
        contada pela da RTP3. Quem preenche tem de o saber."""
        codigo, relatorio = self.remover(RTP1)
        self.assertEqual(codigo, 0)
        self.assertIn(f"continua contada pela prova de rtp3: {RTP3}", relatorio)

    def test_retirar_as_duas_provas_nao_avisa_de_nenhuma(self):
        codigo, relatorio = self.remover(f"{RTP1}; {RTP3}")
        self.assertEqual(codigo, 0)
        self.assertNotIn("continua contada", relatorio)

    def test_o_veto_escrito_e_lido_pelo_coletor_com_o_motivo(self):
        """O veto tem de casar com a prova pela mesma normalizacao que o
        coletor usa, senao o formulario dizia que retirou e o site ficava
        igual. Um motivo com dois pontos nao pode partir o YAML."""
        codigo, relatorio = self.remover(f"{CNN}; {PARTILHADA}", motivo="nota: substituida, ver # fontes")
        self.assertEqual(codigo, 0, relatorio)
        vetos = ler_remocoes(self.curadoria)
        self.assertEqual(vetos[CNN], "nota: substituida, ver # fontes")
        self.assertIn("https://www.instagram.com/p/DeZ6Klqlsyr/", vetos)
        self.assertEqual(len(self.ficheiro()["entrevistas"]), 1)

    def test_uma_prova_ja_vetada_e_recusada(self):
        codigo, relatorio = self.remover("https://exemplo.pt/vetada")
        self.assertEqual(codigo, 1)
        self.assertIn("ja estava vetada", relatorio)

    def test_a_curadoria_real_continua_legivel(self):
        shutil.copy(RAIZ / "config" / "curadoria.yml", self.curadoria)
        antes = len(ler_remocoes(self.curadoria))
        codigo, relatorio = self.remover(SO_NO_TESTE)
        self.assertEqual(codigo, 0, relatorio)
        self.assertEqual(len(ler_remocoes(self.curadoria)), antes + 1)
        self.assertEqual(len(self.ficheiro()["mesma_entrevista"]),
                         len(yaml.safe_load((RAIZ / "config" / "curadoria.yml").read_text(encoding="utf-8"))["mesma_entrevista"]))


class TestFormularios(unittest.TestCase):
    def test_os_campos_nunca_sao_colados_no_shell(self):
        """Um `${{ inputs.x }}` dentro de `run` e texto colado no script: uma
        ligacao com `$(...)` correria como comando com permissao de escrita
        no repositorio. Os campos entram por variaveis de ambiente."""
        for nome, caminho in WORKFLOWS.items():
            workflow = yaml.safe_load(caminho.read_text(encoding="utf-8"))
            for passo in workflow["jobs"][nome]["steps"]:
                with self.subTest(workflow=nome, passo=passo.get("name", passo.get("uses"))):
                    self.assertIsNone(re.search(r"\$\{\{\s*(inputs|github\.event)", passo.get("run", "")))

    def test_os_formularios_nao_partilham_o_grupo_da_recolha(self):
        """Um grupo de concorrencia guarda uma so corrida pendente e cancela
        a anterior: tres formularios seguidos perdiam o do meio."""
        for nome, caminho in WORKFLOWS.items():
            workflow = yaml.safe_load(caminho.read_text(encoding="utf-8"))
            with self.subTest(workflow=nome):
                self.assertNotIn("concurrency", workflow)
                self.assertNotIn("concurrency", workflow["jobs"][nome])

    def test_os_formularios_correm_os_testes_antes_de_publicar(self):
        """A mesma barreira da recolha diaria: uma regressao nunca chega a
        escrever dados."""
        for nome, caminho in WORKFLOWS.items():
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(workflow=nome):
                self.assertLess(texto.index("python -m unittest"), texto.index("python -m recolha.principal"))
                self.assertLess(texto.index("node --test"), texto.index("git push"))


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
