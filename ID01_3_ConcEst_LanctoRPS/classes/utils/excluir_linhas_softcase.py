# """Exclusão de linhas no portal (MudBlazor) via Selenium.

# Fluxo por linha: clicar em "Ações" > clicar em "Excluir" > aguardar a
# linha sair da tabela. A linha é localizada pelo "Numero" (e não pela
# posição), pois a tabela é recarregada após cada exclusão e os índices
# mudam.

# Uso com ``remover_linhas_duplicadas``::

#     from remover_linhas_duplicadas import remover_linhas_duplicadas
#     from excluir_linha_portal import criar_excluir_linha

#     excluir = criar_excluir_linha(driver)
#     resultado = remover_linhas_duplicadas(driver.page_source, excluir=excluir)

# Dependência: ``pip install selenium``
# """

# from __future__ import annotations

# import logging
# from typing import Callable

# from selenium.common.exceptions import TimeoutException
# from selenium.webdriver.common.by import By
# from selenium.webdriver.remote.webdriver import WebDriver
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.support.ui import WebDriverWait
# from ID01_3_ConcEst_LanctoRPS.classes.utils.remover_linhas_duplicadas import COL_NUMERO, Linha

# logger = logging.getLogger(__name__)

# TIMEOUT_PADRAO = 15

# # Linha localizada pelo Numero (coluna com data-label="Numero").
# XPATH_LINHA = (
#     "//table[contains(@class,'mud-table-root')]/tbody/tr"
#     "[td[@data-label='Numero'][normalize-space()='{numero}']]"
# )


# # Diálogo "Confirmar exclusão": o id (_<guid>) é dinâmico, então o
# # diálogo é localizado por role="dialog" + título, e o botão "Confirmar"
# # fica na área de ações (mud-dialog-actions).
# XPATH_BOTAO_CONFIRMAR = (
#     "//div[@role='dialog'][contains(@class,'mud-dialog')]"
#     "[.//h6[contains(normalize-space(),'Confirmar exclusão')]]"
#     "//div[contains(@class,'mud-dialog-actions')]"
#     "//button[contains(normalize-space(),'Confirmar')]"
# )
# # Alternativa: segundo botão da área de ações (…/button[2]).
# XPATH_CONFIRMAR_POSICAO = (
#     "//div[@role='dialog'][contains(@class,'mud-dialog')]"
#     "//div[contains(@class,'mud-dialog-actions')]/button[2]"
# )




# # Botão "Ações" da linha cujo td contém exatamente o Numero.
# XPATH_BOTAO_ACOES = (
#     "//table//tbody/tr[td[normalize-space()='{numero}']]"
#     "/td[1]//button[.//span[contains(@class, 'mud-button-label')]"
#     "[contains(normalize-space(), 'Ações')]]"
# )

# # Item "Excluir" (div clicável que contém o <p>), em qualquer popover.
# XPATH_ITEM_EXCLUIR = (
#     "//div[starts-with(@id, 'popovercontent-')]"
#     "//div[@class='mud-list']"
#     "/div[contains(@class, 'mud-list-item')]"
#     "[.//p[normalize-space()='Excluir']]"
# )

# # Fallback por posição: 2º item da lista (Editar=1, Excluir=2).
# XPATH_ITEM_EXCLUIR_POSICAO = (
#     "//div[starts-with(@id, 'popovercontent-')]"
#     "//div[@class='mud-list']"
#     "/div[contains(@class, 'mud-list-item')][2]"
# )






# def excluir_linha_por_numero(
#     driver: WebDriver,
#     numero: str,
#     timeout: int = TIMEOUT_PADRAO,
#     xpath_confirmacao: str | None = XPATH_BOTAO_CONFIRMAR,
# ) -> None:
#     """Exclui no portal a linha cujo "Numero" é ``numero``.

#     Args:
#         driver: WebDriver já posicionado na tela, com o filtro da
#             empresa aplicado.
#         numero: Valor da coluna "Numero" da linha a excluir.
#         timeout: Tempo máximo (segundos) de cada espera.
#         xpath_confirmacao: XPath do botão "Confirmar" do diálogo que o
#             portal abre após clicar em Excluir. Padrão: botão "Confirmar"
#             do diálogo "Confirmar exclusão". ``None`` = sem diálogo.

