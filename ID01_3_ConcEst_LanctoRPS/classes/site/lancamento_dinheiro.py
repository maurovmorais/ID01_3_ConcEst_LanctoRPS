"""Lançamento de RPS Consolidado para forma de pagamento 'DINHEIRO'.

Fluxo:
    1. Filtra a forma de pagamento DINHEIRO na tela RPS Consolidados.
    2. Se houver RPS, atualiza o existente (Valor e Total taxa).
    3. Se não houver opção/registro para alterar, cria um NOVO
       lançamento, nos mesmos moldes do fluxo Pix.

Módulo autônomo: tem os próprios seletores e funções auxiliares para
a criação (NOVO), sem depender de ``lancamento_pix.py``.
"""

import logging
from datetime import date, timedelta
from time import sleep

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import (
    atualizar_dados,
    editar_rps_consolidado,
    filtrar_forma_pagto,
)
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_forma_pagamento import (
    AutocompleteSelecaoError,
)
from ID01_3_ConcEst_LanctoRPS.classes.utils.util_data import definir_data

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 20
# Texto exibido na lista do diálogo de criação.
# A comparação na seleção ignora maiúsculas/minúsculas.
FORMA_PAGTO_DINHEIRO = "DINHEIRO"
QUANTIDADE_FIXA = "1"
DIAS_COMP_PADRAO = "0"  # só se a fila vier vazia

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
XPATH_ITENS_LISTA = (
    "//div[contains(@class,'mud-popover-open')]"
    "//div[contains(@class,'mud-list-item')]//p"
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


def _selecionar_forma_pagto(driver: WebDriver, texto: str) -> None:
    """Autocomplete: digita o texto e clica no primeiro item igual a ele.

    A comparação ignora maiúsculas/minúsculas. Se houver itens duplicados
    com o mesmo texto, usa o primeiro.
    """
    campo = _esperar_clicavel(driver, XPATH_FORMA_PAGTO)
    campo.click()
    campo.clear()
    campo.send_keys(texto)

    alvo = texto.strip().casefold()

    def _achar_opcao(drv: WebDriver) -> WebElement | bool:
        for item in drv.find_elements(By.XPATH, XPATH_ITENS_LISTA):
            try:
                if item.text.strip().casefold() == alvo:
                    return item
            except StaleElementReferenceException:
                continue  # lista recarregou; tenta no próximo ciclo
        return False

    try:
        opcao = WebDriverWait(driver, TIMEOUT_PADRAO).until(_achar_opcao)
    except TimeoutException:
        logger.error("Forma de pagamento '%s' não encontrada na lista.", texto)
        raise
    opcao.click()


def _normalizar_dias_comp(dias_comp: str | int | None) -> str:
    """Retorna dias_comp como texto; vazio/None vira '0'."""
    if dias_comp is None or str(dias_comp).strip() == "":
        return DIAS_COMP_PADRAO
    return str(dias_comp).strip()


def _criar_novo_dinheiro(
    driver: WebDriver,
    nome_empresa: str,
    forma_pagamento: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None,
    data_lancamento: date | None = None,
) -> None:
    """Cria um novo RPS Consolidado (botão NOVO) para 'DINHEIRO'."""
    dias_comp_texto = _normalizar_dias_comp(dias_comp)

    data = data_lancamento or (date.today() - timedelta(days=1))
    data_str = f"{data.day}/{data.month}/{data.year}"  # formato 'd/m/aaaa'

    logger.info("Criando lançamento DINHEIRO: %s", nome_empresa)
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

    _selecionar_forma_pagto(driver, forma_pagamento)
    _preencher(driver, XPATH_VALOR, valor)
    _preencher(driver, XPATH_QUANTIDADE, QUANTIDADE_FIXA)
    _preencher(driver, XPATH_TOTAL_TAXA, valor_taxa)
    _preencher(driver, XPATH_DIAS_COMP, dias_comp_texto)

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

    logger.info("Lançamento DINHEIRO salvo: %s", nome_empresa)


def lancar_dinheiro(
    driver: WebDriver,
    nome_empresa: str,
    forma_pagamento: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None = None,
    data_lancamento: date | None = None,
) -> None:
    """Atualiza o RPS de DINHEIRO ou, se não existir, cria um NOVO.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados.
        nome_empresa: Nome da empresa a selecionar (só no NOVO).
        forma_pagamento: Forma de pagamento vinda da fila (usada no
            filtro e no NOVO).
        valor: Valor do lançamento.
        valor_taxa: Valor para o campo Total taxa.
        dias_comp: Valor de Dias Comp. vindo da fila.
        data_lancamento: Data do NOVO; padrão é D-1.
    """
    if not forma_pagamento or not str(forma_pagamento).strip():
        raise ValueError("Forma de pagamento vazia.")
    forma_pagamento = str(forma_pagamento).strip()

    try:
        filtrar_forma_pagto(
            driver=driver,
            forma_pgto=forma_pagamento,
            bandeira=None,
        )
    except AutocompleteSelecaoError:
        logger.info(
            "Nenhum RPS '%s' para alterar; criando NOVO lançamento.",
            forma_pagamento,
        )
        _criar_novo_dinheiro(
            driver,
            nome_empresa,
            forma_pagamento,
            valor,
            valor_taxa,
            dias_comp,
            data_lancamento,
        )
        return

    # Existe RPS: atualiza o existente, inclusive Dias Comp. da fila.
    atualizar_dados(driver=driver)
    sleep(1)  # ideal: trocar por WebDriverWait
    editar_rps_consolidado(
        driver=driver,
        valor=valor,
        total_taxa=valor_taxa,
        dias_comp=dias_comp,
    )