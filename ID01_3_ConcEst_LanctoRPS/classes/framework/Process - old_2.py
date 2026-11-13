# Imports dos módulos internos do projeto
# Carrega o InitAllSettings Precisa ser o primeiro a ser carregado
from ID01_3_ConcEst_LanctoRPS.classes.framework.InitAllSettings import InitAllSettings
from ID01_3_ConcEst_LanctoRPS.classes.utils.Log import Log
from ID01_3_ConcEst_LanctoRPS.classes.framework.GetTransaction import GetTransaction
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import pesquisar_empresa
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_remover_linha_vazia import remover_linhas_com_celula_vazia
from ID01_3_ConcEst_LanctoRPS.classes.utils.remover_linhas_duplicadas import remover_linhas_duplicadas
from ID01_3_ConcEst_LanctoRPS.classes.utils.dados_fila import DadosFila
from ID01_3_ConcEst_LanctoRPS.classes.site.remover_linha_manuais import excluir_linhas_manuais
from ID01_3_ConcEst_LanctoRPS.classes.site.lancamento_rps import lancar_rps

# Imports dos pacotes externos
from time import sleep


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
        DadosFila().inserir_item(dado, id_item_fila=GetTransaction.queue_item['id'])
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

        Log.write_log(
            f'Referência: {referencia} | Adquirente: {adquirente} | '
            f'Forma de pagto: {forma_pagto}'
        )

        # Pesquisa a empresa
        pesquisar_empresa(driver=cls.web_driver, empresa=nome_empresa)

        # Prepara a grade e faz o lançamento do RPS (editar ou novo)
        cls._processar_referencia(
            nome_empresa=nome_empresa,
            forma_pagamento=forma_pagamento,
            bandeira=bandeira,
            valor=valor,
            valor_taxa=valor_taxa,
            dias_comp=dias_comp,
        )

        Log.write_log('Process Finished')

    @classmethod
    def _processar_referencia(
        cls,
        nome_empresa: str,
        forma_pagamento: str,
        bandeira: str | None,
        valor: float,
        valor_taxa: float,
        dias_comp: str,
    ) -> None:
        """Limpa a grade e faz o lançamento (editar ou criar NOVO RPS)."""

        # Excluir as linhas com colunas em branco.
        sleep(3)
        remover_linhas_com_celula_vazia(cls.web_driver)

        # Excluir linhas que contenham na forma de pagamento a palavra MANUAL
        excluir_linhas_manuais(cls.web_driver)

        # Remover linhas duplicadas
        resultado = remover_linhas_duplicadas(cls.web_driver.page_source)

        Log.write_log(
            f"Duplicadas encontradas: {len(resultado.removidas)} "
            f"({[d['Numero'] for d in resultado.removidas]})"
        )

        # Forma de pagamento do SoftCase vem da fila (forma_pagamento).
        # Se existir RPS com o mesmo Dias Comp., edita; senão cria NOVO.
        Log.write_log(f'Forma de pagamento (fila): {forma_pagamento}')
        acao = lancar_rps(
            driver=cls.web_driver,
            nome_empresa=nome_empresa,
            forma_pagamento=forma_pagamento,
            bandeira=bandeira,
            valor=valor,
            valor_taxa=valor_taxa,
            dias_comp=dias_comp,
        )
        Log.write_log(f'RPS {acao}.')