#     Raises:
#         ValueError: Se ``numero`` tiver caracteres inesperados.
#         TimeoutException: Se a linha, o menu ou o botão não aparecerem,
#             ou se a linha continuar na tabela após a exclusão.
#     """
#     if not numero.isalnum():
#         raise ValueError(f"Numero inválido para exclusão: {numero!r}")

#     espera = WebDriverWait(driver, timeout)
#     xpath_linha = XPATH_LINHA.format(numero=numero)

#     logger.info("Excluindo linha Numero=%s", numero)
#     botao_acoes = espera.until(
#         EC.element_to_be_clickable(
#             (By.XPATH, XPATH_BOTAO_ACOES.format(numero=numero))
#         )
#     )
#     botao_acoes.click()

#     try:
#         item = espera.until(
#             EC.element_to_be_clickable((By.XPATH, XPATH_ITEM_EXCLUIR))
#         )
#     except TimeoutException:
#         logger.warning("'Excluir' não achado pelo texto; usando posição.")
#         item = espera.until(
#             EC.element_to_be_clickable(
#                 (By.XPATH, XPATH_ITEM_EXCLUIR_POSICAO)
#             )
#         )
#     item.click()

#     if xpath_confirmacao is not None:
#         try:
#             botao_confirmar = espera.until(
#                 EC.element_to_be_clickable((By.XPATH, xpath_confirmacao))
#             )
#         except TimeoutException:
#             logger.warning("'Confirmar' não achado; usando posição.")
#             botao_confirmar = espera.until(
#                 EC.element_to_be_clickable(
#                     (By.XPATH, XPATH_CONFIRMAR_POSICAO)
#                 )
#             )
#         botao_confirmar.click()

#     espera.until(
#         EC.invisibility_of_element_located((By.XPATH, xpath_linha))
#     )
#     logger.info("Linha Numero=%s excluída.", numero)


# def criar_excluir_linha(
#     driver: WebDriver,
#     timeout: int = TIMEOUT_PADRAO,
#     xpath_confirmacao: str | None = XPATH_BOTAO_CONFIRMAR,
# ) -> Callable[[Linha], None]:
#     """Cria a função ``excluir`` esperada por ``remover_linhas_duplicadas``.

#     Args:
#         driver: WebDriver da sessão do portal.
#         timeout: Tempo máximo (segundos) de cada espera.
#         xpath_confirmacao: Ver ``excluir_linha_por_numero``.

#     Returns:
#         Função que recebe a linha duplicada (dict) e a exclui no portal.
#     """

#     def excluir(linha: Linha) -> None:
#         excluir_linha_por_numero(
#             driver,
#             str(linha[COL_NUMERO]),
#             timeout=timeout,
#             xpath_confirmacao=xpath_confirmacao,
#         )

#     return excluir

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
from pathlib import Path
from typing import Callable

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
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

# Botão "Ações" da MESMA linha localizada pelo Numero (td[1]).
# Antes o XPath casava o Numero em qualquer td; agora fixa a coluna.
XPATH_BOTAO_ACOES = (
    XPATH_LINHA + "/td[1]//button"
    "[.//span[contains(@class,'mud-button-label')]"
    "[contains(normalize-space(),'Ações')]]"
)

# Item "Excluir" (div clicável que contém o <p>). O id do popover é um
# GUID dinâmico, então só se usa o prefixo. O MudBlazor pode manter vários
# popovers no DOM; o código escolhe o que está visível.
XPATH_ITEM_EXCLUIR = (
    "//div[starts-with(@id, 'popovercontent-')]"
    "//div[@class='mud-list']"
    "/div[contains(@class, 'mud-list-item')]"
    "[.//p[normalize-space()='Excluir']]"
)

