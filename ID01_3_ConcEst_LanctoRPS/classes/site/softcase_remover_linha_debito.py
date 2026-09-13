"""Remoção de linhas duplicadas por "Forma de pagamento" na tabela de RPS.

Regra de negócio: quando a mesma "Forma de pagamento" (ex.: "DÉBITO
VISA") aparece em mais de uma linha da tabela, mantém-se apenas a
linha de MAIOR valor na coluna "Valor" e exclui-se as demais (via
botão "Ações" -> "Excluir" de cada linha), repetindo até restar no
máximo uma linha por forma de pagamento.

Requisitos:
    - selenium >= 4.x
    - Um WebDriver (Chrome/Edge) já na tela com a tabela de RPS visível.

Observação importante:
    O HTML fornecido para o menu de ações mostra apenas "Editar" e
    "Excluir". Se ao clicar em "Excluir" a tela abrir um modal de
    confirmação, será necessário adicionar uma etapa extra para
    confirmar (não implementada aqui por falta dessa informação).

Uso típico:
    from selenium import webdriver
    from remover_duplicados_forma_pagamento import (
        remover_duplicatas_forma_pagamento,
    )

    driver = webdriver.Chrome()
    # ... já navegado até a tela com a tabela ...

    remover_duplicatas_forma_pagamento(
        driver=driver,
        xpath_tabela=(
            "/html/body/div[1]/div/div[3]/div[2]/div/div[5]/div[3]/table"
        ),
    )
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

CSS_ITENS_MENU = "div.mud-list-item"

# Índices de coluna (1-based, conforme <td> da tabela):
# 1=Ações, 2=Empresa, 3=Número, 4=Data, 5=Forma de pagamento, 6=Valor
TD_FORMA_PAGAMENTO = 5
TD_VALOR = 6


class ExclusaoDuplicadosError(Exception):
    """Erro genérico ao remover linhas duplicadas da tabela de RPS."""


def _converter_valor(texto_valor: str) -> float:
    """Converte o texto da coluna "Valor" para float.

    Aceita tanto números simples ("1008") quanto formato brasileiro
    com separador de milhar e decimal ("1.008,00").

    Args:
        texto_valor: texto bruto da célula de valor.

    Returns:
        Valor numérico correspondente.

    Raises:
        ExclusaoDuplicadosError: se o texto não puder ser convertido.
    """
    texto_limpo = texto_valor.replace("R$", "").strip()
    if "," in texto_limpo:
        texto_limpo = texto_limpo.replace(".", "").replace(",", ".")
    try:
        return float(texto_limpo)
    except ValueError as exc:
        raise ExclusaoDuplicadosError(
            f"Não foi possível converter o valor '{texto_valor}' para número."
        ) from exc


def ler_linhas_tabela(
    driver: WebDriver,
    xpath_tabela: str,
    timeout: int = TIMEOUT_PADRAO,
) -> list[dict]:
    """Lê todas as linhas da tabela, retornando índice, forma e valor.

    Args:
        driver: instância do WebDriver com a tabela visível.
        xpath_tabela: XPath do elemento `<table>`.
        timeout: tempo máximo de espera, em segundos.

    Returns:
        Lista de dicionários com as chaves `indice` (posição 1-based
        do `<tr>` dentro do `<tbody>`), `forma_pagamento` e `valor`.

    Raises:
        ExclusaoDuplicadosError: se a tabela não for encontrada.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.XPATH, f"{xpath_tabela}/tbody/tr"))
        )
        linhas_web = driver.find_elements(By.XPATH, f"{xpath_tabela}/tbody/tr")
    except TimeoutException as exc:
        raise ExclusaoDuplicadosError(
            "Não foi possível localizar as linhas da tabela a tempo."
        ) from exc

    linhas: list[dict] = []
    for indice, linha in enumerate(linhas_web, start=1):
        forma_pagamento = linha.find_element(
            By.XPATH, f"td[{TD_FORMA_PAGAMENTO}]"
        ).text.strip()
        valor_texto = linha.find_element(By.XPATH, f"td[{TD_VALOR}]").text.strip()
        linhas.append(
            {
                "indice": indice,
                "forma_pagamento": forma_pagamento,
                "valor": _converter_valor(valor_texto),
            }
        )
    return linhas


