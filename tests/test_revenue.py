"""
Testes automatizados do Módulo de Receita (`analytics/revenue.py`).
Cobre:
- Diferenciação clara entre receita histórica, potencial mensal e receita em risco.
- Cliente com receita histórica elevada e alto risco.
- Cliente saudável (receita em risco = 0.0).
- Agregação por cidade e segmento sem duplicação de faturamento.
"""

from analytics.churn import classify_customer_churn_risk
from analytics.repurchase import analyze_customer_repurchase
from analytics.revenue import calculate_customer_revenue_metrics, summarize_revenue_by_dimension


def test_calculo_receita_cliente_elevado_valor_em_alto_risco() -> None:
    """
    Cliente que compra R$ 2.000 a cada 10 dias (3x por mês = R$ 6.000/mês estimados)
    e está em Alto Risco (fator 1.0) deve ter R$ 6.000,00 de receita mensal em risco.
    """
    customer = {
        "id": 20,
        "nome_fantasia": "Padaria Grande Porte #020",
        "tipo_estabelecimento": "Padaria & Confeitaria",
        "cidade": "Recife",
    }
    orders = [
        {"id": 1, "cliente_id": 20, "data_compra": "2026-08-01", "valor_total": 2000.0, "status_pedido": "Concluído"},
        {"id": 2, "cliente_id": 20, "data_compra": "2026-08-11", "valor_total": 2000.0, "status_pedido": "Concluído"},
        {"id": 3, "cliente_id": 20, "data_compra": "2026-08-21", "valor_total": 2000.0, "status_pedido": "Concluído"},
    ]
    # Data de referência 40 dias após a última compra -> Alto risco (índice 4.0)
    rep = analyze_customer_repurchase(customer, orders, reference_date="2026-09-30")
    churn = classify_customer_churn_risk(rep)
    rev = calculate_customer_revenue_metrics(churn)

    assert rev["receita_historica"] == 6000.0
    assert rev["receita_historica_cliente_em_risco"] == 6000.0
    assert rev["receita_media_por_pedido"] == 2000.0
    assert rev["receita_mensal_estimada"] == 6000.0
    assert rev["receita_potencial_recompra"] == 2000.0
    assert rev["fator_exposicao_risco"] == 1.0
    assert rev["receita_em_risco"] == 6000.0


def test_cliente_saudavel_possui_zero_receita_em_risco() -> None:
    """Cliente em dia com seu ciclo tem receita potencial mensal, mas R$ 0,00 em risco."""
    customer = {"id": 21, "nome_fantasia": "Restaurante Saudável #021", "cidade": "Fortaleza"}
    orders = [
        {"id": 1, "cliente_id": 21, "data_compra": "2026-10-01", "valor_total": 1500.0, "status_pedido": "Concluído"},
        {"id": 2, "cliente_id": 21, "data_compra": "2026-10-16", "valor_total": 1500.0, "status_pedido": "Concluído"},
    ]
    rep = analyze_customer_repurchase(customer, orders, reference_date="2026-10-20")
    churn = classify_customer_churn_risk(rep)
    rev = calculate_customer_revenue_metrics(churn)

    assert rev["receita_historica"] == 3000.0
    assert rev["receita_historica_cliente_em_risco"] == 0.0
    assert rev["receita_mensal_estimada"] == 3000.0
    assert rev["receita_em_risco"] == 0.0


def test_agregacao_receita_por_cidade_e_segmento() -> None:
    """Verifica se summarize_revenue_by_dimension soma valores corretamente."""
    registros = [
        {
            "cidade": "Recife",
            "tipo_estabelecimento": "Padaria & Confeitaria",
            "em_risco_comercial": True,
            "quantidade_pedidos": 4,
            "receita_historica": 4000.0,
            "receita_mensal_estimada": 2000.0,
            "receita_em_risco": 2000.0,
        },
        {
            "cidade": "Recife",
            "tipo_estabelecimento": "Restaurante",
            "em_risco_comercial": False,
            "quantidade_pedidos": 2,
            "receita_historica": 2000.0,
            "receita_mensal_estimada": 1000.0,
            "receita_em_risco": 0.0,
        },
        {
            "cidade": "Fortaleza",
            "tipo_estabelecimento": "Padaria & Confeitaria",
            "em_risco_comercial": False,
            "quantidade_pedidos": 3,
            "receita_historica": 3000.0,
            "receita_mensal_estimada": 1500.0,
            "receita_em_risco": 0.0,
        },
    ]

    por_cidade = summarize_revenue_by_dimension(registros, "cidade")
    assert len(por_cidade) == 2
    assert por_cidade[0]["cidade"] == "Recife"
    assert por_cidade[0]["receita_historica"] == 6000.0
    assert por_cidade[0]["receita_em_risco"] == 2000.0
    assert por_cidade[0]["ticket_medio_grupo"] == 1000.0
