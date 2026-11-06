"""
Módulo de Análise de Receita e Receita em Risco (`analytics/revenue.py`).

Calcula e separa de forma transparente três conceitos financeiros distintos:
1. `receita_historica`: Faturamento real já concluído e registrado no banco.
2. `receita_potencial_mensal`: Estimativa de quanto o cliente compra em uma
   janela de 30 dias mantendo seu ticket médio e seu intervalo mediano habitual:
       receita_potencial_mensal = ticket_medio * (30 / intervalo_mediano_dias)
   (Para clientes com apenas 1 pedido sem ciclo calculável, a receita potencial
   de recompra imediata equivale a 1 ticket médio, mas a receita mensal recorrente
   fica como `None` ou igual a 1 pedido/mês documentado).
3. `receita_em_risco`: Parcela da receita potencial mensal que está exposta ao
   risco de não se concretizar caso o cliente em atraso não retorne:
   - Saudável / Dados insuficientes : 0% (R$ 0,00 em risco)
   - Atenção                        : 30% da receita potencial mensal
   - Risco moderado                 : 70% da receita potencial mensal
   - Alto risco                     : 100% da receita potencial mensal

Nota Importante:
- Receita potencial e receita em risco são ESTIMATIVAS GERENCIAIS para priorização
  da força de vendas, não representando prejuízo contábil confirmado nem
  faturamento garantido.
- Nenhuma consulta deste módulo faz JOIN direto com `itens_pedido` ao somar
  `pedidos.valor_total`, garantindo zero duplicação de faturamento.
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
    ChurnThresholds,
     DEFAULT_CHURN_THRESHOLDS,
    analyze_all_customers_churn,
)


@dataclass(frozen=True)
class RevenueRiskWeights:
    """
    Pesos configuráveis de exposição financeira para o cálculo da Receita em Risco
    sobre a Receita Potencial Mensal (janela de 30 dias).
    """
    peso_saudavel: float = 0.00
    peso_dados_insuficientes: float = 0.00
    peso_atencao: float = 0.30
    peso_risco_moderado: float = 0.70
    peso_alto_risco: float = 1.00
    janela_dias_projecao: float = 30.0


DEFAULT_REVENUE_WEIGHTS = RevenueRiskWeights()


def calculate_customer_revenue_metrics(
    churn_metrics: dict[str, Any],
    weights: RevenueRiskWeights = DEFAULT_REVENUE_WEIGHTS,
) -> dict[str, Any]:
    """
    Enriquece o dicionário de métricas de um cliente (vindo de `churn.py`) com:
    - `receita_historica`: soma dos pedidos concluídos
    - `receita_media_por_pedido`: ticket médio
    - `receita_mensal_estimada`: projeção para 30 dias baseada no ciclo mediano
    - `receita_potencial_recompra`: valor esperado do próximo pedido (1 ticket médio)
    - `fator_exposicao_risco`: percentual aplicado conforme a faixa de risco
    - `receita_em_risco`: valor estimado em risco na janela de 30 dias
    """
    qtd_pedidos = int(churn_metrics.get("quantidade_pedidos") or 0)
    receita_historica = round(float(churn_metrics.get("valor_total_historico") or 0.0), 2)
    ticket_medio = churn_metrics.get("ticket_medio")
    ciclo_mediano = churn_metrics.get("intervalo_mediano_dias")
    classificacao = churn_metrics.get("classificacao_risco", STATUS_DADOS_INSUFICIENTES)

    if qtd_pedidos == 0 or ticket_medio is None:
        return {
            **churn_metrics,
            "receita_historica": 0.0,
            "receita_historica_cliente_em_risco": 0.0,
            "receita_media_por_pedido": None,
            "receita_mensal_estimada": None,
            "receita_potencial_recompra": 0.0,
            "fator_exposicao_risco": 0.0,
            "receita_em_risco": 0.0,
        }

    ticket_float = round(float(ticket_medio), 2)
    potencial_proximo_pedido = ticket_float
    em_risco_flag = bool(churn_metrics.get("em_risco_comercial", False))
    receita_hist_em_risco = receita_historica if em_risco_flag else 0.0

    # Se possui ciclo mediano calculado, projeta a receita para uma janela de 30 dias
    if ciclo_mediano is not None and float(ciclo_mediano) > 0:
        pedidos_esperados_mes = weights.janela_dias_projecao / float(ciclo_mediano)
        receita_mensal = round(ticket_float * pedidos_esperados_mes, 2)
    else:
        # Cliente com apenas 1 pedido: ainda sem frequência mensal definida
        receita_mensal = None

    mapa_pesos = {
        STATUS_SAUDAVEL: weights.peso_saudavel,
        STATUS_DADOS_INSUFICIENTES: weights.peso_dados_insuficientes,
        STATUS_ATENCAO: weights.peso_atencao,
        STATUS_RISCO_MODERADO: weights.peso_risco_moderado,
        STATUS_ALTO_RISCO: weights.peso_alto_risco,
    }
    fator_risco = mapa_pesos.get(classificacao, 0.0)

    if receita_mensal is not None and fator_risco > 0:
        receita_em_risco = round(receita_mensal * fator_risco, 2)
    else:
        receita_em_risco = 0.0

    return {
        **churn_metrics,
        "receita_historica": receita_historica,
        "receita_historica_cliente_em_risco": receita_hist_em_risco,
        "receita_media_por_pedido": ticket_float,
        "receita_mensal_estimada": receita_mensal,
        "receita_potencial_recompra": potencial_proximo_pedido,
        "fator_exposicao_risco": fator_risco,
        "receita_em_risco": receita_em_risco,
    }


def analyze_all_customers_revenue(
    db_path: Optional[Path | str] = None,
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
    churn_thresholds: ChurnThresholds = DEFAULT_CHURN_THRESHOLDS,
    revenue_weights: RevenueRiskWeights = DEFAULT_REVENUE_WEIGHTS,
) -> list[dict[str, Any]]:
    """
    Executa a cadeia de análise (Recompra -> Churn -> Receita) para todos os clientes.
    """
    churn_list = analyze_all_customers_churn(
        db_path=db_path,
        reference_date=reference_date,
        thresholds=churn_thresholds,
    )
    return [
        calculate_customer_revenue_metrics(item, weights=revenue_weights)
        for item in churn_list
    ]


def summarize_revenue_by_dimension(
    customer_revenue_list: list[dict[str, Any]],
    dimension_key: str,
) -> list[dict[str, Any]]:
    """
    Agrega receita histórica, receita potencial mensal, receita em risco e
    quantidade de clientes por uma dimensão cadastral (`'cidade'`,
    `'tipo_estabelecimento'`, `'classificacao_risco'` ou `'responsavel_comercial'`).
    """
    grouped: dict[str, dict[str, Any]] = {}

    for item in customer_revenue_list:
        dim_val = str(item.get(dimension_key) or "Não informado")
        if dim_val not in grouped:
            grouped[dim_val] = {
                dimension_key: dim_val,
                "total_clientes": 0,
                "clientes_em_risco": 0,
                "quantidade_pedidos": 0,
                "receita_historica": 0.0,
                "receita_historica_clientes_em_risco": 0.0,
                "receita_mensal_estimada": 0.0,
                "receita_em_risco": 0.0,
            }

        grp = grouped[dim_val]
        grp["total_clientes"] += 1
        if item.get("em_risco_comercial"):
            grp["clientes_em_risco"] += 1
            grp["receita_historica_clientes_em_risco"] = round(
                grp["receita_historica_clientes_em_risco"]
                + float(item.get("receita_historica") or 0.0),
                2,
            )
        grp["quantidade_pedidos"] += int(item.get("quantidade_pedidos") or 0)
        grp["receita_historica"] = round(
            grp["receita_historica"] + float(item.get("receita_historica") or 0.0), 2
        )
        grp["receita_mensal_estimada"] = round(
            grp["receita_mensal_estimada"] + float(item.get("receita_mensal_estimada") or 0.0),
            2,
        )
        grp["receita_em_risco"] = round(
            grp["receita_em_risco"] + float(item.get("receita_em_risco") or 0.0), 2
        )

    result = list(grouped.values())
    for grp in result:
        qtd_ped = grp["quantidade_pedidos"]
        grp["ticket_medio_grupo"] = (
            round(grp["receita_historica"] / qtd_ped, 2) if qtd_ped > 0 else 0.0
        )

    result.sort(key=lambda x: x["receita_historica"], reverse=True)
    return result
