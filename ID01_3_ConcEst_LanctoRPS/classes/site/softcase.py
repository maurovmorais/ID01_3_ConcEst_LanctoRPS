"""Função de login no Portal Estabelecimentos Comerciais (SoftCase).

Reutiliza a instância do Chrome/WebDriver já iniciada pela automação
(o driver deve ser criado e passado por quem chama esta função —
nenhuma nova janela de navegador é aberta aqui).
"""

import logging
import time

from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from ID01_3_ConcEst_LanctoRPS.classes.utils.Log import Log, LogLevel, ErrorType
from ID01_3_ConcEst_LanctoRPS.classes.utils.CredentialWindows import obter_credencial_windows
from ID01_3_ConcEst_LanctoRPS.classes.framework.InitAllSettings import InitAllSettings
from ID01_3_ConcEst_LanctoRPS.classes.utils.util_data import obter_intervalo_ontem,definir_data
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_selecionar_qtde_itens import definir_itens_por_pagina
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_forma_pagamento import selecionar_autocomplete
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_remover_linha_debito import remover_duplicatas_forma_pagamento
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_remover_linha_vazia import remover_linhas_com_celula_vazia

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DIRETORIO_DIAGNOSTICO = Path("logs") / "diagnostico"
URL_LOGIN = ('https://rps.portalsoftcase.com.br/')
NOME_CREDENCIAL_WINDOWS = "site_softcase"

USUARIO = InitAllSettings.config['usuarios']

SELETOR_CAMPO_EMAIL = (By.XPATH,'/html/body/div[1]/div/div[3]/div/div/form/div/div[1]/div/div/div/input')
SELETOR_CAMPO_PESQUISA = (By.XPATH,'/html/body/div[1]/div/div[3]/div[2]/div/div[4]/div[1]')
XPATH_CAMPO_BUSCA = ("/html/body/div[1]/div/div[3]/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div/div[1]/div/div/div/div[1]/input")
XPATH_PAINEL_DROPDOWN = ("/html/body/div[1]/div/div[3]/div[2]/div/div[4]/div[2]/div/div/div")

#Tempos e dalays
TIMEOUT_PADRAO_SEGUNDOS = 60
TIMEOUT_PADRAO = 15
TENTATIVAS_MAXIMAS = 3
ESPERA_ENTRE_TENTATIVAS_SEGUNDOS = 3


def fazer_login_softcase(
    driver: WebDriver,
    timeout: int = TIMEOUT_PADRAO_SEGUNDOS,
    tentativas_maximas: int = TENTATIVAS_MAXIMAS,
) -> None:
    """Realiza o login no Portal Estabelecimentos Comerciais (SoftCase).

    Usuário e senha são recuperados do Gerenciador de Credenciais do
    Windows (credencial "site_GreenPass)"). Utiliza a instância de Chrome já
    aberta (o ``driver`` recebido por parâmetro), sem abrir um novo
    navegador.

    Args:
        driver: Instância do WebDriver (Chrome) já iniciada pela automação.
        timeout: Tempo máximo, em segundos, de espera por cada elemento.
        tentativas_maximas: Número máximo de tentativas em caso de falha
            recuperável (ex.: elemento ainda não carregado).

    Raises:
        ValueError: Se a credencial do Windows não for encontrada/estiver
            incompleta.
        TimeoutException: Se os elementos da página não aparecerem dentro
            do tempo esperado, mesmo após todas as tentativas.
    """
    usuario, senha = obter_credencial_windows(NOME_CREDENCIAL_WINDOWS)

    ultima_excecao: Exception | None = None

    for tentativa in range(1, tentativas_maximas + 1):
        try:
            logger.info(
                "Tentativa %d/%d de login no Portal Softcase.",
                tentativa,
                tentativas_maximas,
            )
            driver.get(URL_LOGIN)

            # Maximiza a tela imediatamente depois
            driver.maximize_window()
            time.sleep(3)
            
            espera = WebDriverWait(driver, timeout)

            campo_email = espera.until(
                EC.visibility_of_element_located(SELETOR_CAMPO_EMAIL)
            )
            # Preencher o usuario
            email_usuario = driver.find_element(By.XPATH,'/html/body/div[1]/div/div[3]/div/div/form/div/div[1]/div/div/div/input') 
            email_usuario.send_keys(USUARIO)
            
            # Preencher a senha
            senha_usuario = driver.find_element(By.XPATH,'/html/body/div[1]/div/div[3]/div/div/form/div/div[2]/div/div/div/input')
            senha_usuario.send_keys(senha)

            # Clicar em entrar
            botao_entrar = driver.find_element(By.XPATH,'/html/body/div[1]/div/div[3]/div/div/form/div/div[5]/button/span')
            botao_entrar.click()

            # Confirma que o login foi bem-sucedido aguardando a URL sair
            # da tela de login (ajustar condição conforme comportamento
            # real do site, ex.: aguardar um elemento exclusivo do home).
            espera.until(lambda d: "login" not in d.current_url.lower())

            logger.info("Login no Portal SoftCase realizado com sucesso.")

            return

        except (
            TimeoutException,
            NoSuchElementException,
            ElementNotInteractableException,
        ) as exc:
            ultima_excecao = exc
            logger.warning(
                "Falha na tentativa %d/%d de login: %s",
                tentativa,
                tentativas_maximas,
                exc,
            )
            if tentativa < tentativas_maximas:
                time.sleep(ESPERA_ENTRE_TENTATIVAS_SEGUNDOS)

    logger.error(
        "Login no Portal Softcase falhou após %d tentativas.",
        tentativas_maximas,
    )
    raise TimeoutException(
        f"Não foi possível realizar login após {tentativas_maximas} "
        "tentativas."
    ) from ultima_excecao




