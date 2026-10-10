
"""Automação de campo autocomplete MudBlazor (mud-autocomplete).

Cobre o padrão em que o usuário digita um texto no campo (ex.: "Forma
de pagamento"), o MudBlazor filtra uma lista (`div.mud-list-item`) e um
item deve ser clicado. A lista pode ter itens com o mesmo texto, mas só
um deles é válido, e a posição dele varia. A opção ruim mostra o mesmo
texto no campo; a diferença só aparece após "Pesquisar" (grade vazia,
"0-0 of 0"). Por isso `selecionar_e_pesquisar` valida pelo resultado.

Uso típico:
    selecionar_e_pesquisar(
        driver=driver,
        xpath_campo_input=XPATH_CAMPO_FORMA_PAGAMENTO,
        texto_busca="débito",
        texto_item_alvo="DÉBITO MASTERCARD",
        xpath_botao_pesquisar=XPATH_BOTAO_PESQUISAR,
    )
"""

import logging
import re
import time
import unicodedata

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 10
CSS_ITENS_LISTA = "div.mud-list-item"

# AJUSTAR se necessário, conforme o HTML do rodapé da grade.
XPATH_CONTADOR_GRADE = (
    "//*[contains(@class,'mud-table-pagination-caption') "
    "and contains(.,' of ')]"
)
TEXTO_GRADE_VAZIA = "0-0 of 0"
PAUSA_APOS_PESQUISAR = 1.0  # segundos, para a grade começar a atualizar


class AutocompleteSelecaoError(Exception):
    """Erro genérico ao interagir com um campo autocomplete MudBlazor."""


# --------------------------------------------------------------------------
# Utilitários
# --------------------------------------------------------------------------
def _normalizar_texto(texto: str | None) -> str:
    """Normaliza para comparação: Unicode NFC, espaços colapsados, caixa baixa."""
    texto = unicodedata.normalize("NFC", texto or "")
    return re.sub(r"\s+", " ", texto).strip().casefold()


def _valor_campo(driver: WebDriver, xpath_campo_input: str) -> str:
    """Retorna o `value` atual do input."""
    campo = driver.find_element(By.XPATH, xpath_campo_input)
    return campo.get_attribute("value") or ""


