"""A pagina de comparacao so pode afirmar o que os dados medem.

Cada teste trava um erro concreto:

- uma linha por verificar entrar na contagem;
- o fecho ficar atras da entrevista mais recente, e a pagina contar
  menos do que a pagina inicial, ou recuar para antes do levantamento;
- um ritmo datado, medido sobre meses que ja nao descrevem o presente;
- a pagina por periodos diferentes a competir pelo total, esconder que
  alguem entrou mais tarde, ou mostrar um numero do sujeito que nao bate
  com a pagina inicial;
- uma entrevista em dois canais contar duas vezes, ou duas entrevistas
  no mesmo dia em canais diferentes contarem uma;
- um erro no YAML (canal mal escrito, prova em falta, linha repetida,
  uma prova do site de um partido sem o rotulo que o diz) ficar calado
  na pagina;
- a frase satirica afirmar uma comparacao que os numeros ja nao dizem;
- a pagina publicada perder uma prova, ou mostrar uma por verificar.
"""

from __future__ import annotations

import copy
import datetime as dt
import html
import unittest

from tests.apoio import RAIZ

from ferramentas import comparacao, seo

CANAIS = {"c1", "c2", "c3"}
VISIVEL = dt.date(2024, 1, 1)
RESUMO = {
    "ambito": {"visivel_desde": "2024-01-01"},
    "sujeito": {"id": "s", "nome": "Sujeito"},
    "por_canal": [{"canal": "c1", "nome": "Canal Um"}, {"canal": "c2", "nome": "Canal Dois"},
                  {"canal": "c3", "nome": "Canal Tres"}],
}


def linha(pessoa="a", data="2025-07-01", canal="c1", estado="confirmada", **mais):
    base = {"pessoa": pessoa, "data": data, "canal": canal, "formato": "informativa", "estado": estado,
            "tipo_prova": "canal", "prova": f"https://exemplo.pt/{pessoa}/{data}/{canal}/{estado}"}
    base.update(mais)
    return base


def cfg_minima(entrevistas=()):
    """A configuracao real com duas pessoas de teste: os textos sao os
    publicados, para que um teste nao passe com textos que a pagina nunca
    usaria."""
    real = comparacao.carregar()
    return {
        "janela": {"desde": "2025-06-28", "levantamento": "2026-10-30"},
        "sujeito": {"cargo": "cargo do sujeito"},
        "pessoas": [
            {"id": "a", "nome": "Pessoa A", "cargo": "cargo A", "desde": "2024-01-01"},
            {"id": "b", "nome": "Pessoa B", "cargo": "cargo B", "desde": "2025-06-28",
             "marco": "Pessoa B assume o cargo", "antes": "ainda sem o cargo"},
        ],
        "rotulos_de_prova": {"canal": "ver", "imprensa": "notícia", "partido": "site do partido", "ligacao": "ver"},
        "dominios_de_partido": ["partido.pt"],
        "textos": copy.deepcopy(real["textos"]),
        "entrevistas": list(entrevistas),
    }


def contas(cfg, lista=()):
    norm = comparacao.validar(cfg, CANAIS, VISIVEL)
    return comparacao.contar(norm, list(lista), VISIVEL)


def pessoa(contas_, pid):
    return next(p for p in contas_["pessoas"] if p["id"] == pid)


