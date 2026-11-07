"""Os formularios `adicionar` e `remover`: o que recusam, o que avisam e
o que escrevem.

As ligacoes sao as reais dadas pelo autor a 2026-09-29 e a 2026-10-12, e
as provas publicadas sao reais. Nenhum teste faz um pedido de rede, e
nenhum escreve no repositorio: a curadoria e o dataset sao copias numa
pasta temporaria.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

from ferramentas import adicionar, comparacao, remover, seo
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
COMPARACAO_REAL = RAIZ / "config" / "comparacao.yml"

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
        # A comparacao real, copiada: os testes da outra pessoa escrevem
        # nela, e o ficheiro do repositorio nunca e tocado.
        self.comparacao = self.pasta / "comparacao.yml"
        self.comparacao_original = COMPARACAO_REAL.read_text(encoding="utf-8")
        self.comparacao.write_text(self.comparacao_original, encoding="utf-8", newline="\n")

    def adicionar(self, entradas, pessoa=""):
        return adicionar.correr(entradas, pessoa, curadoria=self.curadoria, publicadas=self.publicadas,
                                comparacao=self.comparacao, hoje=HOJE)

    def remover(self, provas, motivo="prova substituida", pessoa=""):
        return remover.correr(provas, motivo, pessoa, curadoria=self.curadoria, publicadas=self.publicadas,
                              comparacao=self.comparacao, hoje=HOJE)

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


class TestAdicionarOutraPessoa(Base):
    """Pedido do autor a 2026-11-07: acrescentar entrevistas de qualquer
    das tres pessoas pelo mesmo formulario, e o site inteiro acompanhar.
    As datas de teste caem na RTP2, onde o levantamento nao encontrou
    nenhuma entrevista das outras duas pessoas, e os enderecos inventados
    no dominio reservado `.invalid`, para nao colidirem com uma linha real
    que o formulario venha a escrever no ficheiro que estes testes copiam."""

    PESSOA = "José Luís Carneiro"

    def lida(self):
        return yaml.safe_load(self.comparacao.read_text(encoding="utf-8"))

    def intacta(self):
        self.assertEqual(self.comparacao.read_text(encoding="utf-8"), self.comparacao_original)

    def confirmadas(self, pid):
        """As que a pagina conta: confirmadas e sem veto. Contar tambem as
        vetadas partia estes testes no primeiro veto real, e o formulario
        que o escreveu parava (simulacao de 2026-11-07)."""
        lida = self.lida()
        vetadas = {v["prova"] for v in lida.get("remover") or []}
        return [e for e in lida["entrevistas"]
                if e["pessoa"] == pid and e["estado"] == "confirmada" and e["prova"] not in vetadas]

    def test_vai_para_o_fim_da_comparacao_e_nao_toca_na_curadoria(self):
        """A linha entra como a pagina a conta (confirmada, com canal e
        prova) e sem o que o formulario nao perguntou: o formato fica
        vazio, e o tipo de prova fica `ligacao`, sem adivinhar pelo
        dominio se e pagina de canal ou noticia. O resto do ficheiro,
        comentarios incluidos, fica byte a byte."""
        antes = len(self.confirmadas("carneiro"))
        n_antes = len(self.lida()["entrevistas"])
        codigo, relatorio = self.adicionar("2025-07-02 RTP2 https://teste.invalid/carneiro-rtp2", self.PESSOA)
        self.assertEqual(codigo, 0, relatorio)
        self.intacto()
        texto = self.comparacao.read_text(encoding="utf-8")
        self.assertTrue(texto.startswith(self.comparacao_original.rstrip("\n")))
        self.assertEqual(len(self.lida()["entrevistas"]), n_antes + 1)
        nova = self.lida()["entrevistas"][-1]
        self.assertEqual(nova, {"pessoa": "carneiro", "data": date(2025, 7, 2), "canal": "rtp2",
                                "estado": "confirmada", "tipo_prova": "ligacao",
                                "prova": "https://teste.invalid/carneiro-rtp2"})
        self.assertEqual(len(self.confirmadas("carneiro")), antes + 1)
        resumo, entrevistas = seo.dados()
        visivel = comparacao.visivel_de(resumo)
        norm = comparacao.validar(self.lida(), comparacao.canais_validos(), visivel)
        contas = comparacao.contar(norm, seo.visiveis(resumo, entrevistas), visivel)
        self.assertEqual(next(p for p in contas["pessoas"] if p["id"] == "carneiro")["total"], antes + 1)

    def test_uma_entrevista_nova_move_o_fecho_da_pagina(self):
        """Com o fecho escrito a mao, uma entrevista nova depois dele fazia
        falhar o gerador, ou ficava fora da pagina. Agora a pagina conta
        todos ate a entrevista mais recente, de qualquer pessoa. A data e
        no futuro de proposito: e a unica que nenhuma linha real passa."""
        codigo, relatorio = self.adicionar("01-01-2099 RTP2 https://teste.invalid/montenegro-futuro", "Luís Montenegro")
        self.assertEqual(codigo, 0, relatorio)
        self.assertIn("AVISO: data no futuro", relatorio)
        resumo, entrevistas = seo.dados()
        gerado = comparacao.corpo(resumo, seo.visiveis(resumo, entrevistas), self.lida())
        self.assertIn("a 1 de janeiro de 2099</p>", gerado)

    def test_uma_prova_do_site_do_partido_fica_marcada_como_tal(self):
        """A pagina escreve "site do partido" para quem le saber, antes de
        abrir, que a linha assenta numa parte interessada. E o unico tipo
        que o dominio decide, pela lista do YAML."""
        codigo, relatorio = self.adicionar("2025-07-03 RTP2 https://ps.pt/exemplo-do-formulario", self.PESSOA)
        self.assertEqual(codigo, 0, relatorio)
        self.assertIn("[partido]", relatorio)
        self.assertEqual(self.lida()["entrevistas"][-1]["tipo_prova"], "partido")

    def test_recusa_sem_escrever_o_que_a_pagina_nao_contaria(self):
        """Cada caso deixava uma linha no ficheiro que a pagina nao conta
        ou conta mal: antes de a pessoa contar, a mesma prova duas vezes,
        a mesma pessoa no mesmo dia e canal, uma prova que ja e do
        sujeito, uma pessoa que nao existe."""
        real = self.confirmadas("carneiro")[0]
        canal_real = next(c["nome"] for c in yaml.safe_load((RAIZ / "config" / "porquinho.yml").read_text(
            encoding="utf-8"))["canais"] if c["id"] == real["canal"])
        casos = {
            "antes de assumir o cargo": ("2025-06-01 RTP2 https://teste.invalid/cedo", self.PESSOA),
            "prova ja na comparacao": (f"2025-07-04 RTP2 {real['prova']}", self.PESSOA),
            "mesma pessoa, dia e canal": (f"{real['data']} {canal_real} https://teste.invalid/outra", self.PESSOA),
            "prova do sujeito": (f"2025-07-05 RTP2 {SO_NO_TESTE}", self.PESSOA),
            "pessoa desconhecida": ("2025-07-06 RTP2 https://teste.invalid/x", "Pessoa Que Nao Existe"),
            "lote com uma ma": ("2025-07-07 RTP2 https://teste.invalid/boa; 2025-06-01 RTP2 https://teste.invalid/ma",
                                self.PESSOA),
        }
        for nome, (entradas, pessoa) in casos.items():
            with self.subTest(caso=nome):
                codigo, relatorio = self.adicionar(entradas, pessoa)
                self.assertEqual(codigo, 1, relatorio)
                self.assertIn("NADA FOI ESCRITO", relatorio)
                self.intacta()
                self.intacto()

    def test_uma_prova_da_comparacao_nao_entra_como_do_sujeito(self):
        """O seletor esquecido em "sujeito" com a ligacao de uma entrevista
        de outra pessoa punha-a na contagem errada."""
        real = self.confirmadas("carneiro")[0]
        codigo, relatorio = self.adicionar(f"2026-10-11 RTP2 {real['prova']}")
        self.assertEqual(codigo, 1, relatorio)
        self.assertIn("escolher a pessoa certa", relatorio)
        self.intacto()

    def test_a_pessoa_escreve_se_pelo_nome_ou_pelo_id(self):
        cfg = yaml.safe_load((RAIZ / "config" / "porquinho.yml").read_text(encoding="utf-8"))
        pessoas = yaml.safe_load(COMPARACAO_REAL.read_text(encoding="utf-8"))["pessoas"]
        for escrita in ("José Luís Carneiro", "jose luis carneiro", "carneiro"):
            with self.subTest(escrita=escrita):
                self.assertEqual(adicionar.escolher_pessoa(escrita, cfg["sujeito"], pessoas)[0]["id"], "carneiro")
        for escrita in ("", cfg["sujeito"]["nome"], cfg["sujeito"]["id"]):
            with self.subTest(escrita=escrita):
                self.assertEqual(adicionar.escolher_pessoa(escrita, cfg["sujeito"], pessoas), (None, ""))


class TestRemoverOutraPessoa(Base):
    """Pedido do autor a 2026-11-07: retirar provas de qualquer das tres
    pessoas pelo mesmo formulario. Retirar e vetar, nao apagar, como na
    curadoria: a linha fica no ficheiro e o veto tira-a da pagina."""

    PESSOA = "José Luís Carneiro"

    def lida(self):
        return yaml.safe_load(self.comparacao.read_text(encoding="utf-8"))

    def intacta(self):
        self.assertEqual(self.comparacao.read_text(encoding="utf-8"), self.comparacao_original)

    def linha_real(self, estado="confirmada"):
        """Uma linha real sem veto: o ficheiro real pode ja ter vetos."""
        lida = self.lida()
        vetadas = {v["prova"] for v in lida.get("remover") or []}
        return next(e for e in lida["entrevistas"]
                    if e["pessoa"] == "carneiro" and e["estado"] == estado and e["prova"] not in vetadas)

    def contas(self):
        resumo, entrevistas = seo.dados()
        visivel = comparacao.visivel_de(resumo)
        norm = comparacao.validar(self.lida(), comparacao.canais_validos(), visivel)
        return comparacao.contar(norm, seo.visiveis(resumo, entrevistas), visivel), resumo, entrevistas

    def test_o_veto_tira_a_linha_da_pagina_e_deixa_a_no_ficheiro(self):
        """A linha da entrevista fica byte a byte no ficheiro e deixa de
        contar e de aparecer; o motivo fica no veto. Um motivo com dois
        pontos nao pode partir o YAML."""
        real = self.linha_real()
        antes = next(p for p in self.contas()[0]["pessoas"] if p["id"] == "carneiro")["total"]
        codigo, relatorio = self.remover(real["prova"], "nota: canal errado", self.PESSOA)
        self.assertEqual(codigo, 0, relatorio)
        self.assertIn("sai da contagem", relatorio)
        self.intacto()
        lida = self.lida()
        vetos_antes = yaml.safe_load(self.comparacao_original).get("remover") or []
        self.assertEqual(lida["remover"], [*vetos_antes, {"prova": real["prova"], "motivo": "nota: canal errado"}])
        self.assertIn(real, lida["entrevistas"])
        contas, resumo, entrevistas = self.contas()
        self.assertEqual(next(p for p in contas["pessoas"] if p["id"] == "carneiro")["total"], antes - 1)
        gerado = comparacao.corpo(resumo, seo.visiveis(resumo, entrevistas), lida)
        self.assertNotIn(html.escape(real["prova"], quote=True), gerado)

    def test_trocar_uma_prova_por_outra_melhor(self):
        """O caminho para substituir uma prova e `remover` e depois
        `adicionar` no mesmo dia e canal. Sem excluir as linhas vetadas, a
        segunda recusava "ja tem uma entrevista confirmada a esse dia", e
        trocar uma prova ficava impossivel pelo formulario."""
        real = self.linha_real()
        nome_canal = next(c["nome"] for c in yaml.safe_load((RAIZ / "config" / "porquinho.yml").read_text(
            encoding="utf-8"))["canais"] if c["id"] == real["canal"])
        self.assertEqual(self.remover(real["prova"], "troca por prova melhor", self.PESSOA)[0], 0)
        codigo, relatorio = self.adicionar(f"{real['data']} {nome_canal} https://teste.invalid/prova-melhor", self.PESSOA)
        self.assertEqual(codigo, 0, relatorio)
        codigo, relatorio = self.adicionar(f"2025-07-02 RTP2 {real['prova']}", self.PESSOA)
        self.assertEqual(codigo, 1, relatorio)
        self.assertIn("foi vetada na comparacao: troca por prova melhor", relatorio)

    def test_recusa_sem_escrever_o_que_nao_retirava_nada(self):
        """Cada caso era um veto que nao mudava a pagina, ou mudava a
        pessoa errada, e deixava quem preencheu convencido do contrario."""
        real = self.linha_real()
        incerta = self.linha_real("por_verificar")
        vetadas = {v["prova"] for v in self.lida().get("remover") or []}
        outra = next(e for e in self.lida()["entrevistas"]
                     if e["pessoa"] == "montenegro" and e["estado"] == "confirmada" and e["prova"] not in vetadas)
        casos = {
            "nao esta na comparacao": (["https://teste.invalid/nao-existe"], self.PESSOA, "nao esta na comparacao"),
            "de outra pessoa": ([outra["prova"]], self.PESSOA, "de outra pessoa"),
            "linha por verificar": ([incerta["prova"]], self.PESSOA, "nao conta"),
            "prova do sujeito": ([SO_NO_TESTE], self.PESSOA, "e do sujeito"),
            "repetida no lote": ([real["prova"], real["prova"]], self.PESSOA, "repetida"),
            "pessoa desconhecida": ([real["prova"]], "Pessoa Que Nao Existe", "nao reconhecida"),
        }
        for nome, (provas, pessoa, motivo) in casos.items():
            with self.subTest(caso=nome):
                codigo, relatorio = self.remover("; ".join(provas), pessoa=pessoa)
                self.assertEqual(codigo, 1, relatorio)
                self.assertIn(motivo, relatorio)
                self.assertIn("NADA FOI ESCRITO", relatorio)
                self.intacta()
                self.intacto()
        self.assertEqual(self.remover(real["prova"], pessoa=self.PESSOA)[0], 0)
        codigo, relatorio = self.remover(real["prova"], pessoa=self.PESSOA)
        self.assertEqual(codigo, 1, relatorio)
        self.assertIn("ja estava vetada", relatorio)

    def test_uma_prova_da_comparacao_nao_se_retira_como_do_sujeito(self):
        """Com o seletor esquecido no sujeito, a mensagem antiga dizia que
        a ligacao nao estava no site, que e falso: esta, mas e de outra
        pessoa."""
        codigo, relatorio = self.remover(self.linha_real()["prova"])
        self.assertEqual(codigo, 1, relatorio)
        self.assertIn("escolher a pessoa certa", relatorio)
        self.intacto()


class TestFormularios(unittest.TestCase):
    def test_as_opcoes_do_seletor_sao_as_pessoas_da_configuracao(self):
        """As opcoes do seletor vivem nos workflows, porque o GitHub nao as
        le de outro ficheiro. Uma pessoa acrescentada ao YAML sem opcao no
        formulario nao se podia escolher, e uma opcao com o nome mal
        escrito falhava so no dia em que alguem a escolhesse."""
        sujeito = yaml.safe_load((RAIZ / "config" / "porquinho.yml").read_text(encoding="utf-8"))["sujeito"]["nome"]
        pessoas = [p["nome"] for p in yaml.safe_load(COMPARACAO_REAL.read_text(encoding="utf-8"))["pessoas"]]
        for nome, caminho in WORKFLOWS.items():
            with self.subTest(workflow=nome):
                workflow = yaml.safe_load(caminho.read_text(encoding="utf-8"))
                campo = (workflow.get("on") or workflow[True])["workflow_dispatch"]["inputs"]["pessoa"]
                self.assertEqual(campo["type"], "choice")
                self.assertEqual(campo["options"], [sujeito, *pessoas])
                self.assertEqual(campo["default"], sujeito)
                texto = caminho.read_text(encoding="utf-8")
                self.assertIn("config/comparacao.yml", texto.split("git add", 1)[1].splitlines()[0])

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
        """A mesma barreira da recolha: uma regressao nunca chega a
        escrever dados."""
        for nome, caminho in WORKFLOWS.items():
            texto = caminho.read_text(encoding="utf-8")
            with self.subTest(workflow=nome):
                self.assertLess(texto.index("python -m unittest"), texto.index("python -m recolha.principal"))
                self.assertLess(texto.index("node --test"), texto.index("git push"))


    def test_o_site_e_regenerado_antes_dos_testes(self):
        """Simulacao de 2026-11-07: uma entrevista de outra pessoa escrita
        em config/comparacao.yml e os testes corridos logo a seguir davam 3
        falhas (pagina publicada atras do gerado, 37 provas em vez de 38,
        periodo antigo), e o formulario parava sem publicar. A pagina de
        Comparacao le o YAML diretamente; tem de ser regenerada entre o
        formulario escrever e os testes correrem."""
        for nome, caminho in WORKFLOWS.items():
            with self.subTest(workflow=nome):
                texto = caminho.read_text(encoding="utf-8")
                escreve = texto.index(f"python -m ferramentas.{nome}")
                self.assertLess(texto.index("python -m ferramentas.gerar_seo", escreve), texto.index("python -m unittest"))


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
