"""Atualização de RPS Consolidado para forma de pagamento 'TAG'.

Segue o mesmo fluxo do DÉBITO: filtra a forma de pagamento na tela de
pesquisa e atualiza os dados do RPS existente (não cria lançamento novo).

A diferença é que a forma de pagamento considera o nome do adquirente
(ex.: Veloe, SemParar, ConectCar, Greenpass). O texto exato vem da tabela
tbl_FormaDePagamento do banco de dados.
"""

import logging
import re
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path
from time import sleep

from selenium.webdriver.remote.webdriver import WebDriver

from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import (
    atualizar_dados,
    editar_rps_consolidado,
    filtrar_forma_pagto,
)

logger = logging.getLogger(__name__)

PREFIXO_FORMA_PAGTO = "TAG"
CAMINHO_BANCO_DADOS = Path(
    r"C:\Armazenamento\ID01_2_ConcEst_TratarDados\Banco Dados\banco_dados.db"
)
SQL_FORMAS_PAGTO = (
    'SELECT DISTINCT "Forma de Pagamento" FROM tbl_FormaDePagamento '
    'WHERE "Forma de Pagamento" IS NOT NULL'
)


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acentos, espaços e pontuação (ex.: 'Sem Parar' ->
    'semparar'). Usado só para comparar nomes de adquirente."""
    sem_acento = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", sem_acento.casefold())


def obter_forma_pagto_tag(
    adquirente: str,
    caminho_db: Path = CAMINHO_BANCO_DADOS,
) -> str:
    """Retorna o texto da forma de pagamento TAG para o adquirente.

    Consulta "Forma de Pagamento" em tbl_FormaDePagamento e escolhe, entre
    as formas que começam com 'TAG' e contêm o nome do adquirente
    (ignorando caixa, acentos e espaços), a que for exatamente
    'TAG <adquirente>'; se não houver, a mais curta.

    Se o banco não puder ser lido ou nada for encontrado, retorna
    'TAG <adquirente>'.
    """
    padrao = f"{PREFIXO_FORMA_PAGTO} {adquirente}".strip()
    padrao_norm = _normalizar(padrao)
    adquirente_norm = _normalizar(adquirente)
    prefixo_norm = _normalizar(PREFIXO_FORMA_PAGTO)

    try:
        # Somente leitura: esta consulta nunca altera o banco.
        with closing(
            sqlite3.connect(f"{caminho_db.as_uri()}?mode=ro", uri=True)
        ) as conexao:
            linhas = conexao.execute(SQL_FORMAS_PAGTO).fetchall()
    except sqlite3.Error:
        logger.exception(
            "Falha ao ler tbl_FormaDePagamento em '%s'; usando '%s'.",
            caminho_db,
            padrao,
        )
        return padrao

    formas = []
    for (forma,) in linhas:
        texto = str(forma).strip()
        norm = _normalizar(texto)
        if (
            norm.startswith(prefixo_norm)
            and adquirente_norm in norm
            and texto not in formas
        ):
            formas.append(texto)

    if not formas:
        logger.warning("Nenhuma forma '%s' na tabela; usando o padrão.", padrao)
        return padrao

    formas.sort(key=lambda f: (_normalizar(f) != padrao_norm, len(f)))
    if len(formas) > 1:
        logger.info("Formas TAG encontradas %s; usando '%s'.", formas, formas[0])
    return formas[0]


def atualizar_tag(
    driver: WebDriver,
    adquirente: str,
    valor: str,
    valor_taxa: str,
) -> None:
    """Filtra a forma 'TAG <adquirente>' e atualiza os dados do RPS.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados, com a
            empresa e as datas pesquisadas.
        adquirente: Nome do adquirente (ex.: 'Veloe').
        valor: Valor do RPS.
        valor_taxa: Valor do campo Total taxa.

    Raises:
        ValueError: se o adquirente estiver vazio.
    """
    adquirente_texto = str(adquirente).strip() if adquirente else ""
    if not adquirente_texto:
        raise ValueError(
            "Adquirente vazio: não é possível montar a forma de pagamento."
        )

    forma_pagamento = obter_forma_pagto_tag(adquirente_texto)
    logger.info("Atualizando RPS TAG: forma '%s'", forma_pagamento)

    #Ajusta a forma de pagamento somente para casos TAG
    if adquirente in ["ConectCar","Greenpass","SemParar","Veloe"]:
        forma_pagamento = forma_pagamento.replace("TAG", "").strip()
        forma_pagamento = "Sem Parar" if forma_pagamento == 'SemParar' else forma_pagamento

    # Filtrar forma pagamento
    filtrar_forma_pagto(
        driver=driver,
        forma_pgto=forma_pagamento,
        bandeira=None,
    )
    # Editar dados
    atualizar_dados(driver=driver)
    sleep(1)  # mesmo intervalo usado no fluxo dos demais
    editar_rps_consolidado(
        driver=driver,
        valor=valor,
        total_taxa=valor_taxa,
    )