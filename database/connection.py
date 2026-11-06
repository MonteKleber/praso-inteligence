"""
Gerenciador de conexão SQLite e inicialização do esquema do Praso Intelligence.

Garante que todas as conexões habilitem a verificação de chaves estrangeiras
(`PRAGMA foreign_keys = ON`) e retornem linhas acessíveis por nome de coluna.
"""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Generator, Optional

# Caminhos absolutos baseados na localização deste módulo
DATABASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = DATABASE_DIR / "praso_intelligence.db"
SCHEMA_PATH = DATABASE_DIR / "schema.sql"


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """
    Cria e configura uma conexão com o banco SQLite.

    Por que `PRAGMA foreign_keys = ON` é executado aqui?
    No SQLite, a verificação de chaves estrangeiras vem desativada por padrão
    em cada nova conexão. Ativá-la garante integridade referencial real.
    """
    target_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_session(db_path: Optional[Path | str] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager transacional para operações seguras no banco de dados.
    Realiza commit automático em caso de sucesso ou rollback em caso de exceção,
    fechando a conexão ao final.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Path | str] = None, schema_path: Optional[Path | str] = None) -> None:
    """
    Lê o arquivo DDL `schema.sql` e cria as tabelas e índices no banco de dados.
    """
    target_schema = Path(schema_path) if schema_path is not None else SCHEMA_PATH
    if not target_schema.exists():
        raise FileNotFoundError(f"Arquivo de schema não encontrado em: {target_schema}")

    schema_sql = target_schema.read_text(encoding="utf-8")
    with db_session(db_path) as conn:
        conn.executescript(schema_sql)


def inspect_schema_tables(db_path: Optional[Path | str] = None) -> list[str]:
    """
    Retorna a lista de tabelas de domínio criadas no banco (útil para diagnóstico e testes).
    """
    query = """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name;
    """
    with db_session(db_path) as conn:
        rows = conn.execute(query).fetchall()
        return [row["name"] for row in rows]
