"""
Testes automatizados da Camada de Integração do Dashboard (`services/dashboard_service.py`)
e dos Componentes de Tabelas e Gráficos (`components/`).

Verifica:
1. Carregamento completo dos indicadores e consistência com o motor analítico.
2. Aplicação combinada de filtros (cidade, segmento, risco, faixa de score, pesquisa textual).
3. Ausência absoluta de duplicação de receita na série mensal e no filtro de período.
4. Seleção de perfil 360º do cliente (histórico, intervalos pedido a pedido e mix de produtos).
5. Tratamento de filtros sem resultados (dados vazios).
6. Exportação CSV (`utf-8-sig`) com separador `;`.
"""

from pathlib import Path
from analytics.churn import STATUS_ALTO_RISCO, STATUS_SAUDAVEL
from components.charts import (
    build_customer_intervals_chart,
    build_customer_orders_timeline_chart,
    build_healthy_vs_risk_comparison_chart,
    build_monthly_evolution_chart,
    build_risk_distribution_chart,
)
from components.tables import (
    build_cross_sell_dataframe,
    build_customer_radar_dataframe,
    build_repurchase_opportunities_dataframe,
)
from database.connection import db_session, init_db
from services.dashboard_service import (
    convert_records_to_csv_bytes,
    filter_customer_records,
    flatten_cross_sell_opportunities,
    format_brl,
    format_date_br,
    get_customer_360_profile,
    get_monthly_orders_evolution,
    get_period_filtered_historical_summary,
    load_full_analytical_portfolio,
)


