"""Pistas de publicacoes em rede social, para revisao a mao.

    python -m ferramentas.pistas --consultar   # junta pistas novas
    python -m ferramentas.pistas --rever       # abre uma a uma e pergunta
    python -m ferramentas.pistas --exportar    # escreve o YAML para colar
    python -m ferramentas.pistas --resumo      # em que pe esta o trabalho

Isto nao e uma fonte e nunca escreve em `docs/dados`. O motor de busca e
um indice para chegar a publicacao, a publicacao e a prova publica, e a
data e o canal sao afirmacoes de quem abriu a pagina, como tudo o que
entra por `config/curadoria.yml`.

**Porque a revisao e a mao, e nao pode deixar de ser.** Medido a
2026-09-18 sobre 51 publicacoes: uma trazia data no resumo do motor e 22
traziam marcas de tempo relativas. Uma legenda que diz "hoje as 20h30"
nao data nada sem se saber o dia em que foi publicada, e esse dia so
esta dentro da publicacao, que nao e legivel por maquina. Automatizar
este passo seria inventar datas, e o projeto prefere ficar curto.

O ficheiro de trabalho vive fora do repositorio, e a leitura funde
sempre: uma decisao ja escrita nunca se perde porque a consulta mudou.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import webbrowser
from datetime import date
from pathlib import Path

import yaml

from recolha.modelos import RAIZ
from recolha.rede import obter_texto

CONFIG = RAIZ / "config" / "pistas.yml"
# Fora do repositorio, uma pasta acima: tem caminhos locais e o ritmo de
# trabalho de uma pessoa, e o `.gitignore` ja trava o descuido.
TRABALHO = RAIZ.parent / "pistas-trabalho.json"

# A forma do texto de um resultado, nao a marcacao da pagina. Le-se sobre
# o texto visivel de proposito: um seletor do HTML de um motor parte na
# primeira remodelacao e passa a devolver zero em silencio, e esta e a
# regra do projeto. Se a forma do texto mudar, o sinal e visivel, porque
# a consola avisa quando ha enderecos e nao ha pistas.
#
# Grupos: conta (opcional), tipo, codigo, e o texto que vem a seguir ate
# ao proximo resultado.
RESULTADO = re.compile(
    r"(?:^|\s)([a-z0-9_.]+\.com)\s*›\s*(?:([a-z0-9_.]+)\s*›\s*)?(p|reel|tv)\s*›\s*([A-Za-z0-9_-]{6,})\s+(.*?)(?=\s[a-z0-9_.]+\.com\s*›|\Z)",
    re.DOTALL,
)
# O convite a criar conta que o servico devolve a quem nao tem sessao.
# Aparece colado a legenda e nao diz nada sobre a entrevista.
RUIDO = re.compile(r"(Create an account|Crie uma conta|Bem-vindo/a|Inicia sessão|\d+[KM]?\s*(followers|seguidores|siguiendo|following)).*", re.I | re.DOTALL)
DATA_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATA_COMPACTA = re.compile(r"^\d{8}$")


def normalizar_data(escrito: str) -> str:
    """A data em ISO, aceite em duas escritas, ou vazio se nao for data.

    Aceitam-se `20250512` e `2025-05-12`. A forma compacta existe porque
    e o que se escreve depressa quando se estao a rever dezenas de
    publicacoes seguidas, e os dois hifens sao duas teclas de ceder em
    cada linha. O ficheiro de curadoria continua a receber so ISO.

    A data e validada pelo calendario, nao pela forma: `20250230` tem
    oito digitos e nao existe, e uma data assim so daria erro muito mais
    tarde, na colheita, longe de quem a escreveu.
    """
    escrito = escrito.strip()
    if DATA_COMPACTA.match(escrito):
        escrito = f"{escrito[:4]}-{escrito[4:6]}-{escrito[6:]}"
    if not DATA_ISO.match(escrito):
        return ""
    try:
        date.fromisoformat(escrito)
    except ValueError:
        return ""
    return escrito


def carregar(caminho: Path = CONFIG) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def ler_trabalho(caminho: Path = TRABALHO) -> dict:
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def gravar_trabalho(pistas: dict, caminho: Path = TRABALHO) -> None:
    caminho.write_text(json.dumps(pistas, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def limpar(legenda: str) -> str:
    """A legenda sem o convite a criar conta e sem as contagens de perfil."""
    return " ".join(RUIDO.sub("", legenda).split()).strip(" .…")


def extrair(texto: str) -> list[dict]:
    """Pistas lidas do texto visivel de uma pagina de resultados.

    Devolve uma por publicacao, com o endereco montado a partir do caminho
    que o proprio resultado mostra. Sem o codigo nao ha pista: e o codigo
    que identifica a publicacao e que evita registar duas vezes a mesma.
    """
    pistas: list[dict] = []
    vistos: set[str] = set()
    for dominio, conta, tipo, codigo, resto in RESULTADO.findall(texto):
        if codigo in vistos:
            continue
        vistos.add(codigo)
        caminho = f"{conta}/{tipo}/{codigo}" if conta else f"{tipo}/{codigo}"
        pistas.append({
            "codigo": codigo,
            "conta": conta or "",
            "url": f"https://www.{dominio}/{caminho}/",
            "legenda": limpar(resto),
        })
    return pistas


def sugerir_canal(pista: dict, config: dict) -> str:
    """O canal que a conta ou a legenda sugerem, ou vazio.

    Primeiro a conta, porque uma publicacao na conta de um canal e desse
    canal; depois a legenda, do termo mais especifico para o mais
    generico, senao uma legenda que nomeia o canal de noticias ficava
    atribuida ao generalista com o mesmo nome.
    """
    por_conta = (config.get("contas") or {}).get(pista.get("conta") or "")
    if por_conta:
        return por_conta
    legenda = (pista.get("legenda") or "").lower()
    for entrada in config.get("termos_de_canal") or []:
        for termo in entrada.get("termos") or []:
            if termo.lower() in legenda:
                return entrada["canal"]
    return ""


def marcas(pista: dict, config: dict) -> list[str]:
    """Marcas de tempo relativas presentes na legenda, para quem revê ver.

    Nao servem para calcular data nenhuma. Servem para avisar que o dia da
    entrevista pode nao ser o dia da publicacao.
    """
    legenda = (pista.get("legenda") or "").lower()
    return [m for m in config.get("marcas_de_tempo") or [] if m.lower() in legenda]


def consultar(config: dict, trabalho: dict) -> tuple[int, int, int]:
    """Corre as consultas e funde as pistas novas. Nada se grava por cima."""
    novas = falhas = repetidas = 0
    for url in config.get("consultas") or []:
        print(f"  a consultar {url}", flush=True)
        try:
            texto_pagina = obter_texto(url)
        except Exception as erro:  # noqa: BLE001 - a razao da falha interessa a quem le
            print(f"    nao responde: {erro}", flush=True)
            falhas += 1
            continue
        from ferramentas import sondar

        visivel = sondar.extracao.texto_visivel(texto_pagina)
        achadas = extrair(visivel)
        enderecos = len(sondar.extracao.ligacoes(texto_pagina, url, config["dominio"], "/(p|reel|tv)/[A-Za-z0-9_-]{6,}"))
        if enderecos and not achadas:
            print("    ATENCAO: a pagina tem enderecos e nao deu pistas nenhumas.", flush=True)
            print("    A forma do texto do motor mudou. Nao usar este resultado sem corrigir a leitura.", flush=True)
        for pista in achadas:
            if pista["codigo"] in trabalho:
                repetidas += 1
                continue
            trabalho[pista["codigo"]] = pista | {"decisao": ""}
            novas += 1
        print(f"    {len(achadas)} pistas na pagina", flush=True)
    return novas, repetidas, falhas


def por_decidir(trabalho: dict) -> list[dict]:
    return [p for p in trabalho.values() if not p.get("decisao")]


def entrevistas_publicadas() -> set[tuple[str, str]]:
    """Pares (data, canal) ja publicados, para avisar de repeticao."""
    caminho = RAIZ / "docs" / "dados" / "entrevistas.json"
    if not caminho.exists():
        return set()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {(e.get("data", ""), e.get("canal", "")) for e in dados.get("entrevistas", [])}


def rever(config: dict, trabalho: dict, abrir=webbrowser.open, ler=input) -> int:
    """Uma pista de cada vez: mostra, abre no browser, pergunta.

    O gesto minimo e escrever a data que se ve na publicacao. O canal vem
    sugerido e confirma-se com Enter, porque a sugestao acertou nas contas
    de canal e a legenda quase sempre nomeia o canal. Enter vazio salta
    sem decidir, e a pista fica para a proxima.
    """
    pendentes = por_decidir(trabalho)
    if not pendentes:
        print("nao ha pistas por decidir. Correr com --consultar para juntar mais.")
        return 0
    publicadas = entrevistas_publicadas()
    decididas = 0
    for indice, pista in enumerate(pendentes, start=1):
        canal = sugerir_canal(pista, config)
        relativas = marcas(pista, config)
        print()
        print(f"[{indice}/{len(pendentes)}] {pista['url']}")
        print(f"    {pista['legenda'] or '(sem legenda no resultado)'}")
        if canal:
            print(f"    canal sugerido: {canal}")
        if relativas:
            print(f"    atencao, a legenda diz {', '.join(relativas)}: confirmar se o dia da entrevista e o dia da publicacao")
        abrir(pista["url"])
        resposta = ler("    data 20250512 [canal], Enter=saltar, n=nao conta, q=sair: ").strip()
        if resposta.lower() == "q":
            break
        if not resposta:
            continue
        if resposta.lower() == "n":
            pista["decisao"] = "nao"
            decididas += 1
            continue
        partes = resposta.split()
        data = normalizar_data(partes[0])
        if not data:
            print("    data ignorada: escrever 20250512 ou 2025-05-12")
            continue
        if len(partes) > 1:
            canal = partes[1]
        if not canal:
            print("    sem canal sugerido e sem canal escrito: a pista fica por decidir")
            continue
        pista["decisao"] = "sim"
        pista["data"] = data
        pista["canal"] = canal
        decididas += 1
        if (data, canal) in publicadas:
            print("    ja existe uma entrevista publicada nesse dia nesse canal: provavelmente a mesma")
    return decididas


def exportar(trabalho: dict) -> str:
    """As pistas aceites na forma exata de config/curadoria.yml."""
    aceites = sorted((p for p in trabalho.values() if p.get("decisao") == "sim"), key=lambda p: (p.get("data", ""), p.get("canal", "")))
    if not aceites:
        return "# nenhuma pista aceite ate agora\n"
    linhas = ["# Colar em config/curadoria.yml, na lista `entrevistas`.", "# A prova e a publicacao, que qualquer pessoa abre."]
    for p in aceites:
        linhas.append(f"  - data: {p['data']}")
        linhas.append(f"    canal: {p['canal']}")
        linhas.append(f"    prova: {p['url']}")
    return "\n".join(linhas) + "\n"


def resumo(trabalho: dict) -> str:
    total = len(trabalho)
    sim = sum(1 for p in trabalho.values() if p.get("decisao") == "sim")
    nao = sum(1 for p in trabalho.values() if p.get("decisao") == "nao")
    return f"{total} pistas: {sim} aceites, {nao} recusadas, {total - sim - nao} por decidir"


def main(argv: list[str]) -> int:
    analisador = argparse.ArgumentParser(description="Pistas de publicacoes em rede social, para revisao a mao.")
    analisador.add_argument("--consultar", action="store_true", help="corre as consultas e junta pistas novas")
    analisador.add_argument("--rever", action="store_true", help="abre cada pista por decidir e pergunta")
    analisador.add_argument("--exportar", action="store_true", help="escreve o YAML das pistas aceites")
    analisador.add_argument("--resumo", action="store_true", help="em que pe esta o trabalho")
    args = analisador.parse_args(argv)
    if not any((args.consultar, args.rever, args.exportar, args.resumo)):
        analisador.print_help()
        return 1

    config = carregar()
    trabalho = ler_trabalho()
    if args.consultar:
        novas, repetidas, falhas = consultar(config, trabalho)
        gravar_trabalho(trabalho)
        print(f"\n{novas} pistas novas, {repetidas} ja conhecidas, {falhas} consultas sem resposta")
        print(f"ficheiro de trabalho: {TRABALHO}")
    if args.rever:
        decididas = rever(config, trabalho)
        gravar_trabalho(trabalho)
        print(f"\n{decididas} decididas nesta sessao")
    if args.exportar:
        print(exportar(trabalho))
    if args.resumo or args.consultar or args.rever:
        print(resumo(trabalho))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
