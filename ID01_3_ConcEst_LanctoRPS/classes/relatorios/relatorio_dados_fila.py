"""Geração do relatório Excel com os dados da tabela tbl_dados_fila."""

import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

CAMINHO_BANCO = Path(
    r"C:\Armazenamento\ID01_3_ConcEst_LanctoRPS\Banco Dados\banco_dados.db"
)
PASTA_RELATORIOS = Path(r"C:\Armazenamento\ID01_3_ConcEst_LanctoRPS\Relatorios")
PREFIXO_ARQUIVO = "dados_fila"

SQL_SELECT = """
SELECT
    id, id_item_fila, adquirente, softcase, bandeira, dias_comp,
    valor_taxa, taxa_adquirente, forma_pagto, forma_pagamento,
    valor, data_ref, timestamp
FROM tbl_dados_fila
ORDER BY id
"""


class RelatorioDadosFila:
    """Gera o relatório Excel a partir do SELECT em tbl_dados_fila."""

    def __init__(
        self,
        caminho_banco: Path = CAMINHO_BANCO,
        pasta_relatorios: Path = PASTA_RELATORIOS,
        prefixo_arquivo: str = PREFIXO_ARQUIVO,
    ) -> None:
        self.caminho_banco = Path(caminho_banco)
        self.pasta_relatorios = Path(pasta_relatorios)
        self.prefixo_arquivo = prefixo_arquivo

    def _montar_caminho(self) -> Path:
        """Monta o caminho final: <prefixo>_<AAAAMMDD_HHMMSS>.xlsx."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.pasta_relatorios / f"{self.prefixo_arquivo}_{timestamp}.xlsx"

    def _consultar(self) -> tuple[list[str], list[tuple]]:
        """Executa o SELECT e retorna (cabeçalhos, linhas)."""
        with closing(sqlite3.connect(self.caminho_banco)) as conexao:
            cursor = conexao.execute(SQL_SELECT)
            cabecalhos = [coluna[0] for coluna in cursor.description]
            linhas = cursor.fetchall()
        return cabecalhos, linhas

    @staticmethod
    def _formatar(planilha, total_colunas: int) -> None:
        """Aplica estilo ao cabeçalho, filtro, congelamento e larguras."""
        estilo_fonte = Font(bold=True, color="FFFFFF")
        estilo_fundo = PatternFill("solid", fgColor="1F4E78")
        for celula in planilha[1]:
            celula.font = estilo_fonte
            celula.fill = estilo_fundo
            celula.alignment = Alignment(horizontal="center")

        planilha.freeze_panes = "A2"
        planilha.auto_filter.ref = planilha.dimensions

        for indice in range(1, total_colunas + 1):
            letra = get_column_letter(indice)
            maior = max(
                len(str(celula.value)) if celula.value is not None else 0
                for celula in planilha[letra]
            )
            planilha.column_dimensions[letra].width = min(maior + 2, 50)

    def gerar(self) -> Path:
        """Gera o relatório e retorna o caminho do arquivo.

        Raises:
            FileNotFoundError: se o banco de dados não existir.
            FileExistsError: se já existir um arquivo com o mesmo nome
                (duas gerações no mesmo segundo).
        """
        if not self.caminho_banco.exists():
            raise FileNotFoundError(
                f"Banco de dados não encontrado: {self.caminho_banco}"
            )

        cabecalhos, linhas = self._consultar()

        self.pasta_relatorios.mkdir(parents=True, exist_ok=True)
        caminho_relatorio = self._montar_caminho()
        if caminho_relatorio.exists():
            raise FileExistsError(
                f"Relatório já existe e não será sobrescrito: {caminho_relatorio}"
            )

        pasta_trabalho = Workbook()
        planilha = pasta_trabalho.active
        planilha.title = "dados_fila"
        planilha.append(cabecalhos)
        for linha in linhas:
            planilha.append(linha)
        self._formatar(planilha, len(cabecalhos))

        pasta_trabalho.save(caminho_relatorio)

        logger.info(
            "Relatório gerado com %d linha(s): %s", len(linhas), caminho_relatorio
        )
        return caminho_relatorio