# Fallback por posição: 2º item da lista (Editar=1, Excluir=2).
XPATH_ITEM_EXCLUIR_POSICAO = (
    "//div[starts-with(@id, 'popovercontent-')]"
    "//div[@class='mud-list']"
    "/div[contains(@class, 'mud-list-item')][2]"
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

# Overlay do MudBlazor que pode bloquear cliques (ex.: diálogo anterior
# ainda fechando).
XPATH_OVERLAY = (
    "//div[contains(@class,'mud-overlay') "
    "and not(contains(@class,'mud-overlay-absolute'))]"
)


def _primeiro_visivel(driver: WebDriver, xpath: str) -> WebElement | bool:
    """Retorna o primeiro elemento visível e habilitado, ou False.

    Necessário porque o MudBlazor pode manter vários popovers no DOM;
    só o da linha clicada está visível.
    """
    for elemento in driver.find_elements(By.XPATH, xpath):
        try:
            if elemento.is_displayed() and elemento.is_enabled():
                return elemento
        except StaleElementReferenceException:
            continue
    return False


def _clicar(driver: WebDriver, xpath: str, timeout: int) -> WebElement:
    """Espera um elemento visível pelo XPath e clica, com retry e JS.

    Refaz a busca a cada tentativa para evitar StaleElementReference
    (o Blazor re-renderiza o DOM com frequência).

    Raises:
        TimeoutException: Se o elemento não ficar visível ou não puder
            ser clicado após 3 tentativas.
    """
    ultima_excecao: Exception | None = None
    for tentativa in range(1, 4):
        elemento = WebDriverWait(driver, timeout).until(
            lambda d: _primeiro_visivel(d, xpath)
        )
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", elemento
            )
            try:
                elemento.click()
            except ElementClickInterceptedException:
                logger.warning("Click interceptado; usando JS (%s).", xpath)
                driver.execute_script("arguments[0].click();", elemento)
            return elemento
        except StaleElementReferenceException as exc:
            ultima_excecao = exc
            logger.warning("Elemento obsoleto (tentativa %d).", tentativa)
    raise TimeoutException(
        f"Não foi possível clicar em {xpath!r}"
    ) from ultima_excecao


def _salvar_diagnostico(driver: WebDriver, nome: str) -> None:
    """Salva screenshot e HTML da página para análise de falhas."""
    pasta = Path("logs") / "diagnostico"
    pasta.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(pasta / f"{nome}.png"))
    (pasta / f"{nome}.html").write_text(
        driver.page_source, encoding="utf-8"
    )


def _abrir_menu_acoes(driver: WebDriver, numero: str, timeout: int) -> None:
    """Clica em Ações e confirma que o item Excluir ficou visível.

    Raises:
        TimeoutException: Se o menu não abrir após 3 tentativas.
    """
    xpath_botao = XPATH_BOTAO_ACOES.format(numero=numero)
    for tentativa in range(1, 4):
        _clicar(driver, xpath_botao, timeout)
        try:
            WebDriverWait(driver, 5).until(
                lambda d: _primeiro_visivel(d, XPATH_ITEM_EXCLUIR)
            )
            return
        except TimeoutException:
            logger.warning(
                "Menu não abriu (tentativa %d); tentando de novo.",
                tentativa,
            )
    raise TimeoutException(f"Menu de ações não abriu para Numero={numero}")


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

    xpath_linha = XPATH_LINHA.format(numero=numero)
    logger.info("Excluindo linha Numero=%s", numero)

    try:
        # Linha já não existe (excluída antes / lista desatualizada).
        if not driver.find_elements(By.XPATH, xpath_linha):
            logger.warning("Linha Numero=%s não está na tabela.", numero)
            return

        # Espera overlay de ação anterior sumir (não fatal se persistir).
        try:
            WebDriverWait(driver, 5).until(
                EC.invisibility_of_element_located(
                    (By.XPATH, XPATH_OVERLAY)
                )
            )
        except TimeoutException:
            logger.warning("Overlay ainda presente; seguindo mesmo assim.")

        _abrir_menu_acoes(driver, numero, timeout)

        try:
            _clicar(driver, XPATH_ITEM_EXCLUIR, timeout)
        except TimeoutException:
            logger.warning("'Excluir' não achado pelo texto; usando posição.")
            _clicar(driver, XPATH_ITEM_EXCLUIR_POSICAO, timeout)

        if xpath_confirmacao is not None:
            try:
                _clicar(driver, xpath_confirmacao, timeout)
            except TimeoutException:
                logger.warning("'Confirmar' não achado; usando posição.")
                _clicar(driver, XPATH_CONFIRMAR_POSICAO, timeout)

        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.XPATH, xpath_linha))
        )
        logger.info("Linha Numero=%s excluída.", numero)

    except TimeoutException:
        logger.exception("Falha ao excluir Numero=%s", numero)
        _salvar_diagnostico(driver, f"falha_excluir_{numero}")
        raise


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