class TestContagem(unittest.TestCase):
    def test_o_ficheiro_publicado_e_valido(self):
        """O gerador corre dentro do `gerar_seo`, em todos os workflows que
        escrevem dados. Um YAML invalido parava o `adicionar` de uma
        entrevista do sujeito que nada tem a ver com esta pagina; tem de
        falhar aqui, na suite, antes de chegar ao formulario."""
        resumo, _ = seo.dados()
        comparacao.validar(comparacao.carregar(), comparacao.canais_validos(), comparacao.visivel_de(resumo))

    def test_so_as_confirmadas_contam(self):
        """O levantamento de 2026-10-30 trazia tres linhas por verificar do
        segundo lider que, contadas, o levavam de 24 a 27. A 2026-11-06 a
        leitura das provas confirmou duas delas e deixou duas outras sem
        prova do dia. "Nao sei" nao e "sim": uma por verificar fica no
        ficheiro e fora de todos os numeros, e a pagina diz quantas ficaram."""
        cfg = cfg_minima([linha(data="2025-07-01"),
                          linha(data="2025-08-01", estado="por_verificar"),
                          linha(data="2023-12-20", estado="fora_do_ambito")])
        a = pessoa(contas(cfg), "a")
        self.assertEqual((a["janela"], a["por_verificar"]), (1, 1))
        gerado = comparacao.corpo(RESUMO, [], cfg, CANAIS)
        self.assertIn("Pessoa A: 1 entrevista exclusiva", gerado)
        self.assertNotIn("2025-08-01", gerado)
        self.assertNotIn("2023-12-20", gerado)

    def test_o_fecho_segue_a_entrevista_mais_recente_de_qualquer_dos_tres(self):
        """Ate 2026-11-07 o fecho escrevia-se a mao: uma entrevista nova do
        sujeito entrava na pagina inicial e ficava fora desta, e as duas
        paginas discordavam ate alguem mover a data. Pedido do autor nesse
        dia: o site inteiro acompanha cada entrevista nova, de qualquer
        dos tres. O fecho e a entrevista confirmada mais recente, de
        qualquer pessoa, e nunca antes do fim do levantamento, ate onde as
        outras foram procuradas; uma por verificar nao o move."""
        lista = [{"data": "2025-06-27"}, {"data": "2025-06-28"}, {"data": "2026-10-30"}, {"data": "2026-11-03"},
                 {"data": "2024-01-01"}]
        c = contas(cfg_minima(), lista)
        self.assertEqual(c["ate"], dt.date(2026, 11, 3))
        self.assertEqual((c["sujeito"]["janela"], c["sujeito"]["total"]), (3, 5))
        outra = contas(cfg_minima([linha(pessoa="b", data="2026-11-10")]), lista)
        self.assertEqual(outra["ate"], dt.date(2026, 11, 10))
        self.assertEqual(contas(cfg_minima(), [{"data": "2026-01-05"}])["ate"], dt.date(2026, 10, 30))
        incerta = cfg_minima([linha(pessoa="b", data="2026-12-01", estado="por_verificar")])
        self.assertEqual(contas(incerta, lista)["ate"], dt.date(2026, 11, 3))
        gerado = comparacao.corpo(RESUMO, lista, cfg_minima(), CANAIS)
        self.assertIn('<p class="periodo">1 de janeiro de 2024 a 3 de novembro de 2026</p>', gerado)

    def test_uma_entrevista_em_dois_canais_conta_uma_vez(self):
        """O levantamento tem dois casos de simulcast, os dois num par de
        canais do mesmo grupo. Como no resto do site, contam uma vez,
        atribuidos a um canal, e a linha diz por palavras que passou tambem
        no outro."""
        cfg = cfg_minima([linha(canal="c1", tambem_em=["c2"])])
        self.assertEqual(pessoa(contas(cfg), "a")["janela"], 1)
        gerado = comparacao.corpo(RESUMO, [], cfg, CANAIS)
        self.assertIn("Canal Um<span class=\"parcial\"> (também na Canal Dois)</span>", gerado)

    def test_duas_entrevistas_no_mesmo_dia_em_canais_diferentes_contam_as_duas(self):
        """O segundo lider tem dois dias com duas entrevistas em canais
        diferentes (2025-10-29 e 2026-02-18), uma na Grande Entrevista e
        outra noutro canal na mesma noite. A regra do site e que nao
        colapsam, e a verificacao de linhas repetidas nao as pode juntar."""
        cfg = cfg_minima([linha(pessoa="b", data="2025-10-29", canal="c1"),
                          linha(pessoa="b", data="2025-10-29", canal="c2")])
        self.assertEqual(pessoa(contas(cfg), "b")["janela"], 2)

    def test_quem_entrou_mais_tarde_tem_a_faixa_riscada_e_nao_compete_pelo_total(self):
        """O autor pediu a 2026-11-06 todas as entrevistas do sujeito a
        vista, com a ressalva de que o segundo lider so entrou a 2025-06-28.
        A faixa dele fica riscada antes dessa data e diz porque, para uma
        faixa vazia nunca parecer uma pessoa calada; e a comparacao numero
        contra numero faz-se so no periodo comum."""
        cfg = cfg_minima([linha(pessoa="b", data="2025-07-01")])
        b = pessoa(contas(cfg), "b")
        self.assertEqual((b["inicio"], b["total"], b["janela"]), (dt.date(2025, 6, 28), 1, 1))
        gerado = comparacao.corpo(RESUMO, [{"data": "2024-03-01"}, {"data": "2025-07-02"}], cfg, CANAIS)
        self.assertEqual(gerado.count('<span class="antes">'), 17)  # jan 2024 a mai 2025
        self.assertIn("ainda sem o cargo", gerado)
        self.assertIn("28 de junho de 2025: Pessoa B assume o cargo.", gerado)
        self.assertIn("<strong>Sujeito 1</strong>", gerado)  # so a de 2025-07-02 no periodo comum

    def test_o_ritmo_mede_so_o_ultimo_ano(self):
        """Medido desde o inicio, o ritmo do primeiro-ministro dava uma a
        cada 87 dias com o fecho a 2026-11-06, todas antes de 26 de junho
        de 2025: um numero datado, que descrevia um ritmo que ja nao
        existia. Mede-se so o ultimo ano ate ao fecho, igual para todos;
        uma entrevista de ha mais de um ano conta no total e nao no ritmo,
        e o cartao diz "nenhuma no ultimo ano" em vez de um ritmo."""
        cfg = cfg_minima([linha(pessoa="a", data="2024-03-01"), linha(pessoa="a", data="2025-10-30"),
                          linha(pessoa="b", data="2025-11-01"), linha(pessoa="b", data="2026-10-30", canal="c2")])
        c = contas(cfg, [{"data": "2024-01-01"}, {"data": "2025-10-31"}])
        self.assertEqual(c["ano"], dt.date(2025, 10, 31))
        self.assertEqual((pessoa(c, "a")["total"], pessoa(c, "a")["ano"]), (2, 0))
        self.assertEqual((pessoa(c, "b")["ano"], pessoa(c, "b")["ano_duracao"]), (2, 365))
        self.assertEqual((c["sujeito"]["total"], c["sujeito"]["ano"]), (2, 1))
        gerado = comparacao.corpo(RESUMO, [{"data": "2024-01-01"}, {"data": "2025-10-31"}], cfg, CANAIS)
        self.assertIn("uma a cada 182 dias no último ano", gerado)  # 365 / 2, da pessoa B
        self.assertIn("nenhuma no último ano", gerado)
        self.assertIn("de 31 de outubro de 2025 a 30 de outubro de 2026", gerado)

    def test_quem_entra_a_meio_do_ano_mede_se_desde_que_entrou(self):
        """Contar como silencio os meses em que alguem ainda nao estava no
        cargo tornava o seu ritmo artificialmente lento."""
        cfg = cfg_minima([linha(pessoa="b", data="2026-07-01")])
        cfg["pessoas"][1]["desde"] = "2026-06-01"
        self.assertEqual(pessoa(contas(cfg), "b")["ano_duracao"], (dt.date(2026, 10, 30) - dt.date(2026, 6, 1)).days + 1)

    def test_o_ultimo_ano_e_um_ano_de_calendario(self):
        self.assertEqual(comparacao.inicio_do_ultimo_ano(dt.date(2026, 11, 6)), dt.date(2025, 11, 7))
        self.assertEqual(comparacao.inicio_do_ultimo_ano(dt.date(2028, 2, 29)), dt.date(2027, 3, 1))


