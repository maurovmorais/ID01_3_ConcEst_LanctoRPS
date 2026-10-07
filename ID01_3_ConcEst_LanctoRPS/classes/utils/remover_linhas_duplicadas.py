"""Remoção de linhas duplicadas na tabela de pagamentos (MudBlazor).

Critério de duplicidade (somente estas duas colunas):
    * "Forma de pagamento": similaridade >= 90% após normalização
      (caixa, acentos e símbolos como "?" de encoding quebrado).
    * "Dias Comp.": valor idêntico.

De cada grupo de duplicadas, a primeira linha (ordem da tabela) é mantida
e as demais são marcadas para exclusão.

Dependência: ``pip install beautifulsoup4``
"""

from __future__ import annotations

import logging
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LIMIAR_SIMILARIDADE = 0.90
COL_FORMA_PAGAMENTO = "Forma de pagamento"
COL_DIAS_COMP = "Dias Comp."
COL_NUMERO = "Numero"

Linha = dict[str, str | int]


@dataclass
class ResultadoDuplicidade:
    """Resultado da análise de duplicidade.

    Attributes:
        mantidas: Uma linha por grupo (a que segue no fluxo).
        removidas: Linhas duplicadas a excluir.
        grupos: Todos os grupos com mais de uma linha (mantida primeiro).
    """

    mantidas: list[Linha] = field(default_factory=list)
    removidas: list[Linha] = field(default_factory=list)
    grupos: list[list[Linha]] = field(default_factory=list)


def normalizar_texto(texto: str) -> str:
    """Normaliza o texto para comparação.

    Minúsculas, sem acentos e sem símbolos (inclui o "?" de encoding
    quebrado, ex.: "D?bito"). Espaços repetidos viram um só.
    """
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    somente_alfanum = re.sub(r"[^a-z0-9 ]", "", sem_acento.lower())
    return re.sub(r"\s+", " ", somente_alfanum).strip()


def calcular_similaridade(texto_a: str, texto_b: str) -> float:
    """Retorna a similaridade (0 a 1) entre dois textos já normalizados."""
    return SequenceMatcher(None, texto_a, texto_b).ratio()


def _normalizar_dias(valor: str) -> int | str:
    """Converte Dias Comp. para int; se não for número, mantém o texto."""
    try:
        return int(valor.strip())
    except ValueError:
        return valor.strip()


def extrair_linhas(html: str) -> list[Linha]:
    """Extrai as linhas da tabela MudBlazor a partir do HTML.

    Args:
        html: HTML da página ou do elemento da tabela
            (ex.: ``driver.page_source``).

    Returns:
        Lista de dicionários {cabeçalho: texto}, com a chave extra
        ``posicao`` (índice da linha no ``tbody``).

    Raises:
        ValueError: Se a tabela ou as colunas obrigatórias não existirem.
    """
    soup = BeautifulSoup(html, "html.parser")
    tabela = soup.select_one("table.mud-table-root")
    if tabela is None:
        raise ValueError("Tabela 'mud-table-root' não encontrada no HTML.")

    cabecalhos = [th.get_text(strip=True) for th in tabela.select("thead th")]
    ausentes = {COL_FORMA_PAGAMENTO, COL_DIAS_COMP} - set(cabecalhos)
    if ausentes:
        raise ValueError(f"Colunas obrigatórias ausentes: {sorted(ausentes)}")

    linhas: list[Linha] = []
    for posicao, tr in enumerate(tabela.select("tbody tr")):
        celulas = [
            td.get_text(" ", strip=True)
            for td in tr.find_all("td", recursive=False)
        ]
        if len(celulas) != len(cabecalhos):
            logger.warning("Linha %s ignorada: colunas divergentes.", posicao)
            continue
        linha: Linha = dict(zip(cabecalhos, celulas))
        linha["posicao"] = posicao
        linhas.append(linha)

    logger.info("%s linhas extraídas do HTML.", len(linhas))
    return linhas


def remover_linhas_duplicadas(
    html: str,
    limiar: float = LIMIAR_SIMILARIDADE,
    excluir: Callable[[Linha], None] | None = None,
) -> ResultadoDuplicidade:
    """Identifica e remove linhas duplicadas, mantendo só uma por grupo.

    Duplicada = mesmo "Dias Comp." e "Forma de pagamento" com similaridade
    >= ``limiar``. A primeira linha do grupo (ordem da tabela) é mantida.

    Args:
        html: HTML contendo a tabela.
        limiar: Similaridade mínima (0 a 1) da forma de pagamento.
        excluir: Função chamada para cada linha duplicada (ex.: clicar em
            Ações > Excluir no portal, localizando a linha pelo "Numero").
            Se ``None``, nada é excluído (apenas simulação).

    Returns:
        ResultadoDuplicidade com as linhas mantidas e as removidas.
    """
    linhas = extrair_linhas(html)
    grupos: list[dict] = []

    for linha in linhas:
        dias = _normalizar_dias(str(linha[COL_DIAS_COMP]))
        forma = normalizar_texto(str(linha[COL_FORMA_PAGAMENTO]))

        grupo_encontrado = None
        for grupo in grupos:
            if grupo["dias"] != dias:
                continue
            if calcular_similaridade(grupo["forma"], forma) >= limiar:
                grupo_encontrado = grupo
                break

        if grupo_encontrado is None:
            grupos.append({"dias": dias, "forma": forma, "linhas": [linha]})
        else:
            grupo_encontrado["linhas"].append(linha)

    resultado = ResultadoDuplicidade()
    for grupo in grupos:
        mantida, *duplicadas = grupo["linhas"]
        resultado.mantidas.append(mantida)
        if not duplicadas:
            continue
        resultado.removidas.extend(duplicadas)
        resultado.grupos.append(grupo["linhas"])
        logger.info(
            "Mantida %s; duplicadas: %s",
            mantida.get(COL_NUMERO),
            [d.get(COL_NUMERO) for d in duplicadas],
        )

    if excluir is not None:
        for linha in resultado.removidas:
            excluir(linha)

    return resultado


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    caminho = Path(sys.argv[1])
    res = remover_linhas_duplicadas(caminho.read_text(encoding="utf-8"))
    print(f"Mantidas: {len(res.mantidas)} | Removidas: {len(res.removidas)}")
    for dup in res.removidas:
        print(
            f"  remover Numero={dup.get(COL_NUMERO)} | "
            f"{dup[COL_FORMA_PAGAMENTO]} | Dias Comp.={dup[COL_DIAS_COMP]}"
        )