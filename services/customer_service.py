"""
Serviço de acesso e preparação de dados de Clientes B2B.

Centraliza todas as consultas SQL relacionadas à tabela `clientes`, evitando
que os módulos analíticos (`analytics/`) ou a interface (`pages/`) executem
SQL diretamente.
"""

from pathlib import Path
from typing import Any, Optional

from database.connection import db_session


def get_all_customers(
    db_path: Optional[Path | str] = None,
    cidade: Optional[str] = None,
    tipo_estabelecimento: Optional[str] = None,
    responsavel_comercial: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Retorna a lista de clientes cadastrados como dicionários Python,
    permitindo filtros opcionais por cidade, segmento e vendedor responsável.
    """
    query = """
        SELECT
            id,
            nome_fantasia,
            tipo_estabelecimento,
            cidade,
            data_cadastro,
            status_relacionamento,
            responsavel_comercial
        FROM clientes
        WHERE 1 = 1
    """
    params: list[Any] = []

    if cidade:
        query += " AND cidade = ?"
        params.append(cidade)

    if tipo_estabelecimento:
        query += " AND tipo_estabelecimento = ?"
        params.append(tipo_estabelecimento)

    if responsavel_comercial:
        query += " AND responsavel_comercial = ?"
        params.append(responsavel_comercial)

    query += " ORDER BY id ASC;"

    with db_session(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_customer_by_id(
    cliente_id: int,
    db_path: Optional[Path | str] = None,
) -> Optional[dict[str, Any]]:
    """
    Busca os dados cadastrais de um cliente específico pelo seu ID.
    Retorna `None` caso o cliente não exista.
    """
    query = """
        SELECT
            id,
            nome_fantasia,
            tipo_estabelecimento,
            cidade,
            data_cadastro,
            status_relacionamento,
            responsavel_comercial
        FROM clientes
        WHERE id = ?;
    """
    with db_session(db_path) as conn:
        row = conn.execute(query, (cliente_id,)).fetchone()
        return dict(row) if row is not None else None


def get_distinct_filter_options(db_path: Optional[Path | str] = None) -> dict[str, list[str]]:
    """
    Retorna as listas de valores únicos de cidades, tipos de estabelecimento
    e responsáveis comerciais presentes na base para alimentar filtros.
    """
    with db_session(db_path) as conn:
        cidades = [
            r[0] for r in conn.execute("SELECT DISTINCT cidade FROM clientes ORDER BY cidade;").fetchall()
        ]
        segmentos = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT tipo_estabelecimento FROM clientes ORDER BY tipo_estabelecimento;"
            ).fetchall()
        ]
        responsaveis = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT responsavel_comercial FROM clientes ORDER BY responsavel_comercial;"
            ).fetchall()
        ]

    return {
        "cidades": cidades,
        "tipos_estabelecimento": segmentos,
        "responsaveis_comerciais": responsaveis,
    }
