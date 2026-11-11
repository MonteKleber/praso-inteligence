"""
Componentes de Gráficos Interativos Plotly (`components/charts.py`).

Todos os gráficos seguem a paleta corporativa SaaS B2B do Praso Intelligence:
- Azul-Marinho (`#0F172A` / `#1E3A8A`) para séries principais
- Azul Vivo (`#2563EB`) para destaques e projeções
- Verde (`#16A34A`) para clientes saudáveis / em dia
- Amarelo (`#D97706`) para clientes em atenção
- Laranja (`#EA580C`) para risco moderado
- Vermelho (`#DC2626`) para alto risco
- Cinza Azulado (`#64748B`) para dados insuficientes
"""

from typing import Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from analytics.churn import (
    STATUS_ALTO_RISCO,
    STATUS_ATENCAO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_RISCO_MODERADO,
    STATUS_SAUDAVEL,
)

RISK_COLOR_MAP = {
    STATUS_SAUDAVEL: "#16A34A",
    STATUS_ATENCAO: "#D97706",
    STATUS_RISCO_MODERADO: "#EA580C",
    STATUS_ALTO_RISCO: "#DC2626",
    STATUS_DADOS_INSUFICIENTES: "#64748B",
}

RISK_ORDER = [
    STATUS_SAUDAVEL,
    STATUS_ATENCAO,
    STATUS_RISCO_MODERADO,
    STATUS_ALTO_RISCO,
    STATUS_DADOS_INSUFICIENTES,
]


def _apply_corporate_layout(fig: go.Figure, title: str, height: int = 360) -> go.Figure:
    """Padroniza fonte, margens, fundo branco e título nos gráficos Plotly."""
    fig.update_layout(
        title={
            "text": f"<b>{title}</b>",
            "x": 0.01,
            "xanchor": "left",
            "font": {"size": 15, "color": "#0F172A"},
        },
        height=height,
        margin={"l": 20, "r": 20, "t": 50, "b": 25},
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font={"family": "sans-serif", "color": "#334155", "size": 12},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.22,
            "xanchor": "center",
            "x": 0.5,
        },
    )
    fig.update_xaxes(showgrid=False, linecolor="#CBD5E1")
    fig.update_yaxes(gridcolor="#F1F5F9", linecolor="#CBD5E1")
    return fig


