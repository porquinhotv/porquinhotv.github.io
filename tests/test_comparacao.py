"""A pagina de comparacao so pode afirmar o que os dados medem.

Cada teste trava um erro concreto:

- uma linha por verificar entrar na contagem;
- o numero do sujeito crescer depois de o levantamento dos outros ter
  fechado, e o contraste crescer sozinho;
- a pagina mostrar periodos diferentes lado a lado, ou um numero do
  sujeito que nao bate com a pagina inicial;
- uma entrevista em dois canais contar duas vezes, ou duas entrevistas
  no mesmo dia em canais diferentes contarem uma;
- um erro no YAML (canal mal escrito, prova em falta, linha repetida,
  confirmada fora da janela) ficar calado na pagina;
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
        "janela": {"desde": "2025-06-28", "ate": "2026-10-30"},
        "sujeito": {"cargo": "cargo do sujeito"},
        "pessoas": [
            {"id": "a", "nome": "Pessoa A", "cargo": "cargo A", "desde": "2024-01-01"},
            {"id": "b", "nome": "Pessoa B", "cargo": "cargo B", "desde": "2025-06-28"},
        ],
        "rotulos_de_prova": {"canal": "ver", "imprensa": "notícia"},
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

    def test_o_sujeito_conta_ate_ao_mesmo_dia_que_os_outros(self):
        """A 2026-11-06 o sujeito ja tinha uma entrevista (NOW, 2026-11-03)
        depois do dia em que o levantamento dos outros fechou. Contada,
        cada entrevista nova do sujeito aumentava a distancia sem que os
        outros pudessem acompanhar: o contraste crescia sozinho. A janela
        acaba no mesmo dia para todos."""
        lista = [{"data": "2025-06-27"}, {"data": "2025-06-28"}, {"data": "2026-10-30"}, {"data": "2026-11-03"},
                 {"data": "2024-01-01"}]
        s = contas(cfg_minima(), lista)["sujeito"]
        self.assertEqual(s["janela"], 2)

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

    def test_nada_fora_da_janela_entra_na_comparacao(self):
        """A primeira versao punha lado a lado tres anos de uma pessoa e ano
        e meio de outra, e um bloco "desde 2024" com o sujeito cortado a 30
        out (81) ao lado da pagina inicial (82). O autor apontou as duas
        coisas a 2026-11-06: ha uma janela so, e uma linha anterior a ela
        so aparece para dizer quando foi a ultima de quem nao tem nenhuma."""
        cfg = cfg_minima([linha(data="2024-05-01", prova="https://exemplo.pt/antiga"),
                          linha(data="2025-06-20", prova="https://exemplo.pt/ultima-antes")])
        a = pessoa(contas(cfg), "a")
        self.assertEqual(a["janela"], 0)
        self.assertEqual(a["ultima_antes"]["prova"], "https://exemplo.pt/ultima-antes")
        gerado = comparacao.corpo(RESUMO, [{"data": "2024-03-01"}], cfg, CANAIS)
        self.assertIn("https://exemplo.pt/ultima-antes", gerado)
        self.assertNotIn("https://exemplo.pt/antiga", gerado)
        self.assertNotIn("<tr><td>2025-06-20", gerado)
        self.assertIn('<p class="quantas">0</p>', gerado)  # o sujeito de 2024 fica fora


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

    def test_a_pagina_reconcilia_o_numero_do_sujeito_com_a_inicial(self):
        """A pagina inicial conta desde 2024 e esta conta a janela. Dois
        numeros diferentes para a mesma pessoa sem explicacao parecem um
        erro, que foi o que o autor viu a 2026-11-06. A pagina diz por
        palavras o total da inicial, tirado do mesmo resumo."""
        resumo, _ = seo.dados()
        texto = (RAIZ / "docs" / "comparacao.html").read_text(encoding="utf-8")
        self.assertIn(f"o porquinho tem {resumo['totais']['entrevistas']},", texto)


class TestValidacao(unittest.TestCase):
    def test_a_validacao_apanha_os_erros_que_ficariam_calados(self):
        """Cada caso e um erro que a pagina mostraria sem aviso nenhum: um
        canal fora dos nove ficava sem nome e sem cor, uma confirmada sem
        prova afirmava uma entrevista que ninguem pode abrir, uma linha
        repetida contava duas vezes, e uma confirmada depois do fecho
        ficava no ficheiro sem contar. Um texto com um espaco que o gerador
        nao preenche mostrava as chavetas no ecra."""
        casos = {
            "canal desconhecido": [linha(canal="x9")],
            "confirmada sem canal": [linha(canal=None)],
            "prova que nao e endereco": [linha(prova="ver no site")],
            "mesma pessoa, dia e canal": [linha(prova="https://exemplo.pt/1"), linha(prova="https://exemplo.pt/2")],
            "mesma prova em duas linhas": [linha(data="2025-07-01", prova="https://exemplo.pt/1"),
                                           linha(data="2025-07-02", prova="https://exemplo.pt/1")],
            "confirmada depois do fecho": [linha(data="2026-10-31")],
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
        for nome, cfg in (("texto em falta", sem_texto), ("espaco por preencher", espaco_a_mais)):
            with self.subTest(caso=nome):
                with self.assertRaises(ValueError):
                    comparacao.validar(cfg, CANAIS, VISIVEL)
        comparacao.validar(cfg_minima([linha()]), CANAIS, VISIVEL)  # o caso bom continua a passar


class TestPublicado(unittest.TestCase):
    def test_a_pagina_traz_as_provas_da_janela_e_nenhuma_por_verificar(self):
        """E a unica pagina do site onde estas provas aparecem. Uma linha
        contada sem a ligacao a vista era um numero que ninguem podia
        conferir, e uma por verificar com ligacao parecia contada. Fora da
        janela so aparece a ultima de quem nao tem nenhuma dentro."""
        resumo, entrevistas = seo.dados()
        visivel = comparacao.visivel_de(resumo)
        norm = comparacao.validar(comparacao.carregar(), comparacao.canais_validos(), visivel)
        contas_ = comparacao.contar(norm, seo.visiveis(resumo, entrevistas), visivel)
        texto = (RAIZ / "docs" / "comparacao.html").read_text(encoding="utf-8")
        bloco = texto.split(seo.INICIO_CORPO)[1].split(seo.FIM_CORPO)[0]
        mostradas = [e for p in contas_["pessoas"] for e in p["linhas"]]
        self.assertEqual(bloco.count("<tr><td>"), len(mostradas))
        esperadas = {e["prova"] for e in mostradas}
        esperadas |= {p["ultima_antes"]["prova"] for p in contas_["pessoas"] if not p["linhas"] and p["ultima_antes"]}
        for e in norm["entrevistas"]:
            with self.subTest(prova=e["prova"]):
                self.assertEqual(html.escape(e["prova"], quote=True) in bloco, e["prova"] in esperadas)


if __name__ == "__main__":
    unittest.main()
