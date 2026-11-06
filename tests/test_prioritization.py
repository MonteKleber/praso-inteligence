"""
Testes automatizados do Módulo de Priorização Comercial (`analytics/prioritization.py`).
Cobre:
- Cliente de alto valor e alto risco priorizado à frente de cliente de baixo valor.
- Resolução determinística de empates na pontuação de prioridade (tie-breaking).
- Geração da recomendação comercial e sugestão de mensagem de WhatsApp.
"""

from analytics.churn import STATUS_ALTO_RISCO, STATUS_SAUDAVEL
from analytics.prioritization import prioritize_customers


def test_cliente_alto_risco_e_alto_ticket_fica_no_topo() -> None:
    """Garante que um cliente em alto risco e ticket elevado receba ranking #1."""
    clientes_metricas = [
        {
            "cliente_id": 1,
            "nome_fantasia": "Lanchonete Saudável Pequena #001",
            "tipo_estabelecimento": "Hamburgueria & Lanchonete",
            "cidade": "Recife",
            "responsavel_comercial": "Ana",
            "quantidade_pedidos": 5,
            "dias_desde_ultima_compra": 4,
            "intervalo_mediano_dias": 10.0,
            "indice_atraso": 0.4,
            "classificacao_risco": STATUS_SAUDAVEL,
            "em_risco_comercial": False,
            "ticket_medio": 400.0,
            "receita_historica": 2000.0,
            "receita_mensal_estimada": 1200.0,
            "receita_em_risco": 0.0,
        },
        {
            "cliente_id": 2,
            "nome_fantasia": "Padaria VIP em Alto Risco #002",
            "tipo_estabelecimento": "Padaria & Confeitaria",
            "cidade": "Fortaleza",
            "responsavel_comercial": "Lucas",
            "quantidade_pedidos": 10,
            "dias_desde_ultima_compra": 35,
            "intervalo_mediano_dias": 10.0,
            "indice_atraso": 3.5,
            "classificacao_risco": STATUS_ALTO_RISCO,
            "em_risco_comercial": True,
            "ticket_medio": 2500.0,
            "receita_historica": 25000.0,
            "receita_mensal_estimada": 7500.0,
            "receita_em_risco": 7500.0,
        },
    ]

    priorizados = prioritize_customers(clientes_metricas)
    assert priorizados[0]["cliente_id"] == 2
    assert priorizados[0]["ranking_prioridade"] == 1
    assert priorizados[0]["score_prioridade"] > priorizados[1]["score_prioridade"]
    assert "Padaria VIP em Alto Risco #002" in priorizados[0]["sugestao_mensagem_whatsapp"]


def test_desempate_deterministico_na_pontuacao_de_prioridade() -> None:
    """
    Dois clientes com métricas idênticas (empate perfeito de score) devem ser
    desempatados de forma determinística e reproduzível pelo menor cliente_id
    (ou maior dias_desde_ultima_compra se um deles tiver mais dias).
    """
    base_item = {
        "tipo_estabelecimento": "Restaurante",
        "cidade": "Recife",
        "responsavel_comercial": "Carlos",
        "quantidade_pedidos": 6,
        "intervalo_mediano_dias": 10.0,
        "indice_atraso": 3.0,
        "classificacao_risco": STATUS_ALTO_RISCO,
        "em_risco_comercial": True,
        "ticket_medio": 1000.0,
        "receita_historica": 6000.0,
        "receita_mensal_estimada": 3000.0,
        "receita_em_risco": 3000.0,
    }
    c_maior_id = {**base_item, "cliente_id": 50, "nome_fantasia": "Restaurante 50", "dias_desde_ultima_compra": 30}
    c_menor_id = {**base_item, "cliente_id": 10, "nome_fantasia": "Restaurante 10", "dias_desde_ultima_compra": 30}

    resultado = prioritize_customers([c_maior_id, c_menor_id])

    assert resultado[0]["score_prioridade"] == resultado[1]["score_prioridade"]
    assert resultado[0]["cliente_id"] == 10
    assert resultado[0]["ranking_prioridade"] == 1
    assert resultado[1]["cliente_id"] == 50
    assert resultado[1]["ranking_prioridade"] == 2
