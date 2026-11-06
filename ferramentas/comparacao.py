"""Pagina de comparacao: as entrevistas exclusivas de outras pessoas,
contadas com as regras do site, ao lado das do sujeito.

    python -m ferramentas.comparacao     imprime as contagens, nao escreve nada

Quem escreve a pagina e o `gerar_seo`, que todos os workflows que
escrevem dados ja correm. O bloco de `docs/comparacao.html` sai daqui, a
partir de `config/comparacao.yml` e dos dados publicados, e o teste que
compara o publicado com o gerado apanha uma pagina atrasada. A pagina
vem inteira no HTML e o browser nao calcula nada: os numeros tem uma
origem so.

Tres regras, cada uma com a razao:

1. So conta `estado: confirmada`. Uma linha por verificar fica no
   ficheiro com o motivo, para a decisao ficar registada, e nao entra em
   numero nenhum: "nao sei" nao e "sim".
2. A janela e a mesma para todos, incluindo o sujeito, e acaba no dia em
   que o levantamento das outras pessoas fechou (`janela.ate`). Sem isso,
   o numero do sujeito continuava a crescer com cada entrevista nova e o
   das outras ficava parado: o contraste crescia sozinho, que e o erro
   por excesso que o site promete nao cometer.
3. Nenhum nome aqui. As pessoas, os cargos e os textos vivem no YAML; os
   nomes dos canais vem do resumo publicado, como no resto do gerador.

A validacao falha alto e diz todos os problemas de uma vez. Como corre
dentro do `gerar_seo`, um erro no YAML para o workflow antes do commit e
nunca e publicado.
"""

from __future__ import annotations

import datetime as dt
import re
import sys

import yaml

from ferramentas import seo

RAIZ = seo.RAIZ
CONFIG = RAIZ / "config" / "comparacao.yml"
EDITORIAL = RAIZ / "config" / "porquinho.yml"

ESTADOS = ("confirmada", "por_verificar", "fora_do_ambito")
FORMATOS = ("informativa", "entretenimento")

# Os espacos que cada texto pode usar. Um espaco que o gerador nao
# preenche apareceria no ecra com as chavetas a vista, e um texto em falta
# deixava um titulo vazio: as duas coisas param na validacao, como ja
# acontece com os textos satiricos da pagina principal.
ESPACOS = {
    "titulo": set(),
    "intro": set(),
    "janela_titulo": {"desde", "ate"},
    "janela_legenda": {"desde", "ate"},
    "frase_mais": {"n", "soma"},
    "frase_menos": {"n", "soma"},
    "total_titulo": {"desde", "ate"},
    "provas_titulo": set(),
    "provas_legenda": {"fontes"},
    "metodo_titulo": set(),
    "metodo": {"ate"},
    "por_verificar": {"k"},
}

# Nao e configuracao editorial: e a lingua em que as datas se escrevem.
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def carregar() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def canais_validos() -> set:
    """Os ids dos nove canais, lidos da configuracao editorial: um canal
    escrito de outra forma ficava fora da tabela de cores e do nome
    publicado, e ninguem dava por isso na pagina."""
    editorial = yaml.safe_load(EDITORIAL.read_text(encoding="utf-8"))
    return {c["id"] for c in editorial.get("canais", [])}


def data(valor, onde: str) -> dt.date:
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    try:
        return dt.date.fromisoformat(str(valor))
    except ValueError:
        raise ValueError(f"{onde}: data invalida {valor!r}") from None


def por_extenso(dia: dt.date) -> str:
    return f"{dia.day} de {MESES[dia.month - 1]} de {dia.year}"


def _espacos(texto: str) -> set:
    return set(re.findall(r"\{([^{}]*)\}", texto))


def _validar_textos(textos: dict, erros: list) -> None:
    for chave, permitidos in ESPACOS.items():
        valor = textos.get(chave)
        partes = valor if isinstance(valor, list) else [valor]
        if not valor or not all(isinstance(p, str) and p.strip() for p in partes):
            erros.append(f"textos.{chave}: em falta ou vazio")
            continue
        for parte in partes:
            fora = _espacos(parte) - permitidos
            if fora:
                erros.append(f"textos.{chave}: espaco que o gerador nao preenche: {sorted(fora)}")
    for chave in sorted(set(textos) - set(ESPACOS)):
        erros.append(f"textos.{chave}: texto que a pagina nao usa")


