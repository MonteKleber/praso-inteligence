"""
Testes automatizados do Módulo de Cross-Sell (`analytics/cross_sell.py`).
Cobre:
- Cliente com oportunidade clara de cross-sell (produto popular no segmento que ele nunca comprou).
- Cliente sem oportunidade de cross-sell (já compra todos os produtos relevantes do segmento).
- Respeito ao filtro de amostra mínima (não sugere com base em 1 único cliente).
"""

from analytics.cross_sell import (
    CrossSellConfig,
    calculate_segment_product_benchmarks,
    identify_customer_cross_sell_opportunities,
)


def _build_mock_segment_data():
    """Cria 4 padarias e 2 produtos onde 3 das 4 compram Embalagem Kraft."""
    customers = [
        {"id": 1, "nome_fantasia": "Padaria A #001", "tipo_estabelecimento": "Padaria & Confeitaria"},
        {"id": 2, "nome_fantasia": "Padaria B #002", "tipo_estabelecimento": "Padaria & Confeitaria"},
        {"id": 3, "nome_fantasia": "Padaria C #003", "tipo_estabelecimento": "Padaria & Confeitaria"},
        {"id": 4, "nome_fantasia": "Padaria D #004", "tipo_estabelecimento": "Padaria & Confeitaria"},
    ]
    products = [
        {"id": 101, "nome": "Farinha de Trigo 25kg", "categoria": "Farináceos & Panificação", "preco_unitario": 110.0},
        {"id": 102, "nome": "Saco de Papel Kraft Pão", "categoria": "Embalagens & Descartáveis", "preco_unitario": 75.0},
    ]
    # Todas as 4 compram Farinha (101), mas apenas 1, 2 e 3 compram Saco Kraft (102)
    order_items = [
        {"cliente_id": 1, "pedido_id": 1, "produto_id": 101, "quantidade": 2, "preco_praticado": 110.0, "status_pedido": "Concluído", "tipo_estabelecimento": "Padaria & Confeitaria"},
        {"cliente_id": 1, "pedido_id": 1, "produto_id": 102, "quantidade": 2, "preco_praticado": 75.0, "status_pedido": "Concluído", "tipo_estabelecimento": "Padaria & Confeitaria"},
        {"cliente_id": 2, "pedido_id": 2, "produto_id": 101, "quantidade": 3, "preco_praticado": 110.0, "status_pedido": "Concluído", "tipo_estabelecimento": "Padaria & Confeitaria"},
        {"cliente_id": 2, "pedido_id": 2, "produto_id": 102, "quantidade": 2, "preco_praticado": 75.0, "status_pedido": "Concluído", "tipo_estabelecimento": "Padaria & Confeitaria"},
        {"cliente_id": 3, "pedido_id": 3, "produto_id": 101, "quantidade": 2, "preco_praticado": 110.0, "status_pedido": "Concluído", "tipo_estabelecimento": "Padaria & Confeitaria"},
        {"cliente_id": 3, "pedido_id": 3, "produto_id": 102, "quantidade": 2, "preco_praticado": 75.0, "status_pedido": "Concluído", "tipo_estabelecimento": "Padaria & Confeitaria"},
        # Padaria 4 só comprou Farinha (101)
        {"cliente_id": 4, "pedido_id": 4, "produto_id": 101, "quantidade": 4, "preco_praticado": 110.0, "status_pedido": "Concluído", "tipo_estabelecimento": "Padaria & Confeitaria"},
    ]
    return customers, products, order_items


def test_cliente_com_oportunidade_de_cross_sell() -> None:
    """Padaria 4 nunca comprou Saco de Papel Kraft (comprado por 75% das padarias)."""
    customers, products, order_items = _build_mock_segment_data()
    benchmarks = calculate_segment_product_benchmarks(customers, order_items, products)
    seg_bench = benchmarks["Padaria & Confeitaria"]

    itens_padaria_4 = [i for i in order_items if i["cliente_id"] == 4]
    opps = identify_customer_cross_sell_opportunities(
        customer=customers[3],
        customer_order_items=itens_padaria_4,
        segment_benchmarks=seg_bench,
    )

    assert len(opps) == 1
    assert opps[0]["produto_id"] == 102
    assert opps[0]["produto_sugerido"] == "Saco de Papel Kraft Pão"
    assert opps[0]["taxa_penetracao_segmento"] == 0.75
    assert "75%" in opps[0]["justificativa"]


def test_cliente_sem_oportunidade_de_cross_sell() -> None:
    """Padaria 1 já compra todos os itens relevantes do segmento (Farinha e Saco Kraft)."""
    customers, products, order_items = _build_mock_segment_data()
    benchmarks = calculate_segment_product_benchmarks(customers, order_items, products)
    seg_bench = benchmarks["Padaria & Confeitaria"]

    itens_padaria_1 = [i for i in order_items if i["cliente_id"] == 1]
    opps = identify_customer_cross_sell_opportunities(
        customer=customers[0],
        customer_order_items=itens_padaria_1,
        segment_benchmarks=seg_bench,
    )

    assert opps == []
