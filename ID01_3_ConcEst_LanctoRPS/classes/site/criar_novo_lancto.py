"""Atualização de RPS Consolidado para forma de pagamento 'TAG'.

Segue o mesmo fluxo do DÉBITO: filtra a forma de pagamento na tela de
pesquisa e atualiza os dados do RPS existente (não cria lançamento novo).

O texto da forma de pagamento vem da fila (variável ``forma_pagamento``
do Process).
"""

import logging
from time import sleep
from datetime import date, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys

from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import (
    atualizar_dados,
    editar_rps_consolidado,
    filtrar_forma_pagto,
)
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from ID01_3_ConcEst_LanctoRPS.classes.utils.util_data import definir_data

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

XPATH_FORMA_PAGTO_INPUT = (
    "/html/body/div[1]/div/div[1]/div[2]/form/div/div[4]/div[1]"
    "/div/div[6]/div/div/div/div[1]/input"
)
XPATH_FORMA_PAGTO_OPCOES = (
    "//div[contains(@class,'mud-popover-open')]"
    "//div[contains(@class,'mud-list-item')]"
)
XPATH_ERROS_VALIDACAO = (
    "//div[@role='dialog']//*[contains(@class,'mud-input-error') "
    "or contains(@class,'mud-input-helper-text')]"
)
# Espera menor só para detectar que o Salvar não fechou o diálogo.
TIMEOUT_FECHAR_DIALOGO = 5


logger = logging.getLogger(__name__)

class AutocompleteSelecaoError(Exception):
    """Erro genérico ao interagir com um campo autocomplete MudBlazor."""


# def atualizar_tag(
#     driver: WebDriver,
#     forma_pagamento: str,
#     valor: str,
#     valor_taxa: str,
# ) -> None:
#     """Filtra a forma de pagamento (vinda da fila) e atualiza o RPS.

#     Args:
#         driver: WebDriver já posicionado na tela RPS Consolidados, com a
#             empresa e as datas pesquisadas.
#         forma_pagamento: Forma de pagamento vinda da fila (ex.: 'Veloe').
#         valor: Valor do RPS.
#         valor_taxa: Valor do campo Total taxa.

#     Raises:
#         ValueError: se a forma de pagamento estiver vazia.
#     """
#     forma_pagamento = str(forma_pagamento).strip() if forma_pagamento else ""
#     if not forma_pagamento:
#         raise ValueError("Forma de pagamento vazia.")

#     logger.info("Atualizando RPS TAG: forma '%s'", forma_pagamento)

#     # Filtrar forma pagamento
#     filtrar_forma_pagto(
#         driver=driver,
#         forma_pgto=forma_pagamento,
#         bandeira=None,
#     )
#     # Editar dados
#     atualizar_dados(driver=driver)
#     sleep(1)  # mesmo intervalo usado no fluxo dos demais
#     editar_rps_consolidado(
#         driver=driver,
#         valor=valor,
#         total_taxa=valor_taxa,
#     )

def _esperar_clicavel(driver: WebDriver, xpath: str) -> WebElement:
    """Aguarda o elemento ficar clicável e o retorna."""
    return WebDriverWait(driver, TIMEOUT_PADRAO).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )

def _normalizar_dias_comp(dias_comp: str | int | None) -> str:
    """Retorna dias_comp como texto; vazio/None vira '0'."""
    if dias_comp is None or str(dias_comp).strip() == "":
        return DIAS_COMP_PADRAO
    return str(dias_comp).strip()

def _preencher(driver: WebDriver, xpath: str, valor: str) -> None:
    """Limpa e preenche um campo de texto MudBlazor."""
    campo = _esperar_clicavel(driver, xpath)
    campo.click()
    campo.clear()
    campo.send_keys(str(valor))

# def criar_novo_lancto(
#     driver: WebDriver,
#     nome_empresa: str,
#     forma_pagto: str,
#     valor: str,
#     valor_taxa: str,
#     dias_comp: str | int | None = None,
#     data_lancamento: date | None = None,
# ) -> None:
#     """Cria um novo RPS Consolidado (botão NOVO) para o caso TAG.

