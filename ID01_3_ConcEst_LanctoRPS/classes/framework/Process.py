# Imports dos módulos internos do projeto
# Carrega o InitAllSettings Precisa ser o primeiro a ser carregado
from ID01_3_ConcEst_LanctoRPS.classes.framework.InitAllSettings import InitAllSettings
from ID01_3_ConcEst_LanctoRPS.classes.utils.Log import Log, LogLevel, ErrorType
from ID01_3_ConcEst_LanctoRPS.classes.utils.Exceptions import BusinessRuleException
from ID01_3_ConcEst_LanctoRPS.classes.framework.GetTransaction import GetTransaction
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import (
    pesquisar_empresa,
    filtrar_forma_pagto,
    atualizar_dados,
    editar_rps_consolidado,
)
from ID01_3_ConcEst_LanctoRPS.classes.site.credito_pre_pago import (
    lancar_credito_pre_pago,
)
from ID01_3_ConcEst_LanctoRPS.classes.site.lancamento_pix import lancar_pix
from ID01_3_ConcEst_LanctoRPS.classes.site.lancamento_dinheiro import lancar_dinheiro
from ID01_3_ConcEst_LanctoRPS.classes.site.lancamento_tag import atualizar_tag

from ID01_3_ConcEst_LanctoRPS.classes.site.lancamento_conversor_moedas import (
    lancar_credito_conversor_moedas,
)

from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_remover_linha_debito import remover_duplicatas_forma_pagamento
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_remover_linha_vazia import remover_linhas_com_celula_vazia
from ID01_3_ConcEst_LanctoRPS.classes.utils.remover_linhas_duplicadas import remover_linhas_duplicadas
from ID01_3_ConcEst_LanctoRPS.classes.utils.excluir_linhas_softcase import criar_excluir_linha

# Imports dos pacotes externos
from time import sleep
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


# referencia -> (forma_pagto recebida, texto da forma no SoftCase)
FORMA_PAGTO_SOFTCASE: dict[str, tuple[str, str]] = {
    'Cielo/Pix': ('Pix', 'PIX'),
    'Cielo/DEBITO': ('DEBITO', 'DÉBITO'),
    'Cielo/Crédito à vista': ('Crédito à vista', 'CRÉDITO'),
    'Cielo/Crédito pré-pago': ('Crédito pré-pago', 'CRÉDITO'),
    'Cielo/Crédito conversor de moedas': (
        'Crédito conversor de moedas',
        'CRÉDITO CONVERSOR DE MOEDAS',
    ),
    'Cielo/DINHEIRO': ('DINHEIRO', 'DINHEIRO'),  # CONFIRMAR a referência
    'ConectCar/TAG': ('TAG', 'TAG'),
    'Greenpass/TAG': ('TAG', 'TAG'),
    'SemParar/TAG': ('TAG', 'TAG'),
    'Veloe/TAG': ('TAG', 'TAG'),
    'Bradesco/PIX': ('PIX', 'PIX'),
}