def validar(cfg: dict, canais: set, visivel_desde: dt.date) -> dict:
    """Devolve a configuracao com as datas ja convertidas, ou falha com a
    lista de todos os problemas. Cada verificacao trava um erro que, de
    outra forma, ficava calado na pagina: um canal mal escrito, uma linha
    confirmada sem prova, a mesma entrevista duas vezes, uma confirmada
    fora da janela que ninguem via contar."""
    erros: list = []
    janela = cfg.get("janela") or {}
    try:
        desde = data(janela.get("desde"), "janela.desde")
        ate = data(janela.get("ate"), "janela.ate")
    except ValueError as e:
        raise ValueError(f"config/comparacao.yml: {e}") from None
    if desde > ate:
        erros.append("janela: `desde` depois de `ate`")

    pessoas = []
    ids = set()
    for i, p in enumerate(cfg.get("pessoas") or []):
        onde = f"pessoas[{i}]"
        pid = p.get("id")
        if not pid or pid in ids:
            erros.append(f"{onde}: id em falta ou repetido ({pid!r})")
            continue
        ids.add(pid)
        if not p.get("nome") or not p.get("cargo"):
            erros.append(f"{onde}: falta o nome ou o cargo")
        try:
            inicio = data(p.get("desde"), onde + ".desde")
        except ValueError as e:
            erros.append(str(e))
            continue
        if inicio > visivel_desde and not p.get("nota_periodo"):
            erros.append(f"{onde}: entra depois do inicio do site e falta a `nota_periodo` que o diz")
        if _espacos(str(p.get("nota_periodo") or "")):
            erros.append(f"{onde}: a `nota_periodo` nao tem espacos para preencher")
        pessoas.append({"id": pid, "nome": p.get("nome", ""), "cargo": p.get("cargo", ""),
                        "desde": inicio, "nota_periodo": p.get("nota_periodo") or ""})
    if not pessoas:
        erros.append("pessoas: nenhuma")
    inicio_de = {p["id"]: p["desde"] for p in pessoas}

    textos = cfg.get("textos") or {}
    _validar_textos(textos, erros)
    rotulos = cfg.get("rotulos_de_prova") or {}
    cargo_sujeito = (cfg.get("sujeito") or {}).get("cargo") or ""
    if not cargo_sujeito:
        erros.append("sujeito.cargo: em falta")

    entrevistas = []
    vistas_linha = {}
    vistas_prova = {}
    for i, e in enumerate(cfg.get("entrevistas") or []):
        onde = f"entrevistas[{i}]"
        try:
            dia = data(e.get("data"), onde + ".data")
        except ValueError as ex:
            erros.append(str(ex))
            continue
        onde = f"{onde} ({e.get('pessoa')}, {dia})"
        estado = e.get("estado")
        canal = e.get("canal")
        prova = str(e.get("prova") or "")
        tambem = list(e.get("tambem_em") or [])
        if e.get("pessoa") not in inicio_de:
            erros.append(f"{onde}: pessoa desconhecida")
        if estado not in ESTADOS:
            erros.append(f"{onde}: estado {estado!r} nao e um de {list(ESTADOS)}")
        if e.get("formato") not in FORMATOS:
            erros.append(f"{onde}: formato {e.get('formato')!r} nao e um de {list(FORMATOS)}")
        if canal is not None and canal not in canais:
            erros.append(f"{onde}: canal {canal!r} nao e um id de config/porquinho.yml")
        for outro in tambem:
            if outro not in canais or outro == canal:
                erros.append(f"{onde}: tambem_em {outro!r} nao e outro canal valido")
        if not prova.startswith(("https://", "http://")):
            erros.append(f"{onde}: a prova nao e um endereco")
        if prova in vistas_prova:
            erros.append(f"{onde}: a mesma prova que {vistas_prova[prova]}")
        vistas_prova[prova] = onde
        if e.get("tipo_prova") not in rotulos:
            erros.append(f"{onde}: tipo_prova {e.get('tipo_prova')!r} sem rotulo em rotulos_de_prova")
        if estado == "confirmada":
            if canal is None:
                erros.append(f"{onde}: confirmada sem canal")
            chave = (e.get("pessoa"), dia, canal)
            if chave in vistas_linha:
                erros.append(f"{onde}: a mesma pessoa, dia e canal que {vistas_linha[chave]}")
            vistas_linha[chave] = onde
            inicio = inicio_de.get(e.get("pessoa"))
            if dia < visivel_desde or (inicio and dia < inicio):
                erros.append(f"{onde}: confirmada antes do inicio da contagem; e fora_do_ambito")
            if dia > ate:
                erros.append(f"{onde}: confirmada depois de janela.ate; mover a data de fecho")
        entrevistas.append({"pessoa": e.get("pessoa"), "data": dia, "canal": canal, "tambem_em": tambem,
                            "estado": estado, "tipo_prova": e.get("tipo_prova"), "prova": prova})
    if erros:
        raise ValueError("config/comparacao.yml:\n- " + "\n- ".join(erros))
    return {"desde": desde, "ate": ate, "cargo_sujeito": cargo_sujeito, "pessoas": pessoas,
            "rotulos": rotulos, "textos": textos, "entrevistas": entrevistas}


