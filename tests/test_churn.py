"""
Testes automatizados do Módulo de Classificação Heurística de Churn (`analytics/churn.py`).
Cobre:
- Cliente recorrente (Saudável).
- Cliente com intervalo crescente / desaceleração (Atenção).
- Cliente em Risco moderado.
- Cliente com atraso significativo (Alto risco).
- Cliente com histórico insuficiente (0 ou 1 pedido) -> Nunca classificado como churn.
"""

from analytics.churn import (
    STATUS_ALTO_RISCO,
    STATUS_ATENCAO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_RISCO_MODERADO,
    STATUS_SAUDAVEL,
    classify_customer_churn_risk,
    detect_interval_trend,
)
from analytics.repurchase import analyze_customer_repurchase


def test_cliente_com_historico_insuficiente_nao_vira_churn() -> None:
    """Clientes com 0 ou 1 pedido devem receber 'Dados insuficientes' e em_risco_comercial=False."""
    customer = {"id": 1, "nome_fantasia": "Padaria Nova #001"}
    orders_1 = [
        {"id": 1, "cliente_id": 1, "data_compra": "2026-09-01", "valor_total": 400.0, "status_pedido": "Concluído"}
    ]
    rep_1 = analyze_customer_repurchase(customer, orders_1, reference_date="2026-11-05")
    churn_1 = classify_customer_churn_risk(rep_1)

    assert churn_1["classificacao_risco"] == STATUS_DADOS_INSUFICIENTES
    assert churn_1["em_risco_comercial"] is False
    assert churn_1["indice_atraso"] is None


def test_classificacao_das_quatro_faixas_de_risco() -> None:
    """Valida Saudável, Atenção, Risco moderado e Alto risco para um ciclo mediano de 10 dias."""
    customer = {"id": 2, "nome_fantasia": "Restaurante Ciclo 10 #002"}
    orders = [
        {"id": 1, "cliente_id": 2, "data_compra": "2026-09-10", "valor_total": 500.0, "status_pedido": "Concluído"},
        {"id": 2, "cliente_id": 2, "data_compra": "2026-09-20", "valor_total": 500.0, "status_pedido": "Concluído"},
        {"id": 3, "cliente_id": 2, "data_compra": "2026-09-30", "valor_total": 500.0, "status_pedido": "Concluído"},
    ]

    # 1. Saudável: 10 dias após última compra (índice = 1.0 <= 1.15)
    rep_saudavel = analyze_customer_repurchase(customer, orders, reference_date="2026-10-10")
    res_saudavel = classify_customer_churn_risk(rep_saudavel)
    assert res_saudavel["classificacao_risco"] == STATUS_SAUDAVEL
    assert res_saudavel["em_risco_comercial"] is False

    # 2. Atenção: 13 dias após última compra (índice = 1.30, entre 1.15 e 1.50)
    rep_atencao = analyze_customer_repurchase(customer, orders, reference_date="2026-10-13")
    res_atencao = classify_customer_churn_risk(rep_atencao)
    assert res_atencao["classificacao_risco"] == STATUS_ATENCAO
    assert res_atencao["em_risco_comercial"] is True

    # 3. Risco moderado: 20 dias após última compra (índice = 2.00, entre 1.50 e 2.50)
    rep_moderado = analyze_customer_repurchase(customer, orders, reference_date="2026-10-20")
    res_moderado = classify_customer_churn_risk(rep_moderado)
    assert res_moderado["classificacao_risco"] == STATUS_RISCO_MODERADO
    assert res_moderado["em_risco_comercial"] is True

    # 4. Alto risco: 30 dias após última compra (índice = 3.00 > 2.50)
    rep_alto = analyze_customer_repurchase(customer, orders, reference_date="2026-10-30")
    res_alto = classify_customer_churn_risk(rep_alto)
    assert res_alto["classificacao_risco"] == STATUS_ALTO_RISCO
    assert res_alto["em_risco_comercial"] is True
    assert res_alto["indice_atraso"] == 3.0


def test_deteccao_cliente_com_intervalo_crescente() -> None:
    """Verifica detecção de tendência de desaceleração quando o último intervalo aumenta."""
    intervalos_crescentes = [7, 7, 8, 14]
    assert detect_interval_trend(intervalos_crescentes) == "Desacelerando (intervalo crescente)"

    intervalos_estaveis = [10, 10, 11, 10]
    assert detect_interval_trend(intervalos_estaveis) == "Estável"
