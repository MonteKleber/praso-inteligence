"""
Módulo de Classificação Heurística de Risco de Churn (`analytics/churn.py`).

Classifica cada cliente de acordo com a relação entre o tempo transcorrido desde
a última compra e o seu ciclo mediano habitual de recompra:

    indice_atraso = dias_desde_ultima_compra / intervalo_mediano_dias

Importante (Nota Metodológica):
- Esta classificação é um INDICADOR HEURÍSTICO DE RISCO COMERCIAL para apoio à
  tomada de decisão da equipe de vendas, e NÃO um modelo preditivo probabilístico.
- Clientes sem pedidos ou com apenas 1 pedido (ou sem intervalo calculável)
  recebem a classificação `'Dados insuficientes'` e NUNCA são rotulados
  automaticamente como churn.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

from analytics import DEFAULT_REFERENCE_DATE
from analytics.repurchase import analyze_all_customers_repurchase, analyze_customer_repurchase


# Rótulos oficiais de classificação heurística de risco
STATUS_SAUDAVEL = "Saudável"
STATUS_ATENCAO = "Atenção"
STATUS_RISCO_MODERADO = "Risco moderado"
STATUS_ALTO_RISCO = "Alto risco"
STATUS_DADOS_INSUFICIENTES = "Dados insuficientes"


@dataclass(frozen=True)
class ChurnThresholds:
    """
    Limites configuráveis da razão `dias_desde_ultima_compra / intervalo_mediano_dias`.

    Padrão:
    - Saudável (Em dia) : razão <= 1.15 (até 15% de tolerância acima do ciclo mediano)
    - Atenção           : 1.15 < razão <= 1.50 (início de desaceleração ou atraso leve)
    - Risco moderado    : 1.50 < razão <= 2.50 (entre 1,5 e 2,5 ciclos sem comprar)
    - Alto risco        : razão > 2.50 (mais de 2,5 ciclos sem comprar)
    """
    limite_saudavel: float = 1.15
    limite_atencao: float = 1.50
    limite_risco_moderado: float = 2.50
    min_pedidos_para_risco: int = 2


DEFAULT_CHURN_THRESHOLDS = ChurnThresholds()


def detect_interval_trend(intervals: list[int]) -> str:
    """
    Analisa se os intervalos entre compras do cliente estão aumentando
    (sinal de desaceleração recente), estáveis ou reduzindo.
    """
    if len(intervals) < 2:
        return "Sem histórico suficiente"

    # Compara o último intervalo observado com a mediana dos intervalos anteriores
    ultimo_intervalo = intervals[-1]
    anteriores = intervals[:-1]
    media_anteriores = sum(anteriores) / len(anteriores)

    if media_anteriores <= 0:
        return "Estável"

    variacao = ultimo_intervalo / media_anteriores
    if variacao >= 1.25:
        return "Desacelerando (intervalo crescente)"
    if variacao <= 0.80:
        return "Acelerando (intervalo decrescente)"
    return "Estável"


def classify_customer_churn_risk(
    repurchase_metrics: dict[str, Any],
    thresholds: ChurnThresholds = DEFAULT_CHURN_THRESHOLDS,
) -> dict[str, Any]:
    """
    Recebe o dicionário calculado por `analyze_customer_repurchase` e adiciona
    os indicadores heurísticos de risco de churn:
    - `indice_atraso`: razão `dias_desde_ultima_compra / intervalo_mediano_dias`
    - `dias_atraso_ciclo`: dias que ultrapassaram o ciclo mediano (mínimo 0)
    - `classificacao_risco`: `'Saudável'`, `'Atenção'`, `'Risco moderado'`,
      `'Alto risco'` ou `'Dados insuficientes'`
    - `em_risco_comercial`: booleano (`True` para Atenção, Risco moderado ou Alto risco)
    - `tendencia_intervalo`: diagnóstico se o ritmo recente está desacelerando
    - `explicacao_risco`: justificativa textual clara para o vendedor
    """
    qtd_pedidos = int(repurchase_metrics.get("quantidade_pedidos") or 0)
    dias_sem_comprar = repurchase_metrics.get("dias_desde_ultima_compra")
    ciclo_mediano = repurchase_metrics.get("intervalo_mediano_dias")
    intervals = repurchase_metrics.get("intervalos_dias") or []

    tendencia = detect_interval_trend(intervals)

    # Caso 1: Cliente sem pedidos ou com apenas 1 pedido (ou sem ciclo mediano válido)
    if (
        qtd_pedidos < thresholds.min_pedidos_para_risco
        or dias_sem_comprar is None
        or ciclo_mediano is None
        or ciclo_mediano <= 0
    ):
        if qtd_pedidos == 0:
            explicacao = (
                "Cliente sem pedidos concluídos no histórico. "
                "Necessita ativação comercial inicial."
            )
        else:
            explicacao = (
                f"Cliente possui apenas {qtd_pedidos} pedido(s) em data única "
                f"(há {dias_sem_comprar} dias). Dados insuficientes para estimar ciclo."
            )

        return {
            **repurchase_metrics,
            "indice_atraso": None,
            "dias_atraso_ciclo": None,
            "classificacao_risco": STATUS_DADOS_INSUFICIENTES,
            "em_risco_comercial": False,
            "tendencia_intervalo": tendencia,
            "explicacao_risco": explicacao,
        }

    # Caso 2: Cliente com histórico suficiente para comparar ciclo esperado vs. atual
    indice_atraso = round(float(dias_sem_comprar) / float(ciclo_mediano), 2)
    dias_atraso = max(0, int(round(float(dias_sem_comprar) - float(ciclo_mediano))))

    if indice_atraso <= thresholds.limite_saudavel:
        classificacao = STATUS_SAUDAVEL
        em_risco = False
        explicacao = (
            f"Comportamento saudável: última compra há {dias_sem_comprar} dias "
            f"para um ciclo mediano de {ciclo_mediano:.0f} dias (índice {indice_atraso:.2f}x)."
        )
    elif indice_atraso <= thresholds.limite_atencao:
        classificacao = STATUS_ATENCAO
        em_risco = True
        explicacao = (
            f"Sinal de atenção: {dias_sem_comprar} dias sem comprar vs. ciclo mediano "
            f"de {ciclo_mediano:.0f} dias ({dias_atraso} dias além do esperado; índice {indice_atraso:.2f}x)."
        )
    elif indice_atraso <= thresholds.limite_risco_moderado:
        classificacao = STATUS_RISCO_MODERADO
        em_risco = True
        explicacao = (
            f"Risco moderado: ultrapassou {indice_atraso:.2f}x o seu ciclo habitual "
            f"de {ciclo_mediano:.0f} dias ({dias_sem_comprar} dias sem comprar)."
        )
    else:
        classificacao = STATUS_ALTO_RISCO
        em_risco = True
        explicacao = (
            f"Alto risco de abandono: {dias_sem_comprar} dias sem comprar, equivalente "
            f"a {indice_atraso:.2f}x o seu ciclo habitual de {ciclo_mediano:.0f} dias."
        )

    return {
        **repurchase_metrics,
        "indice_atraso": indice_atraso,
        "dias_atraso_ciclo": dias_atraso,
        "classificacao_risco": classificacao,
        "em_risco_comercial": em_risco,
        "tendencia_intervalo": tendencia,
        "explicacao_risco": explicacao,
    }


def analyze_all_customers_churn(
    db_path: Optional[Path | str] = None,
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
    thresholds: ChurnThresholds = DEFAULT_CHURN_THRESHOLDS,
) -> list[dict[str, Any]]:
    """
    Executa a análise de recompra e classificação heurística de risco de churn
    para todos os clientes do banco de dados.
    """
    repurchase_list = analyze_all_customers_repurchase(
        db_path=db_path,
        reference_date=reference_date,
    )
    return [
        classify_customer_churn_risk(metrics, thresholds=thresholds)
        for metrics in repurchase_list
    ]
