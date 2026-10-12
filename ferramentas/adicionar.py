"""Acrescentar uma ou varias entrevistas a curadoria, num passo so.

    python -m ferramentas.adicionar --entradas "2026-10-05 <canal> https://...; 08-10-2026 <canal> https://..."

E o que o workflow `adicionar` corre quando o formulario e preenchido.
Pedido do autor a 2026-10-12: dar o dia, o canal e a ligacao, e ver a
entrevista no site, sem patch, sem PowerShell e sem disparar a recolha
inteira; no mesmo dia, poder fazer o mesmo com varias de uma vez.

**Uma entrada** e o dia, o canal e a ligacao, por qualquer ordem,
separados por espacos ou virgulas. **Varias entradas** separam-se por
ponto e virgula. O ponto e virgula e obrigatorio porque a caixa de texto
do formulario e de uma linha so: o browser apaga as mudancas de linha de
um texto colado, e a ligacao de uma entrada ficaria colada a data da
seguinte. Uma entrada com duas ligacoes e recusada com esse motivo.

**Tudo ou nada.** Se uma entrada do lote nao serve, nada e escrito e o
relatorio diz quais e porque. Escrever as boas e calar as outras deixava
o lote meio entrado sem que quem o preencheu soubesse quais faltam.

**O que esta ferramenta nao decide.** O dia e o canal sao afirmacoes de
quem leu a publicacao, como em todo o `curadoria.yml`, e e isso que da a
esta via a isencao da prova de formato e das rondas. A data nunca e
deduzida da ligacao: o identificador de uma publicacao diz quando ela foi
publicada, nao quando a entrevista passou, e um "amanha as 21h" ficaria
no dia errado. A KB pagou isto com quatro datas erradas em vinte e quatro
(licao vigesima sexta). A data deduzida serve so para avisar.

**Recusa** (nada e escrito): canal que nao se reconhece, data que nao
existe, prova que nao e um endereco, prova ja na curadoria, ja publicada,
ja vetada ou repetida no proprio lote. **Avisa** (escreve na mesma): a
publicacao e de outro dia, o mesmo canal ja tem uma entrevista a um dia
de distancia, a data esta fora do ambito visivel ou no futuro. Um aviso
nao trava porque os tres casos existem de verdade: um anuncio na
vespera, duas entrevistas em dias seguidos, um registo antigo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import yaml

from recolha.extracao import data_para_iso
from recolha.modelos import RAIZ, url_normalizado

CURADORIA = RAIZ / "config" / "curadoria.yml"
PORQUINHO = RAIZ / "config" / "porquinho.yml"
PISTAS = RAIZ / "config" / "pistas.yml"
PUBLICADAS = RAIZ / "docs" / "dados" / "entrevistas.json"
LISBOA = ZoneInfo("Europe/Lisbon")

# As escritas aceites para a data. A compacta e a de dia primeiro existem
# porque o formulario se preenche muitas vezes no telemovel; o ficheiro
# recebe sempre ISO. A forma inteira tem de casar: `data_para_iso` aceita
# um prefixo e deixaria passar "2026-10-05 qualquer coisa".
FORMAS_DE_DATA = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{8}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})$")
# Uma ligacao acaba no primeiro espaco ou ponto e virgula: as entradas
# coladas sem espaco depois do separador nao podem virar uma ligacao so.
LIGACAO = re.compile(r"https?://[^\s;]+")

# A lista onde se acrescenta acaba onde a seguinte comeca. Escreve-se no
# texto, e nao por yaml.dump, porque um dump reescrevia o ficheiro inteiro
# e apagava todos os comentarios, que sao o registo de porque cada linha
# esta ali.
FIM_DA_LISTA = "\nremover:"

# Epoca dos identificadores da rede social, em milissegundos. Os 41 bits
# de cima do identificador sao o instante de publicacao contado a partir
# daqui. Validado ao dia em 2025-04-03 e 2025-08-05, ao minuto em
# 2026-09-28 (20:00 de Lisboa), e nos tres dias dados pelo autor a
# 2026-10-12. Serve para avisar, nunca para datar: ver o topo.
EPOCA_MS = 1314220021721
ALFABETO = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
# Conta opcional no caminho, tipo e codigo. Partilhar do telemovel traz o
# endereco com `?igsh=...`, e o mesmo codigo pode vir com ou sem conta no
# caminho: comparar enderecos por inteiro deixava passar a mesma
# publicacao duas vezes.
CAMINHO_SOCIAL = re.compile(r"^/(?:[A-Za-z0-9_.]+/)?(p|reel|tv)/([A-Za-z0-9_-]{6,})/?$")


def normalizar_data(escrito: str) -> str:
    """A data em ISO, ou vazio se nao for uma data do calendario."""
    escrito = (escrito or "").strip()
    if not FORMAS_DE_DATA.match(escrito):
        return ""
    if len(escrito) == 8 and escrito.isdigit():
        escrito = f"{escrito[:4]}-{escrito[4:6]}-{escrito[6:]}"
    iso = data_para_iso(escrito.replace(".", "-"))
    try:
        date.fromisoformat(iso)
    except ValueError:
        return ""
    return iso


def _simples(texto: str) -> str:
    """Sem acentos, sem maiusculas, hifens e espacos iguais."""
    sem_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(p for p in re.split(r"[\s_-]+", sem_acentos.lower()) if p)


def nomes_de_canal(canais: list[dict]) -> dict[str, str]:
    """{forma escrita: id} a partir do id, do nome, de cada parte do nome
    separada por barra, e dos sinonimos de config/porquinho.yml.

    Uma forma que desse dois canais e um erro da configuracao, e falha ao
    ler: escolher um dos dois seria adivinhar o canal, e a KB pagou isso
    com oito linhas erradas em oito.
    """
    mapa: dict[str, str] = {}
    for canal in canais:
        formas = [canal["id"], canal["nome"], *str(canal["nome"]).split("/"), *(canal.get("sinonimos") or [])]
        for forma in formas:
            chave = _simples(str(forma))
            if chave in mapa and mapa[chave] != canal["id"]:
                raise ValueError(f"'{forma}' daria dois canais: {mapa[chave]} e {canal['id']}")
            mapa[chave] = canal["id"]
    return mapa


def codigo_social(prova: str, dominio: str) -> tuple[str, str] | None:
    """(tipo, codigo) se a prova for uma publicacao da rede social."""
    partes = urlsplit(prova)
    anfitriao = partes.netloc.lower()
    if not dominio or (anfitriao != dominio and not anfitriao.endswith("." + dominio)):
        return None
    encontrado = CAMINHO_SOCIAL.match(partes.path)
    return (encontrado.group(1), encontrado.group(2)) if encontrado else None


def limpar_prova(prova: str, dominio: str) -> str:
    """A ligacao como fica no ficheiro.

    Uma publicacao da rede social fica na forma curta, sem parametros nem
    conta no caminho, que e a forma das linhas que ja estao na curadoria.
    Qualquer outro endereco fica como veio: num site de noticias um
    parametro pode ser parte do endereco, e cortar seria adivinhar.
    """
    prova = (prova or "").strip()
    social = codigo_social(prova, dominio)
    if social:
        tipo, codigo = social
        return f"https://www.{dominio}/{tipo}/{codigo}/"
    return prova


def hora_da_publicacao(codigo: str) -> datetime:
    numero = 0
    for letra in codigo:
        numero = numero * 64 + ALFABETO.index(letra)
    milissegundos = (numero >> 23) + EPOCA_MS
    return datetime.fromtimestamp(milissegundos / 1000, timezone.utc).astimezone(LISBOA)


def chave_de_prova(prova: str, dominio: str) -> str:
    """O que identifica uma prova para efeito de repeticao.

    Uma publicacao da rede social pelo codigo; tudo o resto pela mesma
    normalizacao que o coletor usa nos vetos, para que o formulario e o
    coletor nunca discordem sobre se duas ligacoes sao a mesma.
    """
    social = codigo_social(prova, dominio)
    return f"social:{social[1]}" if social else url_normalizado(prova)


def provas_publicadas(dados: dict) -> list[dict]:
    """Uma linha por transmissao publicada, com a entrevista a que pertence."""
    linhas = []
    for entrevista in dados.get("entrevistas", []):
        for t in entrevista.get("transmissoes") or [entrevista]:
            linhas.append({"data": str(t.get("data", "")), "canal": str(t.get("canal", "")),
                           "prova": str(t.get("prova_url", "")), "entrevista": str(entrevista.get("id", ""))})
    return linhas


def separar_entrada(texto: str, nomes: dict[str, str]) -> tuple[dict, list[str]]:
    """({data, canal, prova}, erros) de uma entrada escrita a mao."""
    erros: list[str] = []
    ligacoes = [l.rstrip(",.") for l in LIGACAO.findall(texto)]
    resto = LIGACAO.sub(" ", texto)
    pedacos = [p for p in re.split(r"[\s,]+", resto) if p]
    datas = [normalizar_data(p) for p in pedacos]
    data = next((d for d in datas if d), "")
    canal_escrito = " ".join(p for p, d in zip(pedacos, datas) if not d)
    if len(ligacoes) != 1:
        erros.append("falta a ligacao" if not ligacoes else
                     f"{len(ligacoes)} ligacoes numa entrada so; separar as entradas com ';'")
    if not data:
        erros.append("falta a data, ou nao existe: escrever AAAA-MM-DD, AAAAMMDD ou DD-MM-AAAA")
    elif sum(1 for d in datas if d) > 1:
        erros.append("mais do que uma data numa entrada so; separar as entradas com ';'")
    canal = nomes.get(_simples(canal_escrito), "")
    if not canal:
        erros.append(f"canal '{canal_escrito}' nao reconhecido; usar um de: {', '.join(sorted(set(nomes.values())))}")
    return {"data": data, "canal": canal, "prova": ligacoes[0] if len(ligacoes) == 1 else ""}, erros


def verificar(data: str, canal: str, prova: str, *, curadoria: dict, publicadas: list[dict],
              tema: dict, dominio: str, hoje: date) -> tuple[list[str], list[str]]:
    erros: list[str] = []
    avisos: list[str] = []
    chave = chave_de_prova(prova, dominio)
    for linha in curadoria.get("entrevistas") or []:
        if chave_de_prova(str(linha.get("prova", "")), dominio) == chave:
            erros.append(f"esta prova ja esta na curadoria, em {linha.get('data')} {linha.get('canal')}")
    for linha in curadoria.get("remover") or []:
        if chave_de_prova(str(linha.get("prova", "")), dominio) == chave:
            erros.append(f"esta prova foi vetada: {linha.get('motivo')}")
    for p in publicadas:
        if chave_de_prova(p["prova"], dominio) == chave:
            erros.append(f"esta prova ja esta publicada, em {p['data']} {p['canal']}")
    if erros:
        # Uma prova repetida nao se escreve: daria uma linha a fingir que e
        # outra entrevista, ou um veto contornado sem ninguem o decidir.
        return sorted(set(erros)), avisos

    social = codigo_social(prova, dominio)
    if social:
        publicada = hora_da_publicacao(social[1])
        if publicada.date().isoformat() != data:
            avisos.append(f"a publicacao e de {publicada:%Y-%m-%d %H:%M} (Lisboa) e a entrevista ficou a {data}; "
                          "certo se for um anuncio de vespera ou um video do dia seguinte")
    dia = date.fromisoformat(data)
    vizinhos = {(str(linha.get("data")), str(linha.get("canal"))) for linha in curadoria.get("entrevistas") or []}
    vizinhos |= {(p["data"], p["canal"]) for p in publicadas}
    for d, c in sorted(vizinhos):
        if c == canal and d and abs((date.fromisoformat(d) - dia).days) <= 1:
            # Pode ser legitimo (duas entrevistas em dias seguidos, ou de
            # manha e a noite), e pode ser a mesma entrevista contada duas
            # vezes. So quem leu as duas paginas sabe.
            avisos.append(f"o mesmo canal ja tem uma entrevista a {d}; confirmar que nao e a mesma")
    if data < str(tema.get("desde", "")):
        erros.append(f"data anterior a {tema.get('desde')}, o inicio do registo")
    elif data < str(tema.get("visivel_desde", "")):
        avisos.append(f"data anterior a {tema.get('visivel_desde')}: fica guardada mas o site nao a mostra")
    if dia > hoje:
        avisos.append("data no futuro: conta como anuncio, e se a entrevista cair a linha tem de ser vetada")
    return erros, avisos


def bloco_yaml(data: str, canal: str, prova: str, dominio: str, hoje: date) -> str:
    linhas = [f"  # Formulario `adicionar`, {hoje.isoformat()}: canal e dia lidos por quem o preencheu."]
    social = codigo_social(prova, dominio)
    if social:
        linhas.append(f"  # Publicacao de {hora_da_publicacao(social[1]):%Y-%m-%d %H:%M} de Lisboa, pelo identificador.")
    linhas += [f"  - data: {data}", f"    canal: {canal}", f"    prova: {prova}"]
    return "\n".join(linhas) + "\n"


def acrescentar(texto: str, blocos: list[str], fim_da_lista: str = FIM_DA_LISTA) -> str:
    """O ficheiro com os blocos no fim de uma lista, que acaba onde a
    seguinte comeca.

    Tudo o resto fica byte a byte: o ficheiro e o registo de porque cada
    linha esta ali, e e lido por quem contesta um numero.
    """
    if texto.count(fim_da_lista) != 1:
        raise ValueError(f"config/curadoria.yml mudou de forma: nao encontro um so '{fim_da_lista.strip()}'")
    antes, depois = texto.split(fim_da_lista)
    return antes.rstrip("\n") + "\n\n" + "\n".join(blocos) + fim_da_lista + depois


def ler_yaml(caminho: Path) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def separar_entradas(texto: str) -> list[str]:
    return [e.strip() for e in re.split(r"[;\n]+", texto or "") if e.strip()]


def correr(entradas: str, *, curadoria: Path = CURADORIA, porquinho: Path = PORQUINHO,
           pistas: Path = PISTAS, publicadas: Path = PUBLICADAS, hoje: date | None = None) -> tuple[int, str]:
    """Devolve (codigo de saida, relatorio). So escreve se nenhuma entrada falhar."""
    hoje = hoje or datetime.now(LISBOA).date()
    config = ler_yaml(porquinho)
    dominio = str(ler_yaml(pistas).get("dominio", ""))
    nomes = nomes_de_canal(config.get("canais", []))
    dados = json.loads(publicadas.read_text(encoding="utf-8")) if publicadas.exists() else {}
    ja_publicadas = provas_publicadas(dados)
    texto = curadoria.read_text(encoding="utf-8")
    atual = yaml.safe_load(texto) or {}

    lista = separar_entradas(entradas)
    if not lista:
        return 1, "NADA FOI ESCRITO: nenhuma entrada; escrever o dia, o canal e a ligacao"
    relatorio: list[str] = []
    blocos: list[str] = []
    falhadas = 0
    vistas: dict[str, int] = {}
    for numero, escrita in enumerate(lista, start=1):
        linha, erros = separar_entrada(escrita, nomes)
        avisos: list[str] = []
        if not erros:
            linha["prova"] = limpar_prova(linha["prova"], dominio)
            erros, avisos = verificar(linha["data"], linha["canal"], linha["prova"], curadoria=atual,
                                      publicadas=ja_publicadas, tema=config.get("tema", {}), dominio=dominio, hoje=hoje)
            chave = chave_de_prova(linha["prova"], dominio)
            if chave in vistas:
                erros.append(f"a mesma prova esta na entrada {vistas[chave]} deste lote")
            vistas.setdefault(chave, numero)
        relatorio.append(f"{numero}. {linha['data'] or '?'} {linha['canal'] or '?'} {linha['prova'] or escrita}")
        relatorio += [f"   AVISO: {a}" for a in avisos]
        relatorio += [f"   RECUSADA: {e}" for e in erros]
        if erros:
            falhadas += 1
        else:
            blocos.append(bloco_yaml(linha["data"], linha["canal"], linha["prova"], dominio, hoje))

    if falhadas:
        relatorio.append(f"NADA FOI ESCRITO: {falhadas} de {len(lista)} entradas recusadas; "
                         "corrigir e voltar a enviar o lote inteiro")
        return 1, "\n".join(relatorio)

    novo = acrescentar(texto, blocos)
    # Confirma que o ficheiro continua legivel e que entraram as linhas
    # pedidas e so essas, antes de gravar. Um ficheiro partido aqui so dava
    # erro na publicacao, longe de quem preencheu o formulario.
    antes = len(atual.get("entrevistas") or [])
    depois = len((yaml.safe_load(novo) or {}).get("entrevistas") or [])
    if depois != antes + len(blocos):
        raise ValueError(f"esperava {antes + len(blocos)} linhas na curadoria e ficam {depois}")
    curadoria.write_text(novo, encoding="utf-8", newline="\n")
    relatorio.append(f"ACRESCENTADAS {len(blocos)}: a curadoria passa de {antes} para {depois} linhas")
    return 0, "\n".join(relatorio)


def escrever_resumo(relatorio: str) -> None:
    """O resumo da corrida e o que se ve no telemovel sem abrir o log."""
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8", newline="\n") as f:
            f.write("```\n" + relatorio + "\n```\n")


def main(argv: list[str]) -> int:
    analisador = argparse.ArgumentParser(description="Acrescentar entrevistas a curadoria.")
    analisador.add_argument("--entradas", required=True,
                            help="dia, canal e ligacao por entrada; varias entradas separadas por ';'")
    args = analisador.parse_args(argv)
    codigo, relatorio = correr(args.entradas)
    print(relatorio, flush=True)
    escrever_resumo(relatorio)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
