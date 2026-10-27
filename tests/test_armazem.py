"""Append-only: primeira_vez nunca regride, ficheiros deterministas."""

import json
import tempfile
import unittest
from pathlib import Path

from tests.apoio import config_teste, fonte, item

from recolha import armazem, criterio, entrevistas


class TestFundir(unittest.TestCase):
    def setUp(self):
        self.config = config_teste()
        self.fonte = fonte(self.config, "podcast-exemplo")

    def test_preserva_primeira_vez(self):
        e = criterio.avaliar(item(), self.fonte, self.config, [])
        existentes = {e.id: {**e.como_dict(), "primeira_vez": "2020-01-01"}}
        fundidas, adicionadas, atualizadas = armazem.fundir(existentes, [e])
        self.assertEqual(fundidas[e.id]["primeira_vez"], "2020-01-01")
        self.assertEqual((adicionadas, atualizadas), (0, 0))

    def test_linha_nova_conta_como_adicionada(self):
        e = criterio.avaliar(item(), self.fonte, self.config, [])
        _, adicionadas, _ = armazem.fundir({}, [e])
        self.assertEqual(adicionadas, 1)

    def test_escrita_e_leitura_sao_estaveis(self):
        """Escrever, ler e voltar a escrever da o mesmo ficheiro.

        Desde 2026-09-11 o ficheiro publicado e uma lista de entrevistas
        com as transmissoes dentro, e o armazem guarda transmissoes: se a
        volta nao fosse exacta, uma corrida perdia linhas ou
        reescrevia `primeira_vez` sem ninguem dar por isso."""
        e = criterio.avaliar(item(), self.fonte, self.config, [])
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "entrevistas.json"
            armazem.guardar(entrevistas.agrupar([e.como_dict()], {}), caminho)
            primeira = caminho.read_text(encoding="utf-8")
            lidas = armazem.carregar(caminho)
            self.assertEqual(list(lidas), [e.id])
            armazem.guardar(entrevistas.agrupar(list(lidas.values()), {}), caminho)
            self.assertEqual(primeira, caminho.read_text(encoding="utf-8"))
            conteudo = json.loads(primeira)
            self.assertEqual(conteudo["total"], 1)
            self.assertEqual(conteudo["esquema"], 2)
            self.assertIn("prova_url", conteudo["entrevistas"][0])
            self.assertIn("prova_url", conteudo["entrevistas"][0]["transmissoes"][0])

    def test_o_total_do_ficheiro_e_de_entrevistas_e_nao_de_transmissoes(self):
        """O `total` do ficheiro publicado e o numero que o site escreve
        em grande. Uma entrevista que passou em dois canais tem duas
        transmissoes la dentro e conta uma vez: se o total contasse
        transmissoes, o ficheiro que qualquer pessoa descarrega
        desmentia o site."""
        a = criterio.avaliar(item(id_nativo="a", prova_url="https://exemplo.pt/a"), self.fonte, self.config, [])
        b = criterio.avaliar(item(id_nativo="b", prova_url="https://exemplo.pt/b"), self.fonte, self.config, [])
        grupos = {"https://exemplo.pt/a": ("k", a.canal), "https://exemplo.pt/b": ("k", a.canal)}
        dobradas = entrevistas.agrupar([a.como_dict(), b.como_dict()], grupos)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "entrevistas.json"
            armazem.guardar(dobradas, caminho)
            conteudo = json.loads(caminho.read_text(encoding="utf-8"))
            self.assertEqual(conteudo["total"], 1)
            self.assertEqual(len(conteudo["entrevistas"][0]["transmissoes"]), 2)
            self.assertEqual(len(armazem.carregar(caminho)), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
