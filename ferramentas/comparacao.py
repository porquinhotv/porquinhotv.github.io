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
2. Cada pessoa conta-se desde que o site conta ou desde que assumiu o
   cargo, o que for mais tarde, e todas ate ao mesmo dia de fecho
   (`janela.ate`), incluindo o sujeito. Os periodos diferentes mostram-se
   numa linha do tempo comum, com a faixa de quem entrou mais tarde
   riscada antes da entrada, e o ritmo (uma entrevista a cada N dias)
   mede cada um no seu periodo. A comparacao directa, numero contra
   numero, faz-se so na janela comum (`janela.desde` a `janela.ate`):
   tres anos de uma pessoa ao lado de ano e meio de outra nao se comparam
   pelo total. Pedido do autor a 2026-11-06: dar o peso visual a todas as
   entrevistas do sujeito, sendo honesto quanto a quem entrou quando.
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
    "periodo": {"desde", "ate"},
    "intro": set(),
    "desde_cartao": {"data"},
    "ritmo": {"dias"},
    "ritmo_zero": set(),
    "linha_titulo": set(),
    "linha_legenda": set(),
    "janela_titulo": {"desde", "ate"},
    "frase_razao": {"nome", "razao"},
    "frase_zero": {"nome"},
    "frase_empate": {"nome", "n"},
    "remate": set(),
    "provas_titulo": set(),
    "provas_legenda": {"fontes"},
    "metodo_titulo": set(),
    "metodo": {"inicio", "desde", "ate"},
    "por_verificar": {"k"},
}

