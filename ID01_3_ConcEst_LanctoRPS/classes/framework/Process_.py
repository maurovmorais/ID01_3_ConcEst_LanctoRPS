# Imports dos módulos internos do projeto
# Carrega o InitAllSettingssSettings Precisa ser o primeiro a ser carregado
from ID01_3_ConcEst_LanctoRPS.classes.framework.InitAllSettings import InitAllSettings
from ID01_3_ConcEst_LanctoRPS.classes.utils.Log import Log, LogLevel, ErrorType
from ID01_3_ConcEst_LanctoRPS.classes.utils.Exceptions import BusinessRuleException
from ID01_3_ConcEst_LanctoRPS.classes.framework.GetTransaction import GetTransaction
# #FIXME Código Exemplo REMOVER
# from ID01_3_ConcEst_LanctoRPS.classes.chrome.google.Homepage import GoogleHomepage
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import pesquisar_empresa,filtrar_forma_pagto,atualizar_dados,editar_rps_consolidado

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

        dado = GetTransaction.queue_item['info_adicionais'][0]
        referencia = GetTransaction.queue_item['referencia']
        adquirente = dado['adquirente']
        nome_empresa = dado['softcase']
        bandeira = dado['bandeira']
        valor_taxa = dado['valor_taxa']
        taxa_adquirente = dado['taxa_adquirente']
        forma_pagto = dado['forma_pagto']
        valor = dado['valor']

        #Pesquisa a empresa
        pesquisar_empresa(driver=cls.web_driver,empresa=nome_empresa)

        #Faz lançamento dos RPS
        if referencia == 'Cielo/Pix':
            pass
        elif referencia == 'Cielo/DEBITO':
            #Adequa para o SoftCase
            if forma_pagto== 'DEBITO':
                forma_pagto= 'DÉBITO'
            bandeira_cartao = str(bandeira).upper()
            forma_pagamento = f"{forma_pagto} {bandeira_cartao}"
            #Filtrar forma pagamento
            filtrar_forma_pagto(driver=cls.web_driver,forma_pgto=forma_pagamento,bandeira=bandeira)
            #Editar dados
            atualizar_dados(driver=cls.web_driver)
            sleep(1)
            editar_rps_consolidado(driver=cls.web_driver, valor=valor, total_taxa=valor_taxa)
        elif referencia == 'Cielo/Crédito à vista':
            #Adequa para o SoftCase
            if forma_pagto == 'Crédito à vista':
                forma_pagto= 'CRÉDITO'
            bandeira_cartao = str(bandeira).upper()
            forma_pagamento = f"{forma_pagto} {bandeira_cartao}"
            #Filtrar forma pagamento
            filtrar_forma_pagto(driver=cls.web_driver,forma_pgto=forma_pagamento,bandeira=bandeira)
            #Editar dados
            atualizar_dados(driver=cls.web_driver)
            sleep(1)
            editar_rps_consolidado(driver=cls.web_driver, valor=valor, total_taxa=valor_taxa)
        elif referencia == 'Cielo/Crédito pré-pago':
            pass
        elif referencia == 'Cielo/Crédito conversor de moedas':
            pass
        elif referencia == 'ConectCar/TAG':
            pass
        elif referencia == 'Greenpass/TAG':
            pass
        elif referencia == 'SemParar/TAG':
            pass
        elif referencia == 'Veloe/TAG':
            pass
        elif referencia == 'Bradesco/PIX':
            pass
        else:
            Log.write_log(f'Adquirente: {adquirente} ou a forma de pagto {forma_pagto} não encontradas')

        #Volta a tela inicial da Pesquisa
        # TODO: Implementar codigo

        
        Log.write_log('Process Finished')
        print()
