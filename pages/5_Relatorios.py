"""
Página 5 — Relatórios Gerenciais e Exportação CSV (`pages/5_Relatorios.py`).

Oferece uma visão analítica multidimensional da carteira B2B:
- Comparações por Cidade, Segmento, Classificação de Risco e Consultor Comercial.
- Filtro de período histórico para análise de faturamento realizado, respeitando
  a regra metodológica de NÃO distorcer os indicadores de ciclo/recompra (que
  pertencem à data de referência `05/11/2026`).
- Exportação direta das visões filtradas em CSV compatível com Excel (`utf-8-sig`).
"""

from datetime import date
import pandas as pd
import streamlit as st

from analytics.revenue import summarize_revenue_by_dimension
from components.charts import (
    build_monthly_evolution_chart,
    build_revenue_by_city_chart,
    build_revenue_by_segment_chart,
)
from components.kpi_cards import (
    inject_custom_css,
    render_kpi_card,
    render_page_header,
    render_synthetic_disclaimer_footer,
)
from components.sidebar import load_portfolio_state, render_sidebar_context
from services.dashboard_service import (
    convert_records_to_csv_bytes,
    flatten_cross_sell_opportunities,
    format_brl,
    format_date_br,
    format_int_br,
    get_monthly_orders_evolution,
    get_period_filtered_historical_summary,
)


def _build_dimension_table_df(dim_records: list[dict], dim_col: str, dim_label: str) -> pd.DataFrame:
    rows = []
    for r in dim_records:
        rows.append(
            {
                dim_label: r[dim_col],
                "Total de Clientes": r["total_clientes"],
                "Clientes em Risco": r["clientes_em_risco"],
                "Pedidos Concluídos (12m)": r["quantidade_pedidos"],
                "Ticket Médio": format_brl(r["ticket_medio_grupo"]),
                "Receita Histórica (12m)": format_brl(r["receita_historica"]),
                "Receita Histórica de Clientes em Risco": format_brl(
                    r.get("receita_historica_clientes_em_risco", 0.0)
                ),
                "Receita Mensal Estimada (30d)": format_brl(r["receita_mensal_estimada"]),
                "Receita Estimada em Risco (30d)": format_brl(r["receita_em_risco"]),
            }
        )
    return pd.DataFrame(rows)


