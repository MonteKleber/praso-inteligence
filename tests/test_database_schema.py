"""
Testes automatizados para validar a Etapa 2 (Modelagem do Banco de Dados).
Verifica criação das tabelas, chaves primárias, integridade referencial (FKs)
e restrições de domínio (CHECK / UNIQUE).
"""

from pathlib import Path
import sqlite3
import pytest

from database.connection import db_session, init_db, inspect_schema_tables


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Cria um banco SQLite temporário e inicializa o schema para cada teste."""
    db_file = tmp_path / "test_praso.db"
    init_db(db_file)
    return db_file


def test_criacao_tabelas_principais(temp_db: Path) -> None:
    """Garante que todas as 4 tabelas obrigatórias do modelo foram criadas."""
    tabelas = inspect_schema_tables(temp_db)
    assert tabelas == ["clientes", "itens_pedido", "pedidos", "produtos"]


def test_integridade_referencial_pedido_sem_cliente_falha(temp_db: Path) -> None:
    """Não deve permitir inserir um pedido apontando para um cliente inexistente."""
    with pytest.raises(sqlite3.IntegrityError):
        with db_session(temp_db) as conn:
            conn.execute(
                """
                INSERT INTO pedidos (cliente_id, data_compra, valor_total, quantidade_produtos, status_pedido)
                VALUES (9999, '2026-10-01', 500.0, 3, 'Concluído');
                """
            )


def test_unicidade_produto_no_mesmo_pedido(temp_db: Path) -> None:
    """
    Garante que o mesmo produto não seja duplicado em linhas separadas do mesmo pedido
    (evita distorção em consultas de cross-sell e frequência de itens).
    """
    with db_session(temp_db) as conn:
        conn.execute(
            """
            INSERT INTO clientes (nome_fantasia, tipo_estabelecimento, cidade, data_cadastro, status_relacionamento, responsavel_comercial)
            VALUES ('Padaria São José', 'Padaria & Confeitaria', 'Recife', '2026-01-10', 'Ativo', 'Ana Silva');
            """
        )
        conn.execute(
            """
            INSERT INTO produtos (nome, categoria, preco_unitario, custo_unitario)
            VALUES ('Farinha de Trigo Especial 25kg', 'Farináceos & Panificação', 110.0, 82.0);
            """
        )
        conn.execute(
            """
            INSERT INTO pedidos (cliente_id, data_compra, valor_total, quantidade_produtos, status_pedido)
            VALUES (1, '2026-05-10', 220.0, 2, 'Concluído');
            """
        )
        conn.execute(
            """
            INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_praticado)
            VALUES (1, 1, 2, 110.0);
            """
        )

    # Tentar inserir o mesmo produto (id=1) novamente no mesmo pedido (id=1) deve falhar
    with pytest.raises(sqlite3.IntegrityError):
        with db_session(temp_db) as conn:
            conn.execute(
                """
                INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_praticado)
                VALUES (1, 1, 1, 110.0);
                """
            )


def test_validacao_check_constraints(temp_db: Path) -> None:
    """Garante que cidades inválidas ou custos maiores que o preço sejam bloqueados pelo banco."""
    # Cidade fora de Recife/Fortaleza
    with pytest.raises(sqlite3.IntegrityError):
        with db_session(temp_db) as conn:
            conn.execute(
                """
                INSERT INTO clientes (nome_fantasia, tipo_estabelecimento, cidade, data_cadastro, status_relacionamento, responsavel_comercial)
                VALUES ('Bar do Centro', 'Bar & Petiscaria', 'São Paulo', '2026-01-10', 'Ativo', 'Carlos Mendes');
                """
            )

    # Custo maior que preço unitário
    with pytest.raises(sqlite3.IntegrityError):
        with db_session(temp_db) as conn:
            conn.execute(
                """
                INSERT INTO produtos (nome, categoria, preco_unitario, custo_unitario)
                VALUES ('Óleo de Algodão 15L', 'Óleos, Gorduras & Conservas', 90.0, 120.0);
                """
            )
