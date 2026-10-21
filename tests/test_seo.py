"""O que os motores de pesquisa e os agentes leem tem de estar publicado.

Cada teste aqui trava um erro concreto:

- o site publicar um numero no HTML diferente do que o resumo mede;
- as paginas voltarem a entregar um esqueleto sem conteudo a quem nao
  executa JavaScript, que e o caso de todos os agentes de recolha dos
  modelos de linguagem;
- um texto de um terceiro, com um travessao, partir a suite no dia em
  que a entrevista entrar;
- a pagina de fontes mostrar colunas diferentes com e sem JavaScript;
- os marcadores desaparecerem de uma pagina e o bloco deixar de ser
  escrito sem que nada falhe.
"""

from __future__ import annotations

import json
import re
import unittest

from tests.apoio import RAIZ

from ferramentas import gerar_seo, seo


class TestGerado(unittest.TestCase):
    def test_o_publicado_corresponde_ao_gerado(self):
        """Mesma garantia que a Metodologia e os textos ja tinham: o que
        esta em docs e o que o gerador produz a partir da configuracao e
        dos dados desta corrida. Sem isto, uma alteracao ao seo.yml ficava
        no repositorio sem nunca chegar ao site."""
        fora = gerar_seo.desactualizados()
        self.assertEqual(fora, [], "correr: python -m ferramentas.gerar_seo")


