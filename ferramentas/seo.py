"""Metadados de pesquisa e conteudo servido sem JavaScript.

O problema que este modulo resolve, medido e nao suposto: as quatro
paginas do site entregam um esqueleto com "A carregar os dados" e so
constroem o conteudo depois de o browser correr o JavaScript e ler os
ficheiros de `docs/dados`. Um motor de pesquisa que renderiza consegue
ve-lo; os agentes de recolha dos modelos de linguagem, nao, porque nao
executam JavaScript. Sem o bloco pre-renderizado, para esses agentes
este site nao tem numero nenhum nem prova nenhuma.

A resposta e pre-renderizar: o gerador escreve dentro do HTML, entre
marcadores, o mesmo que o JavaScript escreveria. Quem tem browser recebe
a pagina completa e o script substitui o bloco logo a seguir; quem nao
executa scripts fica na mesma com o total, a reparticao por canal e a
lista das provas.

Nada aqui e escrito a mao sobre os dados: o bloco sai sempre do
`resumo.json` e do `entrevistas.json` que a recolha acabou de publicar.
Um numero no HTML que nao viesse dali seria um numero sem medicao.

Nenhum nome editorial nestas linhas: o sujeito, os canais e as palavras
de pesquisa vivem em `config/seo.yml` e nos dados publicados, como manda
o invariante do projeto.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config" / "seo.yml"
DADOS = RAIZ / "docs" / "dados"

# O bloco gerado comeca e acaba nestes comentarios. Fora deles, o HTML e
# escrito a mao e o gerador nao lhe toca: sem marcadores, cada corrida
# teria de decidir onde o bloco acaba, e uma decisao dessas engana-se em
# silencio.
INICIO_HEAD = "<!-- seo:head -->"
FIM_HEAD = "<!-- /seo:head -->"
INICIO_CORPO = "<!-- seo:corpo -->"
FIM_CORPO = "<!-- /seo:corpo -->"

# Um travessao em texto de um terceiro nao e escrita do projeto, mas o
# teste que os proibe le o ficheiro publicado e nao sabe distinguir um do
# outro. Desde 2026-10-21 os titulos das pecas ja nao entram no bloco
# (saiu a coluna de programa da pagina de fontes); a troca fica porque
# custa nada e cobre qualquer campo de dados que volte a entrar.
TRAVESSOES = {"\u2014": "-", "\u2013": "-"}


def carregar() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def dados() -> tuple[dict, list]:
    resumo = json.loads((DADOS / "resumo.json").read_text(encoding="utf-8"))
    entrevistas = json.loads((DADOS / "entrevistas.json").read_text(encoding="utf-8")).get("entrevistas", [])
    return resumo, entrevistas


def visiveis(resumo: dict, entrevistas: list) -> list:
    """O dataset guarda tudo desde o inicio da recolha, o site conta a
    partir do corte que o resumo declara. O bloco pre-renderizado tem de
    mostrar exactamente o mesmo conjunto que o site mostra, senao um
    motor le um total e o visitante le outro."""
    desde = (resumo.get("ambito") or {}).get("visivel_desde") or ""
    return sorted((e for e in entrevistas if e.get("data", "") >= desde),
                  key=lambda e: (e["data"], e.get("canal", "")), reverse=True)


def texto(valor) -> str:
    limpo = str(valor)
    for mau, bom in TRAVESSOES.items():
        limpo = limpo.replace(mau, bom)
    return html.escape(limpo, quote=True)


def endereco(cfg: dict, caminho: str) -> str:
    base = cfg["base"]
    if caminho in ("", "index.html"):
        return base
    return base + caminho


def nomes_dos_canais(resumo: dict) -> dict:
    return {c["canal"]: c["nome"] for c in resumo.get("por_canal", [])}


def _ld(objecto: dict) -> str:
    """Os dados estruturados vao num `<script>`: um `<` dentro de um
    titulo fecharia a etiqueta a meio e levaria o resto da pagina com
    ele. O JSON escapa-o, e a pagina deixa de depender do que um canal
    escreveu no titulo."""
    bruto = json.dumps(objecto, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return bruto.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def sujeito_de(resumo: dict) -> str:
    return (resumo.get("sujeito") or {}).get("nome", "")


def conjunto_de_dados(cfg: dict, resumo: dict) -> dict:
    """Descreve o site como aquilo que ele e: um conjunto de dados com um
    ficheiro para descarregar. E o tipo que um modelo ou um motor lem
    para saber do que trata a pagina, e o unico sitio onde as palavras de
    pesquisa entram num campo que alguem le mesmo."""
    ambito = resumo.get("ambito") or {}
    total = (resumo.get("totais") or {}).get("entrevistas", 0)
    sujeito = sujeito_de(resumo)
    objecto = {
        "@type": "Dataset",
        "name": f"Entrevistas exclusivas de {sujeito} na televisão portuguesa",
        "description": (f"Contagem verificável das entrevistas exclusivas de {sujeito} nos canais de televisão "
                        f"portugueses, {ambito.get('rotulo', '')}. {total} entrevistas, cada uma com a ligação "
                        f"para a página do canal ou para a notícia que a prova."),
        "url": endereco(cfg, "index.html"),
        "inLanguage": cfg["idioma"],
        "isAccessibleForFree": True,
        "keywords": list(cfg["palavras_chave"]),
        "creativeWorkStatus": "Published",
        "dateModified": str(resumo.get("gerado_em", ""))[:10],
        "temporalCoverage": f"{ambito.get('visivel_desde', '')}/{resumo.get('ultimo_registo', '')}",
        "variableMeasured": "entrevistas exclusivas",
        "about": {
            "@type": "Person",
            "name": sujeito,
            "sameAs": list(cfg.get("sujeito_mesmo_que") or []),
        },
        "distribution": {
            "@type": "DataDownload",
            "encodingFormat": "application/json",
            "contentUrl": cfg["base"] + "dados/entrevistas.json",
        },
    }
    return objecto


def _sitio(cfg: dict, resumo: dict) -> dict:
    return {
        "@type": "WebSite",
        "name": cfg["nome"],
        "url": cfg["base"],
        "inLanguage": cfg["idioma"],
        "description": cfg["paginas"]["index.html"]["descricao"].strip(),
    }


def _lista_das_provas(cfg: dict, resumo: dict, lista: list) -> dict:
    """Uma entrada por entrevista, com o endereco da prova. E a forma
    normalizada de dizer o que a pagina de Fontes diz em tabela: quem le
    isto fica com a lista e com a ligacao para a verificar."""
    nomes = nomes_dos_canais(resumo)
    itens = []
    for i, e in enumerate(lista, 1):
        itens.append({
            "@type": "ListItem",
            "position": i,
            "name": f"{nomes.get(e.get('canal'), e.get('canal'))}, {e.get('data')}",
            "url": e.get("prova_url", ""),
        })
    return {
        "@type": "ItemList",
        "name": f"Entrevistas exclusivas de {sujeito_de(resumo)} com prova pública",
        "numberOfItems": len(itens),
        "itemListOrder": "https://schema.org/ItemListOrderDescending",
        "itemListElement": itens,
    }


def _pagina_web(cfg: dict, pagina: str) -> dict:
    p = cfg["paginas"][pagina]
    return {
        "@type": "WebPage",
        "name": p["titulo"],
        "description": p["descricao"].strip(),
        "url": endereco(cfg, pagina),
        "inLanguage": cfg["idioma"],
        "isPartOf": {"@type": "WebSite", "name": cfg["nome"], "url": cfg["base"]},
    }


def dados_estruturados(cfg: dict, pagina: str, resumo: dict, lista: list) -> dict:
    if pagina == "index.html":
        grafo = [_sitio(cfg, resumo), conjunto_de_dados(cfg, resumo)]
    elif pagina == "fontes.html":
        grafo = [_pagina_web(cfg, pagina), _lista_das_provas(cfg, resumo, lista)]
    else:
        grafo = [_pagina_web(cfg, pagina)]
    return {"@context": "https://schema.org", "@graph": grafo}


def bloco_head(cfg: dict, pagina: str, resumo: dict, lista: list) -> str:
    """Titulo, descricao, canonical, cartao de partilha e dados
    estruturados. O titulo vive aqui e nao no HTML de cada pagina para
    que nao possa desencontrar-se do que o resto do bloco afirma."""
    p = cfg["paginas"][pagina]
    url = endereco(cfg, pagina)
    descricao = " ".join(p["descricao"].split())
    cartao = cfg["base"] + cfg["cartao"]
    linhas = [
        INICIO_HEAD,
        f"<title>{texto(p['titulo'])}</title>",
        f'<meta name="description" content="{texto(descricao)}">',
        f'<link rel="canonical" href="{texto(url)}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{texto(cfg["nome"])}">',
        f'<meta property="og:locale" content="{texto(cfg["locale"])}">',
        f'<meta property="og:title" content="{texto(p["titulo"])}">',
        f'<meta property="og:description" content="{texto(descricao)}">',
        f'<meta property="og:url" content="{texto(url)}">',
        f'<meta property="og:image" content="{texto(cartao)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{texto(p["titulo"])}">',
        f'<meta name="twitter:description" content="{texto(descricao)}">',
        f'<meta name="twitter:image" content="{texto(cartao)}">',
        '<link rel="alternate" type="application/json" title="Dados em JSON" href="dados/entrevistas.json">',
        f'<script type="application/ld+json">{_ld(dados_estruturados(cfg, pagina, resumo, lista))}</script>',
        FIM_HEAD,
    ]
    return "\n".join(linhas)


def _frase_do_total(resumo: dict, sujeito: str) -> str:
    total = (resumo.get("totais") or {}).get("entrevistas", 0)
    ambito = resumo.get("ambito") or {}
    return (f"{total} entrevistas exclusivas de {sujeito} na televisão portuguesa, "
            f"{ambito.get('rotulo', '')}.")


def corpo_index(cfg: dict, resumo: dict, lista: list) -> str:
    """O que um leitor sem JavaScript tem de encontrar: o numero, o
    periodo, a reparticao por canal e por ano, e por onde se verifica."""
    sujeito = sujeito_de(resumo)
    total = (resumo.get("totais") or {}).get("entrevistas", 0)
    canais = [c for c in resumo.get("por_canal", []) if c.get("entrevistas")]
    canais.sort(key=lambda c: (-c["entrevistas"], c["nome"]))
    linhas = [
        INICIO_CORPO,
        '<section class="cartao">',
        f"<h2>{texto(_frase_do_total(resumo, sujeito))}</h2>",
        f"<p>{texto((resumo.get('tema') or {}).get('pergunta', ''))} "
        f"Esta é a contagem, canal a canal, com uma prova pública por entrevista.</p>",
        "<h3>Por canal</h3>",
        "<ul>",
    ]
    for c in canais:
        linhas.append(f"<li>{texto(c['nome'])}: {c['entrevistas']}</li>")
    linhas.append("</ul>")
    linhas.append("<h3>Por ano</h3>")
    linhas.append("<ul>")
    for a in resumo.get("por_ano", []):
        linhas.append(f"<li>{texto(a['ano'])}: {a['entrevistas']}</li>")
    linhas.append("</ul>")
    if lista:
        primeira = lista[0]
        nomes = nomes_dos_canais(resumo)
        linhas.append(f"<p>Última entrevista: {texto(primeira['data'])}, "
                      f"{texto(nomes.get(primeira.get('canal'), primeira.get('canal')))}.</p>")
    linhas.append(f"<p>Total: {total}. "
                  '<a href="fontes.html">Ver todas as entrevistas e as provas</a>. '
                  '<a href="metodologia.html">Como isto é contado</a>.</p>')
    linhas.append("</section>")
    linhas.append(FIM_CORPO)
    return "\n".join(linhas)


def corpo_calendario(cfg: dict, resumo: dict, lista: list) -> str:
    sujeito = sujeito_de(resumo)
    linhas = [
        INICIO_CORPO,
        '<section class="cartao">',
        f"<h2>Calendário das entrevistas de {texto(sujeito)}</h2>",
        f"<p>{texto(_frase_do_total(resumo, sujeito))} "
        "O calendário dia a dia precisa de JavaScript; a lista completa, com as provas, "
        'está na <a href="fontes.html">página de Fontes</a>.</p>',
        "<ul>",
    ]
    for m in resumo.get("por_mes", []):
        linhas.append(f"<li>{texto(m['mes'])}: {m['entrevistas']}</li>")
    linhas += ["</ul>", "</section>", FIM_CORPO]
    return "\n".join(linhas)


# Sem coluna de programa desde 2026-10-21: o que se conta e o canal, e o
# programa e o titulo eram texto copiado das paginas de prova, muitas
# vezes vazio ou "nao apurado" (54 das 79 linhas visiveis em 2026-10-21).
# Os campos continuam nos dados; so deixam de ser mostrados. Tem de ser
# as mesmas colunas que `docs/fontes.js` desenha, senao quem le sem
# JavaScript ve outra tabela; ha um teste.
COLUNAS_FONTES = ("Data", "Canal", "Prova")


def corpo_fontes(cfg: dict, resumo: dict, lista: list) -> str:
    """A tabela toda em HTML, com uma ligacao por prova. E a pagina com
    mais valor para quem le sem JavaScript: sem ela, o site afirma um
    numero e nao mostra uma unica prova."""
    nomes = nomes_dos_canais(resumo)
    sujeito = sujeito_de(resumo)
    cabecalho = "".join(f"<th>{c}</th>" for c in COLUNAS_FONTES)
    linhas = [INICIO_CORPO]
    anos = sorted({e["data"][:4] for e in lista}, reverse=True)
    for ano in anos:
        do_ano = [e for e in lista if e["data"].startswith(ano)]
        plural = "entrevista exclusiva" if len(do_ano) == 1 else "entrevistas exclusivas"
        linhas.append("<section>")
        linhas.append(f"<h2>{ano}: {len(do_ano)} {plural}</h2>")
        linhas.append(f'<table class="tabela"><thead><tr>{cabecalho}</tr></thead><tbody>')
        for e in do_ano:
            canal = texto(nomes.get(e.get("canal"), e.get("canal")))
            outros = [nomes.get(c, c) for c in (e.get("canais") or [])[1:]]
            if outros:
                canal += " (também na " + texto(", ".join(outros)) + ")"
            provas = []
            transmissoes = e.get("transmissoes") or [e]
            varias = len(transmissoes) > 1
            for t in transmissoes:
                rotulo = (nomes.get(t.get("canal"), t.get("canal")) if varias
                          else ("notícia" if t.get("origem") == "imprensa" else "ver"))
                marca = " (imprensa)" if t.get("origem") == "imprensa" else ""
                provas.append(f'<a href="{texto(t.get("prova_url", ""))}" rel="noopener noreferrer" '
                              f'target="_blank">{texto(rotulo)}</a>{texto(marca)}')
            linhas.append(f"<tr><td>{texto(e['data'])}</td><td>{canal}</td>"
                          f"<td>{', '.join(provas)}</td></tr>")
        linhas.append("</tbody></table>")
        linhas.append("</section>")
    if not anos:
        linhas.append(f'<p class="legenda-secao">Ainda não há entrevistas de {texto(sujeito)} registadas.</p>')
    linhas.append(FIM_CORPO)
    return "\n".join(linhas)


CORPOS = {
    "index.html": corpo_index,
    "calendario.html": corpo_calendario,
    "fontes.html": corpo_fontes,
}


def sitemap(cfg: dict, resumo: dict) -> str:
    """As quatro paginas, com a data da ultima recolha. Um sitemap num
    subdirectorio so e encontrado se alguem o apontar: ver o robots."""
    data = str(resumo.get("gerado_em", ""))[:10]
    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for pagina in cfg["paginas"]:
        linhas.append("  <url>")
        linhas.append(f"    <loc>{html.escape(endereco(cfg, pagina))}</loc>")
        linhas.append(f"    <lastmod>{html.escape(data)}</lastmod>")
        linhas.append("  </url>")
    linhas.append("</urlset>")
    return "\n".join(linhas) + "\n"


def robots(cfg: dict) -> str:
    linhas = ["# Tudo neste site e publico e pode ser lido por qualquer agente,",
              "# de motor de pesquisa ou de modelo de linguagem.",
              "",
              "User-agent: *",
              "Allow: /",
              ""]
    for agente in cfg["robots_agentes"]:
        linhas.append(f"User-agent: {agente}")
        linhas.append("Allow: /")
        linhas.append("")
    linhas.append(f"Sitemap: {cfg['base']}sitemap.xml")
    return "\n".join(linhas) + "\n"


def injetar(pagina_html: str, inicio: str, fim: str, conteudo: str, onde: str) -> str:
    """Substitui o que esta entre os marcadores. Falha alto se eles nao
    existirem: um bloco que nao fosse escrito deixava a pagina sem
    metadados e sem conteudo, e ninguem daria por isso."""
    padrao = re.compile(re.escape(inicio) + r".*?" + re.escape(fim), re.DOTALL)
    if not padrao.search(pagina_html):
        raise ValueError(f"{onde}: faltam os marcadores {inicio} ... {fim}")
    return padrao.sub(lambda _: conteudo, pagina_html, count=1)


def aplicar(pagina: str, pagina_html: str, cfg: dict, resumo: dict, lista: list) -> str:
    """O head em todas as paginas; o corpo so nas que o JavaScript
    constroi a partir dos dados. A Metodologia e texto servido tal como
    esta e nao precisa de corpo nenhum."""
    saida = injetar(pagina_html, INICIO_HEAD, FIM_HEAD, bloco_head(cfg, pagina, resumo, lista), pagina)
    if pagina in CORPOS:
        saida = injetar(saida, INICIO_CORPO, FIM_CORPO, CORPOS[pagina](cfg, resumo, lista), pagina)
    return saida
