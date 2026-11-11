"""
Página 4 — Central de Oportunidades (`pages/4_Oportunidades.py`).

Dividida em duas áreas estratégicas de geração de receita B2B:
A. Oportunidades de Cross-Sell (Expansão de Mix):
   - Lista todas as recomendações calculadas por `analytics/cross_sell.py` com
     base na penetração observada entre pares do mesmo segmento.
   - Permite filtrar por Cidade, Segmento, Cliente e Produto.
B. Oportunidades de Recompra e Recuperação (Retenção):
   - Identifica clientes com recompra atrasada ou prevista para os próximos dias.
   - Permite priorizar clientes e gerar sugestões de mensagem consultiva para WhatsApp.
"""

import streamlit as st

from components.kpi_cards import (
    inject_custom_css,
    render_kpi_card,
    render_page_header,
    render_synthetic_disclaimer_footer,
)
from components.sidebar import load_portfolio_state, render_sidebar_context
from components.tables import (
    build_cross_sell_dataframe,
    build_repurchase_opportunities_dataframe,
)
from services.dashboard_service import (
    filter_customer_records,
    flatten_cross_sell_opportunities,
    format_brl,
    format_date_br,
    format_int_br,
)


def render_opportunities_page() -> None:
    inject_custom_css()
    portfolio = load_portfolio_state()
    sidebar_filters = render_sidebar_context(portfolio, show_global_filters=True)

    render_page_header(
        title="Central de Oportunidades Comerciais — Cross-Sell e Recompra",
        subtitle=(
            "Transforme padrões de consumo em ações ativas de vendas: expansão de mix por "
            "afinidade de segmento e captura de recompras previstas ou em atraso."
        ),
    )

    filtered_customers = filter_customer_records(
        customers=portfolio["customers"],
        cidades=sidebar_filters["cidades"],
        segmentos=sidebar_filters["segmentos"],
    )

    if not filtered_customers:
        st.warning(
            "Nenhum cliente encontrado para os filtros selecionados na barra lateral."
        )
        return

    tab_cross_sell, tab_repurchase = st.tabs(
        [
            "A. Oportunidades de Cross-Sell (Expansão de Mix)",
            "B. Oportunidades de Recompra & Abordagem WhatsApp",
        ]
    )

    # ========================================================================
    # ABA A: CROSS-SELL
    # ========================================================================
    with tab_cross_sell:
        st.markdown(
            """
            <div class="praso-exec-panel">
                <h3>Metodologia de Recomendação por Benchmark de Segmento</h3>
                <p style="margin: 0; color: #334155; font-size: 0.92rem;">
                    As recomendações abaixo são geradas pelo módulo <code>analytics/cross_sell.py</code>
                    comparando o histórico de compras de cada cliente com os estabelecimentos do
                    <strong>mesmo segmento</strong>. Um item somente é sugerido quando possui
                    <strong>alta taxa de penetração no segmento (mínimo 25%)</strong> e
                    <strong>nunca foi adquirido pelo cliente analisado</strong>. Trata-se de
                    afinidade comercial entre pares semelhantes, não implicando causalidade.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        all_cs_rows = flatten_cross_sell_opportunities(
            customers=filtered_customers,
            cidades=sidebar_filters["cidades"],
            segmentos=sidebar_filters["segmentos"],
        )

        # Filtros específicos de Cross-Sell (Cliente e Produto)
        csc1, csc2 = st.columns(2)
        clientes_opcoes = {"Todos os clientes": None}
        for c in filtered_customers:
            clientes_opcoes[f"{c['nome_fantasia']} ({c['cidade']})"] = int(c["cliente_id"])

        produtos_sugeridos_unicos = sorted(
            {r["produto_sugerido"] for r in all_cs_rows}
        )
        produtos_opcoes = ["Todos os produtos recomendados"] + produtos_sugeridos_unicos

        with csc1:
            cliente_label = st.selectbox(
                "Filtrar por Estabelecimento:",
                options=list(clientes_opcoes.keys()),
                index=0,
            )
            cid_filtro = clientes_opcoes[cliente_label]

        with csc2:
            prod_label = st.selectbox(
                "Filtrar por Produto Recomendado:",
                options=produtos_opcoes,
                index=0,
            )
            prod_filtro = None if prod_label == "Todos os produtos recomendados" else prod_label

        cs_filtered = flatten_cross_sell_opportunities(
            customers=filtered_customers,
            cidades=sidebar_filters["cidades"],
            segmentos=sidebar_filters["segmentos"],
            cliente_id=cid_filtro,
            produto_nome=prod_filtro,
        )

        k1, k2, k3 = st.columns(3)
        clientes_distintos_cs = len({r["cliente_id"] for r in cs_filtered})
        potencial_soma_cs = sum(
            float(r["potencial_oportunidade_pedido"]) for r in cs_filtered
        )

        with k1:
            render_kpi_card(
                "Recomendações Mapeadas",
                format_int_br(len(cs_filtered)),
                f"Em {clientes_distintos_cs} estabelecimentos distintos",
                "blue",
            )
        with k2:
            render_kpi_card(
                "Potencial Incremental / Ciclo",
                format_brl(potencial_soma_cs),
                "Caso 1 pedido de cada recomendação seja convertido",
                "green",
            )
        with k3:
            pen_media = (
                sum(float(r["taxa_penetracao_pct"]) for r in cs_filtered) / len(cs_filtered)
                if cs_filtered
                else 0.0
            )
            render_kpi_card(
                "Penetração Média no Segmento",
                f"{pen_media:.1f}%",
                "Adesão média entre estabelecimentos pares",
                "amber",
            )

        if not cs_filtered:
            st.info("Nenhuma recomendação de cross-sell encontrada para este filtro.")
        else:
            df_cs = build_cross_sell_dataframe(cs_filtered)
            st.dataframe(df_cs, width="stretch", hide_index=True, height=420)

    # ========================================================================
    # ABA B: OPORTUNIDADES DE RECOMPRA E ABORDAGEM COMERCIAL
    # ========================================================================
    with tab_repurchase:
        rc1, rc2 = st.columns([2, 2])
        with rc1:
            filtro_janela = st.selectbox(
                "Filtrar Situação da Janela de Recompra:",
                options=[
                    "Prioritários: Recompra Atrasada ou Próxima (<= 5 dias)",
                    "Somente Clientes com Ciclo Atrasado (Em Risco)",
                    "Somente Clientes Saudáveis Próximos da Recompra (<= 5 dias)",
                    "Todos os Clientes com Ciclo Calculado",
                ],
                index=0,
            )
        with rc2:
            ordem_recompra = st.selectbox(
                "Critério de Priorização da Lista:",
                options=[
                    "Score de Prioridade Comercial (Padrão)",
                    "Maior Receita Mensal Estimada",
                    "Maior Dias de Atraso no Ciclo",
                ],
                index=0,
            )

        candidatos_recompra = []
        for c in filtered_customers:
            if not c.get("historico_suficiente_para_ciclo"):
                continue
            atraso = int(c.get("dias_atraso_ciclo") or 0)
            dias_ate_prox = int(c.get("dias_ate_proxima_compra") or 999)

            if filtro_janela == "Prioritários: Recompra Atrasada ou Próxima (<= 5 dias)":
                if atraso > 0 or dias_ate_prox <= 5:
                    candidatos_recompra.append(c)
            elif filtro_janela == "Somente Clientes com Ciclo Atrasado (Em Risco)":
                if c.get("em_risco_comercial"):
                    candidatos_recompra.append(c)
            elif filtro_janela == "Somente Clientes Saudáveis Próximos da Recompra (<= 5 dias)":
                if not c.get("em_risco_comercial") and dias_ate_prox <= 5:
                    candidatos_recompra.append(c)
            else:
                candidatos_recompra.append(c)

        if ordem_recompra == "Maior Receita Mensal Estimada":
            candidatos_recompra.sort(
                key=lambda x: -float(x.get("receita_mensal_estimada") or 0.0)
            )
        elif ordem_recompra == "Maior Dias de Atraso no Ciclo":
            candidatos_recompra.sort(
                key=lambda x: -int(x.get("dias_atraso_ciclo") or 0)
            )
        else:
            candidatos_recompra.sort(key=lambda x: int(x.get("ranking_prioridade") or 999))

        rk1, rk2, rk3 = st.columns(3)
        soma_mensal_op = sum(
            float(c.get("receita_mensal_estimada") or 0.0) for c in candidatos_recompra
        )
        soma_risco_op = sum(
            float(c.get("receita_em_risco") or 0.0) for c in candidatos_recompra
        )

        with rk1:
            render_kpi_card(
                "Clientes na Fila de Recompra",
                format_int_br(len(candidatos_recompra)),
                "Estabelecimentos selecionados para abordagem",
                "blue",
            )
        with rk2:
            render_kpi_card(
                "Receita Mensal Estimada do Grupo",
                format_brl(soma_mensal_op),
                "Potencial recorrente em janela de 30 dias",
                "green",
            )
        with rk3:
            render_kpi_card(
                "Receita em Risco no Grupo",
                format_brl(soma_risco_op),
                "Parcela exposta a atraso de ciclo",
                "red" if soma_risco_op > 0 else "green",
            )

        if not candidatos_recompra:
            st.info("Nenhum estabelecimento encontrado para o recorte de janela selecionado.")
        else:
            df_rep = build_repurchase_opportunities_dataframe(candidatos_recompra)
            st.dataframe(df_rep, width="stretch", hide_index=True, height=380)

            st.markdown("---")
            st.markdown("#### Gerador de Mensagem Consultiva (WhatsApp)")
            opcoes_msg = {
                int(c["cliente_id"]): (
                    f"#{c['ranking_prioridade']} — {c['nome_fantasia']} "
                    f"({c['classificacao_risco']} | Última compra: {format_date_br(c['ultima_compra'])})"
                )
                for c in candidatos_recompra
            }
            cid_msg = st.selectbox(
                "Selecione o cliente para gerar o roteiro de contato comercial:",
                options=list(opcoes_msg.keys()),
                format_func=lambda cid: opcoes_msg[cid],
            )
            cliente_msg_obj = next(
                c for c in candidatos_recompra if int(c["cliente_id"]) == int(cid_msg)
            )
            st.markdown(
                f"**Ação Recomendada:** {cliente_msg_obj['acao_comercial_recomendada']}  \n"
                f"**Justificativa:** {cliente_msg_obj['justificativa_prioridade']}"
            )
            st.code(cliente_msg_obj["sugestao_mensagem_whatsapp"], language=None)

    render_synthetic_disclaimer_footer(format_date_br(portfolio["reference_date"]))


render_opportunities_page()
