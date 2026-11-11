"""
Página 1 — Visão Geral Executiva (`pages/1_Visao_Geral.py`).

Apresenta o panorama gerencial da carteira comercial B2B:
- Cartões de KPI (Total de clientes, Saudáveis, Atenção, Risco moderado, Alto risco,
  Receita histórica, Receita mensal estimada, Receita em risco e Ticket médio).
- Resumo Executivo dinâmico com diagnósticos reais extraídos da base selecionada.
- 5 Gráficos interativos de distribuição de risco, proporção da carteira, receita
  por segmento, receita por cidade e evolução mensal de pedidos.
"""

import streamlit as st

from analytics.executive_summary import build_executive_summary_from_records
from components.charts import (
    build_healthy_vs_risk_comparison_chart,
    build_monthly_evolution_chart,
    build_revenue_by_city_chart,
    build_revenue_by_segment_chart,
    build_risk_distribution_chart,
)
from components.kpi_cards import (
    inject_custom_css,
    render_kpi_card,
    render_page_header,
    render_synthetic_disclaimer_footer,
)
from components.sidebar import load_portfolio_state, render_sidebar_context
from services.dashboard_service import (
    filter_customer_records,
    format_brl,
    format_date_br,
    format_int_br,
    get_monthly_orders_evolution,
)


