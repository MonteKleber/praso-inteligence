"""
Página 3 — Perfil 360º do Cliente (`pages/3_Perfil_do_Cliente.py`).

Apresenta a visão detalhada do relacionamento comercial com um estabelecimento:
- Pesquisa e seleção de cliente sincronizada com `st.session_state["cliente_selecionado_id"]`.
- Indicadores de histórico (quantidade de pedidos, primeira e última compra, dias
  sem comprar, ciclo mediano, ticket médio, receita histórica, receita mensal
  estimada, classificação de risco e score de prioridade).
- Seção de Interpretação Comercial estruturada respondendo às perguntas de negócio.
- Gráficos de histórico de valores de pedidos, intervalos entre compras vs. ciclo
  habitual e mix de produtos adquiridos.
- Oportunidades de Cross-Sell e gerador de abordagem consultiva para WhatsApp.
"""

import pandas as pd
import streamlit as st

from analytics.churn import (
    STATUS_ALTO_RISCO,
    STATUS_ATENCAO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_RISCO_MODERADO,
    STATUS_SAUDAVEL,
)
from components.charts import (
    build_customer_intervals_chart,
    build_customer_orders_timeline_chart,
    build_customer_top_products_chart,
)
from components.kpi_cards import (
    get_risk_badge_html,
    inject_custom_css,
    render_kpi_card,
    render_page_header,
    render_synthetic_disclaimer_footer,
)
from components.sidebar import load_portfolio_state, render_sidebar_context
from services.dashboard_service import (
    format_brl,
    format_date_br,
    format_int_br,
    get_customer_360_profile,
)


def _risk_color_variant(status_risco: str) -> str:
    return {
        STATUS_SAUDAVEL: "green",
        STATUS_ATENCAO: "amber",
        STATUS_RISCO_MODERADO: "orange",
        STATUS_ALTO_RISCO: "red",
        STATUS_DADOS_INSUFICIENTES: "blue",
    }.get(status_risco, "blue")


