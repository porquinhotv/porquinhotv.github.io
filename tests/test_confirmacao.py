"""Confirmacao em rondas.

Um bloco visto uma vez fica a espera e e visivel na quarentena; visto em
duas rondas distintas, entra. Uma segunda leitura no mesmo dia nao conta
como segunda ronda: seria contar duas vezes a mesma leitura.
"""

import unittest

from tests.apoio import RAIZ  # noqa: F401  (garante o sys.path)

from recolha import confirmacao
from recolha.modelos import Transmissao


def transmissao(bloco="b1", fonte="busca-rtp1", **campos):
    base = dict(
        id=f"{fonte}:{bloco}", bloco=bloco, entrevista=bloco, data="2021-03-15",
        data_origem="declarada", publicado_em="2021-03-15", canal="rtp1",
        programa="Programa", origem="canal",
        fonte=fonte, confianca="media", prova_url="https://exemplo.pt/a",
        titulo="Entrevista",
    )
    base.update(campos)
    return Transmissao(**base)


class TestRondas(unittest.TestCase):
    def test_uma_ronda_nao_chega(self):
        c = confirmacao.registar({}, [transmissao()], "2026-09-08")
        quarentena = []
        passam = confirmacao.filtrar([transmissao()], c, 2, quarentena)
        self.assertEqual(passam, [])
        self.assertEqual(len(quarentena), 1)
        self.assertIn("aguarda_confirmacao (1 de 2 rondas)", quarentena[0]["motivo"])

    def test_duas_rondas_distintas_confirmam(self):
        c = confirmacao.registar({}, [transmissao()], "2026-09-08")
        c = confirmacao.registar(c, [transmissao()], "2026-09-09")
        passam = confirmacao.filtrar([transmissao()], c, 2, [])
        self.assertEqual(len(passam), 1)

    def test_duas_leituras_no_mesmo_dia_sao_uma_ronda(self):
        """Correr duas vezes no mesmo dia nao confirma nada: seria contar
        duas vezes a mesma leitura, que e o erro de que as rondas protegem."""
        c = confirmacao.registar({}, [transmissao()], "2026-09-08")
        c = confirmacao.registar(c, [transmissao()], "2026-09-08")
        self.assertEqual(confirmacao.filtrar([transmissao()], c, 2, []), [])

    def test_fontes_distintas_ficam_registadas(self):
        c = confirmacao.registar({}, [transmissao(fonte="busca-rtp1")], "2026-09-08")
        c = confirmacao.registar(c, [transmissao(fonte="busca-sic")], "2026-09-09")
        self.assertEqual(len(c["b1"]["fontes"]), 2)
        anotadas = confirmacao.anotar([transmissao()], c)
        self.assertEqual(anotadas[0].rondas, 2)
        self.assertEqual(anotadas[0].fontes_distintas, 2)

    def test_avistamentos_nunca_se_perdem(self):
        """Append-only: a trilha permite reconstruir porque uma linha entrou."""
        c = confirmacao.registar({}, [transmissao()], "2026-09-08")
        c = confirmacao.registar(c, [transmissao()], "2026-09-09")
        self.assertEqual(c["b1"]["rondas"], ["2026-09-08", "2026-09-09"])
        self.assertEqual(c["b1"]["primeira_ronda"], "2026-09-08")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestIntegracaoComAsFontes(unittest.TestCase):
    """O que distingue fonte verificada a mao de fonte automatica e o
    tipo declarado na configuracao, nunca o nome. Um prefixo de nome
    partiria em silencio ao renomear uma fonte, e o silencio aqui
    significava publicar sem confirmacao."""

    def test_as_fontes_manuais_da_configuracao_real_sao_as_esperadas(self):
        from recolha.modelos import carregar_config

        config = carregar_config()
        a_mao = {f.id for f in config.fontes if f.tipo == "manual"}
        # A lista e escrita a mao de proposito: uma fonte que passe a
        # `manual` ganha a isencao de prova de formato e de rondas, e essa
        # isencao so se justifica se uma pessoa tiver aberto a pagina.
        # Acrescentar um id aqui e afirmar isso.
        self.assertEqual(a_mao, {"curadoria", "registo-curado", "clipping-imprensa"})
        automaticas = [f for f in config.fontes if f.tipo != "manual"]
        self.assertTrue(automaticas, "sem fontes automaticas o site nunca se povoa sozinho")


class TestSegundaRondaNoMesmoDia(unittest.TestCase):
    """A recolha corre uma segunda ronda no mesmo dia, com
    identificador proprio, para publicar no dia em vez de no seguinte."""

    def test_identificadores_distintos_confirmam_no_mesmo_dia(self):
        c = confirmacao.registar({}, [transmissao()], "2026-09-08-r1")
        self.assertEqual(confirmacao.filtrar([transmissao()], c, 2, []), [])
        c = confirmacao.registar(c, [transmissao()], "2026-09-08-r2")
        self.assertEqual(len(confirmacao.filtrar([transmissao()], c, 2, [])), 1)

    def test_o_mesmo_identificador_repetido_continua_a_nao_confirmar(self):
        """A protecao vem de duas leituras, nao de duas escritas."""
        c = confirmacao.registar({}, [transmissao()], "2026-09-08-r1")
        c = confirmacao.registar(c, [transmissao()], "2026-09-08-r1")
        self.assertEqual(confirmacao.filtrar([transmissao()], c, 2, []), [])