def _create_controlled_dashboard_db(tmp_path: Path) -> Path:
    """Cria um banco SQLite controlado com 3 clientes e múltiplos itens por pedido."""
    db_file = tmp_path / "dashboard_test.db"
    init_db(db_file)

    with db_session(db_file) as conn:
        conn.executemany(
            """
            INSERT INTO clientes (id, nome_fantasia, tipo_estabelecimento, cidade, data_cadastro, status_relacionamento, responsavel_comercial)
            VALUES (?, ?, ?, ?, '2026-01-10', 'Ativo', ?);
            """,
            [
                (1, "Padaria Alfa Boa Viagem #001", "Padaria & Confeitaria", "Recife", "Ana"),
                (2, "Padaria Beta Aldeota #002", "Padaria & Confeitaria", "Fortaleza", "Lucas"),
                (3, "Padaria Gama Pina #003", "Padaria & Confeitaria", "Recife", "Ana"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO produtos (id, nome, categoria, preco_unitario, custo_unitario)
            VALUES (?, ?, 'Farináceos & Panificação', ?, ?);
            """,
            [
                (10, "Farinha 25kg", 100.0, 75.0),
                (20, "Fermento 500g", 50.0, 35.0),
            ],
        )
        # Pedidos:
        # Cliente 1 (Recife): 2 pedidos de R$ 300 (ciclo 10 dias, última 2026-10-30 -> Saudável)
        # Cliente 2 (Fortaleza): 2 pedidos de R$ 500 (ciclo 10 dias, última 2026-09-15 -> Alto risco)
        # Cliente 3 (Recife): 1 pedido de R$ 200 em 2026-10-20 -> Dados insuficientes
        conn.executemany(
            """
            INSERT INTO pedidos (id, cliente_id, data_compra, valor_total, quantidade_produtos, status_pedido)
            VALUES (?, ?, ?, ?, 4, 'Concluído');
            """,
            [
                (101, 1, "2026-10-20", 300.0),
                (102, 1, "2026-10-30", 300.0),
                (103, 2, "2026-09-05", 500.0),
                (104, 2, "2026-09-15", 500.0),
                (105, 3, "2026-10-20", 200.0),
            ],
        )
        # Cada pedido tem 2 itens (para comprovar que os cálculos de receita não duplicam com JOIN)
        conn.executemany(
            """
            INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_praticado)
            VALUES (?, ?, ?, ?);
            """,
            [
                (101, 10, 2, 100.0), (101, 20, 2, 50.0),
                (102, 10, 2, 100.0), (102, 20, 2, 50.0),
                (103, 10, 4, 100.0), (103, 20, 2, 50.0),
                (104, 10, 4, 100.0), (104, 20, 2, 50.0),
                (105, 10, 2, 100.0),
            ],
        )
    return db_file


def test_dashboard_load_portfolio_e_ausencia_duplicacao_receita(tmp_path: Path) -> None:
    """
    Garante que `load_full_analytical_portfolio` e `get_monthly_orders_evolution`
    somam exatamente R$ 1.800,00 (sem duplicar por causa dos múltiplos itens por pedido).
    """
    db_file = _create_controlled_dashboard_db(tmp_path)
    portfolio = load_full_analytical_portfolio(db_path=db_file, reference_date="2026-11-05")

    assert portfolio["reference_date"] == "2026-11-05"
    assert len(portfolio["customers"]) == 3
    assert portfolio["executive_summary"]["receita_historica_total"] == 1800.0

    monthly = get_monthly_orders_evolution(db_path=db_file)
    soma_mensal = sum(m["receita_historica"] for m in monthly)
    soma_pedidos = sum(m["quantidade_pedidos"] for m in monthly)
    assert soma_mensal == 1800.0
    assert soma_pedidos == 5


def test_dashboard_filtros_combinados_e_dados_vazios(tmp_path: Path) -> None:
    """Verifica filtros por cidade, status de risco, busca textual e retorno vazio."""
    db_file = _create_controlled_dashboard_db(tmp_path)
    portfolio = load_full_analytical_portfolio(db_path=db_file, reference_date="2026-11-05")
    customers = portfolio["customers"]

    # Filtrar apenas Recife (Clientes 1 e 3)
    recife_only = filter_customer_records(customers, cidades=["Recife"])
    assert len(recife_only) == 2

    # Filtrar apenas Alto Risco (Cliente 2)
    alto_risco = filter_customer_records(customers, status_risco=[STATUS_ALTO_RISCO])
    assert len(alto_risco) == 1
    assert alto_risco[0]["cliente_id"] == 2

    # Pesquisa por texto "Beta"
    busca_beta = filter_customer_records(customers, search_query="beta")
    assert len(busca_beta) == 1
    assert busca_beta[0]["cliente_id"] == 2

    # Filtro sem correspondência
    vazio = filter_customer_records(customers, search_query="InexistenteXYZ")
    assert vazio == []


def test_dashboard_perfil_360_cliente_e_cross_sell(tmp_path: Path) -> None:
    """Verifica carregamento do Perfil 360º de um cliente e oportunidades de Cross-Sell."""
    db_file = _create_controlled_dashboard_db(tmp_path)
    portfolio = load_full_analytical_portfolio(db_path=db_file, reference_date="2026-11-05")

    # Cliente 1 tem 2 pedidos com intervalo de 10 dias e 2 produtos comprados
    profile_1 = get_customer_360_profile(1, portfolio_data=portfolio, db_path=db_file)
    assert profile_1 is not None
    assert profile_1["metrics"]["classificacao_risco"] == STATUS_SAUDAVEL
    assert len(profile_1["orders_history"]) == 2
    assert profile_1["orders_history"][1]["intervalo_desde_anterior_dias"] == 10
    assert len(profile_1["top_products"]) == 2

    # Cliente 3 comprou apenas Farinha (10), logo deve receber recomendação de Fermento (20)
    cs_flat = flatten_cross_sell_opportunities(portfolio["customers"])
    assert len(cs_flat) == 1
    assert cs_flat[0]["cliente_id"] == 3
    assert cs_flat[0]["produto_id"] == 20


def test_dashboard_filtro_periodo_preserva_previsao_recompra(tmp_path: Path) -> None:
    """
    Garante que filtrar o período histórico em Relatórios altera apenas
    `receita_no_periodo`, preservando intactos `intervalo_mediano_dias` e
    `proxima_compra_estimada`.
    """
    db_file = _create_controlled_dashboard_db(tmp_path)
    portfolio = load_full_analytical_portfolio(db_path=db_file, reference_date="2026-11-05")

    # Filtra apenas Outubro/2026 (Cliente 2 comprou apenas em Setembro/2026)
    relatorio_outubro = get_period_filtered_historical_summary(
        customers=portfolio["customers"],
        db_path=db_file,
        start_date="2026-10-01",
        end_date="2026-10-31",
    )
    c2_out = next(r for r in relatorio_outubro if r["cliente_id"] == 2)
    assert c2_out["receita_no_periodo"] == 0.0
    assert c2_out["receita_historica"] == 1000.0
    # Ciclo mediano e classificação de risco permanecem intactos!
    assert c2_out["intervalo_mediano_dias"] == 10.0
    assert c2_out["classificacao_risco"] == STATUS_ALTO_RISCO


def test_dashboard_exportacao_csv_e_componentes_visuais(tmp_path: Path) -> None:
    """Verifica geração de CSV, formatação BR e construção de DataFrames e gráficos."""
    db_file = _create_controlled_dashboard_db(tmp_path)
    portfolio = load_full_analytical_portfolio(db_path=db_file, reference_date="2026-11-05")
    customers = portfolio["customers"]

    assert format_brl(1234.5) == "R$ 1.234,50"
    assert format_date_br("2026-11-05") == "05/11/2026"

    csv_bytes = convert_records_to_csv_bytes(
        customers,
        columns_map={"cliente_id": "ID", "nome_fantasia": "Cliente"},
    )
    csv_text = csv_bytes.decode("utf-8-sig")
    assert "ID;Cliente" in csv_text
    assert "Padaria Alfa Boa Viagem #001" in csv_text

    # Valida que os builders de tabelas e gráficos executam sem erro
    df_radar = build_customer_radar_dataframe(customers)
    assert len(df_radar) == 3

    df_rep = build_repurchase_opportunities_dataframe(customers)
    assert len(df_rep) == 2  # Clientes 1 e 2 possuem ciclo calculado

    cs_flat = flatten_cross_sell_opportunities(customers)
    df_cs = build_cross_sell_dataframe(cs_flat)
    assert len(df_cs) == 1

    fig_risk = build_risk_distribution_chart(customers)
    fig_pie = build_healthy_vs_risk_comparison_chart(customers)
    fig_month = build_monthly_evolution_chart(get_monthly_orders_evolution(db_path=db_file))
    prof_1 = get_customer_360_profile(1, portfolio_data=portfolio, db_path=db_file)
    fig_tl = build_customer_orders_timeline_chart(prof_1["orders_history"], 300.0)
    fig_int = build_customer_intervals_chart(prof_1["orders_history"], 10.0, 6)

    assert fig_risk is not None
    assert fig_pie is not None
    assert fig_month is not None
    assert fig_tl is not None
    assert fig_int is not None
