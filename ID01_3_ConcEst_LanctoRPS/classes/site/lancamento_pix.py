"""Lançamento de RPS Consolidado para forma de pagamento 'Pix'.

Fluxo:
    1. Filtra a forma de pagamento (da fila) na tela RPS Consolidados.
    2. Se a grade trouxer um RPS da empresa, atualiza o existente
       (Ações > Editar).
    3. Se não houver resultado, cria um NOVO lançamento.

A criação (NOVO) usa seletores e funções auxiliares próprios, sem
depender de ``credito_pre_pago.py``.
"""

import time
import logging
from datetime import date, timedelta

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.keys import Keys
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
# Texto exibido na lista do diálogo de criação ('Crédito PIX').
# A comparação na seleção ignora maiúsculas/minúsculas.
#FORMA_PAGTO_PIX = "Crédito PIX"
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


def _selecionar_forma_pagto(driver: WebDriver, texto: str) -> None:
    """Autocomplete: digita o texto e tenta cada opção compatível da lista.

    Se o portal listar mais de um item com o mesmo texto e algum não
    funcionar, tenta o seguinte até a seleção ser confirmada.
    Ordem de tentativa: itens iguais ao texto; depois os que terminam com
    ele (ex.: 'Crédito PIX' para 'PIX'). Ignora maiúsculas/minúsculas.

    Raises:
        TimeoutException: se nenhuma opção aparecer ou for aceita.
    """
    alvo = texto.strip().casefold()

    def _opcoes_compativeis(drv: WebDriver) -> list[WebElement]:
        iguais: list[WebElement] = []
        parciais: list[WebElement] = []
        for item in drv.find_elements(By.XPATH, XPATH_ITENS_LISTA):
            try:
                texto_item = item.text.strip().casefold()
            except StaleElementReferenceException:
                continue  # lista recarregou; pega no próximo ciclo
            if texto_item == alvo:
                iguais.append(item)
            elif texto_item.endswith(alvo):
                parciais.append(item)
        return iguais + parciais

    def _digitar_busca() -> None:
        campo = _esperar_clicavel(driver, XPATH_FORMA_PAGTO)
        campo.click()
        campo.clear()
        campo.send_keys(texto)

    def _clicar(opcao: WebElement) -> None:
        try:
            opcao.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", opcao)

    def _selecao_confirmada() -> bool:
        """Lista fechada e, após sair do campo, valor mantido e sem erro."""
        try:
            WebDriverWait(driver, 3).until(
                lambda d: not d.find_elements(By.XPATH, XPATH_ITENS_LISTA)
            )
        except TimeoutException:
            return False
        campo = driver.find_element(By.XPATH, XPATH_FORMA_PAGTO)
        campo.send_keys(Keys.TAB)  # tira o foco: dispara validação do campo
        time.sleep(0.5)
        campo = driver.find_element(By.XPATH, XPATH_FORMA_PAGTO)
        valor = (campo.get_attribute("value") or "").strip().casefold()
        invalido = campo.get_attribute("aria-invalid") == "true"
        logger.info(
            "Campo após seleção: valor='%s', aria-invalid=%s", valor, invalido
        )
        return valor.endswith(alvo) and not invalido

    indice = 0
    for _ in range(10):  # limite de segurança contra laço infinito
        _digitar_busca()
        try:
            WebDriverWait(driver, TIMEOUT_PADRAO).until(
                lambda d: len(_opcoes_compativeis(d)) > 0
            )
        except TimeoutException:
            logger.error(
                "Forma de pagamento '%s' não encontrada na lista.", texto
            )
            raise
        time.sleep(0.5)  # deixa a lista estabilizar

        opcoes = _opcoes_compativeis(driver)
        if indice >= len(opcoes):
            raise TimeoutException(
                f"Nenhuma das {len(opcoes)} opções de '{texto}' foi aceita."
            )

        logger.info(
            "Forma '%s': tentando opção %d de %d.",
            texto, indice + 1, len(opcoes),
        )
        try:
            _clicar(opcoes[indice])
        except StaleElementReferenceException:
            continue  # lista recarregou; tenta de novo a mesma opção

        if _selecao_confirmada():
            logger.info("Forma '%s' confirmada na opção %d.", texto, indice + 1)
            return
        logger.warning(
            "Opção %d de '%s' não foi confirmada; tentando a próxima.",
            indice + 1, texto,
        )
        indice += 1

    raise TimeoutException(f"Não foi possível selecionar '{texto}'.")


def _normalizar_dias_comp(dias_comp: str | int | None) -> str:
    """Retorna dias_comp como texto; vazio/None vira '0'."""
    if dias_comp is None or str(dias_comp).strip() == "":
        return DIAS_COMP_PADRAO
    return str(dias_comp).strip()


def _criar_novo_pix(
    driver: WebDriver,
    nome_empresa: str,
    forma_pagto: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None = None,
    data_lancamento: date | None = None,
) -> None:
    """Cria um novo RPS Consolidado (botão NOVO) para 'Pix'.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados.
        nome_empresa: Nome da empresa a selecionar.
        forma_pagto: Forma de pagamento a selecionar na lista (vem da fila).
        valor: Valor do lançamento.
        valor_taxa: Valor para o campo Total taxa.
        dias_comp: Valor para o campo Dias Comp.; se vier None/vazio,
            usa '0'.
        data_lancamento: Data do lançamento; padrão é D-1.
    """
    dias_comp_texto = _normalizar_dias_comp(dias_comp)

    data = data_lancamento or (date.today() - timedelta(days=1))
    data_str = f"{data.day}/{data.month}/{data.year}"  # formato 'd/m/aaaa'

    logger.info("Criando lançamento Pix: %s", nome_empresa)
    _esperar_clicavel(driver, XPATH_BOTAO_NOVO).click()

    try:
        WebDriverWait(driver, TIMEOUT_PADRAO).until(
            EC.visibility_of_element_located((By.XPATH, XPATH_DIALOGO))
        )
    # except TimeoutException:
    #     logger.error("Diálogo 'Criar RPS Consolidado' não apareceu.")
    #     raise
    except TimeoutException:
        mensagens = [
            e.text.strip()
            for e in driver.find_elements(
                By.XPATH,
                "//p[contains(@class,'mud-input-helper-text')]"
                " | //div[contains(@class,'mud-snackbar-content-message')]",
            )
            if e.text.strip()
        ]
        logger.error(
            "Diálogo 'Criar RPS Consolidado' não apareceu. "
            "Mensagens na tela: %s",
            mensagens,
        )
        raise

    _selecionar_empresa(driver, nome_empresa)

    # Campo Data é readonly: usa o seletor de calendário já existente.
    definir_data(driver, XPATH_BOTAO_CALENDARIO_DATA, data_str)

    #_selecionar_forma_pagto(driver, FORMA_PAGTO_PIX)
    _selecionar_forma_pagto(driver, forma_pagto)
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

    logger.info("Lançamento Pix salvo: %s", nome_empresa)


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


def lancar_pix(
    driver: WebDriver,
    nome_empresa: str,
    forma_pagto: str,
    valor: str,
    valor_taxa: str,
    dias_comp: str | int | None = None,
    data_lancamento: date | None = None,
) -> None:
    """Atualiza o RPS de Pix existente ou, se não houver, cria um NOVO.

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
        _criar_novo_pix(
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
    logger.info("Lançamento Pix atualizado: %s", nome_empresa)