# Abreviaturas dos meses no eixo da linha do tempo.
MESES_CURTOS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")

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
        if inicio > visivel_desde and not (p.get("marco") and p.get("antes")):
            erros.append(f"{onde}: entra depois do inicio do site; faltam `marco` e `antes`, que a linha do tempo mostra")
        for chave in ("marco", "antes", "desde_texto"):
            if _espacos(str(p.get(chave) or "")):
                erros.append(f"{onde}: `{chave}` nao tem espacos para preencher")
        pessoas.append({"id": pid, "nome": p.get("nome", ""), "cargo": p.get("cargo", ""), "desde": inicio,
                        "marco": p.get("marco") or "", "antes": p.get("antes") or "",
                        "desde_texto": p.get("desde_texto") or ""})
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
    mesmo quando passou em dois canais). Todos acabam no mesmo dia."""
    desde, ate = norm["desde"], norm["ate"]
    dias_sujeito = sorted(d for d in (data(e["data"], "entrevistas.json") for e in lista)
                          if visivel_desde <= d <= ate)
    sujeito = {"inicio": visivel_desde, "dias": dias_sujeito, "total": len(dias_sujeito),
               "janela": sum(desde <= d for d in dias_sujeito),
               "duracao": (ate - visivel_desde).days + 1}
    pessoas = []
    for p in norm["pessoas"]:
        inicio = max(p["desde"], visivel_desde)
        suas = [e for e in norm["entrevistas"] if e["pessoa"] == p["id"]]
        linhas = sorted((e for e in suas if e["estado"] == "confirmada" and inicio <= e["data"] <= ate),
                        key=lambda e: (e["data"], e["canal"]), reverse=True)
        pessoas.append(dict(p, inicio=inicio, linhas=linhas, total=len(linhas),
                            dias=sorted(e["data"] for e in linhas),
                            janela=sum(desde <= e["data"] for e in linhas),
                            duracao=(ate - inicio).days + 1,
                            por_verificar=sum(1 for e in suas if e["estado"] == "por_verificar"
                                              and inicio <= e["data"] <= ate)))
    return {"sujeito": sujeito, "pessoas": pessoas}


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


def _ritmo(t: dict, n: int, duracao: int) -> str:
    return _preencher(t["ritmo"], dias=round(duracao / n)) if n else _preencher(t["ritmo_zero"])


def _cartao(nome: str, cargo: str, n: int, desde: str, ritmo: str, classe: str) -> list:
    return [f'<article class="{" ".join(c for c in ("pessoa", classe) if c)}">',
            f"<h3>{seo.texto(nome)}<small>{seo.texto(cargo)}</small></h3>",
            f'<p class="quantas">{n}</p>',
            f'<p class="desde">{desde}</p>',
            f'<p class="ritmo">{ritmo}</p>',
            "</article>"]


def _meses(inicio: dt.date, fim: dt.date) -> list:
    meses, (a, m) = [], (inicio.year, inicio.month)
    while (a, m) <= (fim.year, fim.month):
        meses.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return meses


def _faixa(nome: str, dias: list, inicio_pessoa: dt.date, meses: list, antes: str, classe: str) -> list:
    """Uma faixa da linha do tempo: um quadrado por entrevista, no mes em
    que passou. Os meses antes de a pessoa entrar ficam riscados e dizem
    porque, para que uma faixa vazia nunca pareca uma pessoa calada."""
    por_mes: dict = {}
    for d in dias:
        por_mes[(d.year, d.month)] = por_mes.get((d.year, d.month), 0) + 1
    celulas = []
    for a, m in meses:
        antes_de_entrar = (a, m) < (inicio_pessoa.year, inicio_pessoa.month)
        quadrados = "".join("<i></i>" for _ in range(por_mes.get((a, m), 0)))
        classe_mes = ' class="antes"' if antes_de_entrar else ""
        celulas.append(f"<span{classe_mes}>{quadrados}</span>")
    n_antes = sum((a, m) < (inicio_pessoa.year, inicio_pessoa.month) for a, m in meses)
    if n_antes:
        celulas.append(f'<em style="width: calc({n_antes} / var(--meses) * 100%)">{seo.texto(antes)}</em>')
    atributo = f" {classe}" if classe else ""
    return [f'<div class="faixa{atributo}">', f'<p class="faixa-nome">{seo.texto(nome)}: {len(dias)}</p>',
            f'<div class="meses">{"".join(celulas)}</div>', "</div>"]


def _eixo(meses: list) -> str:
    """Os anos por baixo da linha do tempo, cada um sobre os seus meses, e
    o primeiro e o ultimo mes por extenso: a pagina diz o periodo sem
    obrigar ninguem a contar colunas."""
    partes, i = [], 0
    while i < len(meses):
        ano = meses[i][0]
        j = i
        while j < len(meses) and meses[j][0] == ano:
            j += 1
        partes.append(f'<span style="grid-column: {i + 1} / span {j - i}">{ano}</span>')
        i = j
    return f'<div class="eixo">{"".join(partes)}</div>'


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
    ate = norm["ate"]
    s, pessoas = contas["sujeito"], contas["pessoas"]
    ordem = sorted(pessoas, key=lambda p: (p["inicio"], -p["total"]))

    linhas = [seo.INICIO_CORPO, '<section class="cartao comparativo">',
              f"<h2>{_preencher(t['titulo'])}</h2>",
              f'<p class="periodo">{_preencher(t["periodo"], desde=por_extenso(visivel_desde), ate=por_extenso(ate))}</p>',
              f'<p class="legenda-secao">{_preencher(t["intro"])}</p>',
              '<div class="trio">']
    linhas += _cartao(sujeito, norm["cargo_sujeito"], s["total"],
                      _preencher(t["desde_cartao"], data=por_extenso(visivel_desde)),
                      _ritmo(t, s["total"], s["duracao"]), "porquinho")
    for p in ordem:
        desde = _preencher(t["desde_cartao"], data=por_extenso(p["inicio"]))
        if p["desde_texto"] and p["inicio"] > visivel_desde:
            desde += ", " + seo.texto(p["desde_texto"])
        linhas += _cartao(p["nome"], p["cargo"], p["total"], desde, _ritmo(t, p["total"], p["duracao"]), "")
    linhas.append("</div>")

    meses = _meses(visivel_desde, ate)
    linhas += [f"<h3>{_preencher(t['linha_titulo'])}</h3>",
               f'<div class="linha-tempo" style="--meses: {len(meses)}">']
    linhas += _faixa(sujeito, s["dias"], visivel_desde, meses, "", "porquinho")
    for p in ordem:
        linhas += _faixa(p["nome"], p["dias"], p["inicio"], meses, p["antes"], "")
    linhas += [_eixo(meses), "</div>"]
    primeiro, ultimo = meses[0], meses[-1]
    marcos = [f"{por_extenso(p['inicio'])}: {seo.texto(p['marco'])}." for p in ordem if p["inicio"] > visivel_desde]
    legenda = f"{MESES_CURTOS[primeiro[1] - 1]} {primeiro[0]} a {MESES_CURTOS[ultimo[1] - 1]} {ultimo[0]}. "
    linhas.append(f'<p class="legenda-secao">{legenda}{_preencher(t["linha_legenda"])} {" ".join(marcos)}</p>')

    desde_j, ate_j = por_extenso(norm["desde"]), por_extenso(ate)
    linhas += [f'<h3>{_preencher(t["janela_titulo"], desde=desde_j, ate=ate_j)}</h3>',
               '<p class="mesmo-periodo">' + " · ".join(
                   [f"<strong>{seo.texto(sujeito)} {s['janela']}</strong>"]
                   + [f"{seo.texto(p['nome'])} {p['janela']}" for p in sorted(pessoas, key=lambda p: -p["janela"])])
               + "</p>",
               '<p class="veredicto">' + " ".join(frases_da_comparacao(t, s["janela"], pessoas)) + "</p>",
               "</section>"]

    fontes = '<a href="fontes.html">página de Fontes</a>'
    linhas += ['<section class="provas-dos-outros">', f"<h2>{_preencher(t['provas_titulo'])}</h2>",
               f'<p class="legenda-secao">{_preencher(t["provas_legenda"], fontes=fontes)}</p>']
    for p in ordem:
        linhas.append(f"<h3>{seo.texto(p['nome'])}: {_plural(p['total'])}, "
                      f"{_preencher(t['desde_cartao'], data=por_extenso(p['inicio']))}</h3>")
        if p["linhas"]:
            linhas += _tabela(p["linhas"], nomes, norm["rotulos"])
        if p["por_verificar"]:
            linhas.append(f'<p class="legenda-secao">{_preencher(t["por_verificar"], k=p["por_verificar"])}</p>')
    linhas.append("</section>")

    linhas += ["<section>", f"<h2>{_preencher(t['metodo_titulo'])}</h2>"]
    linhas += [f"<p>{_preencher(par, inicio=por_extenso(visivel_desde), desde=desde_j, ate=ate_j)}</p>"
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
    s = contas["sujeito"]
    print(f"fecho: {norm['ate']}; periodo comum desde {norm['desde']}")
    print(f"  {seo.sujeito_de(resumo)}: {s['total']} desde {visivel}, {s['janela']} no periodo comum")
    for p in contas["pessoas"]:
        print(f"  {p['nome']}: {p['total']} desde {p['inicio']}, {p['janela']} no periodo comum, "
              f"por verificar {p['por_verificar']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
