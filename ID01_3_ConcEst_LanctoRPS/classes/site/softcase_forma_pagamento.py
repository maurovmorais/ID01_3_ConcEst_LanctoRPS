"""Automação de campo autocomplete MudBlazor (mud-autocomplete).

Cobre o padrão em que o usuário digita um texto no campo (ex.: "Forma
de pagamento"), o MudBlazor filtra uma lista (`div.mud-list-item`) com
as opções compatíveis, e um item específico deve ser clicado — mesmo
quando há textos duplicados na lista (ex.: "DÉBITO VISA" aparecendo
mais de uma vez).

Requisitos:
    - selenium >= 4.x
    - Um WebDriver (Chrome/Edge) já inicializado e na página correta.

Uso típico:
    from selenium import webdriver
    from mud_blazor_autocomplete_selector import selecionar_autocomplete

    driver = webdriver.Chrome()
    driver.get("https://rps.portalsoftcase.com.br/softrps/rpsconsolidateds")

    selecionar_autocomplete(
        driver=driver,
        xpath_campo_input="//label[contains(., 'Forma de pagamento')]"
                           "/ancestor::div[contains(@class,'mud-input-control')]"
                           "//input",
        texto_busca="débito",
        texto_item_alvo="DÉBITO ELO",
    )
"""

import logging

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 10

CSS_ITENS_LISTA = "div.mud-list-item"


class AutocompleteSelecaoError(Exception):
    """Erro genérico ao interagir com um campo autocomplete MudBlazor."""


def digitar_busca(
    driver: WebDriver,
    xpath_campo_input: str,
    texto_busca: str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Limpa o campo e digita o texto de busca, abrindo a lista filtrada.

    Args:
        driver: instância do WebDriver já na página do formulário.
        xpath_campo_input: XPath do `<input>` do autocomplete (ex.:
            campo "Forma de pagamento").
        texto_busca: texto a digitar para filtrar as opções (ex.:
            "débito").
        timeout: tempo máximo de espera, em segundos.

    Raises:
        AutocompleteSelecaoError: se o campo não for encontrado ou a
            lista filtrada não aparecer a tempo.
    """
    try:
        campo = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath_campo_input))
        )
        campo.send_keys(Keys.ENTER)
        campo.clear()
        campo.send_keys(texto_busca)
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_ITENS_LISTA))
        )
        logger.debug("Busca '%s' digitada e lista filtrada exibida.", texto_busca)
    except TimeoutException as exc:
        raise AutocompleteSelecaoError(
            f"Não foi possível digitar '{texto_busca}' ou a lista filtrada "
            "não apareceu a tempo."
        ) from exc


def _listar_itens_por_texto(
    driver: WebDriver,
    texto_item_alvo: str,
) -> list[WebElement]:
    """Retorna todos os itens da lista cujo texto bate com `texto_item_alvo`."""
    itens = driver.find_elements(By.CSS_SELECTOR, CSS_ITENS_LISTA)
    return [item for item in itens if item.text.strip() == texto_item_alvo]


def selecionar_item_autocomplete(
    driver: WebDriver,
    texto_item_alvo: str,
    indice_ocorrencia: int = 0,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Clica no item da lista filtrada com o texto informado.

    Quando a lista tem itens com o mesmo texto (ex.: duas opções
    "DÉBITO VISA"), `indice_ocorrencia` escolhe qual delas clicar
    (0 = primeira ocorrência na lista, na ordem exibida na tela).

    Args:
        driver: instância do WebDriver com a lista filtrada já visível.
        texto_item_alvo: texto exato do item a selecionar (ex.:
            "DÉBITO ELO").
        indice_ocorrencia: índice, entre as ocorrências com esse
            texto, do item a clicar. Padrão: 0 (primeira).
        timeout: tempo máximo de espera, em segundos.

    Raises:
        AutocompleteSelecaoError: se nenhum item (ou nenhum na posição
            pedida) for encontrado com o texto informado.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_ITENS_LISTA))
        )
        itens_encontrados = _listar_itens_por_texto(driver, texto_item_alvo)
        item_alvo = itens_encontrados[indice_ocorrencia]
    except (TimeoutException, IndexError, NoSuchElementException) as exc:
        raise AutocompleteSelecaoError(
            f"Item '{texto_item_alvo}' (ocorrência {indice_ocorrencia}) "
            "não encontrado na lista filtrada."
        ) from exc

    item_alvo.click()
    logger.info(
        "Item '%s' (ocorrência %s) selecionado no autocomplete.",
        texto_item_alvo,
        indice_ocorrencia,
    )


def selecionar_autocomplete(
    driver: WebDriver,
    xpath_campo_input: str,
    texto_busca: str,
    texto_item_alvo: str,
    indice_ocorrencia: int = 0,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Orquestra a seleção completa: digita a busca e clica no item alvo.

    Args:
        driver: instância do WebDriver já na página do formulário.
        xpath_campo_input: XPath do `<input>` do autocomplete.
        texto_busca: texto a digitar para filtrar as opções.
        texto_item_alvo: texto exato do item a selecionar.
        indice_ocorrencia: qual ocorrência clicar quando houver textos
            duplicados na lista filtrada. Padrão: 0 (primeira).
        timeout: tempo máximo de espera por elemento, em segundos.

    Raises:
        AutocompleteSelecaoError: se digitar a busca ou selecionar o
            item falhar.
    """
    digitar_busca(driver, xpath_campo_input, texto_busca, timeout)
    selecionar_item_autocomplete(driver, texto_item_alvo, indice_ocorrencia, timeout)