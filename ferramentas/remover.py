"""Retirar do site uma ou varias provas, com o motivo escrito.

    python -m ferramentas.remover --provas "https://...; https://..." --motivo "..."

E o que o workflow `remover` corre. Pedido do autor a 2026-10-12: retirar
entrevistas por formulario, uma a uma ou em lote.

**Retirar e vetar, nao apagar.** Cada ligacao entra na lista `remover` de
`config/curadoria.yml`, que e o mecanismo que ja existia: o coletor tira
a transmissao do que esta publicado e poe-a na quarentena com o motivo,
visivel na pagina de Fontes. Nada desaparece em silencio, e desfazer e
apagar a linha do veto. Apagar a linha da fonte, em vez de vetar, nao
servia: o dataset e append-only, e uma linha que a fonte deixa de
produzir fica publicada.

**Tudo ou nada**, como no `adicionar`. Uma ligacao que nao esta no site e
recusada, e com ela o lote: um erro de copia num veto que nao veta nada
deixava quem preencheu convencido de que a linha saiu.

**O que se retira e uma prova, nao uma entrevista.** Uma entrevista que
passou em dois canais tem duas provas; retirar uma deixa-a contada pela
outra, e o relatorio diz qual. E a regra da tabela `mesma_entrevista`, e
nao se contorna aqui.

**De quem e a prova.** `--pessoa` escolhe, para o lote inteiro, o sujeito
(por omissao) ou uma das pessoas de `config/comparacao.yml`. Pedido do
autor a 2026-11-07: o mesmo que o `adicionar`, para retirar. Os vetos de
outra pessoa vao para a lista `remover` de `config/comparacao.yml`, e o
ficheiro inteiro passa pela validacao do gerador antes de gravar. A
linha da entrevista fica no ficheiro e deixa de contar: e a mesma regra
de vetar e nao apagar. Ali cada linha tem uma prova so, por isso retirar
a prova retira a entrevista, e o relatorio diz isso. Uma ligacao que e
de outra pessoa, ou de uma linha que nao conta (por verificar, fora do
ambito), e recusada: o veto nao retirava nada do que a pagina mostra.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

from ferramentas import comparacao as comp
from ferramentas.adicionar import (
    COMPARACAO, CURADORIA, LIGACAO, LISBOA, PISTAS, PORQUINHO, PUBLICADAS, acrescentar, chave_de_prova,
    escolher_pessoa, escrever_resumo, ler_yaml, limpar_prova, provas_publicadas,
)

FIM_DA_LISTA = "\nmesma_entrevista:"
# Em config/comparacao.yml a lista `remover` acaba onde comeca a das
# entrevistas, que tem de ficar a ultima para o `adicionar`.
FIM_DOS_VETOS_DA_COMPARACAO = "\nentrevistas:"


def bloco_yaml(prova: str, motivo: str, hoje: date) -> str:
    # O motivo vai entre aspas simples, dobradas por dentro: um motivo
    # escrito a mao pode trazer dois pontos ou um cardinal, e partia o YAML.
    seguro = motivo.replace("'", "''")
    return (f"  # Formulario `remover`, {hoje.isoformat()}.\n"
            f"  - prova: {prova}\n"
            f"    motivo: '{seguro}'\n")


def correr(provas: str, motivo: str, pessoa: str = "", *, curadoria: Path = CURADORIA, pistas: Path = PISTAS,
           publicadas: Path = PUBLICADAS, comparacao: Path = COMPARACAO, porquinho: Path = PORQUINHO,
           hoje: date | None = None) -> tuple[int, str]:
    """Devolve (codigo de saida, relatorio). So escreve se nenhuma ligacao falhar."""
    hoje = hoje or datetime.now(LISBOA).date()
    config = ler_yaml(porquinho)
    escolhida, erro = escolher_pessoa(pessoa, config.get("sujeito") or {}, ler_yaml(comparacao).get("pessoas") or [])
    if erro:
        return 1, f"NADA FOI ESCRITO: {erro}"
    dominio = str(ler_yaml(pistas).get("dominio", ""))
    dados = json.loads(publicadas.read_text(encoding="utf-8")) if publicadas.exists() else {}
    no_site = provas_publicadas(dados)
    texto = curadoria.read_text(encoding="utf-8")
    atual = yaml.safe_load(texto) or {}
    motivo = " ".join((motivo or "").split())

    ligacoes = [l.rstrip(",.;") for l in LIGACAO.findall(provas or "")]
    if not ligacoes:
        return 1, "NADA FOI ESCRITO: nenhuma ligacao"
    if not motivo:
        # A regra do ficheiro: uma remocao sem motivo e indistinguivel de um
        # engano, e daqui a seis meses ninguem sabe qual das duas foi.
        return 1, "NADA FOI ESCRITO: falta o motivo"
    if escolhida is not None:
        return correr_outra(ligacoes, motivo, escolhida, config=config, dominio=dominio, no_site=no_site,
                            curadoria=atual, comparacao=comparacao, hoje=hoje)
    das_outras = {chave_de_prova(str(e.get("prova", "")), dominio)
                  for e in ler_yaml(comparacao).get("entrevistas") or []}

    vetadas = {chave_de_prova(str(l.get("prova", "")), dominio) for l in atual.get("remover") or []}
    na_curadoria = [{"data": str(l.get("data")), "canal": str(l.get("canal")), "prova": str(l.get("prova")), "entrevista": ""}
                    for l in atual.get("entrevistas") or []]
    pedidas = {chave_de_prova(limpar_prova(l, dominio), dominio) for l in ligacoes}
    relatorio: list[str] = [f"Pessoa: {(config.get('sujeito') or {}).get('nome', '')} (config/curadoria.yml)"]
    blocos: list[str] = []
    falhadas = 0
    vistas: set[str] = set()
    for numero, escrita in enumerate(ligacoes, start=1):
        chave = chave_de_prova(limpar_prova(escrita, dominio), dominio)
        encontradas = [p for p in no_site + na_curadoria if chave_de_prova(p["prova"], dominio) == chave]
        if not encontradas and chave in das_outras:
            relatorio.append(f"{numero}. {escrita}\n   RECUSADA: esta prova e de outra pessoa, na comparacao; "
                             "escolher a pessoa certa no formulario")
            falhadas += 1
            continue
        if chave in vistas:
            relatorio.append(f"{numero}. {escrita}\n   RECUSADA: repetida neste lote")
            falhadas += 1
            continue
        vistas.add(chave)
        if chave in vetadas:
            relatorio.append(f"{numero}. {escrita}\n   RECUSADA: ja estava vetada")
            falhadas += 1
            continue
        if not encontradas:
            relatorio.append(f"{numero}. {escrita}\n   RECUSADA: esta ligacao nao esta no site nem na curadoria")
            falhadas += 1
            continue
        # A forma que o site guarda, para que o veto case com ela pela mesma
        # normalizacao que o coletor usa.
        alvo = encontradas[0]
        relatorio.append(f"{numero}. {alvo['data']} {alvo['canal']} {alvo['prova']}")
        companheiras = [p for p in no_site if alvo["entrevista"] and p["entrevista"] == alvo["entrevista"]
                        and chave_de_prova(p["prova"], dominio) not in pedidas]
        for outra in companheiras:
            relatorio.append(f"   AVISO: a entrevista continua contada pela prova de {outra['canal']}: {outra['prova']}")
        blocos.append(bloco_yaml(alvo["prova"], motivo, hoje))

    if falhadas:
        relatorio.append(f"NADA FOI ESCRITO: {falhadas} de {len(ligacoes)} ligacoes recusadas; "
                         "corrigir e voltar a enviar o lote inteiro")
        return 1, "\n".join(relatorio)

    novo = acrescentar(texto, blocos, FIM_DA_LISTA)
    antes = len(atual.get("remover") or [])
    depois = len((yaml.safe_load(novo) or {}).get("remover") or [])
    if depois != antes + len(blocos):
        raise ValueError(f"esperava {antes + len(blocos)} vetos e ficam {depois}")
    curadoria.write_text(novo, encoding="utf-8", newline="\n")
    relatorio.append(f"RETIRADAS {len(blocos)}: os vetos passam de {antes} para {depois}")
    return 0, "\n".join(relatorio)


def correr_outra(ligacoes: list[str], motivo: str, pessoa: dict, *, config: dict, dominio: str,
                 no_site: list[dict], curadoria: dict, comparacao: Path, hoje: date) -> tuple[int, str]:
    """O mesmo lote, tudo ou nada, para uma pessoa da comparacao."""
    texto = comparacao.read_text(encoding="utf-8")
    atual = yaml.safe_load(texto) or {}
    vetos = atual.get("remover") or []
    vetadas = {chave_de_prova(str(v.get("prova", "")), dominio) for v in vetos}
    do_sujeito = [p["prova"] for p in no_site]
    do_sujeito += [str(l.get("prova", "")) for l in curadoria.get("entrevistas") or []]
    do_sujeito = {chave_de_prova(x, dominio) for x in do_sujeito}
    relatorio = [f"Pessoa: {pessoa.get('nome')} (config/comparacao.yml)"]
    blocos: list[str] = []
    falhadas = 0
    vistas: set[str] = set()
    for numero, escrita in enumerate(ligacoes, start=1):
        chave = chave_de_prova(limpar_prova(escrita, dominio), dominio)
        linhas = [e for e in atual.get("entrevistas") or [] if chave_de_prova(str(e.get("prova", "")), dominio) == chave]
        motivo_recusa = ""
        if chave in vistas:
            motivo_recusa = "repetida neste lote"
        elif chave in vetadas:
            motivo_recusa = "ja estava vetada"
        elif not linhas:
            motivo_recusa = ("esta prova e do sujeito; escolher a pessoa certa no formulario" if chave in do_sujeito
                             else "esta ligacao nao esta na comparacao")
        elif linhas[0].get("pessoa") != pessoa.get("id"):
            motivo_recusa = f"esta prova e de outra pessoa ({linhas[0].get('pessoa')}); escolher a pessoa certa no formulario"
        elif linhas[0].get("estado") != "confirmada":
            motivo_recusa = f"esta linha nao conta ({linhas[0].get('estado')}); nao ha nada a retirar da pagina"
        vistas.add(chave)
        if motivo_recusa:
            relatorio.append(f"{numero}. {escrita}\n   RECUSADA: {motivo_recusa}")
            falhadas += 1
            continue
        alvo = linhas[0]
        relatorio.append(f"{numero}. {alvo.get('data')} {alvo.get('canal')} {alvo.get('prova')}")
        # Na comparacao cada linha tem uma prova so, mesmo quando passou em
        # dois canais: retirar a prova retira a entrevista.
        relatorio.append(f"   a entrevista sai da contagem de {pessoa.get('nome')}")
        blocos.append(bloco_yaml(str(alvo.get("prova")), motivo, hoje))

    if falhadas:
        relatorio.append(f"NADA FOI ESCRITO: {falhadas} de {len(ligacoes)} ligacoes recusadas; "
                         "corrigir e voltar a enviar o lote inteiro")
        return 1, "\n".join(relatorio)

    novo = acrescentar(texto, blocos, FIM_DOS_VETOS_DA_COMPARACAO)
    lido = yaml.safe_load(novo) or {}
    if len(lido.get("remover") or []) != len(vetos) + len(blocos):
        raise ValueError(f"esperava {len(vetos) + len(blocos)} vetos na comparacao e ficam {len(lido.get('remover') or [])}")
    try:
        # A mesma validacao que o gerador corre dentro do `gerar_seo`.
        visivel = str((config.get("tema") or {}).get("visivel_desde", ""))
        comp.validar(lido, {c["id"] for c in config.get("canais", [])}, date.fromisoformat(visivel))
    except ValueError as e:
        relatorio.append(f"NADA FOI ESCRITO: o ficheiro ficaria invalido para a pagina de Comparacao:\n{e}")
        return 1, "\n".join(relatorio)
    comparacao.write_text(novo, encoding="utf-8", newline="\n")
    relatorio.append(f"RETIRADAS {len(blocos)}: os vetos da comparacao passam de {len(vetos)} para "
                     f"{len(vetos) + len(blocos)}")
    return 0, "\n".join(relatorio)


def main(argv: list[str]) -> int:
    analisador = argparse.ArgumentParser(description="Retirar provas do site, com motivo.")
    analisador.add_argument("--provas", required=True, help="uma ou varias ligacoes, separadas por espacos ou ';'")
    analisador.add_argument("--motivo", required=True, help="porque saem; fica publicado na pagina de Fontes")
    analisador.add_argument("--pessoa", default="",
                            help="de quem sao as provas, nome ou id; por omissao o sujeito")
    args = analisador.parse_args(argv)
    codigo, relatorio = correr(args.provas, args.motivo, args.pessoa)
    print(relatorio, flush=True)
    escrever_resumo(relatorio)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
