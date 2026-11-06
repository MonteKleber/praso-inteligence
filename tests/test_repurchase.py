"""
Testes automatizados do Módulo de Recompra (`analytics/repurchase.py`).
Cobre:
- Cliente sem pedidos (0 compras) -> diferenciação entre None e 0.
- Cliente com apenas 1 pedido -> sem intervalo calculável, sem previsão artificial.
- Cliente recorrente regular -> cálculo de média, mediana, desvio padrão e próxima compra.
- Cliente com outlier no intervalo -> mediana mais robusta que a média.
- Pedidos cancelados ignorados no cálculo de ciclo de abastecimento.
"""

from datetime import date
from analytics.repurchase import analyze_customer_repurchase, calculate_order_intervals


def test_cliente_sem_pedidos_retorna_nulos_e_zeros_corretos() -> None:
    """Cliente sem histórico deve ter quantidade=0, valor=0.0 e métricas de ciclo=None."""
    customer = {
        "id": 10,
        "nome_fantasia": "Padaria Sem Pedidos #010",
        "tipo_estabelecimento": "Padaria & Confeitaria",
        "cidade": "Recife",
        "responsavel_comercial": "Ana Beatriz Silva",
        "data_cadastro": "2026-10-01",
    }
    res = analyze_customer_repurchase(customer, orders=[], reference_date="2026-11-05")

    assert res["quantidade_pedidos"] == 0
    assert res["valor_total_historico"] == 0.0
    assert res["ticket_medio"] is None
    assert res["intervalo_medio_dias"] is None
    assert res["intervalo_mediano_dias"] is None
    assert res["proxima_compra_estimada"] is None
    assert res["dias_desde_ultima_compra"] is None
    assert res["historico_suficiente_para_ciclo"] is False


def test_cliente_com_apenas_um_pedido_nao_gera_previsao_artificial() -> None:
    """Cliente com 1 pedido tem ticket médio e última compra, mas não tem ciclo nem previsão."""
    customer = {
        "id": 11,
        "nome_fantasia": "Mercadinho Novo #011",
        "tipo_estabelecimento": "Mercadinho & Mercearia",
        "cidade": "Fortaleza",
        "responsavel_comercial": "Lucas Oliveira",
    }
    orders = [
        {"id": 1, "cliente_id": 11, "data_compra": "2026-10-25", "valor_total": 850.0, "status_pedido": "Concluído"}
    ]
    res = analyze_customer_repurchase(customer, orders=orders, reference_date="2026-11-05")

    assert res["quantidade_pedidos"] == 1
    assert res["valor_total_historico"] == 850.0
    assert res["ticket_medio"] == 850.0
    assert res["ultima_compra"] == "2026-10-25"
    assert res["dias_desde_ultima_compra"] == 11
    assert res["intervalo_medio_dias"] is None
    assert res["intervalo_mediano_dias"] is None
    assert res["proxima_compra_estimada"] is None
    assert res["historico_suficiente_para_ciclo"] is False


def test_cliente_recorrente_E_robustez_da_mediana_contra_outlier() -> None:
    """
    Se um cliente compra a cada 10 dias (intervalos: 10, 10, 10, 50),
    a média sobe para 20.0, mas a mediana permanece em 10.0 dias.
    """
    customer = {
        "id": 12,
        "nome_fantasia": "Restaurante Fiel #012",
        "tipo_estabelecimento": "Restaurante",
        "cidade": "Recife",
    }
    orders = [
        {"id": 1, "cliente_id": 12, "data_compra": "2026-08-01", "valor_total": 1000.0, "status_pedido": "Concluído"},
        {"id": 2, "cliente_id": 12, "data_compra": "2026-08-11", "valor_total": 1200.0, "status_pedido": "Concluído"},
        {"id": 3, "cliente_id": 12, "data_compra": "2026-08-21", "valor_total": 1100.0, "status_pedido": "Concluído"},
        {"id": 4, "cliente_id": 12, "data_compra": "2026-10-10", "valor_total": 1300.0, "status_pedido": "Concluído"},  # +50 dias (outlier)
        {"id": 5, "cliente_id": 12, "data_compra": "2026-10-20", "valor_total": 1400.0, "status_pedido": "Concluído"},  # +10 dias
    ]
    res = analyze_customer_repurchase(customer, orders=orders, reference_date=date(2026, 10, 25))

    assert res["quantidade_pedidos"] == 5
    assert res["intervalos_dias"] == [10, 10, 50, 10]
    assert res["intervalo_medio_dias"] == 20.0
    assert res["intervalo_mediano_dias"] == 10.0
    assert res["ticket_medio"] == 1200.0
    assert res["valor_total_historico"] == 6000.0
    assert res["proxima_compra_estimada"] == "2026-10-30"
    assert res["dias_desde_ultima_compra"] == 5
    assert res["historico_suficiente_para_ciclo"] is True


def test_pedidos_cancelados_sao_ignorados_na_recompra() -> None:
    """Pedidos com status 'Cancelado' não devem afetar ciclo nem valor histórico."""
    customer = {"id": 13, "nome_fantasia": "Bar Teste #013"}
    orders = [
        {"id": 1, "cliente_id": 13, "data_compra": "2026-10-01", "valor_total": 500.0, "status_pedido": "Concluído"},
        {"id": 2, "cliente_id": 13, "data_compra": "2026-10-05", "valor_total": 9999.0, "status_pedido": "Cancelado"},
        {"id": 3, "cliente_id": 13, "data_compra": "2026-10-15", "valor_total": 700.0, "status_pedido": "Concluído"},
    ]
    res = analyze_customer_repurchase(customer, orders=orders, reference_date="2026-10-20")

    assert res["quantidade_pedidos"] == 2
    assert res["valor_total_historico"] == 1200.0
    assert res["intervalo_mediano_dias"] == 14.0