def render_customer_profile_page() -> None:
    inject_custom_css()
    portfolio = load_portfolio_state()
    render_sidebar_context(portfolio, show_global_filters=False)

    render_page_header(
        title="Perfil 360º do Estabelecimento — Diagnóstico Individual",
        subtitle=(
            "Análise aprofundada do histórico de compras, regularidade do ciclo de reposição, "
            "mix de produtos e recomendações comerciais personalizadas."
        ),
    )

    customers = portfolio["customers"]
    opcoes_clientes = {
        int(c["cliente_id"]): (
            f"#{c['ranking_prioridade']} — {c['nome_fantasia']} "
            f"({c['cidade']} | {c['tipo_estabelecimento']} | {c['classificacao_risco']})"
        )
        for c in customers
    }

    current_cid = int(st.session_state.get("cliente_selecionado_id", customers[0]["cliente_id"]))
    if current_cid not in opcoes_clientes:
        current_cid = int(customers[0]["cliente_id"])

    selected_cid = st.selectbox(
        "Pesquisar ou Selecionar Estabelecimento B2B:",
        options=list(opcoes_clientes.keys()),
        format_func=lambda cid: opcoes_clientes[cid],
        index=list(opcoes_clientes.keys()).index(current_cid),
    )
    st.session_state["cliente_selecionado_id"] = int(selected_cid)

    profile = get_customer_360_profile(
        cliente_id=int(selected_cid),
        portfolio_data=portfolio,
    )
    if not profile:
        st.error("Estabelecimento não encontrado.")
        return

    m = profile["metrics"]
    orders_hist = profile["orders_history"]
    top_prods = profile["top_products"]
    cs_opps = profile["cross_sell_opportunities"]

    badge_html = get_risk_badge_html(m["classificacao_risco"])
    st.markdown(
        f"""
        <div class="praso-exec-panel">
            <h3>{m['nome_fantasia']} {badge_html}</h3>
            <p style="margin: 0; color: #334155; font-size: 0.92rem;">
                <strong>ID Cliente:</strong> #{m['cliente_id']:03d} &nbsp;|&nbsp;
                <strong>Cidade:</strong> {m['cidade']} &nbsp;|&nbsp;
                <strong>Segmento:</strong> {m['tipo_estabelecimento']} &nbsp;|&nbsp;
                <strong>Cadastro:</strong> {format_date_br(m['data_cadastro'])} &nbsp;|&nbsp;
                <strong>Consultor Responsável:</strong> {m['responsavel_comercial']} &nbsp;|&nbsp;
                <strong>Prioridade na Carteira:</strong> Ranking #{m['ranking_prioridade']} ({m['score_prioridade']:.2f}/100)
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------------
    # 1. CARTÕES DE INDICADORES DO CLIENTE (2 LINHAS DE 4 CARDS)
    # ------------------------------------------------------------------------
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    ciclo_med = m.get("intervalo_mediano_dias")
    ciclo_med_str = f"{ciclo_med:.0f} dias" if ciclo_med is not None else "Insuficiente"

    with r1c1:
        render_kpi_card(
            "Pedidos Concluídos",
            format_int_br(m["quantidade_pedidos"]),
            f"1ª compra: {format_date_br(m['primeira_compra'])}",
            "blue",
        )
    with r1c2:
        render_kpi_card(
            "Última Compra & Tempo",
            f"{m['dias_desde_ultima_compra']} dias atrás"
            if m["dias_desde_ultima_compra"] is not None
            else "—",
            f"Data: {format_date_br(m['ultima_compra'])}",
            _risk_color_variant(m["classificacao_risco"]),
        )
    with r1c3:
        prox_str = format_date_br(m.get("proxima_compra_estimada"))
        render_kpi_card(
            "Ciclo Mediano Habitual",
            ciclo_med_str,
            f"Próxima compra estimada: {prox_str}",
            "blue",
        )
    with r1c4:
        ind_atraso = m.get("indice_atraso")
        ind_str = f"Índice de atraso: {ind_atraso:.2f}x" if ind_atraso is not None else "Em onboarding"
        render_kpi_card(
            "Classificação & Score",
            f"{m['score_prioridade']:.1f} / 100",
            f"{m['classificacao_risco']} ({ind_str})",
            _risk_color_variant(m["classificacao_risco"]),
        )

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    with r2c1:
        render_kpi_card(
            "Ticket Médio",
            format_brl(m.get("ticket_medio")),
            f"Média de intervalos: {m['intervalo_medio_dias']} d"
            if m.get("intervalo_medio_dias")
            else "Único pedido",
            "green",
        )
    with r2c2:
        render_kpi_card(
            "Receita Histórica Acumulada",
            format_brl(m.get("receita_historica")),
            "Total faturado em pedidos concluídos",
            "blue",
        )
    with r2c3:
        render_kpi_card(
            "Receita Mensal Estimada (30d)",
            format_brl(m.get("receita_mensal_estimada")),
            "Projeção baseada no ciclo mediano",
            "blue",
        )
    with r2c4:
        fator_exp = int(round(float(m.get("fator_exposicao_risco") or 0.0) * 100))
        render_kpi_card(
            "Receita Estimada em Risco",
            format_brl(m.get("receita_em_risco")),
            f"Exposição heurística: {fator_exp}% do potencial mensal",
            "red" if float(m.get("receita_em_risco") or 0.0) > 0 else "green",
        )

    # ------------------------------------------------------------------------
    # 2. SEÇÃO DE INTERPRETAÇÃO COMERCIAL (DIAGNÓSTICO CONSULTIVO)
    # ------------------------------------------------------------------------
    st.markdown("#### Diagnóstico e Interpretação Comercial")
    icol1, icol2 = st.columns(2)

    with icol1:
        if m["historico_suficiente_para_ciclo"]:
            comportamento_txt = (
                f"O estabelecimento apresenta um ciclo mediano habitual de **{ciclo_med:.0f} dias** "
                f"(média de {m['intervalo_medio_dias']:.1f} dias e desvio padrão de "
                f"{m['desvio_padrao_intervalo_dias']:.1f} dias). Tendência recente dos intervalos: "
                f"**{m['tendencia_intervalo']}**."
            )
            atraso_dias = int(m.get("dias_atraso_ciclo") or 0)
            if atraso_dias > 0:
                status_ciclo_txt = (
                    f"Sim. O cliente está há **{m['dias_desde_ultima_compra']} dias** sem comprar, "
                    f"acumulando **{atraso_dias} dias além do seu ciclo mediano** "
                    f"(razão de {m['indice_atraso']:.2f}x sobre o intervalo esperado)."
                )
            else:
                status_ciclo_txt = (
                    f"Não. A última compra ocorreu há **{m['dias_desde_ultima_compra']} dias**, "
                    f"dentro da janela habitual de **{ciclo_med:.0f} dias**."
                )
        else:
            comportamento_txt = (
                "O cliente possui apenas **1 data de compra registrada** até o momento. "
                "Ainda não há intervalo histórico entre pedidos para estabelecer um ciclo mediano."
            )
            status_ciclo_txt = (
                "Não aplicável (cliente em fase de onboarding/ativação da 2ª compra)."
            )

        st.markdown(
            f"- **Qual é o comportamento habitual do cliente?**\n  {comportamento_txt}\n"
            f"- **Ele está atrasado em relação ao ciclo esperado?**\n  {status_ciclo_txt}\n"
            f"- **Qual é sua classificação atual e por que a recebeu?**\n  Classificado como "
            f"**{m['classificacao_risco']}** — {m['explicacao_risco']}"
        )

    with icol2:
        st.markdown(
            f"- **Qual é sua exposição financeira estimada?**\n"
            f"  A receita mensal estimada deste cliente é de **{format_brl(m.get('receita_mensal_estimada'))}** "
            f"e a parcela atualmente exposta ao risco é estimada em **{format_brl(m.get('receita_em_risco'))}** "
            f"(além de um histórico acumulado de **{format_brl(m.get('receita_historica'))}**).\n"
            f"- **Qual a recomendação comercial prioritária?**\n"
            f"  **{m['acao_comercial_recomendada']}** — {m['justificativa_prioridade']}\n"
            f"- **Nota de cautela analítica:**\n"
            f"  O atraso em relação ao ciclo habitual é um indicador heurístico de atenção comercial "
            f"e não significa confirmação de abandono definitivo."
        )

    with st.expander("Gerar Sugestão de Abordagem Consultiva para WhatsApp", expanded=False):
        st.caption(
            "Mensagem gerada automaticamente com base no ciclo e nas oportunidades de cross-sell do cliente:"
        )
        st.code(m["sugestao_mensagem_whatsapp"], language=None)

    st.markdown("---")

    # ------------------------------------------------------------------------
    # 3. GRÁFICOS DE COMPORTAMENTO DO CLIENTE
    # ------------------------------------------------------------------------
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.plotly_chart(
            build_customer_orders_timeline_chart(orders_hist, m.get("ticket_medio")),
            width="stretch",
        )
    with gcol2:
        st.plotly_chart(
            build_customer_intervals_chart(
                orders_hist,
                m.get("intervalo_mediano_dias"),
                m.get("dias_desde_ultima_compra"),
            ),
            width="stretch",
        )

    gcol3, gcol4 = st.columns([3, 2])
    with gcol3:
        st.plotly_chart(
            build_customer_top_products_chart(top_prods),
            width="stretch",
        )
    with gcol4:
        st.markdown("##### Recomendações de Cross-Sell para este Cliente")
        if cs_opps:
            for opp in cs_opps:
                st.markdown(
                    f"- **{opp['produto_sugerido']}** (`{opp['categoria_produto']}`)\n"
                    f"  Penetração no segmento: **{opp['taxa_penetracao_segmento']*100:.0f}%** | "
                    f"Potencial: **{format_brl(opp['potencial_oportunidade_pedido'])}/pedido**"
                )
        else:
            st.info(
                "Este cliente já adquire todos os produtos de alta penetração do seu segmento."
            )

    # ------------------------------------------------------------------------
    # 4. HISTÓRICO TABULAR DE PEDIDOS DO CLIENTE
    # ------------------------------------------------------------------------
    st.markdown("##### Histórico Completo de Pedidos do Estabelecimento")
    if orders_hist:
        df_ord = pd.DataFrame(
            [
                {
                    "Nº Sequencial": f"#{o['numero_sequencial']}",
                    "ID Pedido": o["id"],
                    "Data da Compra": format_date_br(o["data_compra"]),
                    "Intervalo desde Pedido Anterior": (
                        f"{o['intervalo_desde_anterior_dias']} dias"
                        if o["intervalo_desde_anterior_dias"] is not None
                        else "1ª Compra"
                    ),
                    "Unidades Compradas": o["quantidade_produtos"],
                    "Valor Total do Pedido": format_brl(o["valor_total"]),
                    "Status": o["status_pedido"],
                }
                for o in orders_hist
            ]
        )
        st.dataframe(df_ord, width="stretch", hide_index=True)

    render_synthetic_disclaimer_footer(format_date_br(portfolio["reference_date"]))


render_customer_profile_page()
