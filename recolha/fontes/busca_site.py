"""Pesquisa do proprio site. A fonte automatica principal.

O levantamento mostrou que a pesquisa dos canais responde do lado do
servidor, com o nome do sujeito no titulo e nos metadados, sem precisar
de JavaScript. E melhor fonte do que qualquer motor de busca externo:

- e a fonte primaria, que e o que a Metodologia manda procurar primeiro;
- nao ha ninguem a bloquear o acesso, ao contrario dos motores de busca,
  que respondem a maquinas de datacenter com muro de consentimento ou
  captcha e tornariam a recolha uma coisa que funciona uma vez;
- da o URL do proprio canal como prova, que e o que cada linha do site
  precisa de ter.

Duas fases, ambas genericas:

1. pedir a pagina de pesquisa do site, uma vez por termo de deteccao do
   sujeito e por pagina de resultados, e colher os URL candidatos do
   mesmo dominio (ver extracao.ligacoes);
2. pedir cada candidato e ler os dados estruturados que a pagina publica
   (ver extracao.extrair): titulo, data, sinopse e etiquetas.

Nao ha um unico seletor CSS de nenhum site em lado nenhum. O que se le e
schema.org e OpenGraph, que os sites mantem por causa dos motores de
busca e das redes sociais, e que por isso sobrevive as remodelacoes.

Esta fonte nao decide nada: o criterio e que diz se o candidato conta.
"""

from __future__ import annotations

import time
import urllib.parse
from typing import Iterable

from .. import extracao
from ..modelos import ItemBruto
from ..rede import ErroDeRede, obter_texto
from .base import PluginDeFonte, registar



@registar
class FonteBuscaSite(PluginDeFonte):
    tipo = "busca_site"

    def _paginas_de_busca(self, termos: list[str]) -> list[str]:
        urls: list[str] = []
        for modelo in self.fonte.busca:
            for termo in termos:
                for pagina in range(1, max(1, self.fonte.paginas_max) + 1):
                    url = (
                        modelo.replace("{termo}", urllib.parse.quote(termo))
                        .replace("{pagina}", str(pagina))
                        # Alguns motores contam as paginas a partir de zero.
                        .replace("{pagina0}", str(pagina - 1))
                    )
                    if url not in urls:
                        urls.append(url)
                    if "{pagina}" not in modelo and "{pagina0}" not in modelo:
                        break
        return urls

    def obter(self, termos: list[str] | None = None, registo: list | None = None) -> Iterable[ItemBruto]:
        # `termos_busca` na fonte substitui os termos de deteccao do
        # sujeito. Serve para as fontes que passam por um motor de busca
        # externo, onde tres consultas por canal seriam tres vezes mais
        # pedidos a um servico que nos pode limitar, sem tres vezes mais
        # resultados: a consulta ja leva o nome completo.
        termos = list(self.fonte.termos_busca) or termos or []
        if not self.fonte.busca or not self.fonte.dominio:
            return []

        candidatos: list[str] = []
        for url in self._paginas_de_busca(termos):
            try:
                html = obter_texto(url)
            except ErroDeRede as exc:
                if registo is not None:
                    registo.append(f"{self.fonte.id}: pesquisa falhou {url}: {exc}")
                continue
            achados = extracao.ligacoes(html, url, self.fonte.dominio, self.fonte.padrao_artigo)
            print(f"  {self.fonte.id}: {len(achados)} candidatos em {url}", flush=True)
            for alvo in achados:
                if alvo not in candidatos:
                    candidatos.append(alvo)
            if registo is not None:
                registo.append(f"{self.fonte.id}: {len(achados)} candidatos em {url}")
            time.sleep(self.fonte.pausa_s)

        # Um limite existe para uma pesquisa que devolva a pagina inteira
        # do site em vez de resultados. Sem ele, um padrao mal apertado
        # transformava uma corrida em milhares de pedidos.
        if self.fonte.max_candidatos and len(candidatos) > self.fonte.max_candidatos:
            if registo is not None:
                registo.append(f"{self.fonte.id}: {len(candidatos)} candidatos, limitado a {self.fonte.max_candidatos}")
            candidatos = candidatos[: self.fonte.max_candidatos]

        # Um passo longo escreve progresso. Sem isto, uma corrida de
        # historico faz centenas de pedidos sem uma linha no ecra, e quem
        # espera nao distingue \"a trabalhar\" de \"encravado\".
        itens: list[ItemBruto] = []
        for indice, alvo in enumerate(candidatos, start=1):
            if indice == 1 or indice % 20 == 0 or indice == len(candidatos):
                print(f"  {self.fonte.id}: {indice}/{len(candidatos)} paginas", flush=True)
            try:
                pagina = obter_texto(alvo)
            except ErroDeRede as exc:
                if registo is not None:
                    registo.append(f"{self.fonte.id}: candidato falhou {alvo}: {exc}")
                continue
            dados = extracao.extrair(pagina, alvo)
            itens.append(
                ItemBruto(
                    id_nativo=alvo,
                    publicado_em=dados["publicado_em"],
                    titulo=dados["titulo"],
                    url=alvo,
                    descricao=dados["descricao"] or dados["excerto"],
                    canal=self.fonte.canal,
                    programa=self.fonte.programa,
                    prova_url=alvo,
                    etiquetas=dados["etiquetas"],
                )
            )
            time.sleep(self.fonte.pausa_s)

        if registo is not None:
            com_data = sum(1 for i in itens if i.publicado_em)
            registo.append(f"{self.fonte.id}: {len(itens)} paginas lidas, {com_data} com data declarada")
        return itens