#     Args:
#         driver: WebDriver já posicionado na tela RPS Consolidados.
#         nome_empresa: Nome da empresa a selecionar.
#         forma_pagto: Forma de pagamento vinda da fila (ex.: 'Veloe').
#         valor: Valor do lançamento.
#         valor_taxa: Valor para o campo Total taxa.
#         dias_comp: Valor para o campo Dias Comp.; se None/vazio, usa '0'.
#         data_lancamento: Data do lançamento; padrão é D-1.
#     """
#     formas_pagto = [forma_pagto.strip()]
#     dias_comp_texto = _normalizar_dias_comp(dias_comp)

#     data = data_lancamento or (date.today() - timedelta(days=1))
#     data_str = f"{data.day}/{data.month}/{data.year}"  # formato 'd/m/aaaa'

#     logger.info("Criando lançamento TAG: %s / %s", nome_empresa, forma_pagto)
#     _esperar_clicavel(driver, XPATH_BOTAO_NOVO).click()

#     try:
#         WebDriverWait(driver, TIMEOUT_PADRAO).until(
#             EC.visibility_of_element_located((By.XPATH, XPATH_DIALOGO))
#         )
#     except TimeoutException:
#         logger.error("Diálogo 'Criar RPS Consolidado' não apareceu.")
#         raise

#     _selecionar_empresa(driver, nome_empresa)

#     # Campo Data é readonly: usa o seletor de calendário já existente.
#     definir_data(driver, XPATH_BOTAO_CALENDARIO_DATA, data_str)

#     _selecionar_forma_pagto(driver, formas_pagto)
#     _preencher(driver, XPATH_VALOR, valor)
#     _preencher(driver, XPATH_QUANTIDADE, QUANTIDADE_FIXA)
#     _preencher(driver, XPATH_TOTAL_TAXA, valor_taxa)
#     _preencher(driver, XPATH_DIAS_COMP, dias_comp_texto)

#     _esperar_clicavel(driver, XPATH_BOTAO_SALVAR).click()

#     try:
#         WebDriverWait(driver, TIMEOUT_PADRAO).until(
#             EC.invisibility_of_element_located((By.XPATH, XPATH_DIALOGO))
#         )
#     except TimeoutException:
#         logger.error(
#             "Diálogo não fechou após Salvar; verifique campos obrigatórios."
#         )
#         raise

#     logger.info("Lançamento TAG salvo: %s / %s", nome_empresa, forma_pagto)

