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
import re

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
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 10
MAX_ITERACOES_PADRAO = 100

CSS_TABELA_PADRAO = "table.mud-table-root"
CSS_LINHAS = "tbody.mud-table-body > tr.mud-table-row"
CSS_BOTAO_ACOES = 'td[data-label="Actions"] button'
CSS_ITENS_MENU = "div.mud-list-item"

RETULO_COLUNA_ACOES = "Actions"

COLUNAS_OBRIGATORIAS: tuple[str, ...] = (
    "SAP Doc. (AUART)",
    "SAP Pgto. Id.(KUNNR)",
)


def _normalizar_rotulo(rotulo: str) -> str:
    """Normaliza um rótulo de coluna (sem espaços e sem diferença de caixa)."""
    return re.sub(r"\s+", "", rotulo).casefold()


_ROTULOS_OBRIGATORIOS_NORMALIZADOS: frozenset[str] = frozenset(
    _normalizar_rotulo(r) for r in COLUNAS_OBRIGATORIAS
)


def _validar_colunas_obrigatorias(
    driver: WebDriver,
    seletor_tabela: str,
) -> None:
    """Garante que as colunas obrigatórias existem na tabela.

    Args:
        driver: instância do WebDriver com a tabela visível.
        seletor_tabela: seletor CSS da `<table>`.

    Raises:
        RemocaoLinhasVaziasError: se alguma coluna obrigatória não for
            encontrada (ex.: cabeçalho alterado no portal).
    """
    celulas = driver.find_elements(
        By.CSS_SELECTOR, f"{seletor_tabela} tbody td[data-label]"
    )
    rotulos_encontrados = {
        _normalizar_rotulo(c.get_attribute("data-label") or "")
        for c in celulas
    }

    faltando = [
        coluna
        for coluna in COLUNAS_OBRIGATORIAS
        if _normalizar_rotulo(coluna) not in rotulos_encontrados
    ]
    if faltando:
        raise RemocaoLinhasVaziasError(
            "Coluna(s) obrigatória(s) não encontrada(s) na tabela: "
            f"{', '.join(faltando)}."
        )


class RemocaoLinhasVaziasError(Exception):
    """Erro genérico ao remover linhas com célula vazia da tabela."""


# def _rotulos_celulas_vazias(linha: WebElement) -> list[str]:
#     """Retorna os rótulos (`data-label`) das colunas de dado vazias na linha.

#     A coluna de ações ("Actions") é ignorada, pois não é um dado —
#     é o botão de operações da linha.

#     Args:
#         linha: elemento `<tr>` da tabela.

#     Returns:
#         Lista de rótulos de coluna cujo texto está vazio nessa linha.
#         Lista vazia significa que a linha não tem célula em branco.
#     """
#     celulas = linha.find_elements(By.TAG_NAME, "td")
#     rotulos_vazios = []
#     for celula in celulas:
#         rotulo = celula.get_attribute("data-label") or ""
#         if rotulo == RETULO_COLUNA_ACOES:
#             continue
#         if celula.text.strip() == "":
#             rotulos_vazios.append(rotulo)
#     return rotulos_vazios

def _rotulos_celulas_vazias(
    linha: WebElement,
    rotulos_normalizados: frozenset[str] | None = None,
) -> list[str]:
    """Retorna os rótulos (`data-label`) das colunas de dado vazias na linha.

    A coluna de ações ("Actions") é ignorada, pois não é um dado —
    é o botão de operações da linha.

    Args:
        linha: elemento `<tr>` da tabela.
        rotulos_normalizados: se informado, considera apenas as colunas
            cujo rótulo normalizado esteja neste conjunto. Se `None`,
            considera todas as colunas de dado.

    Returns:
        Lista de rótulos de coluna (entre as consideradas) cujo texto
        está vazio nessa linha. Lista vazia significa que não há
        célula relevante em branco.
    """
    celulas = linha.find_elements(By.TAG_NAME, "td")
    rotulos_vazios = []
    for celula in celulas:
        rotulo = celula.get_attribute("data-label") or ""
        if rotulo == RETULO_COLUNA_ACOES:
            continue
        if (
            rotulos_normalizados is not None
            and _normalizar_rotulo(rotulo) not in rotulos_normalizados
        ):
            continue
        if celula.text.strip() == "":
            rotulos_vazios.append(rotulo)
    return rotulos_vazios

CSS_DIALOGO_EXCLUSAO: str = "div.mud-dialog[role='dialog']"
CSS_BOTAO_CONFIRMAR_EXCLUSAO: str = (
    f"{CSS_DIALOGO_EXCLUSAO} .mud-dialog-actions "
    "button.mud-button-filled-error"
)