def build_risk_distribution_chart(customers: list[dict[str, Any]]) -> go.Figure:
    """Gráfico 1 (Visão Geral): Distribuição de clientes por classificação de risco."""
    counts = {status: 0 for status in RISK_ORDER}
    for c in customers:
        st_val = c.get("classificacao_risco", STATUS_DADOS_INSUFICIENTES)
        counts[st_val] = counts.get(st_val, 0) + 1

    df = pd.DataFrame(
        [
            {"Classificação": k, "Quantidade de Clientes": v}
            for k, v in counts.items()
        ]
    )

    fig = px.bar(
        df,
        x="Classificação",
        y="Quantidade de Clientes",
        color="Classificação",
        color_discrete_map=RISK_COLOR_MAP,
        text="Quantidade de Clientes",
        category_orders={"Classificação": RISK_ORDER},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig = _apply_corporate_layout(
        fig, "Distribuição da Carteira por Classificação de Risco"
    )
    fig.update_layout(showlegend=False)
    return fig


def build_healthy_vs_risk_comparison_chart(customers: list[dict[str, Any]]) -> go.Figure:
    """
    Gráfico de comparação direta entre Clientes Saudáveis, Clientes em Risco
    (Atenção + Moderado + Alto) e Dados Insuficientes, mostrando clientes e receita.
    """
    grupos = {
        "Saudáveis (Em dia)": {"clientes": 0, "receita_mensal": 0.0, "cor": "#16A34A"},
        "Em Risco Comercial": {"clientes": 0, "receita_mensal": 0.0, "cor": "#DC2626"},
        "Dados Insuficientes (1ª Compra)": {"clientes": 0, "receita_mensal": 0.0, "cor": "#64748B"},
    }

    for c in customers:
        status = c.get("classificacao_risco")
        rec_mes = float(c.get("receita_mensal_estimada") or 0.0)
        if status == STATUS_SAUDAVEL:
            grupos["Saudáveis (Em dia)"]["clientes"] += 1
            grupos["Saudáveis (Em dia)"]["receita_mensal"] += rec_mes
        elif c.get("em_risco_comercial"):
            grupos["Em Risco Comercial"]["clientes"] += 1
            grupos["Em Risco Comercial"]["receita_mensal"] += rec_mes
        else:
            grupos["Dados Insuficientes (1ª Compra)"]["clientes"] += 1
            grupos["Dados Insuficientes (1ª Compra)"]["receita_mensal"] += rec_mes

    df = pd.DataFrame(
        [
            {
                "Grupo": k,
                "Clientes": v["clientes"],
                "Receita Mensal Estimada (R$)": round(v["receita_mensal"], 2),
            }
            for k, v in grupos.items()
        ]
    )

    fig = px.pie(
        df,
        names="Grupo",
        values="Clientes",
        hole=0.55,
        color="Grupo",
        color_discrete_map={
            "Saudáveis (Em dia)": "#16A34A",
            "Em Risco Comercial": "#DC2626",
            "Dados Insuficientes (1ª Compra)": "#64748B",
        },
    )
    fig.update_traces(textinfo="percent+value", textfont_size=12)
    return _apply_corporate_layout(
        fig, "Proporção da Carteira: Saudáveis vs. Em Risco"
    )


def build_revenue_by_segment_chart(segment_summary: list[dict[str, Any]]) -> go.Figure:
    """Gráfico de barras horizontais: Receita Histórica vs. Receita em Risco por Segmento."""
    if not segment_summary:
        return _apply_corporate_layout(go.Figure(), "Receita por Segmento (Sem dados)")

    df = pd.DataFrame(segment_summary).sort_values(
        by="receita_historica", ascending=True
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["tipo_estabelecimento"],
            x=df["receita_historica"],
            name="Receita Histórica Acumulada (R$)",
            orientation="h",
            marker_color="#1E3A8A",
            text=[f"R$ {v:,.0f}".replace(",", ".") for v in df["receita_historica"]],
            textposition="auto",
        )
    )
    fig.add_trace(
        go.Bar(
            y=df["tipo_estabelecimento"],
            x=df["receita_historica_clientes_em_risco"],
            name="Receita Histórica de Clientes em Risco (R$)",
            orientation="h",
            marker_color="#DC2626",
            text=[
                f"R$ {v:,.0f}".replace(",", ".")
                for v in df["receita_historica_clientes_em_risco"]
            ],
            textposition="auto",
        )
    )
    fig.update_layout(barmode="group")
    return _apply_corporate_layout(
        fig, "Receita Histórica Total vs. Associada a Clientes em Risco por Segmento", height=380
    )


def build_revenue_by_city_chart(city_summary: list[dict[str, Any]]) -> go.Figure:
    """Gráfico comparativo de Receita Histórica, Mensal Estimada e Em Risco por Cidade."""
    if not city_summary:
        return _apply_corporate_layout(go.Figure(), "Receita por Cidade (Sem dados)")

    df = pd.DataFrame(city_summary)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["cidade"],
            y=df["receita_historica"],
            name="Receita Histórica (12m)",
            marker_color="#1E3A8A",
            text=[f"R$ {v:,.0f}".replace(",", ".") for v in df["receita_historica"]],
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df["cidade"],
            y=df["receita_mensal_estimada"],
            name="Potencial Mensal (30d)",
            marker_color="#2563EB",
            text=[f"R$ {v:,.0f}".replace(",", ".") for v in df["receita_mensal_estimada"]],
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df["cidade"],
            y=df["receita_em_risco"],
            name="Receita Mensal em Risco",
            marker_color="#DC2626",
            text=[f"R$ {v:,.0f}".replace(",", ".") for v in df["receita_em_risco"]],
            textposition="outside",
        )
    )
    fig.update_layout(barmode="group")
    fig.update_traces(cliponaxis=False)
    return _apply_corporate_layout(
        fig, "Comparativo Financeiro por Cidade de Operação (R$)", height=380
    )