def criar_novo_lancto(
    driver: WebDriver,
    nome_empresa: str,
    forma_pagto: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None = None,
    data_lancamento: date | None = None,
) -> None:
    """Cria um novo RPS Consolidado (botão NOVO) para o caso TAG.

    Se a lista de Forma de pagamento trouxer mais de uma opção (textos
    idênticos), tenta salvar com a 1ª; se o diálogo não fechar, tenta
    a 2ª, e assim por diante.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados.
        nome_empresa: Nome da empresa a selecionar.
        forma_pagto: Forma de pagamento vinda da fila (ex.: 'Veloe').
        valor: Valor do lançamento.
        valor_taxa: Valor para o campo Total taxa.
        dias_comp: Valor para o campo Dias Comp.; se None/vazio, usa '0'.
        data_lancamento: Data do lançamento; padrão é D-1.
    """
    forma_pagto = forma_pagto.strip()
    dias_comp_texto = _normalizar_dias_comp(dias_comp)

    data = data_lancamento or (date.today() - timedelta(days=1))
    data_str = f"{data.day}/{data.month}/{data.year}"  # 'd/m/aaaa'

    logger.info("Criando lançamento TAG: %s / %s", nome_empresa, forma_pagto)
    _esperar_clicavel(driver, XPATH_BOTAO_NOVO).click()

    try:
        WebDriverWait(driver, TIMEOUT_PADRAO).until(
            EC.visibility_of_element_located((By.XPATH, XPATH_DIALOGO))
        )
    except TimeoutException:
        logger.error("Diálogo 'Criar RPS Consolidado' não apareceu.")
        raise

    _selecionar_empresa(driver, nome_empresa)
    definir_data(driver, XPATH_BOTAO_CALENDARIO_DATA, data_str)

    # 1ª opção; o total diz quantas tentativas existem.
    total_opcoes = _selecionar_opcao_forma_pagto(driver, forma_pagto, 0)

    _preencher(driver, XPATH_VALOR, valor)
    _preencher(driver, XPATH_QUANTIDADE, QUANTIDADE_FIXA)
    _preencher(driver, XPATH_TOTAL_TAXA, valor_taxa)
    _preencher(driver, XPATH_DIAS_COMP, dias_comp_texto)

    for indice in range(total_opcoes):
        if indice > 0:
            logger.warning(
                "Salvar falhou com a opção %d; tentando a %d de %d.",
                indice, indice + 1, total_opcoes,
            )
            _selecionar_opcao_forma_pagto(driver, forma_pagto, indice)

        if _salvar_e_aguardar_fechar(driver):
            logger.info(
                "Lançamento TAG salvo (opção %d): %s / %s",
                indice + 1, nome_empresa, forma_pagto,
            )
            return

        _logar_erros_validacao(driver)

    logger.error(
        "Diálogo não fechou após Salvar com nenhuma das %d opção(ões).",
        total_opcoes,
    )
    raise TimeoutException(
        f"Não foi possível salvar o lançamento TAG: {nome_empresa} / "
        f"{forma_pagto}"
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


def _abrir_opcoes_forma_pagto(
    driver: WebDriver, forma_pagto: str
) -> list[WebElement]:
    """Digita a forma de pagamento e devolve as opções da lista."""
    campo = _esperar_clicavel(driver, XPATH_FORMA_PAGTO_INPUT)
    campo.click()
    campo.send_keys(Keys.CONTROL, "a")
    campo.send_keys(forma_pagto)
    return WebDriverWait(driver, TIMEOUT_PADRAO).until(
        EC.presence_of_all_elements_located(
            (By.XPATH, XPATH_FORMA_PAGTO_OPCOES)
        )
    )


def _selecionar_opcao_forma_pagto(
    driver: WebDriver, forma_pagto: str, indice: int
) -> int:
    """Seleciona a opção de posição `indice` (0 = primeira).

    Args:
        driver: WebDriver com o diálogo aberto.
        forma_pagto: Texto buscado no autocomplete.
        indice: Posição da opção na lista (0 = primeira).

    Returns:
        Total de opções que a lista trouxe para o texto buscado.
    """
    opcoes = _abrir_opcoes_forma_pagto(driver, forma_pagto)
    total = len(opcoes)
    if indice >= total:
        raise IndexError(
            f"Opção {indice + 1} não existe; lista tem {total} opção(ões)."
        )
    logger.info(
        "Forma '%s': %d opção(ões); selecionando a %d.",
        forma_pagto, total, indice + 1,
    )
    opcoes[indice].click()
    return total


def _logar_erros_validacao(driver: WebDriver) -> None:
    """Registra mensagens de validação visíveis no diálogo."""
    for el in driver.find_elements(By.XPATH, XPATH_ERROS_VALIDACAO):
        texto = el.text.strip()
        if texto:
            logger.error("Validação no diálogo: %s", texto)


def _salvar_e_aguardar_fechar(driver: WebDriver) -> bool:
    """Clica em Salvar; True se o diálogo fechou, False se continuou."""
    _esperar_clicavel(driver, XPATH_BOTAO_SALVAR).click()
    try:
        WebDriverWait(driver, TIMEOUT_FECHAR_DIALOGO).until(
            EC.invisibility_of_element_located((By.XPATH, XPATH_DIALOGO))
        )
        return True
    except TimeoutException:
        return False