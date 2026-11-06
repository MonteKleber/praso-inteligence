"""
Módulo de Resumo Executivo (`analytics/executive_summary.py`).

Consolida todos os indicadores gerenciais da carteira B2B em uma estrutura de
dicionário Python pronta para consumo pelo dashboard Streamlit ou por relatórios
executivos, além de gerar diagnósticos textuais baseados estritamente nos dados
analisados (sem conclusões inventadas).
"""

from datetime import date
from pathlib import Path
from typing import Any, Optional

from analytics import DEFAULT_REFERENCE_DATE
from analytics.churn import (
    STATUS_ALTO_RISCO,
    STATUS_ATENCAO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_RISCO_MODERADO,
    STATUS_SAUDAVEL,
)
from analytics.prioritization import analyze_and_prioritize_all_customers
from analytics.repurchase import parse_iso_date
from analytics.revenue import summarize_revenue_by_dimension


def build_executive_summary_from_records(
    prioritized_customers: list[dict[str, Any]],
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
    top_n_priority: int = 5,
) -> dict[str, Any]:
    """
    Constrói o dicionário completo do Resumo Executivo a partir da lista já
    processada e priorizada de clientes.
    """
    ref_date_str = parse_iso_date(reference_date).isoformat()
    total_clientes = len(prioritized_customers)

    contagem_status = {
        STATUS_SAUDAVEL: 0,
        STATUS_ATENCAO: 0,
        STATUS_RISCO_MODERADO: 0,
        STATUS_ALTO_RISCO: 0,
        STATUS_DADOS_INSUFICIENTES: 0,
    }

    receita_historica_total = 0.0
    receita_historica_clientes_em_risco_total = 0.0
    receita_mensal_estimada_total = 0.0
    receita_em_risco_total = 0.0
    total_pedidos_concluidos = 0
    total_oportunidades_cross_sell = 0
    clientes_com_cross_sell = 0
    potencial_cross_sell_total = 0.0

    for c in prioritized_customers:
        status = c.get("classificacao_risco", STATUS_DADOS_INSUFICIENTES)
        contagem_status[status] = contagem_status.get(status, 0) + 1

        rec_hist = float(c.get("receita_historica") or 0.0)
        receita_historica_total += rec_hist
        if c.get("em_risco_comercial"):
            receita_historica_clientes_em_risco_total += rec_hist
        receita_mensal_estimada_total += float(c.get("receita_mensal_estimada") or 0.0)
        receita_em_risco_total += float(c.get("receita_em_risco") or 0.0)
        total_pedidos_concluidos += int(c.get("quantidade_pedidos") or 0)

        qtd_cs = int(c.get("quantidade_oportunidades_cross_sell") or 0)
        total_oportunidades_cross_sell += qtd_cs
        if qtd_cs > 0:
            clientes_com_cross_sell += 1
        potencial_cross_sell_total += float(c.get("potencial_cross_sell_pedido") or 0.0)

    receita_historica_total = round(receita_historica_total, 2)
    receita_historica_clientes_em_risco_total = round(
        receita_historica_clientes_em_risco_total, 2
    )
    receita_mensal_estimada_total = round(receita_mensal_estimada_total, 2)
    receita_em_risco_total = round(receita_em_risco_total, 2)
    potencial_cross_sell_total = round(potencial_cross_sell_total, 2)

    clientes_recorrentes = contagem_status[STATUS_SAUDAVEL]
    clientes_atencao = contagem_status[STATUS_ATENCAO]
    clientes_risco_moderado = contagem_status[STATUS_RISCO_MODERADO]
    clientes_alto_risco = contagem_status[STATUS_ALTO_RISCO]
    clientes_dados_insuficientes = contagem_status[STATUS_DADOS_INSUFICIENTES]

    # Clientes em risco englobam Atenção + Risco moderado + Alto risco
    clientes_em_risco_total = (
        clientes_atencao + clientes_risco_moderado + clientes_alto_risco
    )
    # Clientes em risco crítico (Risco moderado + Alto risco)
    clientes_risco_critico = clientes_risco_moderado + clientes_alto_risco

    taxa_clientes_em_risco = (
        round((clientes_em_risco_total / total_clientes) * 100, 2)
        if total_clientes > 0
        else 0.0
    )

    ticket_medio_geral = (
        round(receita_historica_total / total_pedidos_concluidos, 2)
        if total_pedidos_concluidos > 0
        else 0.0
    )

    resumo_por_segmento = summarize_revenue_by_dimension(
        prioritized_customers, "tipo_estabelecimento"
    )
    resumo_por_cidade = summarize_revenue_by_dimension(
        prioritized_customers, "cidade"
    )

    top_prioritarios = [
        {
            "ranking_prioridade": c["ranking_prioridade"],
            "cliente_id": c["cliente_id"],
            "nome_fantasia": c["nome_fantasia"],
            "cidade": c["cidade"],
            "tipo_estabelecimento": c["tipo_estabelecimento"],
            "responsavel_comercial": c["responsavel_comercial"],
            "classificacao_risco": c["classificacao_risco"],
            "dias_desde_ultima_compra": c["dias_desde_ultima_compra"],
            "intervalo_mediano_dias": c["intervalo_mediano_dias"],
            "ticket_medio": c["ticket_medio"],
            "receita_em_risco": c["receita_em_risco"],
            "score_prioridade": c["score_prioridade"],
            "acao_comercial_recomendada": c["acao_comercial_recomendada"],
            "justificativa_prioridade": c["justificativa_prioridade"],
        }
        for c in prioritized_customers[:top_n_priority]
    ]

    # Geração de insights executivos baseados estritamente nos números calculados
    principais_problemas: list[str] = []
    acoes_recomendadas: list[str] = []

    if total_clientes == 0:
        principais_problemas.append("Nenhum cliente encontrado na base analisada.")
    else:
        principais_problemas.append(
            f"{clientes_em_risco_total} de {total_clientes} clientes ({taxa_clientes_em_risco:.1f}%) "
            f"ultrapassaram seu intervalo habitual de recompra ({clientes_alto_risco} em Alto Risco, "
            f"{clientes_risco_moderado} em Risco Moderado e {clientes_atencao} em Atenção)."
        )
        principais_problemas.append(
            f"A receita potencial mensal exposta aos clientes em atraso é estimada em "
            f"R$ {receita_em_risco_total:,.2f} (sobre uma receita mensal estimada da carteira de "
            f"R$ {receita_mensal_estimada_total:,.2f})."
        )
        if resumo_por_segmento:
            seg_maior_risco = max(resumo_por_segmento, key=lambda s: s["receita_em_risco"])
            principais_problemas.append(
                f"O segmento '{seg_maior_risco['tipo_estabelecimento']}' concentra a maior "
                f"exposição financeira atual, com R$ {seg_maior_risco['receita_em_risco']:,.2f} "
                f"de receita estimada em risco ({seg_maior_risco['clientes_em_risco']} clientes em atraso)."
            )

        if top_prioritarios:
            lider = top_prioritarios[0]
            acoes_recomendadas.append(
                f"Iniciar contatos imediatos pelos {len(top_prioritarios)} clientes no topo do ranking, "
                f"começando por '{lider['nome_fantasia']}' ({lider['cidade']}), que está em "
                f"{lider['classificacao_risco']} com R$ {lider['receita_em_risco']:,.2f} em risco."
            )
        if total_oportunidades_cross_sell > 0:
            acoes_recomendadas.append(
                f"Explorar {total_oportunidades_cross_sell} oportunidades de cross-sell mapeadas "
                f"em {clientes_com_cross_sell} clientes, com potencial incremental estimado de "
                f"R$ {potencial_cross_sell_total:,.2f} por ciclo de pedido."
            )
        if clientes_dados_insuficientes > 0:
            acoes_recomendadas.append(
                f"Realizar acompanhamento de onboarding junto aos {clientes_dados_insuficientes} "
                f"clientes com histórico inicial (0 ou 1 pedido) para garantir a recorrência."
            )

    texto_executivo = " ".join(principais_problemas + acoes_recomendadas)

    return {
        "data_referencia": ref_date_str,
        "total_clientes_analisados": total_clientes,
        "clientes_recorrentes_saudaveis": clientes_recorrentes,
        "clientes_em_atencao": clientes_atencao,
        "clientes_em_risco_moderado": clientes_risco_moderado,
        "clientes_em_alto_risco": clientes_alto_risco,
        "clientes_com_dados_insuficientes": clientes_dados_insuficientes,
        "total_clientes_em_risco": clientes_em_risco_total,
        "total_clientes_risco_critico": clientes_risco_critico,
        "taxa_clientes_em_risco_pct": taxa_clientes_em_risco,
        "total_pedidos_concluidos": total_pedidos_concluidos,
        "ticket_medio_geral": ticket_medio_geral,
        "receita_historica_total": receita_historica_total,
        "receita_historica_clientes_em_risco": receita_historica_clientes_em_risco_total,
        "receita_mensal_estimada_total": receita_mensal_estimada_total,
        "receita_estimada_em_risco": receita_em_risco_total,
        "quantidade_oportunidades_cross_sell": total_oportunidades_cross_sell,
        "clientes_com_oportunidade_cross_sell": clientes_com_cross_sell,
        "potencial_incremental_cross_sell_pedido": potencial_cross_sell_total,
        "distribuicao_status_risco": contagem_status,
        "receita_por_segmento": resumo_por_segmento,
        "receita_por_cidade": resumo_por_cidade,
        "clientes_prioritarios_contato": top_prioritarios,
        "principais_problemas_identificados": principais_problemas,
        "acoes_comerciais_recomendadas": acoes_recomendadas,
        "relatorio_textual_executivo": texto_executivo,
    }


def generate_executive_summary(
    db_path: Optional[Path | str] = None,
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
    top_n_priority: int = 5,
) -> dict[str, Any]:
    """
    Executa toda a cadeia analítica sobre o banco SQLite e retorna o Resumo Executivo.
    """
    prioritized = analyze_and_prioritize_all_customers(
        db_path=db_path,
        reference_date=reference_date,
    )
    return build_executive_summary_from_records(
        prioritized_customers=prioritized,
        reference_date=reference_date,
        top_n_priority=top_n_priority,
    )
