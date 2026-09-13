"""Automação de seleção de data em calendário MudBlazor (MudDatePicker).

Este módulo fornece funções para abrir um MudDatePicker, navegar até o
mês/ano desejado e clicar no dia correto, com base na estrutura HTML
gerada pelo componente `mud-picker-calendar` (MudBlazor).

Requisitos:
    - selenium >= 4.x
    - Um WebDriver (Chrome/Edge) já inicializado e apontando para a página
      que contém o(s) campo(s) de data (ex.: "Data Inicial", "Data Final").

Uso típico:
    from selenium import webdriver
    from mud_blazor_date_picker import definir_data
    from datetime import date

    driver = webdriver.Chrome()
    driver.get("https://rps.portalsoftcase.com.br/softrps/rpsconsolidateds")

    definir_data(
        driver=driver,
        xpath_botao_abrir_calendario="//label[contains(., 'Data Inicial')]"
                                      "/ancestor::div[contains(@class,'mud-input-control')]"
                                      "//button",
        data_alvo=date(2026, 9, 3),
    )
"""

import logging
from datetime import date, datetime, timedelta

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

TIMEOUT_PADRAO = 10

MESES_PT: dict[int, str] = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

CSS_CONTAINER_CALENDARIO = "div.mud-picker-calendar-container"
CSS_BOTAO_MES_ATUAL = "button.mud-button-month"
CSS_BOTAO_MES_ANTERIOR = "button.mud-picker-nav-button-prev"
CSS_BOTAO_MES_PROXIMO = "button.mud-picker-nav-button-next"
CSS_DIAS_VISIVEIS = "button.mud-picker-calendar-day:not(.mud-hidden)"


class SeletorDataError(Exception):
    """Erro genérico ao interagir com o MudDatePicker."""


