"""Escreve nas paginas o que os motores e os agentes leem.

    python -m ferramentas.gerar_seo            escreve
    python -m ferramentas.gerar_seo --check    so verifica

Actualiza, a partir de `config/seo.yml` e dos dados publicados:

- o bloco de metadados no `<head>` das cinco paginas;
- o conteudo pre-renderizado do corpo, nas tres paginas que o
  JavaScript constroi a partir dos dados, e a pagina de comparacao
  inteira, que so existe assim (ver `ferramentas/comparacao.py`);
- `docs/sitemap.xml` e `docs/robots.txt`.

A Metodologia recebe o bloco do `<head>` pela mao do proprio gerador
dela, `ferramentas/gerar_metodologia.py`, porque o ficheiro e escrito por
inteiro de cada vez: um bloco injectado depois desaparecia na geracao
seguinte sem erro. Depois de mexer no `config/seo.yml`, correr os dois.

Este passo corre no workflow `recolha`, logo a seguir a recolha e antes
do commit: os numeros dentro do HTML sao os da corrida que acabou de
escrever `docs/dados`, e nunca os da anterior. Ha um teste que falha se
o publicado e o gerado nao coincidirem.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ferramentas import gerar_metodologia, seo

RAIZ = seo.RAIZ
DOCS = RAIZ / "docs"


def construir() -> dict[Path, str]:
    """Devolve o conteudo final de cada ficheiro, sem escrever nada. O
    `--check` e o teste comparam contra isto."""
    cfg = seo.carregar()
    resumo, entrevistas = seo.dados()
    lista = seo.visiveis(resumo, entrevistas)
    saida: dict[Path, str] = {}
    for pagina in ("index.html", "calendario.html", "fontes.html", "comparacao.html"):
        caminho = DOCS / pagina
        saida[caminho] = seo.aplicar(pagina, caminho.read_text(encoding="utf-8"), cfg, resumo, lista)
    saida[DOCS / "sitemap.xml"] = seo.sitemap(cfg, resumo)
    saida[DOCS / "robots.txt"] = seo.robots(cfg)
    saida[gerar_metodologia.ALVO] = gerar_metodologia.construir()
    return saida


def desactualizados() -> list[Path]:
    fora = []
    for caminho, conteudo in construir().items():
        actual = caminho.read_text(encoding="utf-8") if caminho.exists() else ""
        if actual != conteudo:
            fora.append(caminho)
    return fora


def main(argv: list[str]) -> int:
    if "--check" in argv:
        fora = desactualizados()
        if fora:
            nomes = ", ".join(str(c.relative_to(RAIZ)) for c in fora)
            print(f"desactualizado: {nomes}. Correr: python -m ferramentas.gerar_seo", file=sys.stderr)
            return 1
        print("metadados de pesquisa em dia")
        return 0
    for caminho, conteudo in construir().items():
        # newline="\n" nao e opcional: sem ele o Python traduz para CRLF
        # em Windows e o ficheiro publicado fica fora do invariante.
        caminho.write_text(conteudo, encoding="utf-8", newline="\n")
        print(f"escrito {caminho.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