def navegar_RPSConsolidados(driver: WebDriver,empresa:str,forma_pagamento:str,alvo:str) -> None:
    """
    Navega até a aba Estadia do Taggy

    """
    timeout: int = TIMEOUT_PADRAO_SEGUNDOS
    try:
        #Navega para a Tela
        time.sleep(3)
        driver.get('https://rps.portalsoftcase.com.br/softrps/rpsconsolidateds')

        time.sleep(3)
        espera = WebDriverWait(driver, timeout)

        campo_email = espera.until(
            EC.visibility_of_element_located(SELETOR_CAMPO_PESQUISA)
        )
        

        #Expandir campo Pesquisa
        campo_pesquisar_exp = driver.find_element(By.XPATH,'/html/body/div[1]/div/div[3]/div[2]/div/div[4]/div[1]')
        campo_pesquisar_exp.click()

        #Informar a Empresa
        selecionar_empresa(driver,nome_empresa=empresa)

        #Preenche campo data D-1
        texto_para_campo = obter_intervalo_ontem()
        
        campo_data_inicial = '/html/body/div[1]/div/div[3]/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div/div[2]/div/div[1]/div/div/input'
        definir_data(driver,xpath_botao_abrir=campo_data_inicial ,data_alvo=texto_para_campo)

        campo_data_final = '/html/body/div[1]/div/div[3]/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div/div[3]/div/div[1]/div/div/input'
        definir_data(driver,xpath_botao_abrir=campo_data_final ,data_alvo=texto_para_campo)

        #Seleciona 100 itens
        xpath_botao_expandir = '/html/body/div[1]/div/div[3]/div[2]/div/div[5]/div[4]/div/div[2]/div[2]/div/div/div[1]/div[1]'
        definir_itens_por_pagina(driver=driver, xpath_botao_expandir=xpath_botao_expandir)

        #Botão Pesquisar
        botao_pesquisar = driver.find_element(By.XPATH,'/html/body/div[1]/div/div[3]/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div/div[8]/button[2]')
        time.sleep(0.5)                                        
        botao_pesquisar.send_keys(Keys.ENTER)

        #Leitura da Tabela de dados
        tabela_xpath = '//*[@id="app"]/div/div[3]/div[2]/div/div[5]/div[3]/table/tbody'

        #Excluir linhas com colunas em branco
        #remover_linhas_com_celula_vazia(driver)

        #Forma de pagamento
        if forma_pagamento == 'débito':
            #Regra para apagar linhas duplicadas mantendo apenas 1 item
            #remover_duplicatas_forma_pagamento(driver,xpath_tabela=tabela_xpath,filtro_prefixo=texto_generico)

            xpath_campo_forma_pagamento = '/html/body/div[1]/div/div[3]/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div/div[7]/div/div/div/div[1]/input'
            selecionar_autocomplete(
                driver=driver,
                xpath_campo_input=xpath_campo_forma_pagamento,
                texto_busca=forma_pagamento,
                texto_item_alvo=alvo,)

            #Botão Pesquisar
            botao_pesquisar = driver.find_element(By.XPATH,'//*[@id="app"]/div/div[3]/div[2]/div/div[4]/div[2]/div/div/div/div[2]/div/div[8]/button[2]')
            botao_pesquisar.click()

            #Leitura da Tabela de dados
            # tabela = driver.find_element(By.XPATH,'//*[@id="app"]/div/div[3]/div[2]/div/div[5]/div[3]/table/tbody')
            # dados_tabela = tabela.text

            #Validar se existe linhas duplicadas conforme forma de pagamento

            #Alterar valor e taxa

            #Download Relatorio

        elif forma_pagamento == 'crédito':
            pass
        else:
            pass
        
        print()

    
    except Exception:
        Log.write_log("Falha em navegar telas")
        raise


