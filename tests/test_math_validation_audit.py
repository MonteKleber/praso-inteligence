"""
Testes de Auditoria e Validação Matemática Controlada (Etapa 4).

Utiliza pequenas bases controladas e valores calculados manualmente para
comprovar a exatidão matemática das fórmulas de:
1. Recompra (3 pedidos com intervalos conhecidos, múltiplos pedidos na mesma data).
2. Receita e Ticket Médio (incluindo proteção contra explosão de ciclo muito curto).
3. Risco de Churn (limites exatos de fronteira, sazonalidade, irregularidade e dados insuficientes).
4. Cross-Sell (penetração exata por cliente e gasto médio por pedido).
5. Score de Priorização Comercial (cálculo manual passo a passo e desempate determinístico).
"""

from pathlib import Path
from analytics.churn import (
    STATUS_ALTO_RISCO,
    STATUS_ATENCAO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_RISCO_MODERADO,
    STATUS_SAUDAVEL,
    classify_customer_churn_risk,
    detect_interval_trend,
)
from analytics.cross_sell import (
    calculate_segment_product_benchmarks,
    identify_customer_cross_sell_opportunities,
)
from analytics.prioritization import prioritize_customers
from analytics.repurchase import analyze_customer_repurchase
from analytics.revenue import calculate_customer_revenue_metrics
from database.connection import db_session, init_db


def test_auditoria_cliente_tres_pedidos_intervalos_e_receita_conhecidos() -> None:
    """
    Validação manual:
    - Pedidos em: 2026-10-01 (R$ 300), 2026-10-11 (R$ 500), 2026-10-25 (R$ 400).
    - Data de referência: 2026-11-05.
    - Intervalos esperados: [10, 14] dias.
    - Intervalo médio esperado: (10 + 14) / 2 = 12.0 dias.
    - Intervalo mediano esperado: 12.0 dias.
    - Desvio padrão amostral: sqrt(((10-12)^2 + (14-12)^2) / (2-1)) = sqrt(8) = 2.83 dias.
    - Receita histórica: 300 + 500 + 400 = R$ 1.200,00.
    - Ticket médio: 1200 / 3 = R$ 400,00.
    - Próxima compra estimada: 2026-10-25 + 12 dias = 2026-11-06.
    - Dias desde última compra: 2026-11-05 - 2026-10-25 = 11 dias.
    - Índice de atraso: 11 / 12 = 0.92 (<= 1.15 -> Saudável).
    """
    customer = {"id": 1, "nome_fantasia": "Padaria Controle #001", "tipo_estabelecimento": "Padaria & Confeitaria"}
    orders = [
        {"id": 1, "cliente_id": 1, "data_compra": "2026-10-01", "valor_total": 300.0, "status_pedido": "Concluído"},
        {"id": 2, "cliente_id": 1, "data_compra": "2026-10-11", "valor_total": 500.0, "status_pedido": "Concluído"},
        {"id": 3, "cliente_id": 1, "data_compra": "2026-10-25", "valor_total": 400.0, "status_pedido": "Concluído"},
    ]

    rep = analyze_customer_repurchase(customer, orders, reference_date="2026-11-05")
    assert rep["quantidade_pedidos"] == 3
    assert rep["intervalos_dias"] == [10, 14]
    assert rep["intervalo_medio_dias"] == 12.0
    assert rep["intervalo_mediano_dias"] == 12.0
    assert rep["desvio_padrao_intervalo_dias"] == 2.83
    assert rep["valor_total_historico"] == 1200.0
    assert rep["ticket_medio"] == 400.0
    assert rep["proxima_compra_estimada"] == "2026-11-06"
    assert rep["dias_desde_ultima_compra"] == 11
    assert rep["dias_ate_proxima_compra"] == 1

    churn = classify_customer_churn_risk(rep)
    assert churn["indice_atraso"] == 0.92
    assert churn["classificacao_risco"] == STATUS_SAUDAVEL
    assert churn["em_risco_comercial"] is False

    rev = calculate_customer_revenue_metrics(churn)
    # Receita mensal estimada = 400 * (30 / 12) = 1000.0
    assert rev["receita_mensal_estimada"] == 1000.0
    assert rev["receita_em_risco"] == 0.0


