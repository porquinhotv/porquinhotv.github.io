"""Sonda de hipoteses, sem rede.

O ponto que importa: uma hipotese que responde 200 mas nao traz ligacoes
tem de aparecer no relatorio como inutil, e nao como sucesso. Foi por ler
so o codigo de resposta que o arquivo.pt passou por fonte durante uma
corrida inteira.
"""

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from tests.apoio import ler

from ferramentas import sondar
from recolha.rede import ErroDeRede


class TestAnalisar(unittest.TestCase):
    def test_conta_ligacoes_do_dominio(self):
        r = sondar.analisar(ler("pesquisa_resultados.html"), "https://exemplo.pt/p", ["Pessoa Exemplo"], "exemplo.pt")
        self.assertEqual(r["ligacoes"], 2)

    def test_pagina_de_aviso_responde_mas_nao_serve(self):
        html = "<html><body><h1>Verifique que nao e um robot</h1></body></html>"
        r = sondar.analisar(html, "https://motor.exemplo/q", ["ventura entrevista"], "")
        self.assertEqual(r["ligacoes"], 0)
        self.assertEqual(r["termos_presentes"], [])

    def test_termos_encontrados_no_texto(self):
        html = "<html><body>ventura entrevista exclusiva</body></html>"
        r = sondar.analisar(html, "https://x/y", ["ventura entrevista"], "")
        self.assertEqual(r["termos_presentes"], ["ventura entrevista"])

    def test_padrao_do_grupo_apanha_slug_sem_hifen(self):
        """Sem padrao, a heuristica exige um hifen no ultimo segmento e
        descarta em silencio um endereco de publicacao como /p/AbC123xYz9,
        que e a forma dos enderecos de uma rede social. A sonda contaria
        zero e a leitura seria "o indice nao tem", quando quem descartava
        era o filtro: o mesmo erro de motivo que a 2026-09-11 leu a pagina
        da Google como zero resultados."""
        html = '<html><body><a href="https://rede.exemplo/p/AbC123xYz9/">post</a></body></html>'
        sem = sondar.analisar(html, "https://motor.exemplo/q", [], "rede.exemplo")
        self.assertEqual(sem["ligacoes"], 0, "a heuristica sem padrao descarta o slug sem hifen, e e por isso que o padrao do grupo existe")
        com = sondar.analisar(html, "https://motor.exemplo/q", [], "rede.exemplo", padrao="/p/[A-Za-z0-9_-]{6,}")
        self.assertEqual(com["ligacoes"], 1)
        self.assertEqual(com["exemplos"], ["https://rede.exemplo/p/AbC123xYz9"])


class TestEnderecosDeclarados(unittest.TestCase):
    """Uma resposta que declara enderecos sem os ligar nao pode contar zero.

    A 2026-09-09 o `post-sitemap.xml` do jornal de verificacao, 374 KB,
    leu-se como falha porque a sonda so contava `href`. O indice de um
    arquivo da web responde em texto, um endereco por linha, e teria
    contado zero pela mesma razao.
    """

    def test_mapa_de_sitio_conta_os_loc(self):
        r = sondar.analisar(ler("mapa_pecas_exemplo.xml"), "https://jornal.exemplo/mapa.xml", [], "")
        self.assertGreater(r["enderecos"], 0)
        self.assertEqual(r["ligacoes"], 0, "um mapa nao tem href, e e por isso que a coluna dos enderecos existe")
        self.assertTrue(all(e.startswith("http") for e in r["exemplos_enderecos"]))

    def test_indice_em_texto_conta_uma_linha_por_endereco(self):
        cdx = (
            "20210112101500 https://exemplo.pt/pais/2021-01-12-entrevista-a-pessoa-exemplo 200\n"
            "20220305221000 https://exemplo.pt/pais/2022-03-05-pessoa-exemplo-em-entrevista 200\n"
        )
        r = sondar.analisar(cdx, "https://arquivo.exemplo/cdx", ["Pessoa Exemplo"], "")
        self.assertEqual(r["enderecos"], 2)
        self.assertEqual(r["exemplos_enderecos"][0].split()[1], "https://exemplo.pt/pais/2021-01-12-entrevista-a-pessoa-exemplo")

    def test_html_sem_loc_nao_declara_enderecos(self):
        r = sondar.analisar(ler("pesquisa_resultados.html"), "https://exemplo.pt/p", [], "exemplo.pt")
        self.assertEqual(r["enderecos"], 0)
        self.assertEqual(r["ligacoes"], 2)

    def test_amostra_guarda_o_inicio_do_texto(self):
        robots = "User-agent: *\nCrawl-Delay: 300\nSitemap: https://exemplo.pt/mapa.xml\n"
        r = sondar.analisar(robots, "https://exemplo.pt/robots.txt", [], "")
        self.assertIn("Crawl-Delay: 300", r["amostra"])
        self.assertLessEqual(len(r["amostra"]), sondar.AMOSTRA_CHARS)