def _confirmar_exclusao(driver: WebDriver, timeout: int) -> None:
    """Clica em 'Confirmar' no diálogo 'Confirmar exclusão'.

    O `id` do diálogo é gerado dinamicamente pelo Blazor, então o botão
    é localizado pelas classes do MudBlazor. Após o clique, espera o
    diálogo fechar para garantir que a exclusão foi processada.

    Args:
        driver: instância do WebDriver com o diálogo aberto.
        timeout: tempo máximo de espera por elemento, em segundos.

    Raises:
        RemocaoLinhasVaziasError: se o diálogo não aparecer ou não
            fechar dentro do tempo limite.
    """
    espera = WebDriverWait(driver, timeout)
    try:
        botao = espera.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, CSS_BOTAO_CONFIRMAR_EXCLUSAO)
            )
        )
        botao.click()
        espera.until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, CSS_DIALOGO_EXCLUSAO)
            )
        )
    except TimeoutException as erro:
        raise RemocaoLinhasVaziasError(
            "Diálogo 'Confirmar exclusão' não apareceu ou não fechou "
            "após clicar em Confirmar."
        ) from erro


def _excluir_linha(
    driver: WebDriver,
    linha: WebElement,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Abre o menu "Ações" da linha, clica em "Excluir" e confirma.

    Args:
        driver: instância do WebDriver com a tabela visível.
        linha: elemento `<tr>` da linha a excluir.
        timeout: tempo máximo de espera, em segundos.

    Raises:
        RemocaoLinhasVaziasError: se o botão "Ações", o menu, a opção
            "Excluir" ou o diálogo de confirmação não forem
            encontrados a tempo.
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

        _confirmar_exclusao(driver, timeout)

        WebDriverWait(driver, timeout).until(EC.staleness_of(linha))
    except (
        TimeoutException,
        StopIteration,
        NoSuchElementException,
        StaleElementReferenceException,
    ) as exc:
        raise RemocaoLinhasVaziasError(
            "Não foi possível excluir a linha com coluna obrigatória vazia."
        ) from exc

    #     WebDriverWait(driver, timeout).until(EC.staleness_of(linha))
    # except (TimeoutException, StopIteration, NoSuchElementException) as exc:
    #     raise RemocaoLinhasVaziasError(
    #         "Não foi possível excluir a linha com coluna obrigatória vazia."
    #     ) from exc
    except StaleElementReferenceException:
        # A linha já ficou obsoleta antes mesmo da checagem explícita —
        # a exclusão foi bem-sucedida.
        pass


# def _excluir_linha(
#     driver: WebDriver,
#     linha: WebElement,
#     timeout: int = TIMEOUT_PADRAO,
# ) -> None:
#     """Abre o menu "Ações" da linha informada e clica em "Excluir".

#     Args:
#         driver: instância do WebDriver com a tabela visível.
#         linha: elemento `<tr>` da linha a excluir.
#         timeout: tempo máximo de espera, em segundos.

#     Raises:
#         RemocaoLinhasVaziasError: se o botão "Ações", o menu ou a
#             opção "Excluir" não forem encontrados a tempo.
#     """
#     try:
#         botao_acoes = linha.find_element(By.CSS_SELECTOR, CSS_BOTAO_ACOES)
#         botao_acoes.click()

#         WebDriverWait(driver, timeout).until(
#             EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_ITENS_MENU))
#         )
#         itens_menu = driver.find_elements(By.CSS_SELECTOR, CSS_ITENS_MENU)
#         item_excluir = next(
#             item for item in itens_menu if item.text.strip() == "Excluir"
#         )
#         item_excluir.click()

#         WebDriverWait(driver, timeout).until(EC.staleness_of(linha))
#     except (TimeoutException, StopIteration, NoSuchElementException) as exc:
#         raise RemocaoLinhasVaziasError(
#             "Não foi possível excluir a linha com célula vazia."
#         ) from exc
#     except StaleElementReferenceException:
#         # A linha já ficou obsoleta antes mesmo da checagem explícita —
#         # a exclusão foi bem-sucedida.
#         pass


# def remover_linhas_com_celula_vazia(
#     driver: WebDriver,
#     seletor_tabela: str = CSS_TABELA_PADRAO,
#     timeout: int = TIMEOUT_PADRAO,
#     max_iteracoes: int = MAX_ITERACOES_PADRAO,
# ) -> None:
#     """Exclui todas as linhas da tabela que tenham alguma célula vazia.

#     Repete a busca a cada exclusão (os índices/elementos mudam depois
#     de remover uma linha), até não restar nenhuma linha com célula em
#     branco.

#     Args:
#         driver: instância do WebDriver com a tabela visível.
#         seletor_tabela: seletor CSS da `<table>`. Padrão:
#             `"table.mud-table-root"`.
#         timeout: tempo máximo de espera por elemento, em segundos.
#         max_iteracoes: limite de segurança de exclusões, para evitar
#             loop infinito em caso de comportamento inesperado da tela.

#     Raises:
#         RemocaoLinhasVaziasError: se o limite de iterações for
#             atingido sem eliminar todas as linhas com célula vazia,
#             ou se alguma exclusão falhar.
#     """
#     WebDriverWait(driver, timeout).until(
#         EC.visibility_of_element_located((By.CSS_SELECTOR, seletor_tabela))
#     )

#     for _ in range(max_iteracoes):
#         linhas = driver.find_elements(
#             By.CSS_SELECTOR, f"{seletor_tabela} {CSS_LINHAS}"
#         )

#         linha_alvo: WebElement | None = None
#         rotulos_vazios_alvo: list[str] = []
#         for linha in linhas:
#             rotulos_vazios = _rotulos_celulas_vazias(linha)
#             if rotulos_vazios:
#                 linha_alvo = linha
#                 rotulos_vazios_alvo = rotulos_vazios
#                 break

#         if linha_alvo is None:
#             logger.info("Nenhuma linha com célula vazia restante na tabela.")
#             return

#         logger.info(
#             "Excluindo linha com célula(s) vazia(s) em: %s.",
#             ", ".join(rotulos_vazios_alvo),
#         )
#         _excluir_linha(driver, linha_alvo, timeout)

#     raise RemocaoLinhasVaziasError(
#         f"Limite de {max_iteracoes} iterações atingido sem eliminar todas "
#         "as linhas com célula vazia."
#     )

def remover_linhas_com_celula_vazia(
    driver: WebDriver,
    seletor_tabela: str = CSS_TABELA_PADRAO,
    timeout: int = TIMEOUT_PADRAO,
    max_iteracoes: int = MAX_ITERACOES_PADRAO,
) -> None:
    """Exclui as linhas em que 'SAP Doc. (AUART)' ou
    'SAP Pgto. Id.(KUNNR)' estejam vazias.

    Células vazias em outras colunas são ignoradas. Repete a busca a
    cada exclusão (os elementos mudam depois de remover uma linha),
    até não restar nenhuma linha com uma dessas duas colunas em branco.

    Args:
        driver: instância do WebDriver com a tabela visível.
        seletor_tabela: seletor CSS da `<table>`. Padrão:
            `"table.mud-table-root"`.
        timeout: tempo máximo de espera por elemento, em segundos.
        max_iteracoes: limite de segurança de exclusões, para evitar
            loop infinito em caso de comportamento inesperado da tela.

    Raises:
        RemocaoLinhasVaziasError: se as colunas obrigatórias não
            existirem na tabela, se o limite de iterações for atingido
            sem eliminar todas as linhas inválidas, ou se alguma
            exclusão falhar.
    """
    WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, seletor_tabela))
    )
    _validar_colunas_obrigatorias(driver, seletor_tabela)

    for _ in range(max_iteracoes):
        linhas = driver.find_elements(
            By.CSS_SELECTOR, f"{seletor_tabela} {CSS_LINHAS}"
        )

        linha_alvo: WebElement | None = None
        rotulos_vazios_alvo: list[str] = []
        for linha in linhas:
            rotulos_vazios = _rotulos_celulas_vazias(
                linha, _ROTULOS_OBRIGATORIOS_NORMALIZADOS
            )
            if rotulos_vazios:
                linha_alvo = linha
                rotulos_vazios_alvo = rotulos_vazios
                break

        if linha_alvo is None:
            logger.info(
                "Nenhuma linha com %s vazia restante na tabela.",
                " ou ".join(COLUNAS_OBRIGATORIAS),
            )
            return

        logger.info(
            "Excluindo linha com coluna(s) obrigatória(s) vazia(s): %s.",
            ", ".join(rotulos_vazios_alvo),
        )
        _excluir_linha(driver, linha_alvo, timeout)

    raise RemocaoLinhasVaziasError(
        f"Limite de {max_iteracoes} iterações atingido sem eliminar todas "
        "as linhas com SAP Doc. (AUART) ou SAP Pgto. Id.(KUNNR) vazios."
    )