def test_auditoria_multiplos_pedidos_na_mesma_data_sem_historico_ciclo() -> None:
    """
    Cliente que fez 3 pedidos no MESMO dia (ex.: dividiu faturamento em 3 notas)
    tem 3 pedidos e faturamento somado, mas apenas 1 data de abastecimento distinta:
    deve ser classificado como 'Dados insuficientes' e não possui ciclo mediano.
    """
    customer = {"id": 2, "nome_fantasia": "Restaurante Mesma Data #002"}
    orders = [
        {"id": 1, "cliente_id": 2, "data_compra": "2026-10-20", "valor_total": 200.0, "status_pedido": "Concluído"},
        {"id": 2, "cliente_id": 2, "data_compra": "2026-10-20", "valor_total": 300.0, "status_pedido": "Concluído"},
        {"id": 3, "cliente_id": 2, "data_compra": "2026-10-20", "valor_total": 100.0, "status_pedido": "Concluído"},
    ]
    rep = analyze_customer_repurchase(customer, orders, reference_date="2026-11-05")
    churn = classify_customer_churn_risk(rep)

    assert rep["quantidade_pedidos"] == 3
    assert rep["valor_total_historico"] == 600.0
    assert rep["ticket_medio"] == 200.0
    assert rep["intervalos_dias"] == []
    assert rep["intervalo_mediano_dias"] is None
    assert churn["classificacao_risco"] == STATUS_DADOS_INSUFICIENTES
    assert churn["em_risco_comercial"] is False


def test_auditoria_protecao_ciclo_muito_curto_evita_projecao_exagerada() -> None:
    """
    Se um cliente fez 2 pedidos em dias consecutivos (intervalo mediano = 1 dia)
    de R$ 1.000, sem proteção a receita mensal seria 1000 * (30/1) = R$ 30.000.
    Com o piso configurável de 3 dias (`ciclo_minimo_projecao_dias = 3.0`),
    a projeção mensal fica limitada a 1000 * (30/3) = R$ 10.000.
    """
    customer = {"id": 3, "nome_fantasia": "Bar Ciclo 1 Dia #003"}
    orders = [
        {"id": 1, "cliente_id": 3, "data_compra": "2026-10-01", "valor_total": 1000.0, "status_pedido": "Concluído"},
        {"id": 2, "cliente_id": 3, "data_compra": "2026-10-02", "valor_total": 1000.0, "status_pedido": "Concluído"},
    ]
    rep = analyze_customer_repurchase(customer, orders, reference_date="2026-10-10")
    churn = classify_customer_churn_risk(rep)
    rev = calculate_customer_revenue_metrics(churn)

    assert rep["intervalo_mediano_dias"] == 1.0
    assert rev["receita_mensal_estimada"] == 10000.0
    assert rev["receita_em_risco"] == 10000.0


def test_auditoria_fronteiras_exatas_classificacao_churn_e_tendencia_robusta() -> None:
    """
    Testa exatamente os valores de corte (1.15, 1.50, 2.50) e comprova que a
    detecção de tendência usa a mediana dos intervalos anteriores (não se enganando
    por um outlier antigo).
    """
    # Ciclo mediano = 20 dias
    base_rep = {
        "cliente_id": 4,
        "quantidade_pedidos": 3,
        "intervalo_mediano_dias": 20.0,
        "intervalos_dias": [20, 20],
    }

    # Exatamente 23 dias -> 23 / 20 = 1.15 -> Saudável
    c_115 = classify_customer_churn_risk({**base_rep, "dias_desde_ultima_compra": 23})
    assert c_115["indice_atraso"] == 1.15
    assert c_115["classificacao_risco"] == STATUS_SAUDAVEL

    # Exatamente 30 dias -> 30 / 20 = 1.50 -> Atenção
    c_150 = classify_customer_churn_risk({**base_rep, "dias_desde_ultima_compra": 30})
    assert c_150["indice_atraso"] == 1.50
    assert c_150["classificacao_risco"] == STATUS_ATENCAO

    # Exatamente 50 dias -> 50 / 20 = 2.50 -> Risco moderado
    c_250 = classify_customer_churn_risk({**base_rep, "dias_desde_ultima_compra": 50})
    assert c_250["indice_atraso"] == 2.50
    assert c_250["classificacao_risco"] == STATUS_RISCO_MODERADO

    # 51 dias -> 51 / 20 = 2.55 -> Alto risco
    c_255 = classify_customer_churn_risk({**base_rep, "dias_desde_ultima_compra": 51})
    assert c_255["indice_atraso"] == 2.55
    assert c_255["classificacao_risco"] == STATUS_ALTO_RISCO

    # Se teve um outlier antigo (60 dias), mas o padrão era 10 dias e voltou a 10 dias:
    # A mediana dos anteriores [10, 10, 60, 10] é 10.0; logo o último intervalo (10) é Estável!
    assert detect_interval_trend([10, 10, 60, 10, 10]) == "Estável"