class TestFundir(unittest.TestCase):
    """Uma corrida de um grupo so nao pode apagar as outras.

    O commit 98fcc31 escreveu o resultado de `--grupo` por cima do
    ficheiro e perdeu 632 linhas de sondagens do dia anterior.
    """

    def test_grupo_novo_junta_se_aos_antigos(self):
        anterior = {"verificado_em": "2026-09-08T10:00:00+00:00", "termo": "x",
                    "grupos": [{"nome": "A", "hipoteses": [{"url": "a"}]}]}
        novo = {"verificado_em": "2026-09-10T10:00:00+00:00", "termo": "x",
                "grupos": [{"nome": "B", "hipoteses": [{"url": "b"}]}]}
        r = sondar.fundir(anterior, novo)
        self.assertEqual([g["nome"] for g in r["grupos"]], ["A", "B"])
        self.assertEqual(r["grupos"][0]["verificado_em"], "2026-09-08T10:00:00+00:00")
        self.assertEqual(r["grupos"][1]["verificado_em"], "2026-09-10T10:00:00+00:00")

    def test_grupo_com_o_mesmo_nome_e_substituido(self):
        anterior = {"verificado_em": "2026-09-08T10:00:00+00:00", "termo": "x",
                    "grupos": [{"nome": "A", "hipoteses": [{"url": "velho"}]}]}
        novo = {"verificado_em": "2026-09-10T10:00:00+00:00", "termo": "x",
                "grupos": [{"nome": "A", "hipoteses": [{"url": "novo"}]}]}
        r = sondar.fundir(anterior, novo)
        self.assertEqual(len(r["grupos"]), 1)
        self.assertEqual(r["grupos"][0]["hipoteses"][0]["url"], "novo")

    def test_escrever_funde_com_o_ficheiro_existente(self):
        with tempfile.TemporaryDirectory() as pasta:
            sondar.escrever({"verificado_em": "2026-09-08T10:00:00+00:00", "termo": "x",
                             "grupos": [{"nome": "A", "hipoteses": [{"url": "a", "responde": False, "erro": "x"}]}]}, Path(pasta))
            sondar.escrever({"verificado_em": "2026-09-10T10:00:00+00:00", "termo": "x",
                             "grupos": [{"nome": "B", "hipoteses": [{"url": "b", "responde": False, "erro": "y"}]}]}, Path(pasta))
            md = (Path(pasta) / "SONDAGEM.md").read_text(encoding="utf-8")
            self.assertIn("## A", md)
            self.assertIn("## B", md)


class TestGrupoQueNaoExiste(unittest.TestCase):
    """Um nome de grupo errado nao pode acabar em "escrito em ...".

    A 2026-09-10 sete corridas seguidas pediram grupos que a
    configuracao daquele momento nao tinha. Nenhuma pediu nada a lado
    nenhum, todas imprimiram a linha de sucesso, e o relatorio ficou
    vazio no lugar do que la estava. O codigo de saida e a lista dos
    nomes existentes sao o que torna isso visivel na consola, que e a
    interface deste projeto.
    """

    def setUp(self):
        self.config = {"termo": "x", "grupos": [{"nome": "Grupo A", "hipoteses": ["https://x/"]}]}

    def test_nome_errado_nao_corre_e_devolve_erro(self):
        with tempfile.TemporaryDirectory() as pasta:
            alvo = Path(pasta) / "sondagem.json"
            with unittest.mock.patch.object(sondar, "carregar", lambda: self.config), \
                 unittest.mock.patch.object(sondar, "PASTA", Path(pasta)), \
                 unittest.mock.patch.object(sondar, "correr", self._nunca):
                codigo = sondar.main(["--grupo", "Arquivo da web, o indice"])
            self.assertEqual(codigo, 2)
            self.assertFalse(alvo.exists(), "uma corrida que nao encontrou o grupo nao escreve por cima de nada")

    def test_nome_certo_corre(self):
        self.assertIn("Grupo A", sondar.nomes_dos_grupos(self.config))

    def _nunca(self, *args, **kwargs):
        raise AssertionError("nao se pede nada a rede quando o grupo nao existe")