def contar(norm: dict, lista: list, visivel_desde: dt.date) -> dict:
    """As contagens da pagina. O sujeito conta-se sobre a lista publicada,
    a mesma que o resto do site mostra (ja com uma entrevista por linha,
    mesmo quando passou em dois canais), e no mesmo intervalo que as
    outras pessoas."""
    desde, ate = norm["desde"], norm["ate"]

    def no_intervalo(dia: dt.date, inicio: dt.date) -> bool:
        return inicio <= dia <= ate

    dias = [data(e["data"], "entrevistas.json") for e in lista]
    sujeito = {"janela": sum(no_intervalo(d, desde) for d in dias),
               "total": sum(no_intervalo(d, visivel_desde) for d in dias)}
    pessoas = []
    for p in norm["pessoas"]:
        suas = [e for e in norm["entrevistas"] if e["pessoa"] == p["id"]]
        confirmadas = [e for e in suas if e["estado"] == "confirmada"]
        inicio = max(p["desde"], visivel_desde)
        linhas = sorted((e for e in confirmadas if no_intervalo(e["data"], inicio)),
                        key=lambda e: (e["data"], e["canal"]), reverse=True)
        comparavel = p["desde"] <= visivel_desde
        pessoas.append(dict(p,
                            janela=sum(no_intervalo(e["data"], desde) for e in confirmadas),
                            total=len(linhas) if comparavel else None,
                            linhas=linhas,
                            por_verificar=sum(1 for e in suas if e["estado"] == "por_verificar"
                                              and no_intervalo(e["data"], inicio))))
    return {"sujeito": sujeito, "pessoas": pessoas}


def _preencher(modelo: str, **valores) -> str:
    """Escapa o texto escrito no YAML e so depois preenche os espacos: os
    valores sao numeros, datas e, no caso da ligacao para as Fontes, HTML
    escrito aqui, que nao pode ser escapado."""
    return seo.texto(" ".join(modelo.split())).format(**valores)


def _barras(itens: list) -> list:
    maximo = max((n for _, _, n, _ in itens), default=0) or 1
    linhas = ['<ul class="frente">']
    for nome, cargo, n, classe in itens:
        largura = round(100 * n / maximo)
        atributo = f' class="{classe}"' if classe else ""
        linhas.append(f'<li{atributo}><span class="quem">{seo.texto(nome)}<small>{seo.texto(cargo)}</small></span>'
                      f'<span class="pista" aria-hidden="true"><span style="width: {largura}%"></span></span>'
                      f'<span class="valor">{n}</span></li>')
    linhas.append("</ul>")
    return linhas


def _tabela(linhas: list, nomes: dict, rotulos: dict) -> list:
    cabecalho = "".join(f"<th>{c}</th>" for c in seo.COLUNAS_FONTES)
    saida = [f'<table class="tabela"><thead><tr>{cabecalho}</tr></thead><tbody>']
    for e in linhas:
        canal = seo.texto(nomes.get(e["canal"], e["canal"]))
        if e["tambem_em"]:
            outros = ", ".join(nomes.get(c, c) for c in e["tambem_em"])
            canal += f'<span class="parcial"> (também na {seo.texto(outros)})</span>'
        rotulo = seo.texto(rotulos[e["tipo_prova"]])
        saida.append(f'<tr><td>{e["data"].isoformat()}</td>'
                     f'<td class="canal" style="--cor: var(--canal-{seo.texto(e["canal"])})">{canal}</td>'
                     f'<td><a href="{seo.texto(e["prova"])}" rel="noopener noreferrer" target="_blank">{rotulo}</a></td></tr>')
    saida.append("</tbody></table>")
    return saida


def _plural(n: int) -> str:
    return f"{n} entrevista exclusiva" if n == 1 else f"{n} entrevistas exclusivas"