def build_monthly_evolution_chart(monthly_data: list[dict[str, Any]]) -> go.Figure:
    """Evolução mensal do faturamento histórico e volume de pedidos concluídos."""
    if not monthly_data:
        return _apply_corporate_layout(go.Figure(), "Evolução Mensal (Sem dados)")

    df = pd.DataFrame(monthly_data)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["ano_mes"],
            y=df["receita_historica"],
            name="Receita Histórica Mensal (R$)",
            marker_color="#2563EB",
            yaxis="y1",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["ano_mes"],
            y=df["quantidade_pedidos"],
            name="Quantidade de Pedidos",
            mode="lines+markers",
            line={"color": "#0F172A", "width": 3},
            marker={"size": 7},
            yaxis="y2",
        )
    )

    fig = _apply_corporate_layout(
        fig, "Evolução Mensal de Faturamento e Volume de Pedidos Concluídos", height=360
    )
    fig.update_layout(
        yaxis={"title": "Receita (R$)", "showgrid": True, "gridcolor": "#F1F5F9"},
        yaxis2={
            "title": "Nº de Pedidos",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
    )
    return fig


def build_customer_orders_timeline_chart(
    orders_history: list[dict[str, Any]],
    ticket_medio: float | None,
) -> go.Figure:
    """Gráfico do Perfil do Cliente: Evolução dos valores de cada pedido no tempo."""
    if not orders_history:
        return _apply_corporate_layout(go.Figure(), "Histórico de Pedidos (Sem dados)")

    df = pd.DataFrame(orders_history)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["data_compra"],
            y=df["valor_total"],
            mode="lines+markers+text",
            name="Valor do Pedido (R$)",
            line={"color": "#2563EB", "width": 3},
            marker={"size": 9, "color": "#1E3A8A"},
            text=[f"R$ {v:,.0f}".replace(",", ".") for v in df["valor_total"]],
            textposition="top center",
        )
    )

    if ticket_medio:
        fig.add_hline(
            y=float(ticket_medio),
            line_dash="dash",
            line_color="#16A34A",
            annotation_text=f"Ticket Médio: R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            annotation_position="bottom right",
        )

    return _apply_corporate_layout(
        fig, "Linha do Tempo de Compras e Evolução do Valor por Pedido (R$)", height=350
    )


def build_customer_intervals_chart(
    orders_history: list[dict[str, Any]],
    ciclo_mediano: float | None,
    dias_sem_comprar_atual: int | None,
) -> go.Figure:
    """
    Gráfico do Perfil do Cliente: Intervalos em dias entre compras consecutivas
    comparados com o Ciclo Mediano Habitual e o Tempo Atual sem Comprar.
    """
    rows = []
    for o in orders_history:
        interv = o.get("intervalo_desde_anterior_dias")
        if interv is not None:
            rows.append(
                {
                    "Etapa": f"Pedido #{o['numero_sequencial']} ({o['data_compra']})",
                    "Dias": int(interv),
                    "Tipo": "Intervalo Histórico",
                }
            )

    if dias_sem_comprar_atual is not None:
        rows.append(
            {
                "Etapa": "Janela Atual (Até 05/11/2026)",
                "Dias": int(dias_sem_comprar_atual),
                "Tipo": "Tempo Atual sem Comprar",
            }
        )

    if not rows:
        return _apply_corporate_layout(
            go.Figure(), "Intervalos entre Compras (Histórico insuficiente)"
        )

    df = pd.DataFrame(rows)
    fig = px.bar(
        df,
        x="Etapa",
        y="Dias",
        color="Tipo",
        color_discrete_map={
            "Intervalo Histórico": "#1E3A8A",
            "Tempo Atual sem Comprar": "#DC2626"
            if (ciclo_mediano and dias_sem_comprar_atual and dias_sem_comprar_atual > ciclo_mediano * 1.15)
            else "#16A34A",
        },
        text="Dias",
    )
    fig.update_traces(textposition="outside", cliponaxis=False)

    if ciclo_mediano:
        fig.add_hline(
            y=float(ciclo_mediano),
            line_dash="dash",
            line_color="#D97706",
            annotation_text=f"Ciclo Mediano Habitual: {ciclo_mediano:.0f} dias",
            annotation_position="top left",
        )

    return _apply_corporate_layout(
        fig, "Comparação entre Intervalos Históricos e Tempo Atual sem Comprar (Dias)", height=350
    )


def build_customer_top_products_chart(top_products: list[dict[str, Any]]) -> go.Figure:
    """Gráfico de barras horizontais dos produtos mais adquiridos pelo cliente."""
    if not top_products:
        return _apply_corporate_layout(go.Figure(), "Produtos Comprados (Sem dados)")

    df = pd.DataFrame(top_products[:8]).sort_values(
        by="valor_total_comprado", ascending=True
    )
    fig = px.bar(
        df,
        y="produto_nome",
        x="valor_total_comprado",
        orientation="h",
        color="categoria",
        text=[f"R$ {v:,.0f}".replace(",", ".") for v in df["valor_total_comprado"]],
        labels={
            "produto_nome": "Produto",
            "valor_total_comprado": "Valor Acumulado (R$)",
            "categoria": "Categoria",
        },
    )
    fig.update_traces(textposition="auto")
    return _apply_corporate_layout(
        fig, "Mix de Produtos Adquiridos pelo Cliente (Faturamento Acumulado)", height=350
    )