class TestTexto(unittest.TestCase):
    def test_a_razao_nunca_arredonda_para_cima(self):
        """52 contra 25 da 2,08. "Deu duas" seria arredondar a favor de
        ninguem e contra a conta; "deu mais de duas" e verdade. A frase so
        diz um numero redondo quando a divisao e exacta."""
        self.assertEqual(comparacao.razao(52, 25), "mais de duas")
        self.assertEqual(comparacao.razao(50, 25), "duas")
        self.assertEqual(comparacao.razao(13, 1), "13")

    def test_a_frase_do_porquinho_segue_os_numeros(self):
        """O veredicto afirma comparacoes. A satira do fim ("onde ha lama,
        ha camaras") so cabe se o sujeito deu mais do que cada um dos
        outros; se um deles o igualar, a frase tem de o dizer, e nunca o
        contrario do que os numeros mostram."""
        t = cfg_minima()["textos"]
        remate = comparacao._preencher(t["remate"])
        frases = comparacao.frases_da_comparacao(t, 52, [{"nome": "A", "janela": 25}, {"nome": "B", "janela": 0}])
        self.assertEqual(frases[0], comparacao._preencher(t["frase_razao"], nome="A", razao="mais de duas"))
        self.assertEqual(frases[1], comparacao._preencher(t["frase_zero"], nome="B"))
        self.assertEqual(frases[-1], remate)
        empate = comparacao.frases_da_comparacao(t, 25, [{"nome": "A", "janela": 25}])
        self.assertEqual(empate, [comparacao._preencher(t["frase_empate"], nome="A", n=25)])

    def test_o_numero_do_sujeito_bate_com_a_pagina_inicial(self):
        """A primeira versao mostrava 81 (cortado a 30 out) e a pagina
        inicial 82; o autor viu-o a 2026-11-06. Com o fecho derivado
        (2026-11-07), o cartao do sujeito e exactamente o total da pagina
        inicial, sempre, e o periodo acaba no fecho, escrito por extenso."""
        resumo, entrevistas = seo.dados()
        visivel = comparacao.visivel_de(resumo)
        norm = comparacao.validar(comparacao.carregar(), comparacao.canais_validos(), visivel)
        contas_ = comparacao.contar(norm, seo.visiveis(resumo, entrevistas), visivel)
        texto = (RAIZ / "docs" / "comparacao.html").read_text(encoding="utf-8")
        self.assertEqual(contas_["sujeito"]["total"], resumo["totais"]["entrevistas"])
        self.assertIn(f'<article class="pessoa porquinho">\n<h3>{resumo["sujeito"]["nome"]}', texto)
        self.assertIn(f'<p class="quantas">{resumo["totais"]["entrevistas"]}</p>', texto)
        self.assertIn(f"<p class=\"periodo\">1 de janeiro de 2024 a {comparacao.por_extenso(contas_['ate'])}</p>",
                      texto)


