"""
Testes automatizados para validar a Etapa 3 (Geração de Dados Sintéticos - database/seed.py).

Verifica:
- Quantidade exata de clientes (100) e produtos (20).
- Volume aproximado de pedidos (~1.000 pedidos) distribuídos em ~12 meses.
- Existência de múltiplos itens nos pedidos e consistência matemática dos valores.
- Integridade das chaves estrangeiras e restrições do banco.
- Ausência de registros duplicados.
- Reprodutibilidade determinística com seed fixa.
- Idempotência (executar `seed_database` repetidas vezes não duplica registros).
"""

from pathlib import Path
import pytest

from database.connection import db_session
from database.seed import (
    DEFAULT_SEED,
    PERFIL_SEGMENTOS,
    generate_synthetic_dataset,
    seed_database,
)


@pytest.fixture
def seeded_temp_db(tmp_path: Path) -> Path:
    """Cria e popula um banco SQLite temporário isolado para os testes do seed."""
    db_file = tmp_path / "test_seed_praso.db"
    seed_database(db_path=db_file, seed=DEFAULT_SEED)
    return db_file


def test_quantidades_clientes_produtos_e_pedidos(seeded_temp_db: Path) -> None:
    """Verifica se o banco contém 100 clientes, 20 produtos e ~1.000 pedidos com itens."""
    with db_session(seeded_temp_db) as conn:
        qtd_clientes = conn.execute("SELECT COUNT(*) FROM clientes;").fetchone()[0]
        qtd_produtos = conn.execute("SELECT COUNT(*) FROM produtos;").fetchone()[0]
        qtd_pedidos = conn.execute("SELECT COUNT(*) FROM pedidos;").fetchone()[0]
        qtd_itens = conn.execute("SELECT COUNT(*) FROM itens_pedido;").fetchone()[0]

    assert qtd_clientes == 100
    assert qtd_produtos == 20
    assert 900 <= qtd_pedidos <= 1300
    assert qtd_itens > qtd_pedidos * 2  # Multiplos itens por pedido em media


def test_todos_pedidos_possuem_itens_e_soma_consistente(seeded_temp_db: Path) -> None:
    """
    Garante que nenhum pedido ficou sem itens e que o valor_total do cabeçalho
    do pedido corresponde exatamente à soma de (quantidade * preco_praticado) dos seus itens.
    """
    with db_session(seeded_temp_db) as conn:
        pedidos_sem_itens = conn.execute(
            """
            SELECT COUNT(*)
            FROM pedidos p
            LEFT JOIN itens_pedido i ON p.id = i.pedido_id
            WHERE i.id IS NULL;
            """
        ).fetchone()[0]

        divergencias_valor = conn.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    p.id,
                    p.valor_total,
                    ROUND(SUM(i.quantidade * i.preco_praticado), 2) AS soma_itens
                FROM pedidos p
                JOIN itens_pedido i ON p.id = i.pedido_id
                GROUP BY p.id
                HAVING ABS(p.valor_total - soma_itens) > 0.01
            );
            """
        ).fetchone()[0]

    assert pedidos_sem_itens == 0
    assert divergencias_valor == 0


def test_integridade_chaves_estrangeiras_e_ausencia_duplicatas(seeded_temp_db: Path) -> None:
    """Verifica ausência de violações de FK no SQLite e ausência de nomes duplicados."""
    with db_session(seeded_temp_db) as conn:
        fk_errors = conn.execute("PRAGMA foreign_key_check;").fetchall()
        nomes_clientes_distintos = conn.execute(
            "SELECT COUNT(DISTINCT nome_fantasia) FROM clientes;"
        ).fetchone()[0]
        nomes_produtos_distintos = conn.execute(
            "SELECT COUNT(DISTINCT nome) FROM produtos;"
        ).fetchone()[0]

    assert len(fk_errors) == 0
    assert nomes_clientes_distintos == 100
    assert nomes_produtos_distintos == 20


def test_coerencia_comercial_produtos_por_segmento(seeded_temp_db: Path) -> None:
    """
    Garante que os itens comprados por um cliente pertencem exclusivamente aos produtos
    base ou complementares do segmento daquele estabelecimento (sem compras aleatórias sem sentido).
    """
    with db_session(seeded_temp_db) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT c.tipo_estabelecimento, i.produto_id
            FROM clientes c
            JOIN pedidos p ON p.cliente_id = c.id
            JOIN itens_pedido i ON i.pedido_id = p.id;
            """
        ).fetchall()

    for row in rows:
        segmento = row["tipo_estabelecimento"]
        prod_id = row["produto_id"]
        permitidos = set(
            PERFIL_SEGMENTOS[segmento]["produtos_base"]
            + PERFIL_SEGMENTOS[segmento]["produtos_complementares"]
        )
        assert prod_id in permitidos, (
            f"Produto {prod_id} não faz sentido comercial para o segmento {segmento}"
        )


def test_reprodutibilidade_com_seed_fixa() -> None:
    """Duas execuções em memória com a mesma seed devem produzir datasets idênticos."""
    dados_exec_1 = generate_synthetic_dataset(seed=42)
    dados_exec_2 = generate_synthetic_dataset(seed=42)

    assert dados_exec_1["clientes"] == dados_exec_2["clientes"]
    assert dados_exec_1["produtos"] == dados_exec_2["produtos"]
    assert dados_exec_1["pedidos"] == dados_exec_2["pedidos"]
    assert dados_exec_1["itens_pedido"] == dados_exec_2["itens_pedido"]


def test_idempotencia_execucao_repetida_nao_duplica(seeded_temp_db: Path) -> None:
    """
    Executar `seed_database` novamente sobre um banco já populado não deve
    duplicar linhas nem gerar erro de chave primária/única.
    """
    contagem_segunda_execucao = seed_database(db_path=seeded_temp_db, seed=DEFAULT_SEED)

    with db_session(seeded_temp_db) as conn:
        qtd_clientes = conn.execute("SELECT COUNT(*) FROM clientes;").fetchone()[0]
        qtd_produtos = conn.execute("SELECT COUNT(*) FROM produtos;").fetchone()[0]
        qtd_pedidos = conn.execute("SELECT COUNT(*) FROM pedidos;").fetchone()[0]
        qtd_itens = conn.execute("SELECT COUNT(*) FROM itens_pedido;").fetchone()[0]

    assert qtd_clientes == 100
    assert qtd_produtos == 20
    assert qtd_pedidos == contagem_segunda_execucao["pedidos"]
    assert qtd_itens == contagem_segunda_execucao["itens_pedido"]
