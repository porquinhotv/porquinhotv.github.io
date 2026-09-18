"""Sonda de hipoteses. Corre a pedido, nao escreve dados do site.

    python -m ferramentas.sondar
    python -m ferramentas.sondar --grupo "Motores de busca alternativos"

Le config/sondagem.yml e, para cada URL candidato, regista o que se
consegue saber sem adivinhar: se responde, com que codigo, que tamanho
tem o HTML servido, se os termos aparecem nele, e quantas ligacoes uteis
se conseguem colher. Escreve sondagem/SONDAGEM.md.

Existe porque as duas perguntas que faltavam nao se respondem por
raciocinio. Qual e o parametro de paginacao de um site, e se um motor de
busca responde a uma maquina de datacenter, sao factos sobre servidores
que so se sabem perguntando. Uma hipotese que devolva 200 e zero
ligacoes e tao inutil como uma que devolva 403, e o relatorio mostra as
duas coisas para que a leitura nao se engane com o codigo de resposta.

Nada do que esta aqui e configuracao de recolha. O que passar na
sondagem e depois escrito a mao em config/fontes.yml, com os olhos
postos no relatorio.

Duas coisas que a sonda conta para alem das ligacoes, porque ler so as
ligacoes ja enganou: os enderecos que uma resposta declara sem os ligar
(`<loc>` de um mapa de sitio, ou uma linha por endereco numa resposta em
texto, que e como o indice de um arquivo da web responde), e uma amostra
do texto, para que um `robots.txt` ou um indice se leiam no relatorio
sem outro pedido. Um mapa de 374 KB contou zero a 2026-09-09 porque a
funcao que colhe ligacoes procura `href`.

Uma corrida com `--grupo` funde o resultado no ficheiro que ja existe
em vez de o substituir: o registo das sondagens de 8 de setembro, 632
linhas, foi apagado por uma corrida de um grupo so (commit 98fcc31).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import yaml

from recolha import extracao
from recolha.modelos import RAIZ, carregar_config, normalizar
from recolha.rede import ErroDeRede, obter_texto

FICHEIRO = RAIZ / "config" / "sondagem.yml"
PASTA = RAIZ / "sondagem"
PAUSA_S = 1.5
# Enderecos declarados num mapa de sitio ou num indice de mapas.
LOC = re.compile(r"<loc>\s*(https?://[^<\s]+)\s*</loc>", re.I)
# Tamanho da amostra de texto guardada por hipotese. Basta para um
# `robots.txt` inteiro ou para as primeiras linhas de um indice.
AMOSTRA_CHARS = 400
# Abaixo deste numero de caracteres, o texto visivel pode nao dizer o que
# veio. Medido a 2026-09-18: o pedido de `robots.txt` a uma rede social
# devolveu 630137 bytes de marcacao cujo texto visivel era uma palavra,
# nove caracteres. A leitura do relatorio seria "o ficheiro esta vazio"
# quando o que aconteceu foi nao ter vindo ficheiro nenhum. A condicao
# completa esta em `_ilegivel`: este limiar sozinho apanhava tambem um
# `robots.txt` curto que se le perfeitamente, e a suite travou-o.
TEXTO_ILEGIVEL = 200


def carregar(caminho: Path = FICHEIRO) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def enderecos_declarados(resposta: str) -> list[str]:
    """Enderecos que a resposta declara sem os ligar por `href`.

    Um mapa de sitio escreve `<loc>`; o indice de um arquivo da web
    responde em texto, um endereco por linha. `extracao.ligacoes` procura
    `href` e conta zero nas duas, e foi assim que um mapa de 374 KB se leu
    como falha. Numa resposta com marcacao mas sem `<loc>` nao ha nada a
    declarar: as ligacoes de HTML contam-se noutro sitio.
    """
    achados = LOC.findall(resposta)
    if achados:
        return achados
    if "<" in resposta.lstrip()[:200]:
        return []
    return [linha.strip() for linha in resposta.splitlines() if "http" in linha]


def analisar(html: str, url: str, termos: list[str], dominio_alvo: str, dominios_interesse: list[str] | None = None, padrao: str = "") -> dict:
    """O que esta hipotese devolveu, em numeros comparaveis entre si."""
    corpo = extracao.texto_visivel(html)
    palheiro = normalizar(corpo)
    presentes = [t for t in termos if normalizar(t) and normalizar(t) in palheiro]
    enderecos = enderecos_declarados(html)

    # O padrao do grupo aperta a colheita quando a heuristica por omissao
    # nao serve: ela exige um hifen no ultimo segmento do caminho, e ha
    # sites cujos enderecos de artigo nao tem nenhum. Sem isto, uma
    # hipotese cheia de resultados contava zero pelo motivo errado, que e
    # o mesmo defeito ja pago quando a pagina da Google se leu como zero
    # resultados por procurar a palavra errada.
    if dominio_alvo:
        ligacoes = extracao.ligacoes(html, url, dominio_alvo, padrao)
    else:
        # Num motor de busca interessa saber para quantos dominios
        # distintos ele aponta: e a medida de ter mesmo devolvido
        # resultados em vez de uma pagina de aviso.
        ligacoes = []
        for dominio in dominios_interesse or []:
            ligacoes += extracao.ligacoes(html, url, dominio, padrao)

    return {
        "responde": True,
        "bytes_html": len(html),
        "bytes_texto": len(corpo),
        "termos_presentes": presentes,
        "ligacoes": len(ligacoes),
        "exemplos": ligacoes[:3],
        "enderecos": len(enderecos),
        "exemplos_enderecos": enderecos[:3],
        "amostra": corpo[:AMOSTRA_CHARS],
        "amostra_bruta": html[:AMOSTRA_CHARS] if _ilegivel(html, corpo) else "",
    }


def _ilegivel(html: str, corpo: str) -> bool:
    """A resposta nao se le pelo texto visivel, e o bruto e que diz o que veio.

    Duas condicoes, e as duas sao precisas. Texto curto sozinho nao basta:
    um `robots.txt` de tres linhas tem 68 caracteres e le-se inteiro. O que
    denuncia o caso real de 2026-09-18 e a desproporcao, nove caracteres de
    texto para 630137 de corpo, ou seja a remocao de marcacao deitou fora
    tudo. Um desafio de motor de busca, 305 caracteres que se leem bem, nao
    entra por nenhuma das duas.
    """
    return len(corpo) < TEXTO_ILEGIVEL and len(html) > 10 * max(len(corpo), 1)


def nomes_dos_grupos(config: dict) -> list[str]:
    return [g.get("nome", "") for g in config.get("grupos") or []]


def correr(config: dict, obter=obter_texto, so_grupo: str | None = None, dormir=time.sleep) -> dict:
    tema = carregar_config()
    termo = config.get("termo", "")
    termos = [termo] + [t for t in tema.sujeito.detetar]

    resultado = {
        "verificado_em": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "termo": termo,
        "grupos": [],
    }
    for grupo in config.get("grupos") or []:
        if so_grupo and grupo.get("nome") != so_grupo:
            continue
        linha = {"nome": grupo.get("nome", ""), "dominio_alvo": grupo.get("dominio_alvo", ""), "mostrar": bool(grupo.get("mostrar")), "hipoteses": []}
        # Um indice que varre um dominio inteiro demora mais a responder
        # do que uma pagina. Sem isto, a leitura de cinco consultas a
        # 2026-09-10 foi "nao responde" quando era "nao responde em 30s".
        extra = {"limite_s": grupo["tempo_limite_s"]} if grupo.get("tempo_limite_s") else {}
        for modelo in grupo.get("hipoteses") or []:
            url = modelo.replace("{termo}", urllib.parse.quote_plus(termo))
            print(f"  a sondar {url}", flush=True)
            try:
                html = obter(url, **extra)
            except ErroDeRede as exc:
                linha["hipoteses"].append({"url": url, "responde": False, "erro": str(exc)})
                print(f"    nao responde: {exc}", flush=True)
            else:
                dados = analisar(html, url, termos, linha["dominio_alvo"], config.get("dominios_de_interesse") or [], grupo.get("padrao", ""))
                linha["hipoteses"].append({"url": url, **dados})
                print(f"    {dados['bytes_texto']} bytes de texto, {dados['ligacoes']} ligacoes, {dados['enderecos']} enderecos declarados, termos {dados['termos_presentes']}", flush=True)
                if grupo.get("mostrar"):
                    print(f"    | {dados['amostra']}", flush=True)
                    if dados.get("amostra_bruta"):
                        print(f"    | bruto: {dados['amostra_bruta']}", flush=True)
            dormir(PAUSA_S)
        resultado["grupos"].append(linha)
    return resultado


def relatorio(resultado: dict) -> str:
    linhas = [
        "# Sondagem de hipoteses",
        "",
        f"Verificado em {resultado['verificado_em']}. Consulta: {resultado['termo']}.",
        "",
        "Uma hipotese so serve se responder E trouxer ligacoes. Responder com 200",
        "e zero ligacoes e uma pagina de aviso, nao um resultado.",
        "",
    ]
    for grupo in resultado["grupos"]:
        linhas += [f"## {grupo['nome']}", ""]
        if grupo.get("verificado_em"):
            linhas += [f"Verificado em {grupo['verificado_em']}.", ""]
        linhas += ["| Hipotese | Responde | Texto | Ligacoes | Enderecos | Termos |", "|---|---|---|---|---|---|"]
        for h in grupo["hipoteses"]:
            if not h.get("responde"):
                linhas.append(f"| {h['url']} | nao ({h.get('erro', '')[:60]}) | | | | |")
            else:
                linhas.append(
                    f"| {h['url']} | sim | {h['bytes_texto']} | {h['ligacoes']} | {h.get('enderecos', 0)} | {', '.join(h['termos_presentes']) or 'nenhum'} |"
                )
        linhas.append("")
        for h in grupo["hipoteses"]:
            for exemplo in (h.get("exemplos") or []) + (h.get("exemplos_enderecos") or []):
                linhas.append(f"- {h['url']} -> {exemplo}")
        if grupo.get("mostrar"):
            for h in grupo["hipoteses"]:
                if h.get("amostra"):
                    linhas.append(f"- {h['url']}: `{h['amostra'][:AMOSTRA_CHARS]}`")
                if h.get("amostra_bruta"):
                    linhas.append(f"- {h['url']}, bruto: `{h['amostra_bruta'][:AMOSTRA_CHARS]}`")
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


def fundir(anterior: dict | None, novo: dict) -> dict:
    """O resultado de hoje por cima do que ja estava, grupo a grupo.

    Um grupo com o mesmo nome e substituido; os outros ficam como
    estavam, com a sua data. Sem isto, uma corrida com `--grupo` apagava
    o registo das sondagens anteriores (632 linhas a 2026-09-09), e saber
    o que foi tentado faz parte do metodo.
    """
    if not anterior or not anterior.get("grupos"):
        return novo
    novos = {g["nome"]: g for g in novo.get("grupos") or []}
    grupos = []
    for grupo in anterior["grupos"]:
        if grupo["nome"] in novos:
            grupos.append({**novos.pop(grupo["nome"]), "verificado_em": novo["verificado_em"]})
        else:
            grupos.append({**grupo, "verificado_em": grupo.get("verificado_em", anterior.get("verificado_em", ""))})
    grupos += [{**g, "verificado_em": novo["verificado_em"]} for g in novos.values()]
    return {**novo, "grupos": grupos}


def escrever(resultado: dict, pasta: Path = PASTA) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    ficheiro = pasta / "sondagem.json"
    anterior = None
    if ficheiro.exists():
        try:
            anterior = json.loads(ficheiro.read_text(encoding="utf-8"))
        except ValueError:
            anterior = None
    resultado = fundir(anterior, resultado)
    ficheiro.write_text(json.dumps(resultado, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (pasta / "SONDAGEM.md").write_text(relatorio(resultado), encoding="utf-8", newline="\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Sondagem de hipoteses")
    parser.add_argument("--grupo", help="so este grupo")
    args = parser.parse_args(argv)
    config = carregar()
    if args.grupo and args.grupo not in nomes_dos_grupos(config):
        # Uma corrida que nao encontra o grupo nao pode acabar a dizer
        # "escrito em ...". A 2026-09-10 sete corridas seguidas correram
        # com nomes que a configuracao daquele momento nao tinha, cada
        # uma nao pediu nada a lado nenhum, e a ultima linha do ecra
        # dizia o mesmo que diz uma corrida boa. O resultado foi um
        # relatorio vazio publicado por cima do que la estava.
        print(f"nao ha grupo chamado {args.grupo!r}. Os que existem:", flush=True)
        for nome in nomes_dos_grupos(config):
            print(f"  {nome}", flush=True)
        return 2
    resultado = correr(config, so_grupo=args.grupo)
    if not resultado["grupos"]:
        print("nenhum grupo correu: nada foi escrito", flush=True)
        return 2
    escrever(resultado)
    print(f"escrito em {PASTA}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
