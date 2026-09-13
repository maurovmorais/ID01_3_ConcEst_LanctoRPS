"""Automação de seleção de item em lista suspensa MudBlazor (mud-list).

Este módulo cobre o padrão de componente `mud-select` / `mud-list` do
MudBlazor: um botão/campo que, ao ser clicado, expande uma lista de
itens (`div.mud-list-item`), dos quais um deve ser selecionado por
texto (ex.: quantidade de itens por página: 10, 25, 50, 100).

Requisitos:
    - selenium >= 4.x
    - Um WebDriver (Chrome/Edge) já inicializado e na página correta.

Uso típico:
    from selenium import webdriver
    from mud_blazor_list_selector import definir_itens_por_pagina

    driver = webdriver.Chrome()
    driver.get("https://rps.portalsoftcase.com.br/softrps/rpsconsolidateds")

    definir_itens_por_pagina(
        driver=driver,
        xpath_botao_expandir=(
            "/html/body/div[1]/div/div[3]/div[2]/div/div[5]/div[4]/"
            "div/div[2]/div[2]/div/div/div[1]/div[1]"
        ),
        valor_alvo="100",
    )
"""

import logging

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 10

CSS_LISTA = "div.mud-list"
CSS_ITENS_LISTA = "div.mud-list-item"


class ListaSelecaoError(Exception):
    """Erro genérico ao interagir com uma lista suspensa MudBlazor."""


def expandir_lista(
    driver: WebDriver,
    xpath_botao_expandir: str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Clica no elemento que expande a lista suspensa.

    Args:
        driver: instância do WebDriver já na página do formulário.
        xpath_botao_expandir: XPath do elemento que abre a lista.

            Observação: um XPath absoluto (começando em
            `/html/body/...`) é frágil a mudanças de layout da página.
            Se a tela tiver um atributo mais estável (id, aria-label,
            texto do item já selecionado), prefira um XPath relativo.
        timeout: tempo máximo de espera, em segundos.

    Raises:
        ListaSelecaoError: se o botão não for clicável ou a lista não
            aparecer a tempo.
    """
    try:
        botao = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath_botao_expandir))
        )
        botao.click()
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_LISTA))
        )
        logger.debug("Lista suspensa expandida com sucesso.")
    except TimeoutException as exc:
        raise ListaSelecaoError(
            "Não foi possível expandir a lista (botão ou lista "
            "não encontrados a tempo)."
        ) from exc


def selecionar_item_lista(
    driver: WebDriver,
    valor_alvo: str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Clica, dentro da lista já expandida, no item com o texto informado.

    Args:
        driver: instância do WebDriver com a lista (`div.mud-list`) já
            visível na tela.
        valor_alvo: texto exato do item a selecionar (ex.: "100").
        timeout: tempo máximo de espera, em segundos.

    Raises:
        ListaSelecaoError: se nenhum item com o texto informado for
            encontrado.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_ITENS_LISTA))
        )
        itens = driver.find_elements(By.CSS_SELECTOR, CSS_ITENS_LISTA)
        item_alvo = next(
            item for item in itens if item.text.strip() == valor_alvo
        )
    except (TimeoutException, StopIteration, NoSuchElementException) as exc:
        raise ListaSelecaoError(
            f"Item '{valor_alvo}' não encontrado na lista suspensa."
        ) from exc

    item_alvo.click()
    logger.info("Item '%s' selecionado na lista.", valor_alvo)


def definir_itens_por_pagina(
    driver: WebDriver,
    xpath_botao_expandir: str,
    valor_alvo: str = "100",
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Orquestra a seleção completa: expande a lista e clica no valor alvo.

    Args:
        driver: instância do WebDriver já na página do formulário.
        xpath_botao_expandir: XPath do elemento que abre a lista.
        valor_alvo: texto do item a selecionar. Padrão: "100".
        timeout: tempo máximo de espera por elemento, em segundos.

    Raises:
        ListaSelecaoError: se expandir a lista ou selecionar o item
            falhar.
    """
    expandir_lista(driver, xpath_botao_expandir, timeout)
    selecionar_item_lista(driver, valor_alvo, timeout)