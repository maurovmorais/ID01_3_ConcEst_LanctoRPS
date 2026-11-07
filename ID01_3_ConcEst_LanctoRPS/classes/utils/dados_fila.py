"""Persistência dos itens da fila em SQLite (tabela tbl_dados_fila)."""

import hashlib
import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CAMINHO_BANCO = Path(
    r"C:\Armazenamento\ID01_3_ConcEst_LanctoRPS\Banco Dados\banco_dados.db"
)

SQL_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS tbl_dados_fila (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_item_fila TEXT NOT NULL,
    adquirente TEXT,
    softcase TEXT,
    bandeira TEXT,
    dias_comp TEXT,
    valor_taxa TEXT,
    taxa_adquirente TEXT,
    forma_pagto TEXT,
    forma_pagamento TEXT,
    valor TEXT,
    data_ref TEXT,
    hash_item TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL
)
"""

SQL_INSERIR = """
INSERT OR IGNORE INTO tbl_dados_fila (
    id_item_fila, adquirente, softcase, bandeira, dias_comp, valor_taxa,
    taxa_adquirente, forma_pagto, forma_pagamento, valor, data_ref,
    hash_item, timestamp
) VALUES (
    :id_item_fila, :adquirente, :softcase, :bandeira, :dias_comp,
    :valor_taxa, :taxa_adquirente, :forma_pagto, :forma_pagamento,
    :valor, :data_ref, :hash_item, :timestamp
)
"""

CAMPOS = (
    "adquirente", "softcase", "bandeira", "dias_comp", "valor_taxa",
    "taxa_adquirente", "forma_pagto", "forma_pagamento", "valor", "data_ref",
)


class DadosFila:
    """Grava os itens processados da fila sem duplicar reprocessamentos."""

    def __init__(self, caminho_banco: Path = CAMINHO_BANCO) -> None:
        self.caminho_banco = Path(caminho_banco)
        self._criar_tabela()

    def _conectar(self) -> sqlite3.Connection:
        return sqlite3.connect(self.caminho_banco)

    def _criar_tabela(self) -> None:
        """Cria pasta, banco e tabela apenas se ainda não existirem."""
        self.caminho_banco.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conectar()) as conexao, conexao:
            conexao.execute(SQL_CRIAR_TABELA)

    @staticmethod
    def _gerar_hash(dado: dict, id_item_fila: str) -> str:
        """Gera a chave única: conteúdo do dado + identificador na fila."""
        base = {campo: dado.get(campo) for campo in CAMPOS}
        base["id_item_fila"] = id_item_fila
        texto = json.dumps(base, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(texto.encode("utf-8")).hexdigest()

    def inserir_item(self, dado: dict, id_item_fila: str | int) -> bool:
        """Insere o item na tabela.

        Args:
            dado: dicionário `info_adicionais[0]` da fila.
            id_item_fila: identificador do item na fila (o mesmo valor
                em todo reprocessamento desse item).

        Returns:
            True se inseriu; False se o item já existia (reprocessamento).
        """
        id_item_fila = str(id_item_fila)
        registro = {campo: dado.get(campo) for campo in CAMPOS}
        registro["id_item_fila"] = id_item_fila
        registro["hash_item"] = self._gerar_hash(dado, id_item_fila)
        registro["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with closing(self._conectar()) as conexao, conexao:
            cursor = conexao.execute(SQL_INSERIR, registro)
            inserido = cursor.rowcount == 1

        if inserido:
            logger.info("Item %s gravado em tbl_dados_fila.", id_item_fila)
        else:
            logger.info(
                "Item %s já existe em tbl_dados_fila, ignorado.", id_item_fila
            )
        return inserido