"""Acrescentar uma entrevista a curadoria, num passo so.

    python -m ferramentas.adicionar --data 2026-10-05 --canal now --prova https://...

E o que o workflow `adicionar` corre quando o formulario e preenchido.
Pedido do autor a 2026-10-12: dar o dia, o canal e a ligacao, e ver a
entrevista no site, sem patch, sem PowerShell e sem disparar a recolha
inteira. A ferramenta faz as verificacoes que antes se faziam a mao nesta
conversa, escreve a linha em `config/curadoria.yml` e nada mais: publicar
e o passo seguinte do workflow.

**O que esta ferramenta nao decide.** O dia e o canal sao afirmacoes de
quem leu a publicacao, como em todo o `curadoria.yml`, e e isso que da a
esta via a isencao da prova de formato e das rondas. A data nunca e
deduzida da ligacao: o identificador de uma publicacao diz quando ela foi
publicada, nao quando a entrevista passou, e um "amanha as 21h" ficaria
no dia errado. A KB pagou isto com quatro datas erradas em vinte e quatro
(licao vigesima sexta). A data deduzida serve so para avisar.

**Recusa** (nada e escrito): canal fora da tabela, data que nao existe,
prova que nao e um endereco, prova ja na curadoria, ja publicada ou ja
vetada. **Avisa** (escreve na mesma): a publicacao e de outro dia, o
mesmo canal ja tem uma entrevista a um dia de distancia, a data esta fora
do ambito visivel ou no futuro. Um aviso nao trava porque os tres casos
existem de verdade: um anuncio na vespera, duas entrevistas em dias
seguidos, um registo antigo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import yaml

from recolha.extracao import data_para_iso
from recolha.modelos import RAIZ

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

# A lista onde se acrescenta acaba onde a seguinte comeca. Escreve-se no
# texto, e nao por yaml.dump, porque um dump reescrevia o ficheiro inteiro
# e apagava todos os comentarios, que sao o registo de porque cada linha
# esta ali.
FIM_DA_LISTA = "\nremover:\n"

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


def codigo_social(prova: str, dominio: str) -> tuple[str, str] | None:
    """(tipo, codigo) se a prova for uma publicacao da rede social."""
    partes = urlsplit(prova)
    anfitriao = partes.netloc.lower()
    if anfitriao != dominio and not anfitriao.endswith("." + dominio):
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


def _chave_de_prova(prova: str, dominio: str) -> str:
    """O que identifica uma prova para efeito de repeticao."""
    social = codigo_social(prova, dominio)
    return f"social:{social[1]}" if social else prova.strip().rstrip("/")


def provas_publicadas(dados: dict) -> list[tuple[str, str, str]]:
    """(data, canal, prova) de todas as transmissoes publicadas."""
    linhas = []
    for entrevista in dados.get("entrevistas", []):
        for t in entrevista.get("transmissoes") or [entrevista]:
            linhas.append((str(t.get("data", "")), str(t.get("canal", "")), str(t.get("prova_url", ""))))
    return linhas


def verificar(data: str, canal: str, prova: str, *, curadoria: dict, canais: list[str], publicadas: list[tuple[str, str, str]],
              tema: dict, dominio: str, hoje: date) -> tuple[list[str], list[str]]:
    erros: list[str] = []
    avisos: list[str] = []
    if canal not in canais:
        erros.append(f"canal '{canal}' nao existe; os canais sao: {', '.join(canais)}")
    if not data:
        erros.append("data invalida: escrever AAAA-MM-DD, AAAAMMDD ou DD-MM-AAAA")
    if not prova.startswith(("https://", "http://")):
        erros.append("a prova tem de ser um endereco que comece por https://")
    if erros:
        return erros, avisos

    chave = _chave_de_prova(prova, dominio)
    for linha in curadoria.get("entrevistas") or []:
        if _chave_de_prova(str(linha.get("prova", "")), dominio) == chave:
            erros.append(f"esta prova ja esta na curadoria, em {linha.get('data')} {linha.get('canal')}")
    for linha in curadoria.get("remover") or []:
        if _chave_de_prova(str(linha.get("prova", "")), dominio) == chave:
            erros.append(f"esta prova foi vetada: {linha.get('motivo')}")
    for d, c, p in publicadas:
        if _chave_de_prova(p, dominio) == chave:
            erros.append(f"esta prova ja esta publicada, em {d} {c}")
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
    vizinhos |= {(d, c) for d, c, _ in publicadas}
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
    linhas = [f"  # Acrescentada a {hoje.isoformat()} pelo formulario `adicionar`. O canal",
              "  # e o dia sao a leitura de quem o preencheu."]
    social = codigo_social(prova, dominio)
    if social:
        linhas.append(f"  # Publicacao de {hora_da_publicacao(social[1]):%Y-%m-%d %H:%M} de Lisboa, pelo identificador.")
    linhas += [f"  - data: {data}", f"    canal: {canal}", f"    prova: {prova}"]
    return "\n".join(linhas) + "\n"


def acrescentar(texto: str, bloco: str) -> str:
    """O ficheiro com o bloco no fim da lista `entrevistas`.

    Tudo o resto fica byte a byte: o ficheiro e o registo de porque cada
    linha esta ali, e e lido por quem contesta um numero.
    """
    if texto.count(FIM_DA_LISTA) != 1:
        raise ValueError("config/curadoria.yml mudou de forma: nao encontro um so inicio da lista `remover`")
    antes, depois = texto.split(FIM_DA_LISTA)
    return antes.rstrip("\n") + "\n\n" + bloco + FIM_DA_LISTA + depois


def _ler_yaml(caminho: Path) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def correr(data: str, canal: str, prova: str, *, curadoria: Path = CURADORIA, porquinho: Path = PORQUINHO,
           pistas: Path = PISTAS, publicadas: Path = PUBLICADAS, hoje: date | None = None) -> tuple[int, str]:
    """Devolve (codigo de saida, relatorio). So escreve se nao houver erros."""
    hoje = hoje or datetime.now(LISBOA).date()
    config = _ler_yaml(porquinho)
    dominio = str(_ler_yaml(pistas).get("dominio", ""))
    canais = [str(c["id"]) for c in config.get("canais", [])]
    dados = json.loads(publicadas.read_text(encoding="utf-8")) if publicadas.exists() else {}
    texto = curadoria.read_text(encoding="utf-8")
    data_iso = normalizar_data(data)
    canal = (canal or "").strip()
    prova = limpar_prova(prova, dominio)

    erros, avisos = verificar(data_iso, canal, prova, curadoria=yaml.safe_load(texto) or {}, canais=canais,
                              publicadas=provas_publicadas(dados), tema=config.get("tema", {}), dominio=dominio, hoje=hoje)
    relatorio = [f"data: {data_iso or data}", f"canal: {canal}", f"prova: {prova}"]
    relatorio += [f"AVISO: {a}" for a in avisos]
    if erros:
        relatorio += [f"RECUSADA: {e}" for e in erros]
        relatorio.append("nada foi escrito")
        return 1, "\n".join(relatorio)

    novo = acrescentar(texto, bloco_yaml(data_iso, canal, prova, dominio, hoje))
    # Confirma que o ficheiro continua legivel e que entrou uma linha e so
    # uma, antes de gravar. Um ficheiro partido aqui so dava erro na
    # publicacao, longe de quem preencheu o formulario.
    antes = len((yaml.safe_load(texto) or {}).get("entrevistas") or [])
    depois = len((yaml.safe_load(novo) or {}).get("entrevistas") or [])
    if depois != antes + 1:
        raise ValueError(f"esperava {antes + 1} linhas na curadoria e ficam {depois}")
    curadoria.write_text(novo, encoding="utf-8", newline="\n")
    relatorio.append(f"ACRESCENTADA: a curadoria passa de {antes} para {depois} linhas")
    return 0, "\n".join(relatorio)


def main(argv: list[str]) -> int:
    analisador = argparse.ArgumentParser(description="Acrescentar uma entrevista a curadoria.")
    analisador.add_argument("--data", required=True, help="dia em que a entrevista passou: AAAA-MM-DD, AAAAMMDD ou DD-MM-AAAA")
    analisador.add_argument("--canal", required=True, help="id do canal, como em config/porquinho.yml")
    analisador.add_argument("--prova", required=True, help="ligacao publica que prova a entrevista")
    args = analisador.parse_args(argv)
    codigo, relatorio = correr(args.data, args.canal, args.prova)
    print(relatorio, flush=True)
    # O resumo da corrida e o que se ve no telemovel sem abrir o log.
    resumo = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumo:
        with open(resumo, "a", encoding="utf-8", newline="\n") as f:
            f.write("```\n" + relatorio + "\n```\n")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
