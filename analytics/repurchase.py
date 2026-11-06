"""
Módulo de Análise de Recompra (`analytics/repurchase.py`).

Transforma o histórico de pedidos de um cliente B2B em indicadores de ciclo de
reposição, frequência, ticket médio e previsão heurística da próxima compra.

Regras de Negócio e Decisões Técnicas:
1. Diferenciação entre `None` (dado inexistente/não calculável) e `0` (valor zero):
   - Um cliente com 0 pedidos tem `quantidade_pedidos = 0` e `valor_total_historico = 0.0`,
     mas `intervalo_medio_dias = None`, `intervalo_mediano_dias = None` e
     `proxima_compra_estimada = None`.
   - Um cliente com apenas 1 pedido tem `quantidade_pedidos = 1`, `ticket_medio` e
     `dias_desde_ultima_compra` calculados, mas NÃO possui intervalo entre compras
     (`intervalo_medio_dias = None`, `intervalo_mediano_dias = None`,
     `proxima_compra_estimada = None`), evitando previsões artificiais.
2. Uso da Mediana como Ciclo Habitual de Referência:
   - A mediana dos intervalos (`intervalo_mediano_dias`) reduz distorções causadas
     por férias coletivas, reformas ou pedidos emergenciais no mesmo dia/semana.
3. Pedidos no mesmo dia:
   - Se um cliente emite dois pedidos na mesma data (`data_compra` idêntica), eles
     contam no faturamento e no número de pedidos, mas o intervalo entre datas de
     abastecimento é calculado sobre datas distintas de compra para não gerar um
     intervalo artificial de 0 dias caso ele tenha apenas complementado um pedido.
"""

from datetime import date, timedelta
from pathlib import Path
import statistics
from typing import Any, Optional

from analytics import DEFAULT_REFERENCE_DATE
from services.customer_service import get_all_customers
from services.order_service import get_orders_grouped_by_customer


