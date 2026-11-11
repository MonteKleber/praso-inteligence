"""
Componentes de Formatação de Tabelas Interativas (`components/tables.py`).

Prepara DataFrames Pandas com colunas em português brasileiro, valores formatados
e ordenação consistente para exibição no Streamlit.
"""

from typing import Any
import pandas as pd

from services.dashboard_service import format_brl, format_date_br


def build_customer_radar_dataframe(customers: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Constrói o DataFrame formatado para exibição na Página 2 (Radar de Clientes).
    """
    rows = []
    for c in customers:
        ciclo = c.get("intervalo_mediano_dias")
        dias_sem = c.get("dias_desde_ultima_compra")
        rows.append(
            {
                "Ranking": f"#{c['ranking_prioridade']}",
                "ID": c["cliente_id"],
                "Estabelecimento": c["nome_fantasia"],
                "Cidade": c["cidade"],
                "Segmento": c["tipo_estabelecimento"],
                "Classificação de Risco": c["classificacao_risco"],
                "Dias sem Comprar": int(dias_sem) if dias_sem is not None else 0,
                "Ciclo Habitual (Dias)": f"{ciclo:.0f} d" if ciclo is not None else "—",
                "Última Compra": format_date_br(c.get("ultima_compra")),
                "Ticket Médio": format_brl(c.get("ticket_medio")),
                "Receita Mensal Estimada": format_brl(c.get("receita_mensal_estimada")),
                "Receita em Risco (30d)": format_brl(c.get("receita_em_risco")),
                "Score de Prioridade": round(float(c.get("score_prioridade") or 0.0), 2),
                "Consultor Responsável": c.get("responsavel_comercial", ""),
            }
        )
    return pd.DataFrame(rows)


def build_cross_sell_dataframe(opportunities: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Constrói o DataFrame formatado para a seção de Cross-Sell da Página 4.
    """
    rows = []
    for opp in opportunities:
        rows.append(
            {
                "ID Cliente": opp["cliente_id"],
                "Cliente": opp["nome_fantasia"],
                "Cidade": opp["cidade"],
                "Segmento": opp["tipo_estabelecimento"],
                "Status do Cliente": opp["classificacao_risco"],
                "Produto Recomendado": opp["produto_sugerido"],
                "Categoria": opp["categoria_produto"],
                "Penetração no Segmento": f"{opp['taxa_penetracao_pct']:.0f}%",
                "Potencial Estimado / Pedido": format_brl(opp["potencial_oportunidade_pedido"]),
                "Justificativa Comercial": opp["justificativa"],
            }
        )
    return pd.DataFrame(rows)


def build_repurchase_opportunities_dataframe(customers: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Constrói o DataFrame de oportunidades de recompra (clientes com recompra
    prevista para os próximos dias ou já atrasados em relação ao ciclo).
    """
    rows = []
    for c in customers:
        if not c.get("historico_suficiente_para_ciclo"):
            continue
        ciclo = c.get("intervalo_mediano_dias")
        dias_atraso = int(c.get("dias_atraso_ciclo") or 0)
        dias_ate_prox = int(c.get("dias_ate_proxima_compra") or 0)

        if dias_atraso > 0:
            janela_status = f"Atrasado ({dias_atraso} dias)"
        elif dias_ate_prox <= 5:
            janela_status = f"Próxima compra em {dias_ate_prox} d"
        else:
            janela_status = f"Dentro do ciclo (faltam {dias_ate_prox} d)"

        rows.append(
            {
                "Ranking": f"#{c['ranking_prioridade']}",
                "ID": c["cliente_id"],
                "Cliente": c["nome_fantasia"],
                "Cidade": c["cidade"],
                "Segmento": c["tipo_estabelecimento"],
                "Classificação de Risco": c["classificacao_risco"],
                "Última Compra": format_date_br(c.get("ultima_compra")),
                "Próxima Recompra Estimada": format_date_br(c.get("proxima_compra_estimada")),
                "Situação da Janela": janela_status,
                "Dias de Atraso": dias_atraso,
                "Ciclo Habitual": f"{ciclo:.0f} dias" if ciclo else "—",
                "Receita Mensal Estimada": format_brl(c.get("receita_mensal_estimada")),
                "Receita em Risco (30d)": format_brl(c.get("receita_em_risco")),
                "Score de Prioridade": round(float(c.get("score_prioridade") or 0.0), 2),
                "Ação Recomendada": c.get("acao_comercial_recomendada", ""),
            }
        )
    return pd.DataFrame(rows)