def render_reports_page() -> None:
    inject_custom_css()
    portfolio = load_portfolio_state()
    sidebar_filters = render_sidebar_context(portfolio, show_global_filters=True)
    filter_opts = portfolio["filter_options"]

    render_page_header(
        title="Relatórios Gerenciais, Comparativos e Exportação de Dados",
        subtitle=(
            "Consulte o desempenho consolidado por cidade, segmento, faixa de risco e "
            "período de faturamento, com exportação estruturada em CSV."
        ),
    )

    # ------------------------------------------------------------------------
    # 1. FILTROS DE RELATÓRIO E RECORTE TEMPORAL DO HISTÓRICO
    # ------------------------------------------------------------------------
    with st.container():
        pcol1, pcol2, pcol3 = st.columns([1.5, 1.5, 2])
        with pcol1:
            start_dt = st.date_input(
                "Data Inicial (Faturamento Histórico):",
                value=date(2025, 11, 5),
                min_value=date(2025, 1, 1),
                max_value=date(2026, 11, 5),
            )
        with pcol2:
            end_dt = st.date_input(
                "Data Final (Faturamento Histórico):",
                value=date(2026, 11, 5),
                min_value=date(2025, 1, 1),
                max_value=date(2026, 11, 5),
            )
        with pcol3:
            status_rel_sel = st.multiselect(
                "Filtrar por Classificação de Risco:",
                options=filter_opts["status_risco"],
                default=filter_opts["status_risco"],
            )

    if start_dt > end_dt:
        st.error("A Data Inicial não pode ser posterior à Data Final.")
        return

    st.caption(
        "**Nota de Integridade Analítica:** O filtro de datas acima recorta o **faturamento histórico realizado** "
        "no período selecionado. Os indicadores comportamentais de **Ciclo Mediano, Classificação de Risco e "
        "Projeção Mensal** permanecem ancorados na data de referência da carteira (`05/11/2026`), evitando "
        "distorções artificiais nas previsões de recompra."
    )

    period_records = get_period_filtered_historical_summary(
        customers=portfolio["customers"],
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
        cidades=sidebar_filters["cidades"],
        segmentos=sidebar_filters["segmentos"],
        status_risco=status_rel_sel,
    )

    if not period_records:
        st.warning("Nenhum registro encontrado para os filtros aplicados.")
        return

    # ------------------------------------------------------------------------
    # 2. KPIS DO PERÍODO SELECIONADO VS. POTENCIAL ATUAL
    # ------------------------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    rec_periodo = sum(float(r["receita_no_periodo"]) for r in period_records)
    ped_periodo = sum(int(r["pedidos_no_periodo"]) for r in period_records)
    ticket_periodo = (rec_periodo / ped_periodo) if ped_periodo > 0 else 0.0
    rec_risco_grupo = sum(float(r.get("receita_em_risco") or 0.0) for r in period_records)

    with k1:
        render_kpi_card(
            "Receita Realizada no Período",
            format_brl(rec_periodo),
            f"De {format_date_br(start_dt)} a {format_date_br(end_dt)}",
            "blue",
        )
    with k2:
        render_kpi_card(
            "Pedidos Concluídos no Período",
            format_int_br(ped_periodo),
            f"Em {len(period_records)} estabelecimentos analisados",
            "blue",
        )
    with k3:
        render_kpi_card(
            "Ticket Médio no Período",
            format_brl(ticket_periodo),
            "Média dos pedidos concluídos no intervalo",
            "green",
        )
    with k4:
        render_kpi_card(
            "Receita Mensal em Risco (Atual)",
            format_brl(rec_risco_grupo),
            "Exposição atual da carteira filtrada",
            "red" if rec_risco_grupo > 0 else "green",
        )

    # ------------------------------------------------------------------------
    # 3. EVOLUÇÃO MENSAL NO PERÍODO SELECIONADO
    # ------------------------------------------------------------------------
    monthly_period = get_monthly_orders_evolution(
        cidades=sidebar_filters["cidades"],
        segmentos=sidebar_filters["segmentos"],
        start_date=start_dt.isoformat(),
        end_date=end_dt.isoformat(),
    )
    st.plotly_chart(
        build_monthly_evolution_chart(monthly_period),
        width="stretch",
    )

    # ------------------------------------------------------------------------
    # 4. TABELAS COMPARATIVAS POR DIMENSÃO (SEGMENTO, CIDADE, RISCO, CONSULTOR)
    # ------------------------------------------------------------------------
    st.markdown("#### Comparativo Gerencial por Dimensões da Carteira")
    t_seg, t_cid, t_risco, t_resp = st.tabs(
        [
            "Por Segmento B2B",
            "Por Cidade",
            "Por Classificação de Risco",
            "Por Consultor Comercial",
        ]
    )

    by_seg = summarize_revenue_by_dimension(period_records, "tipo_estabelecimento")
    by_cid = summarize_revenue_by_dimension(period_records, "cidade")
    by_risco = summarize_revenue_by_dimension(period_records, "classificacao_risco")
    by_resp = summarize_revenue_by_dimension(period_records, "responsavel_comercial")

    with t_seg:
        st.plotly_chart(build_revenue_by_segment_chart(by_seg), width="stretch")
        st.dataframe(
            _build_dimension_table_df(by_seg, "tipo_estabelecimento", "Segmento B2B"),
            width="stretch",
            hide_index=True,
        )

    with t_cid:
        st.plotly_chart(build_revenue_by_city_chart(by_cid), width="stretch")
        st.dataframe(
            _build_dimension_table_df(by_cid, "cidade", "Cidade"),
            width="stretch",
            hide_index=True,
        )

    with t_risco:
        st.dataframe(
            _build_dimension_table_df(
                by_risco, "classificacao_risco", "Classificação de Risco"
            ),
            width="stretch",
            hide_index=True,
        )

    with t_resp:
        st.dataframe(
            _build_dimension_table_df(
                by_resp, "responsavel_comercial", "Consultor Responsável"
            ),
            width="stretch",
            hide_index=True,
        )

    st.markdown("---")

    # ------------------------------------------------------------------------
    # 5. CENTRAL DE EXPORTAÇÃO CSV (PARA EXCEL / BI)
    # ------------------------------------------------------------------------
    st.markdown("#### Central de Exportação de Relatórios (CSV)")
    st.caption(
        "Os arquivos abaixo são gerados em formato CSV (`UTF-8-SIG` com separador `;`), "
        "prontos para abertura direta no Microsoft Excel ou ferramentas de análise."
    )

    col_exp1, col_exp2, col_exp3 = st.columns(3)

    # 1. CSV da Carteira de Clientes Priorizada e Filtrada
    customer_cols_map = {
        "ranking_prioridade": "Ranking_Prioridade",
        "cliente_id": "ID_Cliente",
        "nome_fantasia": "Nome_Fantasia",
        "cidade": "Cidade",
        "tipo_estabelecimento": "Segmento",
        "responsavel_comercial": "Consultor_Responsavel",
        "classificacao_risco": "Classificacao_Risco",
        "score_prioridade": "Score_Prioridade",
        "quantidade_pedidos": "Pedidos_Concluidos_Total",
        "pedidos_no_periodo": "Pedidos_No_Periodo_Filtrado",
        "ultima_compra": "Data_Ultima_Compra",
        "dias_desde_ultima_compra": "Dias_Sem_Comprar",
        "intervalo_mediano_dias": "Ciclo_Mediano_Dias",
        "proxima_compra_estimada": "Proxima_Compra_Estimada",
        "ticket_medio": "Ticket_Medio_Historico",
        "receita_historica": "Receita_Historica_Total",
        "receita_no_periodo": "Receita_No_Periodo_Filtrado",
        "receita_mensal_estimada": "Receita_Mensal_Estimada_30d",
        "receita_em_risco": "Receita_Estimada_Em_Risco_30d",
        "acao_comercial_recomendada": "Acao_Comercial_Recomendada",
    }
    csv_clientes = convert_records_to_csv_bytes(period_records, customer_cols_map)

    with col_exp1:
        st.download_button(
            label="Baixar Relatório de Clientes e Risco (.CSV)",
            data=csv_clientes,
            file_name=f"praso_relatorio_clientes_{start_dt}_{end_dt}.csv",
            mime="text/csv",
            width="stretch",
            type="primary",
        )

    # 2. CSV de Oportunidades de Cross-Sell
    cs_records = flatten_cross_sell_opportunities(
        customers=period_records,
        cidades=sidebar_filters["cidades"],
        segmentos=sidebar_filters["segmentos"],
    )
    cs_cols_map = {
        "cliente_id": "ID_Cliente",
        "nome_fantasia": "Nome_Fantasia",
        "cidade": "Cidade",
        "tipo_estabelecimento": "Segmento",
        "classificacao_risco": "Status_Risco",
        "produto_sugerido": "Produto_Recomendado",
        "categoria_produto": "Categoria_Produto",
        "taxa_penetracao_pct": "Taxa_Penetracao_Segmento_Pct",
        "potencial_oportunidade_pedido": "Potencial_Estimado_Pedido_BRL",
        "justificativa": "Justificativa_Recomendacao",
    }
    csv_cs = convert_records_to_csv_bytes(cs_records, cs_cols_map)

    with col_exp2:
        st.download_button(
            label="Baixar Oportunidades de Cross-Sell (.CSV)",
            data=csv_cs,
            file_name="praso_oportunidades_cross_sell.csv",
            mime="text/csv",
            width="stretch",
        )

    # 3. CSV de Resumo por Segmento
    seg_cols_map = {
        "tipo_estabelecimento": "Segmento",
        "total_clientes": "Total_Clientes",
        "clientes_em_risco": "Clientes_Em_Risco",
        "quantidade_pedidos": "Pedidos_Concluidos",
        "ticket_medio_grupo": "Ticket_Medio_BRL",
        "receita_historica": "Receita_Historica_BRL",
        "receita_historica_clientes_em_risco": "Receita_Historica_Clientes_Risco_BRL",
        "receita_mensal_estimada": "Receita_Mensal_Estimada_BRL",
        "receita_em_risco": "Receita_Mensal_Em_Risco_BRL",
    }
    csv_seg = convert_records_to_csv_bytes(by_seg, seg_cols_map)

    with col_exp3:
        st.download_button(
            label="Baixar Consolidado por Segmento (.CSV)",
            data=csv_seg,
            file_name="praso_consolidado_segmentos.csv",
            mime="text/csv",
            width="stretch",
        )

    render_synthetic_disclaimer_footer(format_date_br(portfolio["reference_date"]))


render_reports_page()