def test_auditoria_calculo_manual_exato_score_priorizacao() -> None:
    """
    Verifica passo a passo a fórmula matemática do Score de Priorização:
    Carteira com 2 clientes:
    - Cliente A (ID 1):
      * Alto risco (base 0.85), indice_atraso = 3.0 -> bonus = min(0.15, (3.0 - 1.0)*0.05) = 0.10
        -> fator_risco = 0.95 -> nota_risco = round(0.95 * 45, 2) = 42.75
      * Ticket médio = R$ 1.000 (máximo da carteira = R$ 1.000)
        -> fator_ticket = 1.0 -> nota_ticket = 25.00
      * Receita mensal estimada = R$ 3.000 (máximo da carteira = R$ 3.000)
        -> fator_receita = 1.0 -> nota_receita = 20.00
      * Potencial cross-sell = R$ 200 (máximo da carteira = R$ 400)
        -> fator_cs = 0.5 -> nota_cs = 5.00
      * Score Total Esperado para Cliente A = 42.75 + 25.00 + 20.00 + 5.00 = 92.75
    """
    clientes = [
        {
            "cliente_id": 1,
            "nome_fantasia": "Cliente A Auditado",
            "quantidade_pedidos": 5,
            "dias_desde_ultima_compra": 30,
            "intervalo_mediano_dias": 10.0,
            "indice_atraso": 3.0,
            "classificacao_risco": STATUS_ALTO_RISCO,
            "ticket_medio": 1000.0,
            "receita_historica": 5000.0,
            "receita_mensal_estimada": 3000.0,
            "receita_em_risco": 3000.0,
        },
        {
            "cliente_id": 2,
            "nome_fantasia": "Cliente B Auditado",
            "quantidade_pedidos": 4,
            "dias_desde_ultima_compra": 8,
            "intervalo_mediano_dias": 10.0,
            "indice_atraso": 0.8,
            "classificacao_risco": STATUS_SAUDAVEL,
            "ticket_medio": 500.0,
            "receita_historica": 2000.0,
            "receita_mensal_estimada": 1500.0,
            "receita_em_risco": 0.0,
        },
    ]
    cs_map = {
        1: [{"produto_id": 10, "produto_sugerido": "Item X", "potencial_oportunidade_pedido": 200.0}],
        2: [{"produto_id": 11, "produto_sugerido": "Item Y", "potencial_oportunidade_pedido": 400.0}],
    }

    ranked = prioritize_customers(clientes, cross_sell_by_customer=cs_map)
    c_a = ranked[0]
    c_b = ranked[1]

    assert c_a["cliente_id"] == 1
    assert c_a["nota_componente_risco"] == 42.75
    assert c_a["nota_componente_ticket"] == 25.00
    assert c_a["nota_componente_receita"] == 20.00
    assert c_a["nota_componente_cross_sell"] == 5.00
    assert c_a["score_prioridade"] == 92.75

    # Cliente B: Saudável (base 0.05, bonus 0.0) -> nota_risco = 2.25;
    # ticket 500/1000 -> 12.50; receita 1500/3000 -> 10.00; cs 400/400 -> 10.00 -> Total = 34.75
    assert c_b["cliente_id"] == 2
    assert c_b["nota_componente_risco"] == 2.25
    assert c_b["nota_componente_ticket"] == 12.50
    assert c_b["nota_componente_receita"] == 10.00
    assert c_b["nota_componente_cross_sell"] == 10.00
    assert c_b["score_prioridade"] == 34.75