class TestValidacao(unittest.TestCase):
    def test_a_validacao_apanha_os_erros_que_ficariam_calados(self):
        """Cada caso e um erro que a pagina mostraria sem aviso nenhum: um
        canal fora dos nove ficava sem nome e sem cor, uma confirmada sem
        prova afirmava uma entrevista que ninguem pode abrir, uma linha
        repetida contava duas vezes, e uma confirmada depois do fecho
        ficava no ficheiro sem contar. Um texto com um espaco que o gerador
        nao preenche mostrava as chavetas no ecra. Uma prova do site de um
        partido sem o rotulo que o diz escondia de quem le que a linha
        assenta numa parte interessada; e uma `janela.ate` esquecida no
        ficheiro parecia mandar no fecho sem mandar."""
        casos = {
            "canal desconhecido": [linha(canal="x9")],
            "confirmada sem canal": [linha(canal=None)],
            "prova que nao e endereco": [linha(prova="ver no site")],
            "mesma pessoa, dia e canal": [linha(prova="https://exemplo.pt/1"), linha(prova="https://exemplo.pt/2")],
            "mesma prova em duas linhas": [linha(data="2025-07-01", prova="https://exemplo.pt/1"),
                                           linha(data="2025-07-02", prova="https://exemplo.pt/1")],
            "prova de partido sem o tipo": [linha(prova="https://www.partido.pt/noticia")],
            "tipo partido fora dos dominios": [linha(tipo_prova="partido")],
            "formato invalido": [linha(formato="debate")],
            "confirmada antes de a pessoa contar": [linha(pessoa="b", data="2025-06-27")],
            "confirmada antes do site": [linha(data="2023-12-31")],
            "pessoa desconhecida": [linha(pessoa="z")],
            "estado invalido": [linha(estado="talvez")],
            "tambem_em igual ao canal": [linha(canal="c1", tambem_em=["c1"])],
            "tipo de prova sem rotulo": [linha(tipo_prova="podcast")],
        }
        for nome, entrevistas in casos.items():
            with self.subTest(caso=nome):
                with self.assertRaises(ValueError):
                    comparacao.validar(cfg_minima(entrevistas), CANAIS, VISIVEL)
        sem_texto = cfg_minima()
        del sem_texto["textos"]["titulo"]
        espaco_a_mais = cfg_minima()
        espaco_a_mais["textos"]["intro"] = "Texto com {canal}."
        com_ate = cfg_minima()
        com_ate["janela"]["ate"] = "2026-10-30"
        for nome, cfg in (("texto em falta", sem_texto), ("espaco por preencher", espaco_a_mais),
                          ("janela.ate escrita", com_ate)):
            with self.subTest(caso=nome):
                with self.assertRaises(ValueError):
                    comparacao.validar(cfg, CANAIS, VISIVEL)
        comparacao.validar(cfg_minima([linha()]), CANAIS, VISIVEL)  # o caso bom continua a passar
        sem_formato = linha(tipo_prova="partido", prova="https://partido.pt/a")
        del sem_formato["formato"]
        comparacao.validar(cfg_minima([sem_formato]), CANAIS, VISIVEL)  # como o formulario a escreve

    def test_os_dominios_de_partido_batem_com_as_linhas_reais(self):
        """Medido a 2026-11-07, antes de o formulario passar a decidir o
        tipo de prova pelo dominio: as 7 linhas `partido` estao em ps.pt (6)
        ou ad2024.pt (1) e nenhuma outra linha esta nesses dominios. A
        validacao do ficheiro real e a garantia de que continua assim. So
        pode crescer: o formulario corre esta suite depois de escrever, e
        uma igualdade aqui travava a primeira entrevista nova em ps.pt."""
        cfg = comparacao.carregar()
        partido = [e for e in cfg["entrevistas"] if e["tipo_prova"] == "partido"]
        self.assertGreaterEqual(len(partido), 7)
        self.assertLessEqual({"ps.pt", "ad2024.pt"}, {comparacao.anfitriao(e["prova"]) for e in partido})


