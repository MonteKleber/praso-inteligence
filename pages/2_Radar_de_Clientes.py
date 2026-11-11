"""
Página 2 — Radar de Clientes (`pages/2_Radar_de_Clientes.py`).

Tabela interativa de gestão e priorização da carteira comercial B2B:
- Filtros combinados por Cidade, Segmento, Classificação de Risco, Faixa de Score
  e busca textual por nome/ID do estabelecimento.
- Ordenação configurável (iniciando pelo Score de Prioridade Comercial).
- Destaque dos clientes no topo da fila com justificativa da prioridade.
- Seleção direta de um cliente para abrir seu dossiê na Página 3 (Perfil do Cliente).
"""

import streamlit as st

from components.kpi_cards import (
    get_risk_badge_html,
    inject_custom_css,
    render_kpi_card,
    render_page_header,
    render_synthetic_disclaimer_footer,
)
from components.sidebar import load_portfolio_state, render_sidebar_context
from components.tables import build_customer_radar_dataframe
from services.dashboard_service import (
    filter_customer_records,
    format_brl,
    format_date_br,
    format_int_br,
)


def render_customer_radar_page() -> None:
    inject_custom_css()
    portfolio = load_portfolio_state()
    sidebar_filters = render_sidebar_context(portfolio, show_global_filters=True)
    filter_opts = portfolio["filter_options"]

    render_page_header(
        title="Radar de Clientes — Fila de Priorização Comercial",
        subtitle=(
            "Identifique rapidamente estabelecimentos fora do ciclo habitual de compra, "
            "ordene por score multicritério e acione o consultor responsável."
        ),
    )

    # ------------------------------------------------------------------------
    # 1. CONTROLES DE FILTRO ESPECÍFICOS DO RADAR
    # ------------------------------------------------------------------------
    with st.container():
        fcol1, fcol2, fcol3, fcol4 = st.columns([2, 2, 2, 2])

        with fcol1:
            search_text = st.text_input(
                "Pesquisar Estabelecimento (Nome ou ID)",
                value=st.session_state.get("radar_search_text", ""),
                placeholder="Ex.: Padaria, Empório, #025...",
            )
            st.session_state["radar_search_text"] = search_text

        with fcol2:
            status_sel = st.multiselect(
                "Classificação de Risco",
                options=filter_opts["status_risco"],
                default=st.session_state.get(
                    "filtro_status_risco", filter_opts["status_risco"]
                ),
            )
            st.session_state["filtro_status_risco"] = status_sel

        with fcol3:
            score_range = st.slider(
                "Faixa de Score de Prioridade",
                min_value=0.0,
                max_value=100.0,
                value=(0.0, 100.0),
                step=1.0,
            )

        with fcol4:
            sort_option = st.selectbox(
                "Ordenar Carteira por",
                options=[
                    "Score de Prioridade (Maior primeiro)",
                    "Receita em Risco (Maior primeiro)",
                    "Dias sem Comprar (Maior atraso)",
                    "Ticket Médio (Maior primeiro)",
                    "Receita Mensal Estimada (Maior primeiro)",
                ],
                index=0,
            )

    filtered = filter_customer_records(
        customers=portfolio["customers"],
        cidades=sidebar_filters["cidades"],
        segmentos=sidebar_filters["segmentos"],
        status_risco=status_sel,
        score_range=score_range,
        search_query=search_text,
    )

    # Aplica ordenação escolhida pelo usuário
    if sort_option == "Receita em Risco (Maior primeiro)":
        filtered.sort(
            key=lambda x: (
                -float(x.get("receita_em_risco") or 0.0),
                -float(x.get("score_prioridade") or 0.0),
            )
        )
    elif sort_option == "Dias sem Comprar (Maior atraso)":
        filtered.sort(
            key=lambda x: (
                -int(x.get("dias_desde_ultima_compra") or -1),
                -float(x.get("score_prioridade") or 0.0),
            )
        )
    elif sort_option == "Ticket Médio (Maior primeiro)":
        filtered.sort(
            key=lambda x: (
                -float(x.get("ticket_medio") or 0.0),
                -float(x.get("score_prioridade") or 0.0),
            )
        )
    elif sort_option == "Receita Mensal Estimada (Maior primeiro)":
        filtered.sort(
            key=lambda x: (
                -float(x.get("receita_mensal_estimada") or 0.0),
                -float(x.get("score_prioridade") or 0.0),
            )
        )
    else:
        filtered.sort(key=lambda x: int(x.get("ranking_prioridade") or 999))

    st.caption(
        f"Exibindo **{len(filtered)}** de **{len(portfolio['customers'])}** estabelecimentos cadastrados."
    )

    if not filtered:
        st.info(
            "Nenhum cliente corresponde aos critérios de filtro selecionados. "
            "Experimente ampliar a faixa de score ou selecionar mais classificações de risco."
        )
        return

    # ------------------------------------------------------------------------
    # 2. RESUMO RÁPIDO DO RECORTE FILTRADO
    # ------------------------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    qtd_em_risco = sum(1 for c in filtered if c.get("em_risco_comercial"))
    soma_rec_risco = sum(float(c.get("receita_em_risco") or 0.0) for c in filtered)
    soma_rec_mensal = sum(
        float(c.get("receita_mensal_estimada") or 0.0) for c in filtered
    )
    score_medio = sum(float(c.get("score_prioridade") or 0.0) for c in filtered) / len(
        filtered
    )

    with k1:
        render_kpi_card(
            "Clientes no Filtro",
            format_int_br(len(filtered)),
            f"{qtd_em_risco} com alerta comercial ativo",
            "blue",
        )
    with k2:
        render_kpi_card(
            "Potencial Mensal do Grupo",
            format_brl(soma_rec_mensal),
            "Soma das projeções de 30 dias",
            "blue",
        )
    with k3:
        render_kpi_card(
            "Receita em Risco no Grupo",
            format_brl(soma_rec_risco),
            "Exposição financeira estimada (30d)",
            "red" if soma_rec_risco > 0 else "green",
        )
    with k4:
        render_kpi_card(
            "Score Médio de Prioridade",
            f"{score_medio:.1f} / 100",
            f"Líder atual: #{filtered[0]['ranking_prioridade']} ({filtered[0]['score_prioridade']:.1f} pts)",
            "amber",
        )

    # ------------------------------------------------------------------------
    # 3. DESTAQUE EXPLICATIVO DO TOP #1 DA LISTA FILTRADA
    # ------------------------------------------------------------------------
    top_cust = filtered[0]
    badge_html = get_risk_badge_html(top_cust["classificacao_risco"])
    st.markdown(
        f"""
        <div class="praso-exec-panel">
            <h3>Prioridade #1 na Visualização Atual: {top_cust['nome_fantasia']} ({top_cust['cidade']} — {top_cust['tipo_estabelecimento']}) {badge_html}</h3>
            <p style="margin-bottom: 0.35rem; color: #334155; font-size: 0.92rem;">
                <strong>Por que este cliente aparece no topo?</strong> {top_cust['justificativa_prioridade']}
            </p>
            <p style="margin: 0; color: #475569; font-size: 0.86rem;">
                <strong>Composição do Score ({top_cust['score_prioridade']:.2f}/100):</strong>
                Urgência/Risco: <code>{top_cust['nota_componente_risco']:.2f}/45</code> |
                Ticket Médio: <code>{top_cust['nota_componente_ticket']:.2f}/25</code> |
                Potencial Mensal: <code>{top_cust['nota_componente_receita']:.2f}/20</code> |
                Cross-Sell: <code>{top_cust['nota_componente_cross_sell']:.2f}/10</code> —
                <strong>Ação sugerida:</strong> {top_cust['acao_comercial_recomendada']}.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------------
    # 4. TABELA INTERATIVA E NAVEGAÇÃO DIRETA PARA O PERFIL DO CLIENTE
    # ------------------------------------------------------------------------
    df_radar = build_customer_radar_dataframe(filtered)
    st.dataframe(
        df_radar,
        width="stretch",
        hide_index=True,
        height=440,
        column_config={
            "Score de Prioridade": st.column_config.ProgressColumn(
                "Score de Prioridade",
                help="Pontuação heurística de 0 a 100 combinando risco, ticket, receita e cross-sell.",
                format="%.1f",
                min_value=0,
                max_value=100,
            ),
        },
    )

    st.markdown("---")
    st.markdown("#### Inspecionar Perfil Detalhado do Cliente")
    nav_col1, nav_col2 = st.columns([3, 1])

    opcoes_clientes = {
        int(c["cliente_id"]): (
            f"#{c['ranking_prioridade']} — {c['nome_fantasia']} "
            f"({c['cidade']} | {c['classificacao_risco']} | Score {c['score_prioridade']:.1f})"
        )
        for c in filtered
    }
    default_cid = st.session_state.get("cliente_selecionado_id", filtered[0]["cliente_id"])
    if default_cid not in opcoes_clientes:
        default_cid = int(filtered[0]["cliente_id"])

    with nav_col1:
        chosen_cid = st.selectbox(
            "Selecione um estabelecimento da lista filtrada para abrir o Perfil 360º:",
            options=list(opcoes_clientes.keys()),
            format_func=lambda cid: opcoes_clientes[cid],
            index=list(opcoes_clientes.keys()).index(default_cid),
        )

    with nav_col2:
        st.write("")
        st.write("")
        if st.button("Abrir Perfil do Cliente", type="primary", width="stretch"):
            st.session_state["cliente_selecionado_id"] = int(chosen_cid)
            st.switch_page("pages/3_Perfil_do_Cliente.py")

    render_synthetic_disclaimer_footer(format_date_br(portfolio["reference_date"]))


render_customer_radar_page()
