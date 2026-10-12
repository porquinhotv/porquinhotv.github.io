"""Persistencia. Append-only.

Um registo que ja existe nunca perde a sua `primeira_vez`. Os ficheiros
sao escritos com chaves ordenadas e indentacao fixa para que o diff do git
seja legivel: o historico do repositorio e a trilha de auditoria.

Consequencia a nao esquecer: uma linha que deixe de ser produzida nao
desaparece sozinha. Corrigir uma regra que muda classificacoes obriga a
repor docs/dados e a recolher de novo, na mesma operacao.

O que este ficheiro guarda e a **transmissao**, e o que publica e a
**entrevista**. A dobragem de uma na outra e feita em
recolha/entrevistas.py, a publicacao: mudar o agrupamento nao mexe no que
esta guardado e por isso nao exige `repor`.
"""

from __future__ import annotations

import json
from pathlib import Path

from .modelos import DADOS_DIR, Transmissao

ENTREVISTAS = DADOS_DIR / "entrevistas.json"
QUARENTENA = DADOS_DIR / "quarentena.json"
# Subiu para 2 a 2026-09-11, quando o ficheiro deixou de ser uma lista de
# emissoes e passou a ser uma lista de entrevistas com as suas
# transmissoes dentro. Um site antigo a ler um ficheiro novo veria uma
# lista vazia; com o esquema a mudar, ve que mudou.
ESQUEMA = 2


def carregar(caminho: Path = ENTREVISTAS) -> dict[str, dict]:
    """As transmissoes guardadas, por id.

    O ficheiro publicado e uma lista de entrevistas, mas o que o append-only
    protege e a transmissao: e ela que tem prova propria e `primeira_vez`.
    Achata-se na leitura e volta a dobrar-se na escrita, e assim o
    agrupamento nunca entra neste modulo.
    """
    if not caminho.exists():
        return {}
    conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    linhas = {}
    for entrevista in conteudo.get("entrevistas", []):
        for linha in entrevista.get("transmissoes", []):
            linhas[linha["id"]] = linha
    return linhas


def fundir(existentes: dict[str, dict], novas: list[Transmissao]) -> tuple[dict, int, int]:
    adicionadas = 0
    atualizadas = 0
    for transmissao in novas:
        linha = transmissao.como_dict()
        atual = existentes.get(linha["id"])
        if atual is None:
            existentes[linha["id"]] = linha
            adicionadas += 1
            continue
        linha["primeira_vez"] = atual.get("primeira_vez", linha["primeira_vez"])
        if linha != atual:
            existentes[linha["id"]] = linha
            atualizadas += 1
    return existentes, adicionadas, atualizadas


def _escrever(caminho: Path, conteudo: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" para que o ficheiro seja identico seja qual for o
    # sistema que correu a recolha: em CRLF, o diff do git mostraria o
    # ficheiro inteiro alterado e a trilha de auditoria deixaria de servir.
    caminho.write_text(
        json.dumps(conteudo, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def guardar(entrevistas: list[dict], caminho: Path = ENTREVISTAS) -> None:
    """As entrevistas, ja dobradas por recolha/entrevistas.py.

    `total` e o numero que o site publica em grande: entrevistas
    exclusivas, nunca transmissoes. Quem abrir o ficheiro ve as duas
    coisas, mas so uma delas e a contagem.
    """
    _escrever(caminho, {"esquema": ESQUEMA, "total": len(entrevistas), "entrevistas": entrevistas})


def carregar_quarentena(caminho: Path = QUARENTENA) -> list[dict]:
    if not caminho.exists():
        return []
    return json.loads(caminho.read_text(encoding="utf-8")).get("entradas", [])


def fundir_quarentena(anteriores: list[dict], novas: list[dict], so_fonte: str) -> list[dict]:
    """A quarentena de uma corrida que leu uma fonte so.

    A corrida inteira substitui a fotografia, e essa regra fica. Mas uma
    corrida so de uma fonte nao viu as outras, e substituir apagava o
    diagnostico delas sem que ninguem o decidisse: medido a 2026-10-12, a
    corrida so da curadoria punha a quarentena publicada de 66 entradas a
    zero. Fica o que as outras fontes deixaram, e o desta fonte e
    substituido pelo desta corrida.

    Os vetos escritos a mao reaparecem em todas as corridas com a fonte da
    linha vetada, que nao e a desta: o que se repete por inteiro entra uma
    vez.
    """
    fundidas: list[dict] = []
    vistas: set[str] = set()
    for entrada in [e for e in anteriores if e.get("fonte") != so_fonte] + novas:
        chave = json.dumps(entrada, ensure_ascii=False, sort_keys=True)
        if chave not in vistas:
            vistas.add(chave)
            fundidas.append(entrada)
    return fundidas


def guardar_quarentena(entradas: list[dict], caminho: Path = QUARENTENA) -> None:
    """Rejeitados desta corrida, com motivo. Substituido a cada corrida:
    e uma fotografia, nao um historico."""
    ordenadas = sorted(entradas, key=lambda e: (e["fonte"], e.get("publicado_em", ""), e["titulo"]))
    _escrever(caminho, {"esquema": ESQUEMA, "total": len(ordenadas), "entradas": ordenadas})