class TestPublicado(unittest.TestCase):
    def test_a_pagina_traz_todas_as_provas_contadas_e_nenhuma_por_verificar(self):
        """E a unica pagina do site onde estas provas aparecem. Uma linha
        contada sem a ligacao a vista era um numero que ninguem podia
        conferir, e uma por verificar com ligacao parecia contada."""
        resumo, entrevistas = seo.dados()
        visivel = comparacao.visivel_de(resumo)
        norm = comparacao.validar(comparacao.carregar(), comparacao.canais_validos(), visivel)
        contas_ = comparacao.contar(norm, seo.visiveis(resumo, entrevistas), visivel)
        texto = (RAIZ / "docs" / "comparacao.html").read_text(encoding="utf-8")
        bloco = texto.split(seo.INICIO_CORPO)[1].split(seo.FIM_CORPO)[0]
        mostradas = [e for p in contas_["pessoas"] for e in p["linhas"]]
        self.assertEqual(bloco.count("<tr><td>"), len(mostradas))
        esperadas = {e["prova"] for e in mostradas}
        for e in norm["entrevistas"]:
            with self.subTest(prova=e["prova"]):
                self.assertEqual(html.escape(e["prova"], quote=True) in bloco, e["prova"] in esperadas)


if __name__ == "__main__":
    unittest.main()