def clicar_com_fallback(
    driver: WebDriver,
    xpath: str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Clica no elemento; se for interceptado, usa clique via JavaScript."""
    elemento = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    try:
        elemento.click()
    except ElementClickInterceptedException:
        logger.warning("Clique interceptado; usando clique via JavaScript.")
        driver.execute_script("arguments[0].click();", elemento)


# --------------------------------------------------------------------------
# Campo autocomplete
# --------------------------------------------------------------------------
def _limpar_campo(
    driver: WebDriver,
    xpath_campo_input: str,
    timeout: int = 5,
) -> None:
    """Esvazia o autocomplete e confirma que o valor ficou vazio."""
    # campo = WebDriverWait(driver, timeout).until(
    #     EC.element_to_be_clickable((By.XPATH, xpath_campo_input))
    # )
    # campo.click()
    campo = WebDriverWait(driver, timeout).until(
    EC.element_to_be_clickable((By.XPATH, xpath_campo_input))
    )
    # Centraliza o campo na tela: evita que fique escondido sob a barra
    # superior fixa (mud-toolbar-appbar) após a rolagem da página.
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
        campo,
    )
    time.sleep(0.3)  # deixa a rolagem terminar
    try:
        campo.click()
    except ElementClickInterceptedException:
        logger.warning("Clique interceptado no campo; usando foco via JavaScript.")
        driver.execute_script("arguments[0].focus(); arguments[0].click();", campo)
    campo.send_keys(Keys.CONTROL, "a")
    campo.send_keys(Keys.DELETE)

    if (campo.get_attribute("value") or "") == "":
        return

    # Plano B: botão "X" do componente MudBlazor.
    xpath_limpar = f"{xpath_campo_input}/parent::div//button[@aria-label='Clear']"
    WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath_limpar))
    ).click()
    WebDriverWait(driver, timeout).until(
        lambda drv: _valor_campo(drv, xpath_campo_input) == ""
    )


def digitar_busca(
    driver: WebDriver,
    xpath_campo_input: str,
    texto_busca: str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Limpa o campo e digita o texto de busca, abrindo a lista filtrada.

    Raises:
        AutocompleteSelecaoError: se a lista filtrada não aparecer a tempo.
    """
    try:
        _limpar_campo(driver, xpath_campo_input, timeout)
        driver.find_element(By.XPATH, xpath_campo_input).send_keys(texto_busca)
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


def _clicar_ocorrencia(
    driver: WebDriver,
    texto_item_alvo: str,
    indice: int,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Clica na ocorrência `indice`, rebuscando o item se ficar stale."""

    def _tentar(drv: WebDriver) -> bool:
        itens = _listar_itens_por_texto(drv, texto_item_alvo)
        if indice >= len(itens):
            return False
        itens[indice].click()
        return True

    WebDriverWait(
        driver,
        timeout,
        ignored_exceptions=(
            StaleElementReferenceException,
            ElementClickInterceptedException,
        ),
    ).until(_tentar)


def _aguardar_selecao_assentar(
    driver: WebDriver,
    xpath_campo_input: str,
    texto_esperado: str,
    timeout: int = 5,
) -> None:
    """Espera a lista fechar e o campo exibir o texto selecionado."""
    WebDriverWait(driver, timeout).until(
        EC.invisibility_of_element_located((By.CSS_SELECTOR, CSS_ITENS_LISTA))
    )
    WebDriverWait(driver, timeout).until(
        lambda drv: _normalizar_texto(_valor_campo(drv, xpath_campo_input))
        == _normalizar_texto(texto_esperado)
    )
    time.sleep(0.5)  # margem para o round-trip do Blazor


# --------------------------------------------------------------------------
# Validação pelo resultado da pesquisa
# --------------------------------------------------------------------------
def _resultado_pesquisa_tem_dados(
    driver: WebDriver,
    timeout: int = 8,
) -> bool:
    """Após clicar em Pesquisar, retorna True se a grade trouxe linhas.

    Decide pelo contador de paginação: "0-0 of 0" = vazio; qualquer
    outro texto = com dados.
    """
    time.sleep(PAUSA_APOS_PESQUISAR)

    def _contador_lido(drv: WebDriver) -> str | bool:
        try:
            textos = [
                e.text.strip()
                for e in drv.find_elements(By.XPATH, XPATH_CONTADOR_GRADE)
                if e.is_displayed()
            ]
        except StaleElementReferenceException:
            return False
        return textos[-1] if textos and textos[-1] else False

    try:
        contador = WebDriverWait(driver, timeout).until(_contador_lido)
    except TimeoutException:
        logger.warning("Contador da grade não apareceu após pesquisar.")
        return False

    contador = contador.replace("\xa0", " ").strip()
    logger.debug("Contador da grade: '%s'.", contador)
    return contador != TEXTO_GRADE_VAZIA


# --------------------------------------------------------------------------
# Funções públicas
# --------------------------------------------------------------------------
def selecionar_autocomplete(
    driver: WebDriver,
    xpath_campo_input: str,
    texto_busca: str,
    texto_item_alvo: str,
    indice_ocorrencia: int = 0,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Digita a busca e clica numa ocorrência fixa do item alvo.

    Uso simples, sem validação pelo resultado. Para casos com itens
    duplicados, prefira `selecionar_e_pesquisar`.

    Raises:
        AutocompleteSelecaoError: se digitar ou clicar falhar.
    """
    digitar_busca(driver, xpath_campo_input, texto_busca, timeout)
    try:
        _clicar_ocorrencia(driver, texto_item_alvo, indice_ocorrencia, timeout)
    except TimeoutException as exc:
        raise AutocompleteSelecaoError(
            f"Item '{texto_item_alvo}' (ocorrência {indice_ocorrencia}) "
            "não encontrado ou não clicável na lista filtrada."
        ) from exc
    logger.info(
        "Item '%s' (ocorrência %s) selecionado.",
        texto_item_alvo,
        indice_ocorrencia,
    )


def selecionar_e_pesquisar(
    driver: WebDriver,
    xpath_campo_input: str,
    texto_busca: str,
    texto_item_alvo: str,
    xpath_botao_pesquisar: str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Seleciona a forma de pagamento e pesquisa, validando pelo resultado.

    Tenta cada ocorrência do item. Para cada uma, clica em Pesquisar e
    verifica se a grade trouxe dados. Se vier vazia, tenta a próxima.
    Funciona com o item bom em qualquer posição.

    Raises:
        AutocompleteSelecaoError: se nenhuma ocorrência retornar dados.
    """
    tentativa = 0
    total: int | None = None

    while total is None or tentativa < total:
        digitar_busca(driver, xpath_campo_input, texto_busca, timeout)
        total = len(_listar_itens_por_texto(driver, texto_item_alvo))
        if tentativa >= total:
            break

        try:
            _clicar_ocorrencia(driver, texto_item_alvo, tentativa, timeout)
        except TimeoutException:
            logger.warning("Ocorrência %s não clicável.", tentativa)
            tentativa += 1
            continue

        _aguardar_selecao_assentar(driver, xpath_campo_input, texto_item_alvo)
        clicar_com_fallback(driver, xpath_botao_pesquisar)

        if _resultado_pesquisa_tem_dados(driver):
            logger.info(
                "Pesquisa com dados (ocorrência %s de %s).", tentativa, total
            )
            return

        logger.warning(
            "Ocorrência %s de '%s' retornou grade vazia; tentando a próxima.",
            tentativa,
            texto_item_alvo,
        )
        tentativa += 1

    raise AutocompleteSelecaoError(
        f"Nenhuma ocorrência de '{texto_item_alvo}' retornou dados."
    )