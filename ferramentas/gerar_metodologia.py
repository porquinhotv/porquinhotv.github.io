"""Gera docs/metodologia.html a partir de METODOLOGIA.md.

    python -m ferramentas.gerar_metodologia            escreve
    python -m ferramentas.gerar_metodologia --check    so verifica

Converte apenas o subconjunto de Markdown usado nesse documento: titulos,
paragrafos, listas, tabelas, blocos de codigo, negrito, codigo inline e
ligacoes `mailto:`.
Nao e um conversor geral e nao deve passar a ser.

O que este gerador NAO garante: que o Markdown diz a verdade sobre o
site. Isso e trabalho de quem muda o comportamento do site.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from ferramentas import seo

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "METODOLOGIA.md"
ALVO = RAIZ / "docs" / "metodologia.html"

# Esta pagina e escrita por inteiro de cada vez, por isso o bloco de
# metadados de pesquisa tem de vir daqui: injectado depois, desaparecia
# na geracao seguinte sem erro nenhum, que e exactamente o que ja
# aconteceu com o contador de visitas.
CABECA = """<!doctype html>
<html lang="pt-PT">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{seo}
<meta name="robots" content="index, follow">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="estilo.css">
<script defer src="https://cloud.umami.is/script.js" data-website-id="f45a246b-61d5-4d3f-a74b-c66ec8e9364e"></script>
</head>
<body class="pagina-texto">
<header class="topo">
  <a class="marca" href="index.html" aria-label="Porquinho TV, início">
    <img src="favicon.svg" alt="" width="44" height="44">
    <h1>Porquinho TV</h1>
  </a>
  <nav class="menu" aria-label="Páginas">
    <a href="index.html">Hoje</a>
    <a href="calendario.html">Calendário</a>
    <a href="fontes.html">Fontes</a>
  </nav>
</header>
<main class="texto">
<h2>Metodologia</h2>
"""

# O botao de partilha esta em todas as paginas, decisao do autor a
# 2026-10-27, e esta pagina nao e escrita a mao: os scripts tem de vir
# daqui pela mesma razao que o bloco de metadados.
CAUDA = """</main>
<script src="enquadramento.js"></script>
<script src="partilha.js"></script>
</body>
</html>
"""


def em_linha(texto: str) -> str:
    partes = re.split(r"(`[^`]+`)", texto)
    saida = []
    for parte in partes:
        if parte.startswith("`") and parte.endswith("`") and len(parte) > 1:
            saida.append(f"<code>{html.escape(parte[1:-1])}</code>")
            continue
        escapado = html.escape(parte)
        escapado = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escapado)
        # Unica ligacao suportada: [texto](mailto:...), para o contacto da
        # seccao de correcoes. Nao se abre a sintaxe a http: o site nao
        # pede nada a terceiros, e isto continua a nao ser um conversor geral.
        escapado = re.sub(r"\[([^\]]+)\]\(mailto:([^)\s]+)\)", r'<a href="mailto:\2">\1</a>', escapado)
        saida.append(escapado)
    return "".join(saida)


def converter(markdown: str) -> str:
    linhas = markdown.splitlines()
    saida: list[str] = []
    i = 0
    lista_aberta = ""

    def fechar_lista() -> None:
        nonlocal lista_aberta
        if lista_aberta:
            saida.append(f"</{lista_aberta}>")
            lista_aberta = ""

    while i < len(linhas):
        linha = linhas[i].strip()
        if not linha:
            fechar_lista()
            i += 1
            continue
        if linha.startswith("```"):
            fechar_lista()
            i += 1
            bloco = []
            while i < len(linhas) and not linhas[i].strip().startswith("```"):
                bloco.append(html.escape(linhas[i]))
                i += 1
            i += 1
            saida.append("<pre>\n" + "\n".join(bloco) + "\n</pre>")
            continue
        if linha.startswith("|"):
            fechar_lista()
            filas = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                filas.append([c.strip() for c in linhas[i].strip().strip("|").split("|")])
                i += 1
            cabeca, corpo = filas[0], filas[2:]
            saida.append("<table><thead><tr>" + "".join(f"<th>{em_linha(c)}</th>" for c in cabeca) + "</tr></thead><tbody>")
            for fila in corpo:
                saida.append("<tr>" + "".join(f"<td>{em_linha(c)}</td>" for c in fila) + "</tr>")
            saida.append("</tbody></table>")
            continue
        titulo = re.match(r"^(#{1,3})\s+(.*)$", linha)
        if titulo:
            fechar_lista()
            nivel = len(titulo.group(1))
            if nivel > 1:
                saida.append(f"<h{nivel}>{em_linha(titulo.group(2))}</h{nivel}>")
            i += 1
            continue
        item = re.match(r"^(\d+\.|-)\s+(.*)$", linha)
        if item:
            etiqueta = "ul" if item.group(1) == "-" else "ol"
            if lista_aberta != etiqueta:
                fechar_lista()
                saida.append(f"<{etiqueta}>")
                lista_aberta = etiqueta
            saida.append(f"<li>{em_linha(item.group(2))}</li>")
            i += 1
            continue
        fechar_lista()
        saida.append(f"<p>{em_linha(linha)}</p>")
        i += 1
    fechar_lista()
    return cabeca_html() + "\n".join(saida) + "\n" + CAUDA


def cabeca_html() -> str:
    cfg = seo.carregar()
    resumo, entrevistas = seo.dados()
    bloco = seo.bloco_head(cfg, "metodologia.html", resumo, seo.visiveis(resumo, entrevistas))
    return CABECA.replace("{seo}", bloco)


def construir() -> str:
    return converter(ORIGEM.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    gerado = construir()
    if "--check" in argv:
        atual = ALVO.read_text(encoding="utf-8") if ALVO.exists() else ""
        if atual != gerado:
            print("docs/metodologia.html desatualizado. Correr: python -m ferramentas.gerar_metodologia", file=sys.stderr)
            return 1
        print("docs/metodologia.html em dia")
        return 0
    # newline="\n" nao e opcional: sem ele, o Python traduz \n para \r\n
    # em Windows e o ficheiro publicado fica em CRLF. Ha um teste que o
    # apanha, e o site nao deve depender do sistema de quem o gerou.
    ALVO.write_text(gerado, encoding="utf-8", newline="\n")
    print(f"escrito {ALVO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