def test_auditoria_integrada_banco_sqlite_pequeno_controlado(tmp_path: Path) -> None:
    """
    Cria um banco SQLite pequeno do zero (sem usar o seed de 100 clientes)
    com apenas 3 padarias e valida todo o pipeline SQL -> Serviços -> Analytics.
    """
    db_file = tmp_path / "mini_audit.db"
    init_db(db_file)

    with db_session(db_file) as conn:
        conn.executemany(
            """
            INSERT INTO clientes (id, nome_fantasia, tipo_estabelecimento, cidade, data_cadastro, status_relacionamento, responsavel_comercial)
            VALUES (?, ?, 'Padaria & Confeitaria', 'Recife', '2026-01-01', 'Ativo', 'Ana');
            """,
            [
                (1, "Padaria 1 Recorrente"),
                (2, "Padaria 2 Atrasada"),
                (3, "Padaria 3 Apenas 1 Pedido"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO produtos (id, nome, categoria, preco_unitario, custo_unitario)
            VALUES (?, ?, 'Farináceos & Panificação', ?, ?);
            """,
            [
                (1, "Farinha 25kg", 100.0, 75.0),
                (2, "Fermento 500g", 50.0, 35.0),
            ],
        )
        # Pedidos:
        # Padaria 1: 2 pedidos (ciclo 10 dias, última em 2026-10-30 -> 6 dias atrás -> Saudável)
        # Padaria 2: 2 pedidos (ciclo 10 dias, última em 2026-09-20 -> 46 dias atrás -> Alto risco)
        # Padaria 3: 1 pedido (em 2026-10-25 -> Dados insuficientes)
        conn.executemany(
            """
            INSERT INTO pedidos (id, cliente_id, data_compra, valor_total, quantidade_produtos, status_pedido)
            VALUES (?, ?, ?, ?, 2, 'Concluído');
            """,
            [
                (1, 1, "2026-10-20", 300.0),
                (2, 1, "2026-10-30", 300.0),
                (3, 2, "2026-09-10", 500.0),
                (4, 2, "2026-09-20", 500.0),
                (5, 3, "2026-10-25", 200.0),
            ],
        )
        # Itens: Padaria 1 e 2 compram Farinha (1) e Fermento (2); Padaria 3 só comprou Farinha (1)
        conn.executemany(
            """
            INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_praticado)
            VALUES (?, ?, ?, ?);
            """,
            [
                (1, 1, 2, 100.0), (1, 2, 2, 50.0),
                (2, 1, 2, 100.0), (2, 2, 2, 50.0),
                (3, 1, 4, 100.0), (3, 2, 2, 50.0),
                (4, 1, 4, 100.0), (4, 2, 2, 50.0),
                (5, 1, 2, 100.0),
            ],
        )

    from analytics.executive_summary import generate_executive_summary

    resumo = generate_executive_summary(db_path=db_file, reference_date="2026-11-05")
    assert resumo["total_clientes_analisados"] == 3
    assert resumo["clientes_recorrentes_saudaveis"] == 1
    assert resumo["clientes_em_alto_risco"] == 1
    assert resumo["clientes_com_dados_insuficientes"] == 1
    assert resumo["receita_historica_total"] == 1800.0
    assert resumo["receita_historica_clientes_em_risco"] == 1000.0
    # Padaria 3 tem oportunidade de cross-sell para Fermento (comprado por 2 de 3 padarias = 66.7%)
    assert resumo["quantidade_oportunidades_cross_sell"] == 1
    assert resumo["clientes_prioritarios_contato"][0]["cliente_id"] == 2