class TestConteudoSemJavaScript(unittest.TestCase):
    def setUp(self):
        self.resumo, self.entrevistas = seo.dados()
        self.lista = seo.visiveis(self.resumo, self.entrevistas)
        self.cfg = seo.carregar()

    def test_a_pagina_principal_traz_o_total_e_os_canais(self):
        texto = (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")
        bloco = texto.split(seo.INICIO_CORPO)[1].split(seo.FIM_CORPO)[0]
        total = self.resumo["totais"]["entrevistas"]
        self.assertIn(str(total), bloco)
        for canal in self.resumo["por_canal"]:
            if canal["entrevistas"]:
                self.assertIn(canal["nome"], bloco, f"falta {canal['canal']} no bloco servido sem JavaScript")

    def test_a_pagina_de_fontes_traz_todas_as_provas(self):
        """E a pagina que vale por si a quem le sem JavaScript: sem ela o
        site afirma um numero e nao mostra uma unica prova."""
        texto = (RAIZ / "docs" / "fontes.html").read_text(encoding="utf-8")
        bloco = texto.split(seo.INICIO_CORPO)[1].split(seo.FIM_CORPO)[0]
        self.assertEqual(bloco.count("<tr><td>"), len(self.lista))
        for entrevista in self.lista:
            for transmissao in entrevista.get("transmissoes") or [entrevista]:
                self.assertIn(transmissao["prova_url"].replace("&", "&amp;"), bloco)

    def test_o_bloco_nao_inventa_numeros(self):
        """Todo o numero do bloco vem do resumo. Um total escrito a mao
        no HTML seria um numero sem medicao, e envelhecia na primeira
        recolha."""
        gerado = seo.corpo_index(self.cfg, self.resumo, self.lista)
        for canal in self.resumo["por_canal"]:
            if canal["entrevistas"]:
                self.assertIn(f"{canal['nome']}: {canal['entrevistas']}", gerado)

    def test_um_travessao_em_texto_de_terceiro_nao_chega_ao_html(self):
        """Ha um teste que proibe travessoes em tudo o que e versionado,
        e o bloco escreve texto que veio dos dados. Sem esta troca, um
        campo de terceiros com um travessao parava a recolha seguinte."""
        self.assertEqual(seo.texto("Entrevista \u2014 parte 1 \u2013 fim"), "Entrevista - parte 1 - fim")

    def test_o_programa_e_o_titulo_nao_chegam_a_pagina_de_fontes(self):
        """A coluna de programa saiu a 2026-10-21: o que se conta e o
        canal. Medido nos dados de 2026-10-21: o programa vinha vazio ou
        "nao apurado" em 54 das 79 linhas visiveis. Trava o regresso da
        coluna pela porta do gerador."""
        entrevista = dict(self.lista[0])
        entrevista["programa"] = "Programa-sentinela"
        entrevista["titulo"] = "Titulo-sentinela"
        gerado = seo.corpo_fontes(self.cfg, self.resumo, [entrevista])
        self.assertNotIn("Programa-sentinela", gerado)
        self.assertNotIn("Titulo-sentinela", gerado)
        self.assertNotIn("<th>Programa</th>", gerado)
        linha = re.search(r"<tr><td>.*?</tr>", gerado).group(0)
        self.assertEqual(linha.count("<td>"), len(seo.COLUNAS_FONTES))

    def test_a_tabela_sem_javascript_tem_as_colunas_do_site(self):
        """A pagina de fontes e desenhada duas vezes: pelo `fontes.js` no
        browser e pelo gerador para quem le sem JavaScript. Se uma das
        duas mudar de colunas sozinha, um motor e um visitante leem
        tabelas diferentes da mesma pagina."""
        js = (RAIZ / "docs" / "fontes.js").read_text(encoding="utf-8")
        achado = re.search(r'el\("tr", \{\}, \[([^\]]*)\]\.map', js)
        self.assertIsNotNone(achado, "cabecalho da tabela nao encontrado em docs/fontes.js")
        do_js = tuple(re.findall(r'"([^"]+)"', achado.group(1)))
        self.assertEqual(do_js, seo.COLUNAS_FONTES)
        publicado = (RAIZ / "docs" / "fontes.html").read_text(encoding="utf-8")
        bloco = publicado.split(seo.INICIO_CORPO)[1].split(seo.FIM_CORPO)[0]
        for cabecalho in re.findall(r"<thead>(.*?)</thead>", bloco):
            self.assertEqual(tuple(re.findall(r"<th>(.*?)</th>", cabecalho)), seo.COLUNAS_FONTES)

    def test_um_titulo_com_etiqueta_nao_fecha_o_bloco_de_dados(self):
        """Um `<` num titulo fecharia o `<script>` a meio e levava o
        resto da pagina com ele."""
        resumo = json.loads(json.dumps(self.resumo))
        entrevista = dict(self.lista[0])
        entrevista["titulo"] = "<script>mau</script>"
        gerado = seo.bloco_head(self.cfg, "fontes.html", resumo, [entrevista])
        self.assertEqual(gerado.count("</script>"), 1)


class TestMetadados(unittest.TestCase):
    def setUp(self):
        self.cfg = seo.carregar()

    def test_todas_as_paginas_tem_canonical_e_o_titulo_da_configuracao(self):
        for pagina, definicao in self.cfg["paginas"].items():
            texto = (RAIZ / "docs" / pagina).read_text(encoding="utf-8")
            with self.subTest(ficheiro=pagina):
                self.assertIn(f"<title>{definicao['titulo']}</title>", texto)
                self.assertIn(f'<link rel="canonical" href="{seo.endereco(self.cfg, pagina)}">', texto)

    def test_os_dados_estruturados_sao_json_valido(self):
        """Um bloco malformado nao da erro nenhum no browser: e ignorado
        em silencio, e o site fica sem a unica declaracao que diz aos
        motores e aos modelos do que trata."""
        for pagina in self.cfg["paginas"]:
            texto = (RAIZ / "docs" / pagina).read_text(encoding="utf-8")
            achados = re.findall(r'<script type="application/ld\+json">(.*?)</script>', texto, re.DOTALL)
            with self.subTest(ficheiro=pagina):
                self.assertEqual(len(achados), 1)
                objecto = json.loads(achados[0])
                self.assertEqual(objecto["@context"], "https://schema.org")
                self.assertTrue(objecto["@graph"])

    def test_o_sitemap_tem_as_paginas_todas_e_o_robots_aponta_para_ele(self):
        sitemap = (RAIZ / "docs" / "sitemap.xml").read_text(encoding="utf-8")
        for pagina in self.cfg["paginas"]:
            self.assertIn(f"<loc>{seo.endereco(self.cfg, pagina)}</loc>", sitemap)
        robots = (RAIZ / "docs" / "robots.txt").read_text(encoding="utf-8")
        self.assertIn(f"Sitemap: {self.cfg['base']}sitemap.xml", robots)
        self.assertIn("User-agent: *", robots)

    def test_um_marcador_em_falta_falha_alto(self):
        """Uma pagina que perca os marcadores deixaria de receber o bloco
        e ninguem daria por isso: o HTML continuava valido e o site
        continuava a servir."""
        with self.assertRaises(ValueError):
            seo.injetar("<html></html>", seo.INICIO_HEAD, seo.FIM_HEAD, "x", "teste")


if __name__ == "__main__":
    unittest.main()
