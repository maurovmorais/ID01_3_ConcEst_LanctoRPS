# Imports dos módulos internos do projeto
# Carrega o InitAllSettingssSettings Precisa ser o primeiro a ser carregado
from ID01_3_ConcEst_LanctoRPS.classes.framework.InitAllSettings import InitAllSettings
from ID01_3_ConcEst_LanctoRPS.classes.utils.Log import Log, LogLevel, ErrorType
from ID01_3_ConcEst_LanctoRPS.classes.utils.Exceptions import BusinessRuleException
from ID01_3_ConcEst_LanctoRPS.classes.framework.GetTransaction import GetTransaction
#FIXME Código Exemplo REMOVER
from ID01_3_ConcEst_LanctoRPS.classes.chrome.google.Homepage import GoogleHomepage
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import fazer_login_softcase,navegar_RPSConsolidados

# Imports dos pacotes externos
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from time import sleep

# Classe responsável pelo processamento principal, necessário preencher com o seu código no método execute
class Process:
    """
    Classe responsável pelo processamento principal.

    Parâmetros:
    
    Retorna:
    """
    _config = InitAllSettings.config
    
    @classmethod
    def execute(cls):
        """
        Método principal para execução do código.


        Parâmetros:


        Retorna:
        """
        cls.web_driver = InitAllSettings.web_driver

        Log.write_log('Process Started')

        #Informa valor no campo de pesquisa
        #nome_empresa = GetTransaction.queue_item['info_adicionais']['nome_empresa']
        #texto_simples = GetTransaction.queue_item['info_adicionais']['texto_simples']
        #texto_alvo = GetTransaction.queue_item['info_adicionais']['texto_alvo']
        #valor_total = GetTransaction.queue_item['info_adicionais']['valor_total']
        #taxa = GetTransaction.queue_item['info_adicionais']['taxa']
        #forma_pagamento = GetTransaction.queue_item['info_adicionais']['forma_pagamento']

        #TODO APAGAR APÓS DESENVOLVIMENTO
        ##-------------------------------------
        nome_empresa = 'JARAGUA DO SUL (WPS)'
        texto_simples = 'débito'
        texto_alvo = 'DÉBITO VISA'
        valor_total = ''
        taxa = ''
        ##-------------------------------------

        sleep(5)

        #Login site Softcase
        fazer_login_softcase(driver=cls.web_driver)

        #Navegar e Aplicar as Alterações
        navegar_RPSConsolidados(driver=cls.web_driver,empresa=nome_empresa,forma_pagamento=texto_simples,alvo=texto_alvo)

        Log.write_log('Process Finished')
