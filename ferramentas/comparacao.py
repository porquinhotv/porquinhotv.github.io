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
2. Ha uma janela so, a mesma para todos, incluindo o sujeito: comeca no
   dia em que a pessoa mais recente no cargo o assumiu e acaba no ultimo
   dia ate onde se procuraram as entrevistas das outras pessoas
   (`janela.ate`). Por isso so se mostra o que cai dentro dela: comparar
   tres anos de uma pessoa com ano e meio de outra nao e comparavel, e um
   numero do sujeito cortado noutro dia que nao o da pagina inicial
   parecia um erro (81 contra 82, apontado pelo autor a 2026-11-06).
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
    "intro": {"desde", "ate"},
    "frase_razao": {"nome", "razao"},
    "frase_zero": {"nome"},
    "frase_empate": {"nome", "n"},
    "remate": set(),
    "ritmo": {"dias"},
    "ritmo_zero": set(),
    "provas_titulo": set(),
    "provas_legenda": {"fontes"},
    "nenhuma_na_janela": {"data", "canal"},
    "metodo_titulo": set(),
    "metodo": {"desde", "ate", "total"},
    "por_verificar": {"k"},
}

# Nao e configuracao editorial: e a lingua em que as datas se escrevem.
# Para a frase "por cada entrevista de X, o porquinho deu mais de duas".
NUMERAIS = ("zero", "uma", "duas", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez")

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
        pessoas.append({"id": pid, "nome": p.get("nome", ""), "cargo": p.get("cargo", ""), "desde": inicio})
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
    """As contagens da pagina, todas dentro da janela. O sujeito conta-se
    sobre a lista publicada, a mesma que o resto do site mostra (ja com
    uma entrevista por linha, mesmo quando passou em dois canais)."""
    desde, ate = norm["desde"], norm["ate"]

    def na_janela(dia: dt.date) -> bool:
        return desde <= dia <= ate

    dias = [data(e["data"], "entrevistas.json") for e in lista]
    sujeito = {"janela": sum(na_janela(d) for d in dias),
               "total": sum(visivel_desde <= d for d in dias)}
    pessoas = []
    for p in norm["pessoas"]:
        suas = [e for e in norm["entrevistas"] if e["pessoa"] == p["id"]]
        confirmadas = [e for e in suas if e["estado"] == "confirmada"]
        linhas = sorted((e for e in confirmadas if na_janela(e["data"])),
                        key=lambda e: (e["data"], e["canal"]), reverse=True)
        anteriores = sorted((e for e in confirmadas if e["data"] < desde), key=lambda e: e["data"])
        pessoas.append(dict(p, janela=len(linhas), linhas=linhas,
                            ultima_antes=anteriores[-1] if anteriores else None,
                            por_verificar=sum(1 for e in suas if e["estado"] == "por_verificar"
                                              and na_janela(e["data"]))))
    return {"sujeito": sujeito, "pessoas": pessoas, "dias": (ate - desde).days + 1}


def _preencher(modelo: str, **valores) -> str:
    """Escapa o texto escrito no YAML e so depois preenche os espacos: os
    valores sao numeros, datas e, no caso da ligacao para as Fontes, HTML
    escrito aqui, que nao pode ser escapado."""
    return seo.texto(" ".join(modelo.split())).format(**valores)


def razao(n_sujeito: int, n_outro: int) -> str:
    """"duas" quando a conta e exacta, "mais de duas" quando nao e. Nunca
    arredonda para cima: 52 contra 25 da 2,08, e "duas" seria pouco, mas
    "mais de duas" e verdade."""
    inteiro, resto = divmod(n_sujeito, n_outro)
    palavra = NUMERAIS[inteiro] if inteiro < len(NUMERAIS) else str(inteiro)
    return palavra if resto == 0 else f"mais de {palavra}"


def frases_da_comparacao(t: dict, n_sujeito: int, pessoas: list) -> list:
    """Uma frase por pessoa, da que mais deu para a que menos deu. A frase
    satirica do fim so aparece se o sujeito deu mais do que cada uma das
    outras: e uma afirmacao, e tem de mudar sozinha se deixar de ser
    verdade."""
    frases = []
    for p in sorted(pessoas, key=lambda p: -p["janela"]):
        n = p["janela"]
        if n == 0:
            frases.append(_preencher(t["frase_zero"], nome=seo.texto(p["nome"])))
        elif n >= n_sujeito:
            frases.append(_preencher(t["frase_empate"], nome=seo.texto(p["nome"]), n=n))
        else:
            frases.append(_preencher(t["frase_razao"], nome=seo.texto(p["nome"]), razao=razao(n_sujeito, n)))
    if all(n_sujeito > p["janela"] for p in pessoas):
        frases.append(_preencher(t["remate"]))
    return frases


def _cartao(nome: str, cargo: str, n: int, dias: int, t: dict, classe: str) -> list:
    """Um cartao por pessoa: o numero, um quadrado por entrevista e o ritmo.
    Os quadrados sao a mesma unidade para todos, por isso a diferenca le-se
    sem escala nenhuma."""
    ritmo = _preencher(t["ritmo"], dias=round(dias / n)) if n else _preencher(t["ritmo_zero"])
    quadrados = "".join("<i></i>" for _ in range(n))
    return [f'<article class="{" ".join(c for c in ("pessoa", classe) if c)}">',
            f"<h3>{seo.texto(nome)}<small>{seo.texto(cargo)}</small></h3>",
            f'<p class="quantas">{n}</p>',
            f'<p class="quadrados" aria-hidden="true">{quadrados}</p>',
            f'<p class="ritmo">{ritmo}</p>',
            "</article>"]


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
    n_sujeito = contas["sujeito"]["janela"]

    linhas = [seo.INICIO_CORPO, '<section class="cartao comparativo">',
              f"<h2>{_preencher(t['titulo'])}</h2>",
              f'<p class="legenda-secao">{_preencher(t["intro"], desde=desde, ate=ate)}</p>',
              '<div class="trio">']
    linhas += _cartao(sujeito, norm["cargo_sujeito"], n_sujeito, contas["dias"], t, "porquinho")
    for p in sorted(pessoas, key=lambda p: -p["janela"]):
        linhas += _cartao(p["nome"], p["cargo"], p["janela"], contas["dias"], t, "")
    linhas.append("</div>")
    linhas.append('<p class="veredicto">' + " ".join(frases_da_comparacao(t, n_sujeito, pessoas)) + "</p>")
    linhas.append("</section>")

    fontes = '<a href="fontes.html">página de Fontes</a>'
    linhas += ['<section class="provas-dos-outros">', f"<h2>{_preencher(t['provas_titulo'])}</h2>",
               f'<p class="legenda-secao">{_preencher(t["provas_legenda"], fontes=fontes)}</p>']
    for p in sorted(pessoas, key=lambda p: -p["janela"]):
        linhas.append(f"<h3>{seo.texto(p['nome'])}: {_plural(p['janela'])}</h3>")
        if p["linhas"]:
            linhas += _tabela(p["linhas"], nomes, norm["rotulos"])
        elif p["ultima_antes"]:
            u = p["ultima_antes"]
            frase = _preencher(t["nenhuma_na_janela"], data=por_extenso(u["data"]),
                               canal=seo.texto(nomes.get(u["canal"], u["canal"])))
            rotulo = seo.texto(norm["rotulos"][u["tipo_prova"]])
            linhas.append(f'<p class="legenda-secao">{frase} <a href="{seo.texto(u["prova"])}" '
                          f'rel="noopener noreferrer" target="_blank">{rotulo}</a>.</p>')
        if p["por_verificar"]:
            linhas.append(f'<p class="legenda-secao">{_preencher(t["por_verificar"], k=p["por_verificar"])}</p>')
    linhas.append("</section>")

    linhas += ["<section>", f"<h2>{_preencher(t['metodo_titulo'])}</h2>"]
    linhas += [f"<p>{_preencher(par, desde=desde, ate=ate, total=contas['sujeito']['total'])}</p>"
               for par in t["metodo"]]
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
    print(f"janela: {norm['desde']} a {norm['ate']} ({contas['dias']} dias)")
    print(f"  {seo.sujeito_de(resumo)}: {contas['sujeito']['janela']} (desde {visivel}: {contas['sujeito']['total']})")
    for p in contas["pessoas"]:
        print(f"  {p['nome']}: {p['janela']}, por verificar {p['por_verificar']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
