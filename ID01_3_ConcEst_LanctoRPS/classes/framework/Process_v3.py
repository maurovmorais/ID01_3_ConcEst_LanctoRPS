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
        valor_taxa = dado['valor_taxa']
        forma_pagto = dado['forma_pagto']
        valor = dado['valor']
        dias_comp = dado['dias_comp']

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
    ) -> None:
        """Direciona o lançamento conforme a referência (adquirente/forma)."""
        if referencia not in FORMA_PAGTO_SOFTCASE:
            Log.write_log(
                f'Adquirente: {adquirente} ou a forma de pagto '
                f'{forma_pagto} não encontradas (referência: {referencia})'
            )
            return

        forma_original, forma_softcase = FORMA_PAGTO_SOFTCASE[referencia]

        # Crédito pré-pago: cria um novo lançamento (módulo separado).
        # Precisa vir antes da adequação ao SoftCase, que troca o texto.
        if forma_pagto == 'Crédito pré-pago':
            lancar_credito_pre_pago(
                driver=cls.web_driver,
                nome_empresa=nome_empresa,
                valor=valor,
                valor_taxa=valor_taxa,
                dias_comp=dias_comp,
                bandeira=bandeira,
            )
            return

        # Crédito à vista também atualiza o campo Dias Comp.
        # Decidido antes da adequação, que troca o texto da forma.
        dias_comp_edicao = dias_comp if forma_pagto == 'Crédito à vista' else None

        # Adequa para o SoftCase
        if forma_pagto == forma_original:
            forma_pagto = forma_softcase

        cls._lancar(
            forma_pagto, bandeira, valor, valor_taxa, dias_comp_edicao
        )

    @classmethod
    def _lancar(
        cls,
        forma_pagto: str,
        bandeira: str | None,
        valor: float,
        valor_taxa: float,
        dias_comp: str | None = None,
    ) -> None:
        """Filtra a forma de pagamento no SoftCase e edita o RPS.

        Se dias_comp for informado, o campo Dias Comp. também é atualizado.
        """
        bandeira_cartao = str(bandeira).strip().upper() if bandeira else ''
        forma_pagamento = f'{forma_pagto} {bandeira_cartao}'.strip()

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