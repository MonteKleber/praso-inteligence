"""
Módulo de Priorização Comercial (`analytics/prioritization.py`).

Calcula um Score de Prioridade Comercial (0 a 100) combinando múltiplos fatores
de negócio para que a equipe de vendas saiba exatamente qual cliente contatar
primeiro e qual abordagem adotar.

Pilares da Pontuação (Pesos Configuráveis, soma = 100 pontos):
- Nota Metodológica: Os pesos abaixo (45/25/20/10) são PARÂMETROS HEURÍSTICOS
  INICIAIS definidos por regra de negócio, ainda não calibrados empiricamente
  com dados comerciais reais de conversão/recuperação.
1. Urgência / Risco de Churn (até 45 pontos):
   Baseado na faixa de risco (`Alto risco`=100%, `Risco moderado`=75%,
   `Atenção`=45%, `Dados insuficientes`=25%, `Saudável`=10%) combinado com a
   intensidade do índice de atraso (`dias_desde_ultima_compra / intervalo_mediano_dias`).
2. Valor por Pedido / Ticket Médio (até 25 pontos):
   Normalizado em relação ao maior ticket médio da carteira analisada. Evita que
   clientes de altíssimo ticket sejam esquecidos atrás de clientes pequenos.
3. Receita Histórica / Potencial de Recompra (até 20 pontos):
   Normalizado pela receita potencial mensal e receita histórica acumulada.
4. Potencial de Expansão / Cross-Sell (até 10 pontos):
   Valor financeiro estimado das oportunidades de cross-sell identificadas para
   o cliente.

Critério Determinístico de Desempate (Tie-breaking):
Quando dois clientes obtêm exatamente o mesmo `score_prioridade`:
1º Maior `receita_em_risco`
2º Maior `ticket_medio`
3º Maior `dias_desde_ultima_compra`
4º Menor `cliente_id` (ordem cadastral estável)
"""

from dataclasses import dataclass
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
from analytics.cross_sell import analyze_all_customers_cross_sell
from analytics.revenue import analyze_all_customers_revenue


@dataclass(frozen=True)
class PrioritizationWeights:
    """Pesos configuráveis do Score de Prioridade Comercial (soma = 100.0)."""
    peso_risco_atraso: float = 45.0
    peso_ticket_medio: float = 25.0
    peso_receita_potencial: float = 20.0
    peso_cross_sell: float = 10.0


DEFAULT_PRIORITIZATION_WEIGHTS = PrioritizationWeights()


def _calculate_risk_component_score(metrics: dict[str, Any]) -> float:
    """Retorna uma nota de 0.0 a 1.0 referente ao risco de churn e atraso."""
    classificacao = metrics.get("classificacao_risco", STATUS_DADOS_INSUFICIENTES)
    indice_atraso = float(metrics.get("indice_atraso") or 0.0)

    base_map = {
        STATUS_ALTO_RISCO: 0.85,
        STATUS_RISCO_MODERADO: 0.65,
        STATUS_ATENCAO: 0.40,
        STATUS_DADOS_INSUFICIENTES: 0.25,
        STATUS_SAUDAVEL: 0.05,
    }
    base = base_map.get(classificacao, 0.10)

    # Bônus proporcional ao índice de atraso (limitado a +0.15)
    bonus_atraso = min(0.15, max(0.0, (indice_atraso - 1.0) * 0.05))
    return min(1.0, base + bonus_atraso)