def excluir_linha(
    driver: WebDriver,
    xpath_tabela: str,
    indice_linha: int,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Abre o menu "Ações" da linha informada e clica em "Excluir".

    Espera a linha (`<tr>`) ficar obsoleta (stale) após a exclusão,
    confirmando que a tabela foi atualizada.

    Args:
        driver: instância do WebDriver com a tabela visível.
        xpath_tabela: XPath do elemento `<table>`.
        indice_linha: posição 1-based do `<tr>` dentro do `<tbody>`.
        timeout: tempo máximo de espera, em segundos.

    Raises:
        ExclusaoDuplicadosError: se o botão "Ações", o menu ou a
            opção "Excluir" não forem encontrados a tempo.
    """
    xpath_linha = f"{xpath_tabela}/tbody/tr[{indice_linha}]"
    xpath_botao_acoes = f"{xpath_linha}/td[1]/div/button"

    try:
        linha_elemento: WebElement = driver.find_element(By.XPATH, xpath_linha)
        botao_acoes = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath_botao_acoes))
        )
        botao_acoes.click()

        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_ITENS_MENU))
        )
        itens_menu = driver.find_elements(By.CSS_SELECTOR, CSS_ITENS_MENU)
        item_excluir = next(
            item for item in itens_menu if item.text.strip() == "Excluir"
        )
        item_excluir.click()

        WebDriverWait(driver, timeout).until(EC.staleness_of(linha_elemento))
    except (TimeoutException, StopIteration, NoSuchElementException) as exc:
        raise ExclusaoDuplicadosError(
            f"Não foi possível excluir a linha {indice_linha} da tabela."
        ) from exc
    except StaleElementReferenceException:
        # A linha já ficou obsoleta antes mesmo da checagem explícita —
        # a exclusão foi bem-sucedida.
        pass

    logger.info("Linha %s excluída com sucesso.", indice_linha)


def remover_duplicatas_forma_pagamento(
    driver: WebDriver,
    xpath_tabela: str,
    filtro_prefixo: str | None = "DÉBITO",
    timeout: int = TIMEOUT_PADRAO,
    max_iteracoes: int = MAX_ITERACOES_PADRAO,
) -> None:
    """Remove linhas duplicadas de forma de pagamento, mantendo o maior valor.

    Enquanto houver mais de uma linha com a mesma "Forma de pagamento"
    (restrito ao prefixo `filtro_prefixo`, quando informado), exclui a
    linha de menor "Valor" dentro daquele grupo. Repete até restar no
    máximo uma linha por forma de pagamento.

    Args:
        driver: instância do WebDriver com a tabela visível.
        xpath_tabela: XPath do elemento `<table>`.
        filtro_prefixo: se informado, só considera duplicidade entre
            formas de pagamento cujo texto comece com esse prefixo
            (comparação sem diferenciar maiúsculas/minúsculas). Padrão:
            `"DÉBITO"`, conforme o cenário observado na tela. Passe
            `None` para considerar duplicidade em qualquer forma de
            pagamento.
        timeout: tempo máximo de espera por elemento, em segundos.
        max_iteracoes: limite de segurança de exclusões, para evitar
            loop infinito em caso de comportamento inesperado da tela.

    Raises:
        ExclusaoDuplicadosError: se o limite de iterações for atingido
            sem eliminar todas as duplicidades, ou se alguma exclusão
            falhar.
    """
    for _ in range(max_iteracoes):
        linhas = ler_linhas_tabela(driver, xpath_tabela, timeout)

        grupos: dict[str, list[dict]] = {}
        for linha in linhas:
            if filtro_prefixo and not linha["forma_pagamento"].upper().startswith(
                filtro_prefixo.upper()
            ):
                continue
            grupos.setdefault(linha["forma_pagamento"], []).append(linha)

        grupo_duplicado = next(
            (grupo for grupo in grupos.values() if len(grupo) > 1), None
        )
        if grupo_duplicado is None:
            logger.info("Nenhuma forma de pagamento duplicada restante.")
            return

        linha_menor_valor = min(grupo_duplicado, key=lambda linha: linha["valor"])
        logger.info(
            "Forma '%s' duplicada — excluindo linha %s (valor %s), a de menor valor.",
            linha_menor_valor["forma_pagamento"],
            linha_menor_valor["indice"],
            linha_menor_valor["valor"],
        )
        excluir_linha(driver, xpath_tabela, linha_menor_valor["indice"], timeout)

    raise ExclusaoDuplicadosError(
        f"Limite de {max_iteracoes} iterações atingido sem eliminar todas as "
        "duplicidades de forma de pagamento."
    )