def parse_iso_date(value: date | str) -> date:
    """Converte uma string ISO (`YYYY-MM-DD`) ou objeto `date` em `datetime.date`."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def calculate_order_intervals(order_dates: list[date | str]) -> list[int]:
    """
    Recebe uma lista de datas de compra, remove datas duplicadas no mesmo dia,
    ordena cronologicamente e retorna a lista de intervalos em dias entre
    compras consecutivas.

    Se houver menos de 2 datas distintas, retorna lista vazia `[]`.
    """
    unique_sorted_dates = sorted({parse_iso_date(d) for d in order_dates})
    if len(unique_sorted_dates) < 2:
        return []

    return [
        (unique_sorted_dates[i] - unique_sorted_dates[i - 1]).days
        for i in range(1, len(unique_sorted_dates))
    ]


def analyze_customer_repurchase(
    customer: dict[str, Any],
    orders: list[dict[str, Any]],
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
) -> dict[str, Any]:
    """
    Calcula todas as métricas de comportamento de recompra para um único cliente.

    Parâmetros:
    - `customer`: dicionário com dados cadastrais do cliente (`id`, `nome_fantasia`, etc.).
    - `orders`: lista de pedidos concluídos do cliente.
    - `reference_date`: data de referência da análise (padrão `2026-11-05`).

    Limitações documentadas da estimativa:
    - A previsão `proxima_compra_estimada` soma a mediana histórica à data da última
      compra. Ela pressupõe continuidade operacional do estabelecimento e não captura
      mudanças bruscas de cardápio ou fechamento temporário sem histórico prévio.
    """
    ref_date = parse_iso_date(reference_date)

    # Filtra apenas pedidos concluídos caso uma lista mista seja passada
    completed_orders = [
        o for o in orders if o.get("status_pedido", "Concluído") == "Concluído"
    ]
    qtd_pedidos = len(completed_orders)

    base_result: dict[str, Any] = {
        "cliente_id": customer["id"],
        "nome_fantasia": customer.get("nome_fantasia", ""),
        "tipo_estabelecimento": customer.get("tipo_estabelecimento", ""),
        "cidade": customer.get("cidade", ""),
        "responsavel_comercial": customer.get("responsavel_comercial", ""),
        "data_cadastro": customer.get("data_cadastro"),
        "quantidade_pedidos": qtd_pedidos,
        "primeira_compra": None,
        "ultima_compra": None,
        "dias_desde_ultima_compra": None,
        "intervalos_dias": [],
        "intervalo_medio_dias": None,
        "intervalo_mediano_dias": None,
        "desvio_padrao_intervalo_dias": None,
        "valor_total_historico": 0.0,
        "ticket_medio": None,
        "proxima_compra_estimada": None,
        "dias_ate_proxima_compra": None,
        "historico_suficiente_para_ciclo": False,
    }

    if qtd_pedidos == 0:
        return base_result

    # Ordena datas e calcula totais financeiros
    sorted_orders = sorted(completed_orders, key=lambda o: str(o["data_compra"]))
    order_dates = [parse_iso_date(o["data_compra"]) for o in sorted_orders]

    first_date = order_dates[0]
    last_date = order_dates[-1]
    days_since_last = (ref_date - last_date).days

    valor_total = round(sum(float(o["valor_total"]) for o in sorted_orders), 2)
    ticket_medio = round(valor_total / qtd_pedidos, 2)

    intervals = calculate_order_intervals(order_dates)

    intervalo_medio: Optional[float] = None
    intervalo_mediano: Optional[float] = None
    desvio_padrao: Optional[float] = None
    proxima_compra: Optional[str] = None
    dias_ate_proxima: Optional[int] = None
    historico_suficiente = len(intervals) >= 1

    if historico_suficiente:
        intervalo_medio = round(statistics.mean(intervals), 2)
        intervalo_mediano = round(float(statistics.median(intervals)), 2)
        # Desvio padrão amostral requer pelo menos 2 intervalos (3 compras em datas distintas)
        if len(intervals) >= 2:
            desvio_padrao = round(statistics.stdev(intervals), 2)
        else:
            desvio_padrao = 0.0

        ciclo_dias_int = max(1, int(round(intervalo_mediano)))
        estimated_next_date = last_date + timedelta(days=ciclo_dias_int)
        proxima_compra = estimated_next_date.isoformat()
        dias_ate_proxima = (estimated_next_date - ref_date).days

    base_result.update(
        {
            "primeira_compra": first_date.isoformat(),
            "ultima_compra": last_date.isoformat(),
            "dias_desde_ultima_compra": days_since_last,
            "intervalos_dias": intervals,
            "intervalo_medio_dias": intervalo_medio,
            "intervalo_mediano_dias": intervalo_mediano,
            "desvio_padrao_intervalo_dias": desvio_padrao,
            "valor_total_historico": valor_total,
            "ticket_medio": ticket_medio,
            "proxima_compra_estimada": proxima_compra,
            "dias_ate_proxima_compra": dias_ate_proxima,
            "historico_suficiente_para_ciclo": historico_suficiente,
        }
    )
    # Remove chave com typo inicial se existir
    base_result.pop("historico_suficiente_Para_ciclo", None)
    return base_result


def analyze_all_customers_repurchase(
    db_path: Optional[Path | str] = None,
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
) -> list[dict[str, Any]]:
    """
    Executa a análise de recompra para todos os clientes cadastrados no banco.
    """
    customers = get_all_customers(db_path=db_path)
    orders_by_customer = get_orders_grouped_by_customer(db_path=db_path, only_completed=True)

    results: list[dict[str, Any]] = []
    for customer in customers:
        cid = int(customer["id"])
        cust_orders = orders_by_customer.get(cid, [])
        metrics = analyze_customer_repurchase(
            customer=customer,
            orders=cust_orders,
            reference_date=reference_date,
        )
        results.append(metrics)

    return results
