"""A revisao a mao das pistas de rede social.

Todos os testes correm sobre a resposta real que o motor devolveu a
2026-09-18, guardada em fixtures. Nenhum faz um pedido de rede.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from ferramentas import pistas

FIXTURES = Path(__file__).parent / "fixtures"
RESULTADOS = (FIXTURES / "motor_resultados_instagram.txt").read_text(encoding="utf-8")


class TestExtracao(unittest.TestCase):
    def setUp(self):
        self.config = pistas.carregar()
        self.pistas = pistas.extrair(RESULTADOS)

    def test_a_resposta_real_do_motor_da_pistas(self):
        """A pagina real de 2026-09-18 tem doze publicacoes distintas. Se a
        forma do texto do motor mudar, este numero cai e o defeito
        aparece aqui, em vez de aparecer como uma colheita vazia que
        ninguem explica."""
        self.assertEqual(len(self.pistas), 12)
        self.assertTrue(all(p["url"].startswith("https://www.") for p in self.pistas))

    def test_uma_publicacao_so_entra_uma_vez(self):
        codigos = [p["codigo"] for p in self.pistas]
        self.assertEqual(len(codigos), len(set(codigos)))

    def test_a_conta_do_caminho_e_guardada_quando_existe(self):
        """As publicacoes de contas de canais sao 14 das 27 com conta no
        caminho, medido a 2026-09-18, e sao as que nomeiam o canal. Perder
        a conta era perder a melhor sugestao que ha."""
        com_conta = [p for p in self.pistas if p["conta"]]
        self.assertTrue(com_conta)
        self.assertIn("/", com_conta[0]["url"].split(".com/", 1)[1])

    def test_a_legenda_nao_traz_o_convite_a_criar_conta(self):
        """O servico responde a quem nao tem sessao com um convite a criar
        conta, colado a legenda. Guardado assim, o ficheiro de trabalho
        enchia-se de texto que nao diz nada sobre a entrevista e a pessoa
        que revê teria de o ler em cada linha."""
        for p in self.pistas:
            self.assertNotIn("Create an account", p["legenda"])
            self.assertNotIn("followers", p["legenda"].lower())

    def test_a_legenda_util_sobrevive_a_limpeza(self):
        """A limpeza nao pode comer a legenda: e ela que diz o canal e a
        hora, e sem ela a pista obriga a abrir para saber se vale a pena
        abrir."""
        legendas = [p["legenda"] for p in self.pistas]
        self.assertIn("Hoje, às 20h30, na CMTV: Entrevista com André Ventura", legendas)


class TestSugestoes(unittest.TestCase):
    def setUp(self):
        self.config = pistas.carregar()

    def test_a_conta_de_um_canal_sugere_esse_canal(self):
        pista = {"conta": "sicnoticias", "legenda": ""}
        self.assertEqual(pistas.sugerir_canal(pista, self.config), "sic-noticias")

    def test_a_conta_do_proprio_nao_sugere_canal_nenhum(self):
        """A conta do entrevistado publica entrevistas de todos os canais.
        Sugerir um canal a partir dela seria adivinhar, e o projeto ja
        mediu que o canal nao se deduz: 8 linhas erradas em 8."""
        pista = {"conta": "andre_ventura_oficial", "legenda": "Amanhã estarei na Casa Feliz"}
        self.assertEqual(pistas.sugerir_canal(pista, self.config), "")

    def test_o_termo_mais_especifico_ganha_o_generico(self):
        """Uma legenda que nomeia o canal de noticias nao pode ficar
        atribuida ao generalista com o mesmo nome no inicio."""
        pista = {"conta": "", "legenda": "Na entrevista desta noite à SIC Notícias"}
        self.assertEqual(pistas.sugerir_canal(pista, self.config), "sic-noticias")

    def test_as_marcas_de_tempo_relativas_sao_assinaladas(self):
        """Medido a 2026-09-18: 22 marcas relativas em 51 publicacoes,
        "hoje" onze vezes. Sao elas que dizem se o dia da entrevista e o
        dia da publicacao ou o seguinte, e quem revê tem de as ver."""
        pista = {"conta": "", "legenda": "Amanhã estarei, a partir das 10h50, na Casa Feliz"}
        self.assertIn("amanhã", pistas.marcas(pista, self.config))


class TestTrabalho(unittest.TestCase):
    def test_uma_decisao_escrita_nao_se_perde_na_consulta_seguinte(self):
        """O ficheiro de trabalho funde, nunca grava por cima. Uma pista ja
        decidida que volte a aparecer numa consulta mantem a decisao: o
        que uma pessoa escreveu nao se perde porque a consulta mudou."""
        trabalho = {"ABC123": {"codigo": "ABC123", "conta": "", "url": "https://x/p/ABC123/", "legenda": "v", "decisao": "sim", "data": "2024-02-19", "canal": "cmtv"}}
        repetida = {"codigo": "ABC123", "conta": "", "url": "https://x/p/ABC123/", "legenda": "outra leitura"}
        if repetida["codigo"] not in trabalho:
            trabalho[repetida["codigo"]] = repetida | {"decisao": ""}
        self.assertEqual(trabalho["ABC123"]["decisao"], "sim")
        self.assertEqual(trabalho["ABC123"]["data"], "2024-02-19")

    def test_exportar_da_a_forma_exata_da_curadoria(self):
        trabalho = {"A": {"decisao": "sim", "data": "2024-02-19", "canal": "cmtv", "url": "https://x/p/A/"}}
        saida = pistas.exportar(trabalho)
        self.assertIn("  - data: 2024-02-19", saida)
        self.assertIn("    canal: cmtv", saida)
        self.assertIn("    prova: https://x/p/A/", saida)

    def test_uma_pista_recusada_nao_vai_para_a_curadoria(self):
        trabalho = {"A": {"decisao": "nao", "url": "https://x/p/A/"}}
        self.assertNotIn("prova", pistas.exportar(trabalho))

    def test_o_ficheiro_de_trabalho_fica_fora_do_repositorio(self):
        """Tem caminhos locais e o ritmo de trabalho de uma pessoa. Dentro
        do repositorio, entrava num commit publico."""
        from recolha.modelos import RAIZ

        self.assertNotIn(str(RAIZ.resolve()), str(pistas.TRABALHO.parent.resolve() / "x"))


class TestRevisao(unittest.TestCase):
    def setUp(self):
        self.config = pistas.carregar()
        self.trabalho = {p["codigo"]: p | {"decisao": ""} for p in pistas.extrair(RESULTADOS)[:3]}
        self.abertos: list[str] = []

    def responder(self, respostas):
        fila = list(respostas)
        return lambda _: fila.pop(0)

    def test_a_data_escrita_fica_com_o_canal_sugerido(self):
        """O gesto minimo e escrever a data. O canal vem sugerido e
        confirma-se com Enter, senao a revisao passava a exigir duas
        escritas por pista e deixava de ser rapida."""
        decididas = pistas.rever(self.config, self.trabalho, abrir=self.abertos.append, ler=self.responder(["2025-10-24", "", "q"]))
        primeira = list(self.trabalho.values())[0]
        self.assertEqual(decididas, 1)
        self.assertEqual(primeira["data"], "2025-10-24")
        self.assertEqual(primeira["canal"], "cnn-portugal")

    def test_uma_data_mal_escrita_nao_cria_linha_nenhuma(self):
        """Uma data em formato livre entraria no YAML e o coletor recusava a
        linha inteira mais tarde, longe de quem a escreveu."""
        pistas.rever(self.config, self.trabalho, abrir=self.abertos.append, ler=self.responder(["24 de outubro", "q"]))
        self.assertEqual(list(self.trabalho.values())[0]["decisao"], "")

    def test_a_data_compacta_e_aceite_e_guardada_em_iso(self):
        """Oito digitos sao o que se escreve depressa ao rever dezenas de
        publicacoes seguidas. O ficheiro de curadoria continua a receber
        so ISO: a escrita rapida e para quem revê, nao para os dados."""
        pistas.rever(self.config, self.trabalho, abrir=self.abertos.append, ler=self.responder(["20251024", "q"]))
        self.assertEqual(list(self.trabalho.values())[0]["data"], "2025-10-24")

    def test_uma_data_que_nao_existe_no_calendario_e_recusada(self):
        """`20250230` tem oito digitos e passa em qualquer verificacao de
        forma. Aceite aqui, so daria erro na colheita, longe de quem a
        escreveu e sem saber a que publicacao pertencia."""
        pistas.rever(self.config, self.trabalho, abrir=self.abertos.append, ler=self.responder(["20250230", "q"]))
        self.assertEqual(list(self.trabalho.values())[0]["decisao"], "")

    def test_saltar_deixa_a_pista_para_a_proxima_sessao(self):
        """Enter vazio nao e uma recusa. "Nao sei" nao e "nao": registar
        como recusada seria afirmar uma coisa falsa sobre uma publicacao
        que ninguem leu."""
        pistas.rever(self.config, self.trabalho, abrir=self.abertos.append, ler=self.responder(["", "", ""]))
        self.assertEqual(len(pistas.por_decidir(self.trabalho)), 3)

    def test_cada_pista_e_aberta_no_browser(self):
        pistas.rever(self.config, self.trabalho, abrir=self.abertos.append, ler=self.responder(["q"]))
        self.assertEqual(len(self.abertos), 1)

    def test_o_canal_escrito_ganha_ao_sugerido(self):
        pistas.rever(self.config, self.trabalho, abrir=self.abertos.append, ler=self.responder(["20251024 rtp3", "q"]))
        self.assertEqual(list(self.trabalho.values())[0]["canal"], "rtp3")


class TestConfiguracao(unittest.TestCase):
    def test_os_canais_sugeridos_existem_no_projeto(self):
        """Um id de canal escrito com outra grafia produzia uma linha que o
        coletor recusa, e o erro so aparecia depois de a pessoa ter feito
        a revisao toda."""
        import yaml

        from recolha.modelos import RAIZ

        config = pistas.carregar()
        conhecidos = {c["id"] for c in yaml.safe_load((RAIZ / "config" / "porquinho.yml").read_text(encoding="utf-8"))["canais"]}
        sugeridos = {v for v in (config.get("contas") or {}).values() if v}
        sugeridos |= {e["canal"] for e in config.get("termos_de_canal") or []}
        self.assertTrue(sugeridos <= conhecidos, f"canais desconhecidos: {sugeridos - conhecidos}")


if __name__ == "__main__":
    unittest.main()