class TestTempoLimite(unittest.TestCase):
    """Um grupo que pede mais tempo por pedido tem de o passar a rede.

    A 2026-09-10 cinco de nove consultas ao indice de um arquivo da web
    apareceram no relatorio como "nao responde", e o que se tinha passado
    era terem demorado mais do que os 30 s de omissao. "Nao responde em
    30 s" e outra coisa, e um indice que varre um dominio inteiro demora
    mesmo mais.
    """

    def test_o_limite_do_grupo_chega_ao_pedido(self):
        pedidos = []

        def obter(url, **extra):
            pedidos.append(extra)
            return "<html></html>"

        config = {"termo": "x", "grupos": [
            {"nome": "Lento", "tempo_limite_s": 120, "hipoteses": ["https://lento/"]},
            {"nome": "Normal", "hipoteses": ["https://normal/"]},
        ]}
        sondar.correr(config, obter=obter, dormir=lambda s: None)
        self.assertEqual(pedidos, [{"limite_s": 120}, {}])


class TestCorrida(unittest.TestCase):
    def setUp(self):
        self.config = {
            "termo": "ventura entrevista",
            "grupos": [
                {"nome": "G1", "dominio_alvo": "exemplo.pt", "hipoteses": [
                    "https://exemplo.pt/pesquisa?q={termo}",
                    "https://falha.pt/?q={termo}",
                ]},
            ],
        }

    def _obter(self, url):
        if "falha" in url:
            raise ErroDeRede("HTTP Error 403")
        return ler("pesquisa_resultados.html")

    def test_corrida_e_relatorio(self):
        r = sondar.correr(self.config, obter=self._obter, dormir=lambda s: None)
        h = r["grupos"][0]["hipoteses"]
        self.assertTrue(h[0]["responde"])
        self.assertEqual(h[0]["ligacoes"], 2)
        self.assertFalse(h[1]["responde"])
        md = sondar.relatorio(r)
        self.assertIn("| G1", md) if "| G1" in md else self.assertIn("## G1", md)
        for t in ("\u2014", "\u2013"):
            self.assertNotIn(t, md)

    def test_termo_codificado_no_url(self):
        r = sondar.correr(self.config, obter=self._obter, dormir=lambda s: None)
        self.assertIn("ventura+entrevista", r["grupos"][0]["hipoteses"][0]["url"])

    def test_escrita_em_lf(self):
        r = sondar.correr(self.config, obter=self._obter, dormir=lambda s: None)
        with tempfile.TemporaryDirectory() as pasta:
            sondar.escrever(r, Path(pasta))
            for nome in ("sondagem.json", "SONDAGEM.md"):
                self.assertNotIn(b"\r\n", (Path(pasta) / nome).read_bytes())

    def test_nomes_de_grupo_nao_se_repetem(self):
        """Dois grupos com o mesmo nome tornam --grupo ambiguo.

        O nome do grupo e o que a pessoa escreve na consola e o que a
        fusao usa para saber o que substituir. Dois iguais fariam o
        --grupo correr um deles sem dizer qual, e a fusao apagar o outro.
        """
        nomes = sondar.nomes_dos_grupos(sondar.carregar())
        repetidos = sorted({n for n in nomes if nomes.count(n) > 1})
        self.assertEqual(repetidos, [], "grupos com nome repetido")

    def test_configuracao_real_carrega(self):
        cfg = sondar.carregar()
        self.assertTrue(cfg["grupos"])
        self.assertTrue(cfg["dominios_de_interesse"], "sem dominios, um motor de busca nunca conta ligacoes")
        for g in cfg["grupos"]:
            self.assertTrue(g["hipoteses"], g["nome"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