def desenhar(norm: dict, contas: dict, resumo: dict, visivel_desde: dt.date) -> str:
    t = norm["textos"]
    nomes = seo.nomes_dos_canais(resumo)
    sujeito = seo.sujeito_de(resumo)
    desde, ate = por_extenso(norm["desde"]), por_extenso(norm["ate"])
    pessoas = contas["pessoas"]

    linhas = [seo.INICIO_CORPO, '<section class="cartao">',
              f"<h2>{_preencher(t['titulo'])}</h2>",
              f"<p>{_preencher(t['intro'])}</p>",
              "</section>"]

    linhas += ["<section>", f"<h2>{_preencher(t['janela_titulo'], desde=desde, ate=ate)}</h2>",
               f'<p class="legenda-secao">{_preencher(t["janela_legenda"], desde=desde, ate=ate)}</p>']
    itens = [(sujeito, norm["cargo_sujeito"], contas["sujeito"]["janela"], "porquinho")]
    itens += [(p["nome"], p["cargo"], p["janela"], "") for p in pessoas]
    linhas += _barras(itens)
    n, soma = contas["sujeito"]["janela"], sum(p["janela"] for p in pessoas)
    frase = t["frase_mais"] if n > soma else t["frase_menos"]
    linhas += [f'<p class="comparacao">{_preencher(frase, n=n, soma=soma)}</p>', "</section>"]

    comparaveis = [p for p in pessoas if p["total"] is not None]
    if comparaveis:
        linhas += ["<section>",
                   f"<h2>{_preencher(t['total_titulo'], desde=por_extenso(visivel_desde), ate=ate)}</h2>"]
        itens = [(sujeito, norm["cargo_sujeito"], contas["sujeito"]["total"], "porquinho")]
        itens += [(p["nome"], p["cargo"], p["total"], "") for p in comparaveis]
        linhas += _barras(itens)
        for p in pessoas:
            if p["total"] is None:
                linhas.append(f'<p class="legenda-secao">{_preencher(p["nota_periodo"])}</p>')
        linhas.append("</section>")

    fontes = '<a href="fontes.html">página de Fontes</a>'
    linhas += ['<section class="provas-dos-outros">', f"<h2>{_preencher(t['provas_titulo'])}</h2>",
               f'<p class="legenda-secao">{_preencher(t["provas_legenda"], fontes=fontes)}</p>']
    for p in pessoas:
        linhas.append(f"<h3>{seo.texto(p['nome'])}: {_plural(len(p['linhas']))}</h3>")
        if p["linhas"]:
            linhas += _tabela(p["linhas"], nomes, norm["rotulos"])
        if p["por_verificar"]:
            linhas.append(f'<p class="legenda-secao">{_preencher(t["por_verificar"], k=p["por_verificar"])}</p>')
    linhas.append("</section>")

    linhas += ["<section>", f"<h2>{_preencher(t['metodo_titulo'])}</h2>"]
    linhas += [f"<p>{_preencher(paragrafo, ate=ate)}</p>" for paragrafo in t["metodo"]]
    linhas.append('<p><a href="metodologia.html">Como o resto do site é contado</a>.</p>')
    linhas += ["</section>", seo.FIM_CORPO]
    return "\n".join(linhas)


def visivel_de(resumo: dict) -> dt.date:
    return data((resumo.get("ambito") or {}).get("visivel_desde") or "0001-01-01", "resumo.ambito.visivel_desde")


def corpo(resumo: dict, lista: list, cfg: dict | None = None, canais: set | None = None) -> str:
    """O bloco pre-renderizado da pagina. `cfg` e `canais` so se passam nos
    testes; em uso real leem-se dos ficheiros do repositorio."""
    cfg = carregar() if cfg is None else cfg
    canais = canais_validos() if canais is None else canais
    visivel = visivel_de(resumo)
    norm = validar(cfg, canais, visivel)
    return desenhar(norm, contar(norm, lista, visivel), resumo, visivel)


def main() -> int:
    """O resumo na consola, para quem acrescenta uma linha ao YAML ver o
    efeito sem abrir a pagina."""
    resumo, entrevistas = seo.dados()
    lista = seo.visiveis(resumo, entrevistas)
    visivel = visivel_de(resumo)
    norm = validar(carregar(), canais_validos(), visivel)
    contas = contar(norm, lista, visivel)
    print(f"janela comum: {norm['desde']} a {norm['ate']}")
    s = contas["sujeito"]
    print(f"  {seo.sujeito_de(resumo)}: {s['janela']} na janela, {s['total']} desde {visivel}")
    for p in contas["pessoas"]:
        total = "so na janela" if p["total"] is None else f"{p['total']} desde {max(p['desde'], visivel)}"
        print(f"  {p['nome']}: {p['janela']} na janela, {total}, por verificar {p['por_verificar']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
