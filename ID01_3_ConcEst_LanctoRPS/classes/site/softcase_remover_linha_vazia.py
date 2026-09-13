"""Remoção de linhas com célula vazia na tabela de RPS.

Agora que temos o HTML real da tabela (com `data-label` em cada
`<td>`), a leitura fica mais robusta do que por posição de coluna:
cada célula é identificada pelo seu rótulo (ex.: "Empresa", "Numero",
"Forma de pagamento", "Valor" etc.), ignorando a coluna de ações
("Actions"), que não é dado e sim o botão de operações da linha.

Regra: se qualquer célula de dado de uma linha estiver vazia (texto
em branco), a linha é excluída via botão "Ações" -> "Excluir".

Requisitos:
    - selenium >= 4.x
    - Um WebDriver (Chrome/Edge) já na tela com a tabela visível.

Uso típico:
    from selenium import webdriver
    from remover_linhas_celula_vazia import remover_linhas_com_celula_vazia

    driver = webdriver.Chrome()
    # ... já navegado até a tela com a tabela ...

    remover_linhas_com_celula_vazia(driver)
"""

import logging

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 10
MAX_ITERACOES_PADRAO = 100

CSS_TABELA_PADRAO = "table.mud-table-root"
CSS_LINHAS = "tbody.mud-table-body > tr.mud-table-row"
CSS_BOTAO_ACOES = 'td[data-label="Actions"] button'
CSS_ITENS_MENU = "div.mud-list-item"

RETULO_COLUNA_ACOES = "Actions"


class RemocaoLinhasVaziasError(Exception):
    """Erro genérico ao remover linhas com célula vazia da tabela."""


def _rotulos_celulas_vazias(linha: WebElement) -> list[str]:
    """Retorna os rótulos (`data-label`) das colunas de dado vazias na linha.

    A coluna de ações ("Actions") é ignorada, pois não é um dado —
    é o botão de operações da linha.

    Args:
        linha: elemento `<tr>` da tabela.

    Returns:
        Lista de rótulos de coluna cujo texto está vazio nessa linha.
        Lista vazia significa que a linha não tem célula em branco.
    """
    celulas = linha.find_elements(By.TAG_NAME, "td")
    rotulos_vazios = []
    for celula in celulas:
        rotulo = celula.get_attribute("data-label") or ""
        if rotulo == RETULO_COLUNA_ACOES:
            continue
        if celula.text.strip() == "":
            rotulos_vazios.append(rotulo)
    return rotulos_vazios


def _excluir_linha(
    driver: WebDriver,
    linha: WebElement,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Abre o menu "Ações" da linha informada e clica em "Excluir".

    Args:
        driver: instância do WebDriver com a tabela visível.
        linha: elemento `<tr>` da linha a excluir.
        timeout: tempo máximo de espera, em segundos.

    Raises:
        RemocaoLinhasVaziasError: se o botão "Ações", o menu ou a
            opção "Excluir" não forem encontrados a tempo.
    """
    try:
        botao_acoes = linha.find_element(By.CSS_SELECTOR, CSS_BOTAO_ACOES)
        botao_acoes.click()

        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_ITENS_MENU))
        )
        itens_menu = driver.find_elements(By.CSS_SELECTOR, CSS_ITENS_MENU)
        item_excluir = next(
            item for item in itens_menu if item.text.strip() == "Excluir"
        )
        item_excluir.click()

        WebDriverWait(driver, timeout).until(EC.staleness_of(linha))
    except (TimeoutException, StopIteration, NoSuchElementException) as exc:
        raise RemocaoLinhasVaziasError(
            "Não foi possível excluir a linha com célula vazia."
        ) from exc
    except StaleElementReferenceException:
        # A linha já ficou obsoleta antes mesmo da checagem explícita —
        # a exclusão foi bem-sucedida.
        pass


def remover_linhas_com_celula_vazia(
    driver: WebDriver,
    seletor_tabela: str = CSS_TABELA_PADRAO,
    timeout: int = TIMEOUT_PADRAO,
    max_iteracoes: int = MAX_ITERACOES_PADRAO,
) -> None:
    """Exclui todas as linhas da tabela que tenham alguma célula vazia.

    Repete a busca a cada exclusão (os índices/elementos mudam depois
    de remover uma linha), até não restar nenhuma linha com célula em
    branco.

    Args:
        driver: instância do WebDriver com a tabela visível.
        seletor_tabela: seletor CSS da `<table>`. Padrão:
            `"table.mud-table-root"`.
        timeout: tempo máximo de espera por elemento, em segundos.
        max_iteracoes: limite de segurança de exclusões, para evitar
            loop infinito em caso de comportamento inesperado da tela.

    Raises:
        RemocaoLinhasVaziasError: se o limite de iterações for
            atingido sem eliminar todas as linhas com célula vazia,
            ou se alguma exclusão falhar.
    """
    WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, seletor_tabela))
    )

    for _ in range(max_iteracoes):
        linhas = driver.find_elements(
            By.CSS_SELECTOR, f"{seletor_tabela} {CSS_LINHAS}"
        )

        linha_alvo: WebElement | None = None
        rotulos_vazios_alvo: list[str] = []
        for linha in linhas:
            rotulos_vazios = _rotulos_celulas_vazias(linha)
            if rotulos_vazios:
                linha_alvo = linha
                rotulos_vazios_alvo = rotulos_vazios
                break

        if linha_alvo is None:
            logger.info("Nenhuma linha com célula vazia restante na tabela.")
            return

        logger.info(
            "Excluindo linha com célula(s) vazia(s) em: %s.",
            ", ".join(rotulos_vazios_alvo),
        )
        _excluir_linha(driver, linha_alvo, timeout)

    raise RemocaoLinhasVaziasError(
        f"Limite de {max_iteracoes} iterações atingido sem eliminar todas "
        "as linhas com célula vazia."
    )