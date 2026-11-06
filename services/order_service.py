"""
Serviço de acesso e preparação de dados de Pedidos, Produtos e Itens de Pedido.

Importante para a integridade dos cálculos comerciais:
- Consultas de faturamento e frequência de pedidos (`get_orders`) leem APENAS a
  tabela `pedidos` (com opção de dados cadastrais via JOIN 1:1 com `clientes`),
  NUNCA fazendo JOIN direto com `itens_pedido` sem agregação prévia, evitando a
  duplicação de valores de pedidos.
- Consultas de mix de produtos e cross-sell (`get_order_items_enriched`) trazem
  a granularidade de item (`itens_pedido` + `produtos` + `pedidos` + `clientes`).
"""

from pathlib import Path
from typing import Any, Optional

from database.connection import db_session


def get_orders(
    db_path: Optional[Path | str] = None,
    cliente_id: Optional[int] = None,
    only_completed: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Retorna a lista de pedidos ordenada por `cliente_id` e `data_compra` crescente.

    Por padrão (`only_completed=True`), filtra apenas pedidos com
    `status_pedido = 'Concluído'`, pois pedidos cancelados não representam
    abastecimento efetivo de estoque pelo cliente.
    """
    query = """
        SELECT
            p.id,
            p.cliente_id,
            p.data_compra,
            p.valor_total,
            p.quantidade_produtos,
            p.status_pedido
        FROM pedidos p
        WHERE 1 = 1
    """
    params: list[Any] = []

    if only_completed:
        query += " AND p.status_pedido = 'Concluído'"

    if cliente_id is not None:
        query += " AND p.cliente_id = ?"
        params.append(cliente_id)

    if start_date:
        query += " AND p.data_compra >= ?"
        params.append(start_date)

    if end_date:
        query += " AND p.data_compra <= ?"
        params.append(end_date)

    query += " ORDER BY p.cliente_id ASC, p.data_compra ASC, p.id ASC;"

    with db_session(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_orders_grouped_by_customer(
    db_path: Optional[Path | str] = None,
    only_completed: bool = True,
) -> dict[int, list[dict[str, Any]]]:
    """
    Agrupa todos os pedidos em um dicionário `{cliente_id: [lista_de_pedidos]}`
    já ordenados cronologicamente. Ideal para processar toda a carteira em O(N)
    sem executar 100 queries separadas (evita o problema N+1 queries).
    """
    orders = get_orders(db_path=db_path, only_completed=only_completed)
    grouped: dict[int, list[dict[str, Any]]] = {}
    for order in orders:
        cid = int(order["cliente_id"])
        if cid not in grouped:
            grouped[cid] = []
        grouped[cid].append(order)
    return grouped


def get_all_products(db_path: Optional[Path | str] = None) -> list[dict[str, Any]]:
    """Retorna todos os produtos do catálogo B2B."""
    query = """
        SELECT
            id,
            nome,
            categoria,
            preco_unitario,
            custo_unitario
        FROM produtos
        ORDER BY id ASC;
    """
    with db_session(db_path) as conn:
        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]


def get_order_items_enriched(
    db_path: Optional[Path | str] = None,
    cliente_id: Optional[int] = None,
    only_completed: bool = True,
) -> list[dict[str, Any]]:
    """
    Retorna os itens dos pedidos enriquecidos com informações do pedido,
    do cliente (segmento e cidade) e do produto (nome e categoria).
    Usado exclusivamente para análises de mix de produtos e Cross-Sell.
    """
    query = """
        SELECT
            i.id AS item_id,
            i.pedido_id,
            p.cliente_id,
            c.nome_fantasia,
            c.tipo_estabelecimento,
            c.cidade,
            p.data_compra,
            p.status_pedido,
            i.produto_id,
            pr.nome AS produto_nome,
            pr.categoria AS produto_categoria,
            pr.preco_unitario AS preco_catalogo,
            pr.custo_unitario,
            i.quantidade,
            i.preco_praticado,
            ROUND(i.quantidade * i.preco_praticado, 2) AS subtotal_item
        FROM itens_pedido i
        JOIN pedidos p ON p.id = i.pedido_id
        JOIN clientes c ON c.id = p.cliente_id
        JOIN produtos pr ON pr.id = i.produto_id
        WHERE 1 = 1
    """
    params: list[Any] = []

    if only_completed:
        query += " AND p.status_pedido = 'Concluído'"

    if cliente_id is not None:
        query += " AND p.cliente_id = ?"
        params.append(cliente_id)

    query += " ORDER BY p.data_compra ASC, i.pedido_id ASC, i.produto_id ASC;"

    with db_session(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
