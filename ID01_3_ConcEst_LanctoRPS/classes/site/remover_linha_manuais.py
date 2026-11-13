"""Exclusão de RPS Consolidados cuja forma de pagamento contém 'MANUAL'."""

import logging
import unicodedata

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 15
PALAVRA_CHAVE = "MANUAL"

XPATH_LINHAS = "//table[contains(@class,'mud-table-root')]/tbody/tr"
XPATH_CELULA_FORMA = ".//td[@data-label='Forma de pagamento']"
XPATH_BOTAO_ACOES = ".//td[@data-label='Actions']//button"
XPATH_ITEM_EXCLUIR = (
    "//div[contains(@class,'mud-popover-open')]"
    "//*[contains(@class,'mud-menu-item')][contains(.,'Excluir')]"
)
XPATH_DIALOGO = (
    "//div[@role='dialog'][.//h6[contains(.,'Confirmar exclusão')]]"
)
XPATH_BOTAO_CONFIRMAR = (
    f"{XPATH_DIALOGO}//button[contains(@class,'mud-button-filled-error')]"
)


def _normalizar(texto: str) -> str:
    """Remove acentos e converte para maiúsculas."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.upper().strip()


def _linha_e_manual(linha: WebElement) -> bool:
    """Indica se a forma de pagamento da linha contém 'MANUAL'."""
    celula = linha.find_element(By.XPATH, XPATH_CELULA_FORMA)
    return PALAVRA_CHAVE in _normalizar(celula.text)


def _buscar_primeira_linha_manual(driver: WebDriver) -> WebElement | None:
    """Retorna a primeira linha com forma de pagamento 'MANUAL', se houver."""
    for linha in driver.find_elements(By.XPATH, XPATH_LINHAS):
        try:
            if _linha_e_manual(linha):
                return linha
        except Exception:  # linha de rodapé/sem coluna
            continue
    return None


def _excluir_linha(driver: WebDriver, linha: WebElement) -> None:
    """Executa o fluxo AÇÕES -> EXCLUIR -> CONFIRMAR para uma linha."""
    espera = WebDriverWait(driver, TIMEOUT_PADRAO)

    botao_acoes = linha.find_element(By.XPATH, XPATH_BOTAO_ACOES)
    espera.until(EC.element_to_be_clickable(botao_acoes)).click()

    item_excluir = espera.until(
        EC.element_to_be_clickable((By.XPATH, XPATH_ITEM_EXCLUIR))
    )
    item_excluir.click()

    espera.until(EC.visibility_of_element_located((By.XPATH, XPATH_DIALOGO)))
    espera.until(
        EC.element_to_be_clickable((By.XPATH, XPATH_BOTAO_CONFIRMAR))
    ).click()

    # Aguarda o diálogo fechar antes de reescanear a tabela
    espera.until(
        EC.invisibility_of_element_located((By.XPATH, XPATH_DIALOGO))
    )


def excluir_linhas_manuais(
    driver: WebDriver,
    dry_run: bool = False,
    limite: int = 200,
) -> int:
    """Exclui as linhas cuja 'Forma de pagamento' contém 'MANUAL'.

    Args:
        driver: Instância do Selenium já na tela RPS Consolidados (aba Ativos).
        dry_run: Se True, apenas registra no log o que seria excluído.
        limite: Teto de exclusões por execução (proteção contra loop infinito).

    Returns:
        Quantidade de linhas excluídas (ou encontradas, se dry_run).
    """
    excluidas = 0

    while excluidas < limite:
        linha = _buscar_primeira_linha_manual(driver)
        if linha is None:
            break

        numero = linha.find_element(
            By.XPATH, ".//td[@data-label='Numero']"
        ).text
        forma = linha.find_element(By.XPATH, XPATH_CELULA_FORMA).text

        if dry_run:
            logger.info("[DRY-RUN] Seria excluído: nº %s (%s)", numero, forma)
            return _contar_manuais(driver)

        logger.info("Excluindo RPS nº %s (%s)", numero, forma)
        try:
            _excluir_linha(driver, linha)
        except TimeoutException:
            logger.exception("Timeout ao excluir RPS nº %s", numero)
            raise
        excluidas += 1

    logger.info("Total de linhas excluídas: %d", excluidas)
    return excluidas


def _contar_manuais(driver: WebDriver) -> int:
    """Conta linhas 'MANUAL' (usado no dry_run)."""
    total = 0
    for linha in driver.find_elements(By.XPATH, XPATH_LINHAS):
        try:
            if _linha_e_manual(linha):
                total += 1
        except Exception:
            continue
    return total