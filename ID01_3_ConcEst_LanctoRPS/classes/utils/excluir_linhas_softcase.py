"""Exclusão de linhas no portal (MudBlazor) via Selenium.

Fluxo por linha: clicar em "Ações" > clicar em "Excluir" > aguardar a
linha sair da tabela. A linha é localizada pelo "Numero" (e não pela
posição), pois a tabela é recarregada após cada exclusão e os índices
mudam.

Uso com ``remover_linhas_duplicadas``::

    from remover_linhas_duplicadas import remover_linhas_duplicadas
    from excluir_linha_portal import criar_excluir_linha

    excluir = criar_excluir_linha(driver)
    resultado = remover_linhas_duplicadas(driver.page_source, excluir=excluir)

Dependência: ``pip install selenium``
"""

from __future__ import annotations

import logging
from typing import Callable

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from ID01_3_ConcEst_LanctoRPS.classes.utils.remover_linhas_duplicadas import COL_NUMERO, Linha

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 15

# Linha localizada pelo Numero (coluna com data-label="Numero").
XPATH_LINHA = (
    "//table[contains(@class,'mud-table-root')]/tbody/tr"
    "[td[@data-label='Numero'][normalize-space()='{numero}']]"
)
# Botão "Ações" fica na primeira coluna (td[1]) da linha.
XPATH_BOTAO_ACOES = XPATH_LINHA + "/td[1]//button"

# O id do popover é dinâmico (popovercontent-<guid>), por isso o
# seletor usa starts-with. Primeiro tenta pelo texto "Excluir".
XPATH_ITEM_EXCLUIR = (
    "//div[starts-with(@id,'popovercontent-') "
    "and contains(@class,'mud-popover-open')]"
    "//*[contains(@class,'mud-menu-item')]"
    "[contains(normalize-space(),'Excluir')]"
)
# Alternativa: segundo item do menu (…/div/div[2]).
XPATH_ITEM_EXCLUIR_POSICAO = (
    "//div[starts-with(@id,'popovercontent-')]/div/div[2]"
)

# Diálogo "Confirmar exclusão": o id (_<guid>) é dinâmico, então o
# diálogo é localizado por role="dialog" + título, e o botão "Confirmar"
# fica na área de ações (mud-dialog-actions).
XPATH_BOTAO_CONFIRMAR = (
    "//div[@role='dialog'][contains(@class,'mud-dialog')]"
    "[.//h6[contains(normalize-space(),'Confirmar exclusão')]]"
    "//div[contains(@class,'mud-dialog-actions')]"
    "//button[contains(normalize-space(),'Confirmar')]"
)
# Alternativa: segundo botão da área de ações (…/button[2]).
XPATH_CONFIRMAR_POSICAO = (
    "//div[@role='dialog'][contains(@class,'mud-dialog')]"
    "//div[contains(@class,'mud-dialog-actions')]/button[2]"
)


def excluir_linha_por_numero(
    driver: WebDriver,
    numero: str,
    timeout: int = TIMEOUT_PADRAO,
    xpath_confirmacao: str | None = XPATH_BOTAO_CONFIRMAR,
) -> None:
    """Exclui no portal a linha cujo "Numero" é ``numero``.

    Args:
        driver: WebDriver já posicionado na tela, com o filtro da
            empresa aplicado.
        numero: Valor da coluna "Numero" da linha a excluir.
        timeout: Tempo máximo (segundos) de cada espera.
        xpath_confirmacao: XPath do botão "Confirmar" do diálogo que o
            portal abre após clicar em Excluir. Padrão: botão "Confirmar"
            do diálogo "Confirmar exclusão". ``None`` = sem diálogo.

    Raises:
        ValueError: Se ``numero`` tiver caracteres inesperados.
        TimeoutException: Se a linha, o menu ou o botão não aparecerem,
            ou se a linha continuar na tabela após a exclusão.
    """
    if not numero.isalnum():
        raise ValueError(f"Numero inválido para exclusão: {numero!r}")

    espera = WebDriverWait(driver, timeout)
    xpath_linha = XPATH_LINHA.format(numero=numero)

    logger.info("Excluindo linha Numero=%s", numero)
    botao_acoes = espera.until(
        EC.element_to_be_clickable(
            (By.XPATH, XPATH_BOTAO_ACOES.format(numero=numero))
        )
    )
    botao_acoes.click()

    try:
        item = espera.until(
            EC.element_to_be_clickable((By.XPATH, XPATH_ITEM_EXCLUIR))
        )
    except TimeoutException:
        logger.warning("'Excluir' não achado pelo texto; usando posição.")
        item = espera.until(
            EC.element_to_be_clickable(
                (By.XPATH, XPATH_ITEM_EXCLUIR_POSICAO)
            )
        )
    item.click()

    if xpath_confirmacao is not None:
        try:
            botao_confirmar = espera.until(
                EC.element_to_be_clickable((By.XPATH, xpath_confirmacao))
            )
        except TimeoutException:
            logger.warning("'Confirmar' não achado; usando posição.")
            botao_confirmar = espera.until(
                EC.element_to_be_clickable(
                    (By.XPATH, XPATH_CONFIRMAR_POSICAO)
                )
            )
        botao_confirmar.click()

    espera.until(
        EC.invisibility_of_element_located((By.XPATH, xpath_linha))
    )
    logger.info("Linha Numero=%s excluída.", numero)


def criar_excluir_linha(
    driver: WebDriver,
    timeout: int = TIMEOUT_PADRAO,
    xpath_confirmacao: str | None = XPATH_BOTAO_CONFIRMAR,
) -> Callable[[Linha], None]:
    """Cria a função ``excluir`` esperada por ``remover_linhas_duplicadas``.

    Args:
        driver: WebDriver da sessão do portal.
        timeout: Tempo máximo (segundos) de cada espera.
        xpath_confirmacao: Ver ``excluir_linha_por_numero``.

    Returns:
        Função que recebe a linha duplicada (dict) e a exclui no portal.
    """

    def excluir(linha: Linha) -> None:
        excluir_linha_por_numero(
            driver,
            str(linha[COL_NUMERO]),
            timeout=timeout,
            xpath_confirmacao=xpath_confirmacao,
        )

    return excluir