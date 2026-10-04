"""Lançamento de RPS Consolidado para forma de pagamento 'Crédito pré-pago'."""

import logging
from datetime import date, timedelta

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ID01_3_ConcEst_LanctoRPS.classes.utils.util_data import definir_data

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 20
PREFIXO_FORMA_PAGTO = "CRÉDITO"
# Bandeiras cujo texto no SoftCase varia; tenta na ordem listada.
# (o '?' é literal: o portal exibe 'Cr?dito' por problema de encoding)
FORMAS_PAGTO_ALTERNATIVAS: dict[str, list[str]] = {
    "ELO": ["Crédito Elo", "Crédito Elo Cr?dito", "Crédito Elo Credito"],
}
XPATH_ITENS_LISTA = (
    "//div[contains(@class,'mud-popover-open')]"
    "//div[contains(@class,'mud-list-item')]//p"
)
QUANTIDADE_FIXA = "1"

XPATH_BOTAO_NOVO = (
    "/html/body/div[1]/div/div[3]/div[2]/div/div[5]/div[1]/div[1]/button[1]"
)
XPATH_DIALOGO = "//div[contains(@class,'mud-dialog-title')][.//h6]"
BASE_FORM = "/html/body/div[1]/div/div[1]/div[2]/form/div/div[4]/div[1]/div"
XPATH_EMPRESA = (
    "//label[normalize-space()='Empresa']"
    "/ancestor::div[contains(@class,'mud-select')][1]//input"
)
XPATH_BOTAO_CALENDARIO_DATA = f"{BASE_FORM}/div[5]/div/div[1]/div/div//button"
XPATH_FORMA_PAGTO = f"{BASE_FORM}/div[6]/div/div/div/div[1]/input"
XPATH_VALOR = f"{BASE_FORM}/div[7]/div/div/div/input"
XPATH_QUANTIDADE = f"{BASE_FORM}/div[8]/div/div/div/input"
XPATH_TOTAL_TAXA = f"{BASE_FORM}/div[12]/div/div/div/input"
XPATH_DIAS_COMP = f"{BASE_FORM}/div[20]/div/div/div/input"
XPATH_BOTAO_SALVAR = (
    "/html/body/div[1]/div/div[1]/div[2]/form/div/div[4]/div[2]/button[2]"
)


def _esperar_clicavel(driver: WebDriver, xpath: str) -> WebElement:
    """Aguarda o elemento ficar clicável e o retorna."""
    return WebDriverWait(driver, TIMEOUT_PADRAO).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )


def _preencher(driver: WebDriver, xpath: str, valor: str) -> None:
    """Limpa e preenche um campo de texto MudBlazor."""
    campo = _esperar_clicavel(driver, xpath)
    campo.click()
    campo.clear()
    campo.send_keys(str(valor))


def _selecionar_empresa(driver: WebDriver, nome_empresa: str) -> None:
    """Abre o select Empresa (readonly) e clica na opção pelo texto."""
    _esperar_clicavel(driver, XPATH_EMPRESA).click()
    opcao = WebDriverWait(driver, TIMEOUT_PADRAO).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//div[contains(@class,'mud-popover-open')]"
                f"//p[normalize-space()='{nome_empresa}']",
            )
        )
    )
    opcao.click()


def _formas_pagto_candidatas(bandeira_cartao: str) -> list[str]:
    """Retorna os textos aceitos para a forma de pagamento da bandeira."""
    return FORMAS_PAGTO_ALTERNATIVAS.get(
        bandeira_cartao, [f"{PREFIXO_FORMA_PAGTO} {bandeira_cartao}"]
    )


def _selecionar_forma_pagto(driver: WebDriver, candidatas: list[str]) -> None:
    """Autocomplete: digita a 1ª candidata e clica no primeiro item que
    corresponda a alguma das candidatas (respeitando a ordem da lista).

    A comparação ignora maiúsculas/minúsculas. Se houver itens duplicados
    com o mesmo texto, usa o primeiro.
    """
    campo = _esperar_clicavel(driver, XPATH_FORMA_PAGTO)
    campo.click()
    campo.clear()
    campo.send_keys(candidatas[0])

    alvos = [c.strip().casefold() for c in candidatas]

    def _achar_opcao(drv: WebDriver) -> WebElement | bool:
        itens = drv.find_elements(By.XPATH, XPATH_ITENS_LISTA)
        for alvo in alvos:
            for item in itens:
                try:
                    if item.text.strip().casefold() == alvo:
                        return item
                except StaleElementReferenceException:
                    continue  # lista recarregou; tenta no próximo ciclo
        return False

    try:
        opcao = WebDriverWait(driver, TIMEOUT_PADRAO).until(_achar_opcao)
    except TimeoutException:
        logger.error("Forma de pagamento não encontrada. Tentadas: %s", candidatas)
        raise
    opcao.click()


def lancar_credito_pre_pago(
    driver: WebDriver,
    nome_empresa: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str,
    bandeira: str,
    data_lancamento: date | None = None,
) -> None:
    """Cria um novo RPS Consolidado para 'Crédito pré-pago'.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados.
        nome_empresa: Nome da empresa a selecionar.
        valor: Valor do lançamento.
        valor_taxa: Valor para o campo Total taxa.
        dias_comp: Valor para o campo Dias Comp.
        bandeira: Bandeira do cartão (ex.: 'Visa'); a forma de pagamento
            selecionada será 'CRÉDITO ' + bandeira em maiúsculas.
        data_lancamento: Data do lançamento; padrão é D-1.

    Raises:
        ValueError: se a bandeira estiver vazia.
    """
    bandeira_cartao = str(bandeira).strip().upper() if bandeira else ""
    if not bandeira_cartao:
        raise ValueError("Bandeira vazia: não é possível montar a forma de pagamento.")
    formas_pagto = _formas_pagto_candidatas(bandeira_cartao)  # ex.: CRÉDITO VISA

    data = data_lancamento or (date.today() - timedelta(days=1))
    data_str = f"{data.day}/{data.month}/{data.year}"  # formato 'd/m/aaaa'

    logger.info("Criando lançamento Crédito pré-pago: %s", nome_empresa)
    _esperar_clicavel(driver, XPATH_BOTAO_NOVO).click()

    try:
        WebDriverWait(driver, TIMEOUT_PADRAO).until(
            EC.visibility_of_element_located((By.XPATH, XPATH_DIALOGO))
        )
    except TimeoutException:
        logger.error("Diálogo 'Criar RPS Consolidado' não apareceu.")
        raise

    _selecionar_empresa(driver, nome_empresa)

    # Campo Data é readonly: usa o seletor de calendário já existente.
    definir_data(driver, XPATH_BOTAO_CALENDARIO_DATA, data_str)

    _selecionar_forma_pagto(driver, formas_pagto)
    _preencher(driver, XPATH_VALOR, valor)
    _preencher(driver, XPATH_QUANTIDADE, QUANTIDADE_FIXA)
    _preencher(driver, XPATH_TOTAL_TAXA, valor_taxa)
    _preencher(driver, XPATH_DIAS_COMP, dias_comp)

    _esperar_clicavel(driver, XPATH_BOTAO_SALVAR).click()

    # Confirma que o diálogo fechou (salvou sem erro de validação).
    try:
        WebDriverWait(driver, TIMEOUT_PADRAO).until(
            EC.invisibility_of_element_located((By.XPATH, XPATH_DIALOGO))
        )
    except TimeoutException:
        logger.error(
            "Diálogo não fechou após Salvar; verifique campos obrigatórios."
        )
        raise

    logger.info("Lançamento Crédito pré-pago salvo: %s", nome_empresa)