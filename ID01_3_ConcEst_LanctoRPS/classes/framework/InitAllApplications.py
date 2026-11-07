# Imports dos módulos internos do projeto
# Carrega o InitAllSettingsSettings Precisa ser o primeiro a ser carregado
from ID01_3_ConcEst_LanctoRPS.classes.framework.InitAllSettings import InitAllSettings
from ID01_3_ConcEst_LanctoRPS.classes.utils.Log import Log, LogLevel, ErrorType
from ID01_3_ConcEst_LanctoRPS.classes.utils.Exceptions import BusinessRuleException
from ID01_3_ConcEst_LanctoRPS.classes.queue.QueueManager import QueueManager
import ID01_3_ConcEst_LanctoRPS.classes.utils.GenericReusable as GenericReusable
from ID01_3_ConcEst_LanctoRPS.classes.framework.InitAllSettings import Browser
from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import fazer_login_softcase,download_relatorio_softcase


from time import sleep
from pathlib import Path
from datetime import datetime,timedelta
import os

class InitAllApplications:
    """
    Classe feita para Iniciar as aplicações de inicio de processo e também preencher a fila caso seja um processo simples para capturar
    itens que vão para a fila.
        
    Parâmetros:

    Retorna:
    """
    _config:dict = InitAllSettings.config


    @classmethod
    def add_to_queue(cls):
        """
        Adiciona itens à fila no início do processo, se necessário.

        Observação:
        - Código placeholder.
        - Se o seu projeto precisa de mais do que um método simples para subir a sua fila, considere fazer um projeto dispatcher.

        Parâmetros:
        """
       

    @classmethod
    def _fechar_driver(cls) -> None:
        """Encerra o WebDriver atual, ignorando falhas.

        Após um erro (ex.: InvalidSessionIdException) o driver costuma estar
        morto, então o quit() pode falhar. Isso não deve interromper o retry.
        """
        driver = getattr(cls, "web_driver", None)
        if driver is None:
            return
        try:
            driver.quit()
        except Exception as err:
            Log.write_log(
                mensagem_log=f"Não foi possível fechar o driver: {err}",
                log_level=LogLevel.WARNING,
            )
        finally:
            cls.web_driver = None

    @classmethod
    def execute(cls, first_run=False):
        """
        Executa a inicialização dos aplicativos necessários.

        
        Parâmetros:
        - first_run (bool): indica se é a primeira execução (default=False).
        
        Observação:
        - Edite o valor da variável `max_tentativas` no arquivo Config.xlsx.
        - Em toda tentativa o browser é aberto e o login no Softcase é feito.
          O download do relatório "antes dos lançamentos" só ocorre quando
          `first_run=True`.
        
        Retorna:
        """
      

        Log.write_log("InitAllApplications Started")

        #Chama o método para subir a fila, apenas se for a primeira vez
        #(fica fora do retry para não subir a fila duas vezes)
        if first_run:
            cls.add_to_queue()

        caminho_download = InitAllSettings.config['relatorio_rps_antes']

        #Edite o valor dessa variável a no arquivo Config.xlsx
        #int() protege contra o Excel devolver float/str
        max_tentativas = int(cls._config["MaxRetryNumber"])

        for tentativa in range(1, max_tentativas + 1):
            try:
                Log.write_log(f"Iniciando aplicativos, tentativa {tentativa}")

                #Login site Softcase
                InitAllSettings.initiate_web_manipulator(headless=False, browser_escolhido=Browser.CHROME,pasta_download=caminho_download)
                cls.web_driver = InitAllSettings.web_driver
                fazer_login_softcase(driver=cls.web_driver)

                #Download do relatorio antes dos lançamentos
                if first_run:
                    download_relatorio_softcase(driver=cls.web_driver)

            except BusinessRuleException:
                raise
            except Exception as err:
                Log.write_log(GenericReusable.get_computer_usage())
                Log.write_log(mensagem_log=f"Erro, tentativa {tentativa}: {err}", log_level=LogLevel.ERROR, error_type=ErrorType.APP_ERROR)

                #Fecha o browser quebrado antes de tentar de novo
                cls._fechar_driver()

                if tentativa == max_tentativas:
                    raise
            else:
                Log.write_log("InitAllApplications Finished")
                break