def abrir_calendario(
    driver: WebDriver,
    xpath_botao_abrir: str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Clica no botão/ícone que abre o popup do calendário.

    Args:
        driver: instância do WebDriver já na página do formulário.
        xpath_botao_abrir: XPath do botão de calendário associado ao
            campo de data (ex.: ícone ao lado de "Data Inicial").
        timeout: tempo máximo de espera, em segundos.

    Raises:
        SeletorDataError: se o botão não for encontrado/clicável ou se o
            popup do calendário não aparecer a tempo.
    """
    try:
        botao = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath_botao_abrir))
        )
        botao.click()
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, CSS_CONTAINER_CALENDARIO)
            )
        )
        logger.debug("Calendário aberto com sucesso.")
    except TimeoutException as exc:
        raise SeletorDataError(
            "Não foi possível abrir o calendário (botão ou popup "
            "não encontrados a tempo)."
        ) from exc


def _ler_mes_ano_atual(driver: WebDriver, timeout: int) -> tuple[int, int]:
    """Lê o mês/ano exibidos no cabeçalho do calendário aberto.

    Espera um texto no formato "setembro de 2026" e retorna (mes, ano).
    """
    elemento = WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_BOTAO_MES_ATUAL))
    )
    texto = elemento.text.strip().lower()
    try:
        nome_mes, _, ano_texto = texto.partition(" de ")
        mes = next(num for num, nome in MESES_PT.items() if nome == nome_mes)
        ano = int(ano_texto)
    except (StopIteration, ValueError) as exc:
        raise SeletorDataError(
            f"Não foi possível interpretar o cabeçalho do calendário: '{texto}'."
        ) from exc
    return mes, ano


def navegar_para_mes(
    driver: WebDriver,
    mes_alvo: int,
    ano_alvo: int,
    timeout: int = TIMEOUT_PADRAO,
    max_cliques: int = 240,
) -> None:
    """Navega o calendário (já aberto) até o mês/ano desejados.

    Clica repetidamente em "próximo mês" ou "mês anterior" conforme a
    diferença entre o mês/ano atualmente exibido e o alvo.

    Args:
        driver: instância do WebDriver com o popup do calendário aberto.
        mes_alvo: mês desejado (1-12).
        ano_alvo: ano desejado (ex.: 2026).
        timeout: tempo máximo de espera por elemento, em segundos.
        max_cliques: limite de segurança para evitar loop infinito.

    Raises:
        SeletorDataError: se o mês/ano alvo não for alcançado dentro do
            limite de cliques.
    """
    for _ in range(max_cliques):
        mes_atual, ano_atual = _ler_mes_ano_atual(driver, timeout)
        if (mes_atual, ano_atual) == (mes_alvo, ano_alvo):
            logger.debug("Calendário já está em %s/%s.", mes_alvo, ano_alvo)
            return

        indice_atual = ano_atual * 12 + mes_atual
        indice_alvo = ano_alvo * 12 + mes_alvo
        seletor = (
            CSS_BOTAO_MES_PROXIMO if indice_alvo > indice_atual else CSS_BOTAO_MES_ANTERIOR
        )

        botao_navegacao = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
        )
        botao_navegacao.click()

    raise SeletorDataError(
        f"Não foi possível alcançar {mes_alvo}/{ano_alvo} "
        f"após {max_cliques} cliques de navegação."
    )


def selecionar_dia(
    driver: WebDriver,
    dia_alvo: int,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Clica no botão do dia desejado dentro do mês atualmente exibido.

    Considera apenas os botões sem a classe `mud-hidden`, pois dias de
    meses adjacentes usados para preencher a grade recebem essa classe.

    Args:
        driver: instância do WebDriver com o calendário já no mês correto.
        dia_alvo: dia do mês a selecionar (1-31).
        timeout: tempo máximo de espera, em segundos.

    Raises:
        SeletorDataError: se o botão do dia não for encontrado.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_DIAS_VISIVEIS))
        )
        botoes_dia = driver.find_elements(By.CSS_SELECTOR, CSS_DIAS_VISIVEIS)
        botao_alvo = next(
            botao for botao in botoes_dia if botao.text.strip() == str(dia_alvo)
        )
    except (TimeoutException, StopIteration, NoSuchElementException) as exc:
        raise SeletorDataError(
            f"Dia {dia_alvo} não encontrado no mês atualmente exibido."
        ) from exc

    botao_alvo.click()
    logger.info("Dia %s selecionado no calendário.", dia_alvo)


def _converter_data(data_alvo: date | str) -> date:
    """Normaliza `data_alvo` para `datetime.date`.

    Aceita tanto um objeto `date` quanto uma string no formato
    `"d/m/aaaa"` ou `"dd/mm/aaaa"` (ex.: `"9/9/2026"`, `"09/09/2026"`).

    Args:
        data_alvo: data já como `date`, ou string `dia/mes/ano`.

    Returns:
        Objeto `date` correspondente.

    Raises:
        SeletorDataError: se a string não estiver em um formato aceito.
        TypeError: se `data_alvo` não for `date` nem `str`.
    """
    if isinstance(data_alvo, date):
        return data_alvo

    if isinstance(data_alvo, str):
        for formato in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(data_alvo, formato).date()
            except ValueError:
                continue
        raise SeletorDataError(
            f"Formato de data inválido: '{data_alvo}'. "
            "Use 'dd/mm/aaaa' ou um objeto datetime.date."
        )

    raise TypeError(
        f"data_alvo deve ser date ou str, recebido {type(data_alvo)!r}."
    )


def definir_data(
    driver: WebDriver,
    xpath_botao_abrir: str,
    data_alvo: date | str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Orquestra a seleção completa de uma data em um MudDatePicker.

    Abre o calendário, navega até o mês/ano corretos e clica no dia.

    Args:
        driver: instância do WebDriver já na página do formulário.
        xpath_botao_abrir: XPath do botão/ícone que abre o calendário
            (ex.: ícone ao lado do campo "Data Inicial").
        data_alvo: data a ser selecionada — objeto `datetime.date` ou
            string no formato `"dd/mm/aaaa"` (ex.: `"9/9/2026"`).
        timeout: tempo máximo de espera por elemento, em segundos.

    Raises:
        SeletorDataError: se qualquer etapa (converter data, abrir,
            navegar ou selecionar o dia) falhar.
    """
    data_convertida = _converter_data(data_alvo)
    abrir_calendario(driver, xpath_botao_abrir, timeout)
    navegar_para_mes(driver, data_convertida.month, data_convertida.year, timeout)
    selecionar_dia(driver, data_convertida.day, timeout)

def obter_intervalo_ontem():
    """Gera o intervalo de datas baseado em D-1 no formato 'DD/MM/AAAA - DD/MM/AAAA'"""
    # Obtém a data de hoje e subtrai 1 dia
    ontem = datetime.now() - timedelta(days=1)
    
    # Formata no padrão brasileiro
    ontem_formatado = ontem.strftime('%d/%m/%Y')
    
    # Retorna o intervalo repetido
    return f"{ontem_formatado}"