# Classe responsável pelo processamento principal
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
        bandeira = (
                bandeira.strip().upper()
                if isinstance(bandeira, str) and bandeira.strip()
                else None
        )
        valor_taxa = dado['valor_taxa']
        forma_pagto = dado['forma_pagto']
        valor = dado['valor']
        dias_comp = dado['dias_comp']
        forma_pagamento = dado['forma_pagamento']

        # Pesquisa a empresa
        pesquisar_empresa(driver=cls.web_driver, empresa=nome_empresa)

        # Faz lançamento dos RPS
        cls._processar_referencia(
            referencia=referencia,
            adquirente=adquirente,
            forma_pagto=forma_pagto,
            bandeira=bandeira,
            valor=valor,
            valor_taxa=valor_taxa,
            nome_empresa=nome_empresa,
            dias_comp=dias_comp,
            forma_pagamento=forma_pagamento,
        )


        Log.write_log('Process Finished')

    @classmethod
    def _processar_referencia(
        cls,
        referencia: str,
        adquirente: str,
        forma_pagto: str,
        bandeira: str | None,
        valor: float,
        valor_taxa: float,
        nome_empresa: str,
        dias_comp: str,
        forma_pagamento: str,
    ) -> None:

        #Excluir AS linhas com colunas em branco.
        sleep(3)
        remover_linhas_com_celula_vazia(cls.web_driver)

        #Remover linhas Duplicadas
        excluir = criar_excluir_linha(cls.web_driver)
        resultado = remover_linhas_duplicadas(cls.web_driver .page_source, excluir=excluir)
        resultado = remover_linhas_duplicadas(cls.web_driver.page_source)

        Log.write_log(
            f"Duplicadas encontradas: {len(resultado.removidas)} "
            f"({[d['Numero'] for d in resultado.removidas]})"
        )

        """Direciona o lançamento conforme a referência (adquirente/forma)."""
        if referencia not in FORMA_PAGTO_SOFTCASE:
            Log.write_log(
                f'Adquirente: {adquirente} ou a forma de pagto '
                f'{forma_pagto} não encontradas (referência: {referencia})'
            )
            return

       
        
        if forma_pagto == 'Crédito pré-pago':
            Log.write_log(f'Forma de pagamento (fila): {forma_pagamento}')
            lancar_credito_pre_pago(
                driver=cls.web_driver,
                nome_empresa=nome_empresa,
                forma_pagto=forma_pagamento,
                valor=valor,
                valor_taxa=valor_taxa,
                dias_comp=dias_comp,
            )
            return
       

        if str(forma_pagto).strip().casefold() == 'pix':
            Log.write_log(f'Forma de pagamento (fila): {forma_pagamento}')
            lancar_pix(
                driver=cls.web_driver,
                nome_empresa=nome_empresa,
                forma_pagto=forma_pagamento,
                valor=valor,
                valor_taxa=valor_taxa,
                dias_comp=dias_comp,
            )
            return

        # DINHEIRO: filtra e atualiza o RPS existente; se não houver
        # opção para alterar, cria um NOVO (módulo separado, nos moldes
        # do Pix). Antes da adequação ao SoftCase.
        if forma_pagto == 'DINHEIRO':
            lancar_dinheiro(
                driver=cls.web_driver,
                nome_empresa=nome_empresa,
                forma_pagamento=forma_pagamento,
                valor=valor,
                valor_taxa=valor_taxa,
                dias_comp=dias_comp,
            )
            return

        # TAG: mesmo fluxo do débito (filtra e atualiza o RPS existente),
        # em módulo separado; a forma de pagamento considera o adquirente
        # (ex.: 'TAG <adquirente>'). Antes da adequação ao SoftCase.
        if forma_pagto == 'TAG':
            atualizar_tag(
                driver=cls.web_driver,
                forma_pagamento=forma_pagamento,
                valor=valor,
                valor_taxa=valor_taxa,
            )
            return

  

        if forma_pagto == 'Crédito conversor de moedas':
            Log.write_log(f'Forma de pagamento (fila): {forma_pagamento}')
            lancar_credito_conversor_moedas(
                driver=cls.web_driver,
                nome_empresa=nome_empresa,
                forma_pagto=forma_pagamento,
                valor=valor,
                valor_taxa=valor_taxa,
                dias_comp=dias_comp,
            )
            return


        # Crédito à vista também atualiza o campo Dias Comp.
        # Decidido antes da adequação, que troca o texto da forma.
        dias_comp_edicao = dias_comp if forma_pagto == 'Crédito à vista' else None


        # Forma de pagamento do SoftCase vem da fila (forma_pagamento)
        Log.write_log(f'Forma de pagamento (fila): {forma_pagamento}')

        cls._lancar(
            forma_pagamento, bandeira, valor, valor_taxa, dias_comp_edicao
        )

    @classmethod
    def _lancar(
        cls,
        forma_pagamento: str,
        bandeira: str | None,
        valor: float,
        valor_taxa: float,
        dias_comp: str | None = None,
    ) -> None:
        """Filtra a forma de pagamento no SoftCase e edita o RPS.

        Se dias_comp for informado, o campo Dias Comp. também é atualizado.
        """
    
        forma_pagamento = str(forma_pagamento).strip()

        # Filtrar forma pagamento
        filtrar_forma_pagto(
            driver=cls.web_driver,
            forma_pgto=forma_pagamento,
            bandeira=bandeira,
        )
        # Editar dados
        atualizar_dados(driver=cls.web_driver)
        sleep(1)  # ideal: trocar por WebDriverWait
        editar_rps_consolidado(
            driver=cls.web_driver,
            valor=valor,
            total_taxa=valor_taxa,
            dias_comp=dias_comp,
        )