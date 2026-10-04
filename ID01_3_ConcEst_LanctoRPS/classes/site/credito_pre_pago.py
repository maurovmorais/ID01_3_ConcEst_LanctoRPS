"""Lançamento de RPS Consolidado para forma de pagamento 'Crédito pré-pago'."""

import logging
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
PREFIXO_FORMA_PAGTO = "CRÉDITO"

# As formas de pagamento válidas (inclusive variações de texto, como
# 'Crédito Elo Cr?dito') vêm da tabela tbl_FormaDePagamento do banco.
CAMINHO_BANCO_DADOS = Path(
    r"C:\Armazenamento\ID01_2_ConcEst_TratarDados\Banco Dados\banco_dados.db"
)
SQL_FORMAS_PAGTO = (
    'SELECT DISTINCT "Forma de Pagamento" FROM tbl_FormaDePagamento '
    'WHERE "Forma de Pagamento" IS NOT NULL'
)
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


def _formas_pagto_candidatas(
    bandeira_cartao: str,
    caminho_db: Path = CAMINHO_BANCO_DADOS,
) -> list[str]:
    """Retorna os textos aceitos para a forma de pagamento da bandeira.

    Consulta a coluna "Forma de Pagamento" de tbl_FormaDePagamento e mantém
    as formas que começam com 'CRÉDITO <bandeira>' (sem diferenciar
    maiúsculas/minúsculas). O texto exato vem primeiro; as variações vêm
    depois, das mais curtas para as mais longas.

    A filtragem é feita em Python porque o LIKE do SQLite não ignora
    maiúsculas/minúsculas em caracteres acentuados (ex.: 'É' x 'é').

    Se o banco não puder ser lido ou nenhuma forma for encontrada, usa
    o texto padrão 'CRÉDITO <bandeira>'.
    """
    padrao = f"{PREFIXO_FORMA_PAGTO} {bandeira_cartao}"
    padrao_cf = padrao.casefold()

    try:
        # Somente leitura: esta consulta nunca altera o banco.
        with closing(
            sqlite3.connect(f"{caminho_db.as_uri()}?mode=ro", uri=True)
        ) as conexao:
            linhas = conexao.execute(SQL_FORMAS_PAGTO).fetchall()
    except sqlite3.Error:
        logger.exception(
            "Falha ao ler tbl_FormaDePagamento em '%s'; usando '%s'.",
            caminho_db,
            padrao,
        )
        return [padrao]

    formas: list[str] = []
    for (forma,) in linhas:
        texto = str(forma).strip()
        if texto.casefold().startswith(padrao_cf) and texto not in formas:
            formas.append(texto)

    formas.sort(key=lambda f: (f.casefold() != padrao_cf, len(f)))
    if not formas:
        logger.warning("Nenhuma forma '%s' na tabela; usando o padrão.", padrao)
        return [padrao]

    logger.info("Formas de pagamento candidatas: %s", formas)
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