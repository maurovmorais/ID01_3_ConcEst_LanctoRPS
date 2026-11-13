"""Edita um RPS Consolidado existente ou cria um NOVO.

Fluxo (uma única regra para todas as formas de pagamento):

1. Filtra a forma de pagamento na tela de pesquisa.
2. Se a grade retornar uma ou mais linhas, compara ``dias_comp`` (fila)
   com a coluna "Dias Comp." de cada linha, da primeira para a última.
   Na primeira linha igual, abre Ações > Editar e atualiza o RPS.
3. Se a pesquisa não retornar dados, ou nenhuma linha tiver o mesmo
   ``dias_comp``, clica em NOVO e cadastra o lançamento
   (``criar_novo_lancto``).

Colocar em ``ID01_3_ConcEst_LanctoRPS/classes/site/lancamento_rps.py``.
"""

from __future__ import annotations

import logging
from time import sleep

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ID01_3_ConcEst_LanctoRPS.classes.site.criar_novo_lancto import (
    criar_novo_lancto,
)
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import (
    clicar_editar,
    editar_rps_consolidado,
    filtrar_forma_pagto,
)
# Esta é a classe que filtrar_forma_pagto realmente propaga quando a
# pesquisa não traz dados (as cópias em softcase.py / lancamento_tag.py
# são classes diferentes e nunca casam com o ``except``).
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_forma_pagamento import (
    AutocompleteSelecaoError,
)
from ID01_3_ConcEst_LanctoRPS.classes.utils.Log import Log

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 15
DIAS_COMP_PADRAO = "0"

XPATH_TBODY = (
    "/html/body/div[1]/div/div[3]/div[2]/div/div[5]/div[3]/table/tbody"
)
XPATH_LINHAS = f"{XPATH_TBODY}/tr"
# A coluna é localizada pelo data-label (equivale ao td[12] e não quebra
# se a ordem das colunas mudar).
XPATH_CELULAS_DIAS_COMP = (
    f"{XPATH_LINHAS}/td[@data-label='Dias Comp.']"
)


def _xpath_botao_acoes(indice: int) -> str:
    """XPath do botão Ações da linha ``indice`` (base 1)."""
    return f"{XPATH_LINHAS}[{indice}]/td[1]/div/button"


def _normalizar_dias_comp(valor: str | int | float | None) -> str:
    """Normaliza Dias Comp. para comparação ('2', 2 e '2.0' viram '2').

    Vazio/None vira '0', o mesmo padrão usado na criação de novo RPS.
    """
    texto = "" if valor is None else str(valor).strip()
    if not texto:
        return DIAS_COMP_PADRAO
    try:
        return str(int(float(texto.replace(",", "."))))
    except ValueError:
        return texto.casefold()


def _pesquisar_forma_pagto(
    driver: WebDriver, forma_pagamento: str, bandeira: str | None
) -> bool:
    """Filtra a forma de pagamento; retorna False se não vier nenhum dado.

    Qualquer outra falha (timeout, elemento ausente...) é propagada de
    propósito: tratá-la como "sem dados" criaria um RPS duplicado.
    """
    try:
        filtrar_forma_pagto(
            driver=driver, forma_pgto=forma_pagamento, bandeira=bandeira
        )
    except AutocompleteSelecaoError:
        Log.write_log(
            f"Forma de pagamento '{forma_pagamento}' sem dados na pesquisa."
        )
        return False
    return True


def _ler_dias_comp_das_linhas(driver: WebDriver) -> list[str]:
    """Lê a coluna Dias Comp. de todas as linhas da grade, em ordem."""
    WebDriverWait(driver, TIMEOUT_PADRAO).until(
        EC.presence_of_element_located((By.XPATH, XPATH_LINHAS))
    )
    for _ in range(3):
        try:
            celulas = driver.find_elements(By.XPATH, XPATH_CELULAS_DIAS_COMP)
            return [
                (c.get_attribute("textContent") or "").strip()
                for c in celulas
            ]
        except StaleElementReferenceException:
            sleep(0.5)  # grade recarregando; tenta de novo
    raise StaleElementReferenceException(
        "Grade instável ao ler a coluna Dias Comp."
    )


def _localizar_linha_por_dias_comp(
    dias_comp: str | int | float | None, dias_na_grade: list[str]
) -> int | None:
    """Índice (base 1) da primeira linha com o mesmo Dias Comp., ou None."""
    alvo = _normalizar_dias_comp(dias_comp)
    for indice, texto in enumerate(dias_na_grade, start=1):
        if _normalizar_dias_comp(texto) == alvo:
            return indice
    return None


def _abrir_edicao_da_linha(driver: WebDriver, indice: int) -> None:
    """Clica em Ações da linha ``indice`` e depois em Editar.

    Equivale a ``atualizar_dados``, que só funciona com uma única linha
    na grade (usa ``tr`` sem índice).
    """
    botao = WebDriverWait(driver, TIMEOUT_PADRAO).until(
        EC.element_to_be_clickable((By.XPATH, _xpath_botao_acoes(indice)))
    )
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});", botao
    )
    try:
        botao.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", botao)
    clicar_editar(driver)


def _editar_linha(
    driver: WebDriver, indice: int, valor: str, valor_taxa: str
) -> None:
    """Abre o diálogo da linha e preenche Valor e Total taxa."""
    _abrir_edicao_da_linha(driver, indice)
    sleep(1)  # mesmo intervalo do fluxo anterior; ideal: WebDriverWait
    editar_rps_consolidado(
        driver=driver,
        valor=valor,
        total_taxa=valor_taxa,
        # Dias Comp. já é igual ao da fila, não precisa ser reescrito.
        dias_comp=None,
    )


def lancar_rps(
    driver: WebDriver,
    nome_empresa: str,
    forma_pagamento: str,
    bandeira: str | None,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None,
) -> str:
    """Edita o RPS que tenha o mesmo Dias Comp. ou cria um NOVO.

    O driver deve estar na tela RPS Consolidados, com a empresa e as
    datas já pesquisadas (``pesquisar_empresa``).

    Returns:
        ``"editado"`` ou ``"novo"``, para o log de quem chamou.

    Raises:
        ValueError: se a forma de pagamento estiver vazia.
        TimeoutException: se algum elemento não aparecer a tempo.
    """
    forma_pagamento = str(forma_pagamento).strip() if forma_pagamento else ""
    if not forma_pagamento:
        raise ValueError("Forma de pagamento vazia.")

    Log.write_log(
        f"Lançamento RPS: forma '{forma_pagamento}', dias_comp '{dias_comp}'."
    )

    if _pesquisar_forma_pagto(driver, forma_pagamento, bandeira):
        dias_na_grade = _ler_dias_comp_das_linhas(driver)
        Log.write_log(f"Linhas encontradas: {dias_na_grade}")
        indice = _localizar_linha_por_dias_comp(dias_comp, dias_na_grade)
        if indice is not None:
            Log.write_log(f"Dias Comp. igual na linha {indice}; editando.")
            _editar_linha(driver, indice, valor, valor_taxa)
            return "editado"
        Log.write_log("Nenhuma linha com o mesmo Dias Comp.; criando NOVO.")

    criar_novo_lancto(
        driver=driver,
        nome_empresa=nome_empresa,
        forma_pagto=forma_pagamento,
        valor=valor,
        valor_taxa=valor_taxa,
        dias_comp=dias_comp,
    )
    return "novo"