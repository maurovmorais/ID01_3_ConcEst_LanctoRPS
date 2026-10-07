"""Lançamento de RPS Consolidado para 'Crédito conversor de moedas'.

Cria um novo lançamento pelo botão NOVO (diálogo 'Criar RPS Consolidado').

Regra da forma de pagamento:
1. Lê a origem entre parênteses no nome da empresa (variável softcase),
   ex.: 'BETIM (NEPOS)' -> 'NEPOS'.
2. Na tabela tbl_FormaDePagamento do banco de dados, filtra
   Origem = <origem> e Tipo = 'CONVERSOR DE MOEDAS' e retorna a coluna
   'Forma de Pagamento' (ex.: 'Digital Wallet').

Módulo autônomo: tem os próprios seletores e funções auxiliares.
"""

import logging
import re
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

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
TIPO_FORMA_PAGTO = "CONVERSOR DE MOEDAS"
QUANTIDADE_FIXA = "1"
DIAS_COMP_PADRAO = "0"

CAMINHO_BANCO_DADOS = Path(
    r"C:\Armazenamento\ID01_2_ConcEst_TratarDados\Banco Dados\banco_dados.db"
)
SQL_FORMAS_PAGTO = (
    'SELECT "Origem", "Tipo", "Forma de Pagamento" FROM tbl_FormaDePagamento'
)

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


def _extrair_origem(nome_empresa: str) -> str:
    """Retorna o texto entre parênteses do nome da empresa.

    Ex.: 'BETIM (NEPOS)' -> 'NEPOS'. Havendo mais de um par de parênteses,
    usa o último.

    Raises:
        ValueError: se não houver texto entre parênteses.
    """
    trechos = [
        t.strip()
        for t in re.findall(r"\(([^()]*)\)", str(nome_empresa or ""))
        if t.strip()
    ]
    if not trechos:
        raise ValueError(
            f"Origem não encontrada entre parênteses em '{nome_empresa}'."
        )
    return trechos[-1]


def _formas_pagto_candidatas(
    origem: str,
    caminho_db: Path = CAMINHO_BANCO_DADOS,
) -> list[str]:
    """Retorna as formas de pagamento da origem para CONVERSOR DE MOEDAS.

    Filtra tbl_FormaDePagamento por Origem = <origem> e
    Tipo = 'CONVERSOR DE MOEDAS' (sem diferenciar maiúsculas/minúsculas)
    e devolve a coluna "Forma de Pagamento", sem repetições.

    Raises:
        sqlite3.Error: se o banco não puder ser lido.
        ValueError: se nenhuma forma for encontrada para a origem.
    """
    origem_cf = origem.strip().casefold()
    tipo_cf = TIPO_FORMA_PAGTO.casefold()

    try:
        # Somente leitura: esta consulta nunca altera o banco.
        with closing(
            sqlite3.connect(f"{caminho_db.as_uri()}?mode=ro", uri=True)
        ) as conexao:
            linhas = conexao.execute(SQL_FORMAS_PAGTO).fetchall()
    except sqlite3.Error:
        logger.exception(
            "Falha ao ler tbl_FormaDePagamento em '%s'.", caminho_db
        )
        raise

    formas: list[str] = []
    for linha_origem, linha_tipo, forma in linhas:
        if forma is None:
            continue
        if (
            str(linha_origem).strip().casefold() == origem_cf
            and str(linha_tipo).strip().casefold() == tipo_cf
            and str(forma).strip() not in formas
        ):
            formas.append(str(forma).strip())

    if not formas:
        raise ValueError(
            "Nenhuma forma de pagamento em tbl_FormaDePagamento para "
            f"Origem='{origem}' e Tipo='{TIPO_FORMA_PAGTO}'."
        )

    logger.info("Formas de pagamento para %s: %s", origem, formas)
    return formas


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


def lancar_credito_conversor_moedas(
    driver: WebDriver,
    nome_empresa: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None = None,
    data_lancamento: date | None = None,
) -> None:
    """Cria um novo RPS Consolidado para 'Crédito conversor de moedas'.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados.
        nome_empresa: Nome da empresa (variável softcase), com a origem
            entre parênteses, ex.: 'BETIM (NEPOS)'.
        valor: Valor do lançamento.
        valor_taxa: Valor para o campo Total taxa.
        dias_comp: Valor para o campo Dias Comp.; se vier None/vazio,
            usa '0'.
        data_lancamento: Data do lançamento; padrão é D-1.

    Raises:
        ValueError: se o nome da empresa não tiver origem entre parênteses
            ou se a tabela não tiver forma de pagamento para a origem.
    """
    # Resolve a forma de pagamento antes de abrir o diálogo.
    origem = _extrair_origem(nome_empresa)
    formas_pagto = _formas_pagto_candidatas(origem)
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