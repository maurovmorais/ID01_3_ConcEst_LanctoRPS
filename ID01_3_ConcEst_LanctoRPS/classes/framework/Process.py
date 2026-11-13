# O InitAllSettings precisa ser o primeiro import do projeto a ser carregado
from ID01_3_ConcEst_LanctoRPS.classes.framework.InitAllSettings import InitAllSettings
from ID01_3_ConcEst_LanctoRPS.classes.framework.GetTransaction import GetTransaction
from ID01_3_ConcEst_LanctoRPS.classes.site.lancamento_rps import lancar_rps
from ID01_3_ConcEst_LanctoRPS.classes.site.remover_linha_manuais import excluir_linhas_manuais
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import pesquisar_empresa,tratar_dias_comp_dinheiro
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase_remover_linha_vazia import remover_linhas_com_celula_vazia
from ID01_3_ConcEst_LanctoRPS.classes.utils.dados_fila import DadosFila
from ID01_3_ConcEst_LanctoRPS.classes.utils.Log import Log
from ID01_3_ConcEst_LanctoRPS.classes.utils.remover_linhas_duplicadas import remover_linhas_duplicadas
from ID01_3_ConcEst_LanctoRPS.classes.utils.excluir_linhas_softcase import criar_excluir_linha
from ID01_3_ConcEst_LanctoRPS.classes.utils.util_data import obter_intervalo_ontem,obter_dia_semana,obter_dias_comp_dinheiro

from time import sleep

ESPERA_ANTES_LIMPEZA_SEG = 3


class Process:
    """Processamento principal: lança o RPS de uma referência da fila."""

    _config = InitAllSettings.config

    @classmethod
    def execute(cls) -> None:
        """Lê o item da fila, pesquisa a empresa e lança o RPS."""
        cls.web_driver = InitAllSettings.web_driver

        item = GetTransaction.queue_item
        dado = item['info_adicionais'][0]
        DadosFila().inserir_item(dado, id_item_fila=item['id'])

        Log.write_log(
            f"Referência: {item['referencia']} | "
            f"Adquirente: {dado['adquirente']} | "
            f"Forma de pagto: {dado['forma_pagto']}"
        )

        nome_empresa = dado['softcase']
        pesquisar_empresa(driver=cls.web_driver, empresa=nome_empresa)

        cls._processar_referencia(
            nome_empresa=nome_empresa,
            forma_pagamento=dado['forma_pagamento'],
            bandeira=cls._normalizar_bandeira(dado['bandeira']),
            valor=dado['valor'],
            valor_taxa=dado['valor_taxa'],
            dias_comp=dado['dias_comp'],
        )

        Log.write_log('Process Finished')

    @staticmethod
    def _normalizar_bandeira(bandeira: str | None) -> str | None:
        """Retorna a bandeira em maiúsculas, ou None se vazia/inválida."""
        if isinstance(bandeira, str) and bandeira.strip():
            return bandeira.strip().upper()
        return None

    @classmethod
    def _limpar_grade(cls) -> None:
        """Remove da grade linhas vazias, manuais e duplicadas."""
        sleep(ESPERA_ANTES_LIMPEZA_SEG)
        
        remover_linhas_com_celula_vazia(cls.web_driver)

        excluir_linhas_manuais(cls.web_driver)
        
        excluir = criar_excluir_linha(cls.web_driver)
        resultado = remover_linhas_duplicadas(cls.web_driver.page_source, excluir=excluir)

        numeros = [d['Numero'] for d in resultado.removidas]
        Log.write_log(f'Duplicadas encontradas: {len(numeros)} ({numeros})')
        
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
        """Limpa a grade e lança o RPS (edita se existir Dias Comp. igual, senão cria NOVO)."""
        cls._limpar_grade()

        # Trata informação de Dias Comp para DINHEIRO
        texto_para_campo = obter_intervalo_ontem()

        nome_dia_semana = obter_dia_semana(texto_para_campo)

        dias_comp_dinheiro = obter_dias_comp_dinheiro(nome_dia_semana)

        tratar_dias_comp_dinheiro(cls.web_driver, dias_comp_dinheiro)
        
        Log.write_log(f'Alterado Dias Comp da Forma de pagamento Dinheiro da empresa {nome_empresa}')
    
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