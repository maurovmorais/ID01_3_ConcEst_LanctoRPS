"""Lançamento de RPS Consolidado para 'Crédito conversor de moedas'.

Fluxo:
    1. Filtra a forma de pagamento (da fila) na tela RPS Consolidados.
    2. Se a grade trouxer um RPS da empresa, atualiza o existente
       (Ações > Editar).
    3. Se não houver resultado, cria um NOVO lançamento pelo botão NOVO
       (diálogo 'Criar RPS Consolidado').

A forma de pagamento vem da fila (variável ``forma_pagamento`` do Process).

A criação (NOVO) usa seletores e funções auxiliares próprios.
"""

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
QUANTIDADE_FIXA = "1"
DIAS_COMP_PADRAO = "0"

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


def _normalizar_dias_comp(dias_comp: str | int | None) -> str:
    """Retorna dias_comp como texto; vazio/None vira '0'."""
    if dias_comp is None or str(dias_comp).strip() == "":
        return DIAS_COMP_PADRAO
    return str(dias_comp).strip()


def _criar_novo_conversor_moedas(
    driver: WebDriver,
    nome_empresa: str,
    forma_pagto: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None = None,
    data_lancamento: date | None = None,
) -> None:
    """Cria um novo RPS Consolidado (botão NOVO) para 'Crédito conversor
    de moedas'.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados.
        nome_empresa: Nome da empresa a selecionar.
        forma_pagto: Texto da forma de pagamento a selecionar na lista
            (vem da fila).
        valor: Valor do lançamento.
        valor_taxa: Valor para o campo Total taxa.
        dias_comp: Valor para o campo Dias Comp.; se vier None/vazio,
            usa '0'.
        data_lancamento: Data do lançamento; padrão é D-1.
    """
    formas_pagto = [forma_pagto.strip()]  # vem da fila
    dias_comp_texto = _normalizar_dias_comp(dias_comp)

    data = data_lancamento or (date.today() - timedelta(days=1))
    data_str = f"{data.day}/{data.month}/{data.year}"  # formato 'd/m/aaaa'

    logger.info("Criando lançamento Crédito conversor de moedas: %s", nome_empresa)
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

    logger.info("Lançamento Crédito conversor de moedas salvo: %s", nome_empresa)


def _existe_rps_na_grade(
    driver: WebDriver, nome_empresa: str, timeout: int = 5
) -> bool:
    """Retorna True se a grade tem uma linha cuja coluna Empresa contém o
    nome da empresa (ex.: 'BETIM (NEPOS) (30296394000561)').
    """
    xpath = (
        "//td[@data-label='Empresa']"
        f"[contains(normalize-space(.), \"{nome_empresa.strip()}\")]"
    )
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
    except TimeoutException:
        return False
    return True


def lancar_credito_conversor_moedas(
    driver: WebDriver,
    nome_empresa: str,
    forma_pagto: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None = None,
    data_lancamento: date | None = None,
) -> None:
    """Atualiza o RPS de 'Crédito conversor de moedas' ou cria um NOVO.

    Primeiro filtra a forma de pagamento na tela de pesquisa. Se a grade
    trouxer o RPS da empresa, clica em Ações > Editar e atualiza Valor,
    Total taxa e Dias Comp.; caso contrário, clica em NOVO.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados, com a
            empresa e as datas pesquisadas.
        nome_empresa: Nome da empresa (confere a coluna Empresa da grade
            e é selecionada no NOVO).
        forma_pagto: Forma de pagamento vinda da fila.
        valor: Valor do lançamento.
        valor_taxa: Valor para o campo Total taxa.
        dias_comp: Valor para o campo Dias Comp.; no NOVO, None/vazio
            vira '0'; na edição, None mantém o valor atual do portal.
        data_lancamento: Data do NOVO; padrão é D-1.

    Raises:
        ValueError: se o texto da forma de pagamento estiver vazio.
    """
    if not forma_pagto or not str(forma_pagto).strip():
        raise ValueError("Forma de pagamento vazia.")
    forma_pagto = str(forma_pagto).strip()

    try:
        filtrar_forma_pagto(
            driver=driver,
            forma_pgto=forma_pagto,
            bandeira=None,
        )
        existe = _existe_rps_na_grade(driver, nome_empresa)
    except AutocompleteSelecaoError:
        existe = False  # grade vazia para essa forma de pagamento

    if not existe:
        logger.info(
            "Nenhum RPS '%s' para '%s'; criando NOVO lançamento.",
            forma_pagto,
            nome_empresa,
        )
        _criar_novo_conversor_moedas(
            driver,
            nome_empresa,
            forma_pagto,
            valor,
            valor_taxa,
            dias_comp,
            data_lancamento,
        )
        return

    logger.info(
        "RPS '%s' encontrado para '%s'; atualizando (Ações > Editar).",
        forma_pagto,
        nome_empresa,
    )
    atualizar_dados(driver=driver)
    editar_rps_consolidado(
        driver=driver,
        valor=valor,
        total_taxa=valor_taxa,
        dias_comp=dias_comp,
    )
    logger.info(
        "Lançamento Crédito conversor de moedas atualizado: %s", nome_empresa
    )