def render_overview_page() -> None:
    inject_custom_css()
    portfolio = load_portfolio_state()
    filters = render_sidebar_context(portfolio, show_global_filters=True)

    render_page_header(
        title="Visão Geral Executiva — Inteligência Comercial B2B",
        subtitle=(
            "Monitoramento consolidado de retenção, previsão de recompra, exposição ao risco "
            "e desempenho de faturamento da carteira."
        ),
    )

    filtered_customers = filter_customer_records(
        customers=portfolio["customers"],
        cidades=filters["cidades"],
        segmentos=filters["segmentos"],
    )

    if not filtered_customers:
        st.warning(
            "Nenhum cliente encontrado para os filtros de Cidade e Segmento selecionados na barra lateral."
        )
        return

    # Recalcula o Resumo Executivo dinamicamente para o recorte selecionado
    summary = build_executive_summary_from_records(
        prioritized_customers=filtered_customers,
        reference_date=portfolio["reference_date"],
        top_n_priority=5,
    )

    # ------------------------------------------------------------------------
    # 1. LINHA DE CARTÕES DE INDICADORES DE CARTEIRA E RISCO (5 CARDS)
    # ------------------------------------------------------------------------
    st.markdown("#### Indicadores de Saúde da Carteira")
    col1, col2, col3, col4, col5 = st.columns(5)

    total_c = summary["total_clientes_analisados"]
    saudaveis = summary["clientes_recorrentes_saudaveis"]
    atencao = summary["clientes_em_atencao"]
    moderado = summary["clientes_em_risco_moderado"]
    alto_risco = summary["clientes_em_alto_risco"]

    with col1:
        render_kpi_card(
            title="Total de Clientes",
            value=format_int_br(total_c),
            subtitle=f"{summary['clientes_com_dados_insuficientes']} em onboarding (1ª compra)",
            color_variant="blue",
        )
    with col2:
        pct_saud = (saudaveis / total_c * 100) if total_c > 0 else 0.0
        render_kpi_card(
            title="Clientes Saudáveis",
            value=format_int_br(saudaveis),
            subtitle=f"{pct_saud:.1f}% da carteira em dia",
            color_variant="green",
        )
    with col3:
        pct_at = (atencao / total_c * 100) if total_c > 0 else 0.0
        render_kpi_card(
            title="Em Atenção",
            value=format_int_br(atencao),
            subtitle=f"{pct_at:.1f}% (1,15x a 1,50x do ciclo)",
            color_variant="amber",
        )
    with col4:
        pct_mod = (moderado / total_c * 100) if total_c > 0 else 0.0
        render_kpi_card(
            title="Risco Moderado",
            value=format_int_br(moderado),
            subtitle=f"{pct_mod:.1f}% (1,50x a 2,50x do ciclo)",
            color_variant="orange",
        )
    with col5:
        pct_alto = (alto_risco / total_c * 100) if total_c > 0 else 0.0
        render_kpi_card(
            title="Alto Risco",
            value=format_int_br(alto_risco),
            subtitle=f"{pct_alto:.1f}% (> 2,50x do ciclo habitual)",
            color_variant="red",
        )

    # ------------------------------------------------------------------------
    # 2. LINHA DE INDICADORES FINANCEIROS (4 CARDS)
    # ------------------------------------------------------------------------
    st.markdown("#### Indicadores Financeiros e Exposição ao Risco")
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)

    with fcol1:
        render_kpi_card(
            title="Receita Histórica Total",
            value=format_brl(summary["receita_historica_total"]),
            subtitle=f"{format_int_br(summary['total_pedidos_concluidos'])} pedidos concluídos (12m)",
            color_variant="blue",
        )
    with fcol2:
        render_kpi_card(
            title="Receita Mensal Estimada",
            value=format_brl(summary["receita_mensal_estimada_total"]),
            subtitle="Projeção de 30 dias no ritmo mediano",
            color_variant="blue",
        )
    with fcol3:
        pct_rec_risco = (
            (summary["receita_estimada_em_risco"] / summary["receita_mensal_estimada_total"] * 100)
            if summary["receita_mensal_estimada_total"] > 0
            else 0.0
        )
        render_kpi_card(
            title="Receita Estimada em Risco (30d)",
            value=format_brl(summary["receita_estimada_em_risco"]),
            subtitle=f"{pct_rec_risco:.1f}% do potencial mensal ({summary['total_clientes_em_risco']} clientes)",
            color_variant="red",
        )
    with fcol4:
        render_kpi_card(
            title="Ticket Médio da Carteira",
            value=format_brl(summary["ticket_medio_geral"]),
            subtitle=f"Potencial Cross-Sell: +{format_brl(summary['potencial_incremental_cross_sell_pedido'])}/ciclo",
            color_variant="green",
        )

    # ------------------------------------------------------------------------
    # 3. RESUMO EXECUTIVO DINÂMICO
    # ------------------------------------------------------------------------
    seg_lider = (
        summary["receita_por_segmento"][0]
        if summary["receita_por_segmento"]
        else {"tipo_estabelecimento": "—", "receita_historica": 0.0}
    )
    cid_lider = (
        summary["receita_por_cidade"][0]
        if summary["receita_por_cidade"]
        else {"cidade": "—", "receita_historica": 0.0}
    )

    st.markdown(
        f"""
        <div class="praso-exec-panel">
            <h3>Resumo Executivo da Carteira (Data Base: {format_date_br(summary['data_referencia'])})</h3>
            <p style="margin-bottom: 0.6rem; color: #334155; font-size: 0.94rem;">
                A análise comportamental sobre os <strong>{total_c} estabelecimentos</strong> selecionados indica que
                <strong>{summary['total_clientes_em_risco']} clientes ({summary['taxa_clientes_em_risco_pct']:.1f}%)</strong>
                ultrapassaram sua janela habitual de recompra, sendo <strong>{alto_risco} em Alto Risco</strong> e
                <strong>{moderado} em Risco Moderado</strong>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ecol1, ecol2 = st.columns(2)
    with ecol1:
        st.markdown("**Principais Diagnósticos Identificados nos Dados:**")
        st.markdown(
            f"- **Exposição Crítica:** Os clientes em atraso concentram **{format_brl(summary['receita_estimada_em_risco'])}** "
            f"em receita mensal estimada em risco (e acumularam historicamente **{format_brl(summary['receita_historica_clientes_em_risco'])}**).\n"
            f"- **Segmento de Maior Faturamento:** `{seg_lider['tipo_estabelecimento']}` lidera a receita histórica com "
            f"**{format_brl(seg_lider['receita_historica'])}**.\n"
            f"- **Praça de Maior Concentração:** `{cid_lider['cidade']}` representa **{format_brl(cid_lider['receita_historica'])}** "
            f"do faturamento acumulado."
        )
    with ecol2:
        st.markdown("**Direcionamentos Comerciais Recomendados:**")
        for acao in summary["acoes_comerciais_recomendadas"]:
            st.markdown(f"- {acao}")

    st.markdown("---")

    # ------------------------------------------------------------------------
    # 4. GRÁFICOS INTERATIVOS DE INTELIGÊNCIA COMERCIAL
    # ------------------------------------------------------------------------
    gcol1, gcol2 = st.columns([3, 2])
    with gcol1:
        st.plotly_chart(
            build_risk_distribution_chart(filtered_customers),
            width="stretch",
        )
    with gcol2:
        st.plotly_chart(
            build_healthy_vs_risk_comparison_chart(filtered_customers),
            width="stretch",
        )

    gcol3, gcol4 = st.columns([3, 2])
    with gcol3:
        st.plotly_chart(
            build_revenue_by_segment_chart(summary["receita_por_segmento"]),
            width="stretch",
        )
    with gcol4:
        st.plotly_chart(
            build_revenue_by_city_chart(summary["receita_por_cidade"]),
            width="stretch",
        )

    monthly_data = get_monthly_orders_evolution(
        cidades=filters["cidades"],
        segmentos=filters["segmentos"],
    )
    st.plotly_chart(
        build_monthly_evolution_chart(monthly_data),
        width="stretch",
    )

    render_synthetic_disclaimer_footer(format_date_br(summary["data_referencia"]))


render_overview_page()
