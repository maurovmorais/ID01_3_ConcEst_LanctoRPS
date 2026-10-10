"""Atualização de RPS Consolidado para forma de pagamento 'TAG'.

Segue o mesmo fluxo do DÉBITO: filtra a forma de pagamento na tela de
pesquisa e atualiza os dados do RPS existente (não cria lançamento novo).

O texto da forma de pagamento vem da fila (variável ``forma_pagamento``
do Process).
"""

import logging
from time import sleep

from selenium.webdriver.remote.webdriver import WebDriver

from ID01_3_ConcEst_LanctoRPS.classes.site.softcase import (
    atualizar_dados,
    editar_rps_consolidado,
    filtrar_forma_pagto,
)

logger = logging.getLogger(__name__)


def atualizar_tag(
    driver: WebDriver,
    forma_pagamento: str,
    valor: str,
    valor_taxa: str,
) -> None:
    """Filtra a forma de pagamento (vinda da fila) e atualiza o RPS.

    Args:
        driver: WebDriver já posicionado na tela RPS Consolidados, com a
            empresa e as datas pesquisadas.
        forma_pagamento: Forma de pagamento vinda da fila (ex.: 'Veloe').
        valor: Valor do RPS.
        valor_taxa: Valor do campo Total taxa.

    Raises:
        ValueError: se a forma de pagamento estiver vazia.
    """
    forma_pagamento = str(forma_pagamento).strip() if forma_pagamento else ""
    if not forma_pagamento:
        raise ValueError("Forma de pagamento vazia.")

    logger.info("Atualizando RPS TAG: forma '%s'", forma_pagamento)

    # Filtrar forma pagamento
    filtrar_forma_pagto(
        driver=driver,
        forma_pgto=forma_pagamento,
        bandeira=None,
    )
    # Editar dados
    atualizar_dados(driver=driver)
    sleep(1)  # mesmo intervalo usado no fluxo dos demais
    editar_rps_consolidado(
        driver=driver,
        valor=valor,
        total_taxa=valor_taxa,
    )