def _build_commercial_recommendation(
    metrics: dict[str, Any],
    cross_sell_opps: list[dict[str, Any]],
) -> tuple[str, str]:
    """
    Gera a recomendação de ação comercial e a justificativa da prioridade
    de forma interpretável para o consultor de vendas.
    """
    classificacao = metrics.get("classificacao_risco", STATUS_DADOS_INSUFICIENTES)
    dias_sem = metrics.get("dias_desde_ultima_compra")
    ciclo = metrics.get("intervalo_mediano_dias")
    ticket = float(metrics.get("ticket_medio") or 0.0)
    rec_risco = float(metrics.get("receita_em_risco") or 0.0)
    qtd_pedidos = int(metrics.get("quantidade_pedidos") or 0)

    top_prod_sugerido = (
        cross_sell_opps[0]["produto_sugerido"] if cross_sell_opps else None
    )

    if classificacao == STATUS_ALTO_RISCO:
        acao = "Ação urgente de recuperação (reativação comercial)"
        justificativa = (
            f"Cliente em Alto Risco ({dias_sem} dias sem comprar vs. ciclo de {ciclo:.0f} dias), "
            f"com ticket médio de R$ {ticket:.2f} e R$ {rec_risco:.2f} de receita mensal em risco."
        )
    elif classificacao == STATUS_RISCO_MODERADO:
        acao = "Contato prioritário de retenção e reposição de estoque"
        justificativa = (
            f"Atraso significativo ({dias_sem} dias sem comprar vs. ciclo de {ciclo:.0f} dias) "
            f"e R$ {rec_risco:.2f} em risco."
        )
    elif classificacao == STATUS_ATENCAO:
        acao = "Contato preventivo de reposição (janela de compra ultrapassada)"
        justificativa = (
            f"Ultrapassou o ciclo habitual de {ciclo:.0f} dias (está há {dias_sem} dias sem pedido); "
            f"ticket médio de R$ {ticket:.2f}."
        )
    elif classificacao == STATUS_DADOS_INSUFICIENTES:
        if qtd_pedidos == 0:
            acao = "Realizar primeira abordagem de ativação de cadastro"
            justificativa = "Cliente cadastrado ainda sem pedidos concluídos."
        else:
            acao = "Acompanhamento de onboarding (incentivar 2ª compra)"
            justificativa = (
                f"Cliente recém-ativado com apenas 1 pedido (ticket de R$ {ticket:.2f} há {dias_sem} dias)."
            )
    else:
        if top_prod_sugerido:
            acao = f"Abordagem de expansão de mix (oferecer {top_prod_sugerido})"
            justificativa = (
                f"Cliente saudável no ciclo ({ciclo:.0f} dias) com {len(cross_sell_opps)} "
                f"oportunidade(s) de cross-sell identificada(s)."
            )
        else:
            acao = "Manutenção de relacionamento e acompanhamento do próximo ciclo"
            justificativa = (
                f"Cliente recorrente e em dia com seu ciclo de {ciclo:.0f} dias "
                f"(ticket médio R$ {ticket:.2f})."
            )

    return acao, justificativa


def generate_whatsapp_suggestion(customer_priority: dict[str, Any]) -> str:
    """
    Gera um texto personalizado e consultivo de WhatsApp baseado na situação
    atual do cliente e nas suas oportunidades de cross-sell.
    """
    nome = customer_priority.get("nome_fantasia", "Parceiro")
    responsavel = customer_priority.get("responsavel_comercial", "Consultor Praso")
    classificacao = customer_priority.get("classificacao_risco")
    dias_sem = customer_priority.get("dias_desde_ultima_compra")
    opps = customer_priority.get("oportunidades_cross_sell") or []
    sugestao_item = opps[0]["produto_sugerido"] if opps else None

    if classificacao in (STATUS_ALTO_RISCO, STATUS_RISCO_MODERADO, STATUS_ATENCAO):
        complemento_item = (
            f" Também separei uma condição especial em *{sugestao_item}*, que tem tido ótima saída no seu segmento."
            if sugestao_item
            else ""
        )
        return (
            f"Olá, equipe da *{nome}*! Tudo bem? Aqui é {responsavel}, da Praso. "
            f"Notei que já faz {dias_sem} dias desde a última reposição de vocês conosco e "
            f"gostaria de checar como está o estoque para esta semana.{complemento_item} "
            f"Posso enviar nossa sugestão de pedido atualizada?"
        )

    if sugestao_item:
        return (
            f"Olá, pessoal da *{nome}*! Aqui é {responsavel}, da Praso. "
            f"Para o próximo pedido programado de vocês, gostaria de apresentar o item "
            f"*{sugestao_item}*, muito utilizado por outros estabelecimentos do mesmo perfil. "
            f"Querem incluir algumas unidades para teste na próxima entrega?"
        )

    return (
        f"Olá, equipe da *{nome}*! Aqui é {responsavel}, da Praso. "
        f"Passando para acompanhar o estoque de vocês e confirmar se podemos "
        f"programar a próxima reposição conforme o calendário habitual. Conte comigo!"
    )