def _salvar_diagnostico(driver: WebDriver, contexto: str) -> None:
    """Salva o HTML da página e uma screenshot para depuração.

    Usado quando um elemento esperado não é encontrado, para permitir
    investigar o estado real da página no momento da falha sem
    precisar reproduzir o erro novamente.

    Args:
        driver: instância do WebDriver no estado em que a falha ocorreu.
        contexto: identificador curto do que estava sendo feito (ex.:
            "opcao_nao_encontrada"), usado no nome dos arquivos.
    """
    DIRETORIO_DIAGNOSTICO.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_html = DIRETORIO_DIAGNOSTICO / f"{timestamp}_{contexto}.html"
    caminho_screenshot = DIRETORIO_DIAGNOSTICO / f"{timestamp}_{contexto}.png"

    try:
        caminho_html.write_text(driver.page_source, encoding="utf-8")
        driver.save_screenshot(str(caminho_screenshot))
        logger.info(
            "Diagnóstico salvo em '%s' e '%s'",
            caminho_html,
            caminho_screenshot,
        )
    except OSError:
        logger.exception("Falha ao salvar arquivos de diagnóstico")


def selecionar_empresa(
    driver: WebDriver,
    nome_empresa: str,
    timeout: int = TIMEOUT_PADRAO,
) -> None:
    """Abre o dropdown de empresas e seleciona a opção informada.

    Args:
        driver: instância do WebDriver já na página de RPSs Consolidados.
        nome_empresa: texto visível da opção a selecionar, por exemplo
            "ARAPIRACA (WPS)". A busca é feita por texto exato.
        timeout: tempo máximo (em segundos) de espera por cada elemento.

    Raises:
        TimeoutException: se o campo, o painel ou a opção desejada não
            forem encontrados dentro do tempo limite.
    """
    wait = WebDriverWait(driver, timeout)

    logger.info("Abrindo dropdown de empresas")
    try:
        campo_busca = wait.until(
            EC.element_to_be_clickable((By.XPATH, XPATH_CAMPO_BUSCA))
        )
    except TimeoutException:
        logger.error("Campo de busca do dropdown não encontrado")
        _salvar_diagnostico(driver, "campo_busca_nao_encontrado")
        raise
    campo_busca.click()

    logger.info("Aguardando painel de opções ficar visível")
    try:
        wait.until(
            EC.visibility_of_element_located(
                (By.XPATH, XPATH_PAINEL_DROPDOWN)
            )
        )
    except TimeoutException:
        logger.error("Painel do dropdown não ficou visível")
        _salvar_diagnostico(driver, "painel_nao_visivel")
        raise

    logger.info("Selecionando empresa: %s", nome_empresa)
    # A lista de opções (mud-list) costuma ser renderizada por um
    # "popover provider" do MudBlazor, que pode não ficar aninhado
    # dentro do XPATH_PAINEL_DROPDOWN medido manualmente. Por isso a
    # busca do <p> é feita na página inteira, e não restrita ao painel.
    xpath_opcao = (
        f"//p[normalize-space(text())='{nome_empresa}']"
        f"/ancestor::div[contains(@class, 'mud-list-item')][1]"
    )
    try:
        opcao = wait.until(
            EC.presence_of_element_located((By.XPATH, xpath_opcao))
        )
        try:
            opcao.click()
            
        except (
            ElementClickInterceptedException,
            ElementNotInteractableException,
        ):
            logger.warning(
                "Clique direto falhou para '%s'; tentando via JavaScript",
                nome_empresa,
            )
            driver.execute_script("arguments[0].click();", opcao)
    except TimeoutException:
        logger.error("Empresa '%s' não encontrada no dropdown", nome_empresa)
        nome_arquivo = nome_empresa.replace(" ", "_").replace("/", "-")
        _salvar_diagnostico(driver, f"opcao_nao_encontrada_{nome_arquivo}")
        raise

    logger.info("Empresa '%s' selecionada com sucesso", nome_empresa)