def prioritize_customers(
    revenue_metrics_list: list[dict[str, Any]],
    cross_sell_by_customer: Optional[dict[int, list[dict[str, Any]]]] = None,
    weights: PrioritizationWeights = DEFAULT_PRIORITIZATION_WEIGHTS,
) -> list[dict[str, Any]]:
    """
    Calcula a pontuação de prioridade comercial para uma lista de clientes e
    retorna a lista ordenada do mais prioritário (ranking #1) ao menos prioritário.
    """
    if not revenue_metrics_list:
        return []

    cs_map = cross_sell_by_customer or {}

    # Calcula máximos da carteira para normalização em escala 0..1 (evitando divisão por zero)
    max_ticket = max(
        (float(m.get("ticket_medio") or 0.0) for m in revenue_metrics_list),
        default=1.0,
    ) or 1.0

    max_potencial = max(
        (
            float(
                m.get("receita_mensal_estimada")
                if m.get("receita_mensal_estimada") is not None
                else (m.get("ticket_medio") or 0.0)
            )
            for m in revenue_metrics_list
        ),
        default=1.0,
    ) or 1.0

    potenciais_cs_totais: dict[int, float] = {}
    for m in revenue_metrics_list:
        cid = int(m["cliente_id"])
        opps = cs_map.get(cid, [])
        potenciais_cs_totais[cid] = round(
            sum(float(o.get("potencial_oportunidade_pedido") or 0.0) for o in opps), 2
        )

    max_cs = max(potenciais_cs_totais.values(), default=1.0) or 1.0

    scored_customers: list[dict[str, Any]] = []

    for m in revenue_metrics_list:
        cid = int(m["cliente_id"])
        opps = cs_map.get(cid, [])
        potencial_cs = potenciais_cs_totais.get(cid, 0.0)

        fator_risco = _calculate_risk_component_score(m)
        fator_ticket = min(1.0, float(m.get("ticket_medio") or 0.0) / max_ticket)
        rec_ref = float(
            m.get("receita_mensal_estimada")
            if m.get("receita_mensal_estimada") is not None
            else (m.get("ticket_medio") or 0.0)
        )
        fator_receita = min(1.0, rec_ref / max_potencial)
        fator_cs = min(1.0, potencial_cs / max_cs) if max_cs > 0 else 0.0

        nota_risco = round(fator_risco * weights.peso_risco_atraso, 2)
        nota_ticket = round(fator_ticket * weights.peso_ticket_medio, 2)
        nota_receita = round(fator_receita * weights.peso_receita_potencial, 2)
        nota_cs = round(fator_cs * weights.peso_cross_sell, 2)

        score_total = round(nota_risco + nota_ticket + nota_receita + nota_cs, 2)

        if score_total >= 65.0:
            nivel_prioridade = "Alta"
        elif score_total >= 40.0:
            nivel_prioridade = "Média"
        else:
            nivel_prioridade = "Baixa"

        acao_recomendada, justificativa = _build_commercial_recommendation(m, opps)

        enriched = {
            **m,
            "quantidade_oportunidades_cross_sell": len(opps),
            "potencial_cross_sell_pedido": potencial_cs,
            "oportunidades_cross_sell": opps,
            "nota_componente_risco": nota_risco,
            "nota_componente_ticket": nota_ticket,
            "nota_componente_receita": nota_receita,
            "nota_componente_cross_sell": nota_cs,
            "score_prioridade": score_total,
            "nivel_prioridade": nivel_prioridade,
            "acao_comercial_recomendada": acao_recomendada,
            "justificativa_prioridade": justificativa,
        }
        enriched["sugestao_mensagem_whatsapp"] = generate_whatsapp_suggestion(enriched)
        scored_customers.append(enriched)

    # Ordenação determinística com critérios claros de desempate:
    # 1. Maior score_prioridade
    # 2. Maior receita_em_risco
    # 3. Maior ticket_medio
    # 4. Maior dias_desde_ultima_compra
    # 5. Menor cliente_id (estabilidade em empates perfeitos)
    scored_customers.sort(
        key=lambda x: (
            -float(x.get("score_prioridade") or 0.0),
            -float(x.get("receita_em_risco") or 0.0),
            -float(x.get("ticket_medio") or 0.0),
            -int(x.get("dias_desde_ultima_compra") or -1),
            int(x["cliente_id"]),
        )
    )

    for rank_idx, item in enumerate(scored_customers, start=1):
        item["ranking_prioridade"] = rank_idx

    return scored_customers


def analyze_and_prioritize_all_customers(
    db_path: Optional[Path | str] = None,
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
    weights: PrioritizationWeights = DEFAULT_PRIORITIZATION_WEIGHTS,
) -> list[dict[str, Any]]:
    """
    Executa todo o pipeline analítico (Recompra -> Churn -> Receita -> Cross-Sell -> Priorização)
    para todos os clientes do banco de dados.
    """
    revenue_list = analyze_all_customers_revenue(
        db_path=db_path,
        reference_date=reference_date,
    )
    cross_sell_map = analyze_all_customers_cross_sell(db_path=db_path)
    return prioritize_customers(
        revenue_metrics_list=revenue_list,
        cross_sell_by_customer=cross_sell_map,
        weights=weights,
    )
