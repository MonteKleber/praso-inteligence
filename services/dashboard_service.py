"""
Camada de Integração do Dashboard (`services/dashboard_service.py`).

Responsável por conectar a interface Streamlit aos módulos de `services/` e
`analytics/` sem duplicar fórmulas matemáticas ou consultas SQL.

Regras arquiteturais importantes:
1. Auto-inicialização segura: Caso o banco SQLite ainda não exista ou esteja vazio,
   inicializa e popula automaticamente com `seed_database()`.
2. Preservação da integridade analítica: As métricas comportamentais de recompra,
   risco de churn e score de priorização são SEMPRE calculadas sobre o histórico
   completo até a data de referência (`2026-11-05`), nunca sendo distorcidas por
   filtros visuais de período na tela de relatórios.
3. Formatação e Exportação: Fornece funções utilitárias de filtragem, agregação
   temporal, detalhamento 360º do cliente e exportação limpa em CSV (UTF-8-SIG
   compatível com Excel em português).
"""

from datetime import date
import io
from pathlib import Path
from typing import Any, Optional
import pandas as pd

from analytics import DEFAULT_REFERENCE_DATE
from analytics.churn import (
    STATUS_ALTO_RISCO,
    STATUS_ATENCAO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_RISCO_MODERADO,
    STATUS_SAUDAVEL,
)
from analytics.cross_sell import (
    analyze_all_customers_cross_sell,
    calculate_segment_product_benchmarks,
)
from analytics.executive_summary import build_executive_summary_from_records
from analytics.prioritization import analyze_and_prioritize_all_customers
from analytics.repurchase import parse_iso_date
from analytics.revenue import summarize_revenue_by_dimension
from database.connection import DEFAULT_DB_PATH, db_session, init_db
from database.seed import DEFAULT_SEED, seed_database
from services.customer_service import get_all_customers, get_distinct_filter_options
from services.order_service import (
    get_all_products,
    get_order_items_enriched,
    get_orders,
)


def ensure_database_ready(db_path: Optional[Path | str] = None) -> Path:
    """
    Verifica se o banco SQLite existe e possui clientes cadastrados.
    Caso contrário, inicializa o schema e executa o povoamento sintético (`seed=42`).
    """
    target_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    init_db(target_path)

    with db_session(target_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM clientes;").fetchone()[0]

    if count == 0:
        seed_database(db_path=target_path, seed=DEFAULT_SEED)

    return target_path


def format_brl(value: Optional[float | int]) -> str:
    """Formata um valor numérico no padrão monetário brasileiro `R$ 1.234,56`."""
    if value is None:
        return "—"
    val = float(value)
    formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def format_date_br(iso_str: Optional[str | date]) -> str:
    """Converte uma data ISO (`YYYY-MM-DD`) para o formato brasileiro (`DD/MM/YYYY`)."""
    if not iso_str:
        return "—"
    d = parse_iso_date(iso_str)
    return d.strftime("%d/%m/%Y")


def format_int_br(value: Optional[int | float]) -> str:
    """Formata um número inteiro com separador de milhar brasileiro (`1.234`)."""
    if value is None:
        return "—"
    return f"{int(round(float(value))):,}".replace(",", ".")


def load_full_analytical_portfolio(
    db_path: Optional[Path | str] = None,
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
) -> dict[str, Any]:
    """
    Carrega e processa toda a carteira analítica a partir dos módulos oficiais:
    - `customers_prioritized`: lista de todos os clientes com métricas de recompra,
      churn, receita, cross-sell e priorização.
    - `executive_summary`: resumo executivo consolidado.
    - `filter_options`: opções únicas de cidades, segmentos, responsáveis e status.
    - `segment_benchmarks`: benchmarks de penetração de produtos por segmento.
    """
    ready_db = ensure_database_ready(db_path)
    prioritized = analyze_and_prioritize_all_customers(
        db_path=ready_db,
        reference_date=reference_date,
    )
    summary = build_executive_summary_from_records(
        prioritized_customers=prioritized,
        reference_date=reference_date,
        top_n_priority=10,
    )
    filter_opts = get_distinct_filter_options(db_path=ready_db)
    filter_opts["status_risco"] = [
        STATUS_ALTO_RISCO,
        STATUS_RISCO_MODERADO,
        STATUS_ATENCAO,
        STATUS_SAUDAVEL,
        STATUS_DADOS_INSUFICIENTES,
    ]

    customers_raw = get_all_customers(db_path=ready_db)
    products_raw = get_all_products(db_path=ready_db)
    items_raw = get_order_items_enriched(db_path=ready_db, only_completed=True)
    benchmarks = calculate_segment_product_benchmarks(
        customers=customers_raw,
        order_items=items_raw,
        products=products_raw,
    )

    return {
        "reference_date": parse_iso_date(reference_date).isoformat(),
        "customers": prioritized,
        "executive_summary": summary,
        "filter_options": filter_opts,
        "segment_benchmarks": benchmarks,
        "products": products_raw,
    }


def filter_customer_records(
    customers: list[dict[str, Any]],
    cidades: Optional[list[str]] = None,
    segmentos: Optional[list[str]] = None,
    status_risco: Optional[list[str]] = None,
    responsaveis: Optional[list[str]] = None,
    score_range: Optional[tuple[float, float]] = None,
    search_query: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Filtra a lista de clientes processados mantendo a ordenação original (ou score).
    """
    filtered: list[dict[str, Any]] = []
    q_norm = (search_query or "").strip().lower()

    for c in customers:
        if cidades and c.get("cidade") not in cidades:
            continue
        if segmentos and c.get("tipo_estabelecimento") not in segmentos:
            continue
        if status_risco and c.get("classificacao_risco") not in status_risco:
            continue
        if responsaveis and c.get("responsavel_comercial") not in responsaveis:
            continue
        if score_range is not None:
            min_s, max_s = score_range
            score_val = float(c.get("score_prioridade") or 0.0)
            if not (min_s <= score_val <= max_s):
                continue
        if q_norm:
            nome = str(c.get("nome_fantasia") or "").lower()
            cid_str = str(c.get("cliente_id") or "")
            if q_norm not in nome and q_norm not in cid_str:
                continue

        filtered.append(c)

    return filtered


def get_monthly_orders_evolution(
    db_path: Optional[Path | str] = None,
    cidades: Optional[list[str]] = None,
    segmentos: Optional[list[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Agrega a evolução mensal de receita histórica e quantidade de pedidos concluídos
    DIRETO da tabela `pedidos` + `clientes` (sem JOIN com `itens_pedido` para evitar
    qualquer duplicação de faturamento).
    """
    ready_db = ensure_database_ready(db_path)
    orders = get_orders(
        db_path=ready_db,
        only_completed=True,
        start_date=start_date,
        end_date=end_date,
    )
    customers = get_all_customers(db_path=ready_db)
    cust_map = {int(c["id"]): c for c in customers}

    monthly: dict[str, dict[str, Any]] = {}
    for o in orders:
        cid = int(o["cliente_id"])
        cust = cust_map.get(cid, {})
        if cidades and cust.get("cidade") not in cidades:
            continue
        if segmentos and cust.get("tipo_estabelecimento") not in segmentos:
            continue

        ano_mes = str(o["data_compra"])[:7]  # YYYY-MM
        if ano_mes not in monthly:
            monthly[ano_mes] = {
                "ano_mes": ano_mes,
                "quantidade_pedidos": 0,
                "receita_historica": 0.0,
                "clientes_ativos_mes": set(),
            }

        grp = monthly[ano_mes]
        grp["quantidade_pedidos"] += 1
        grp["receita_historica"] = round(grp["receita_historica"] + float(o["valor_total"]), 2)
        grp["clientes_ativos_mes"].add(cid)

    result: list[dict[str, Any]] = []
    for ano_mes in sorted(monthly.keys()):
        grp = monthly[ano_mes]
        qtd_ped = grp["quantidade_pedidos"]
        rec = grp["receita_historica"]
        result.append(
            {
                "ano_mes": ano_mes,
                "quantidade_pedidos": qtd_ped,
                "clientes_compradores": len(grp["clientes_ativos_mes"]),
                "receita_historica": rec,
                "ticket_medio_mes": round(rec / qtd_ped, 2) if qtd_ped > 0 else 0.0,
            }
        )
    return result


def get_customer_360_profile(
    cliente_id: int,
    portfolio_data: Optional[dict[str, Any]] = None,
    db_path: Optional[Path | str] = None,
    reference_date: date | str = DEFAULT_REFERENCE_DATE,
) -> Optional[dict[str, Any]]:
    """
    Retorna o dossiê 360º de um cliente específico:
    - `metrics`: dicionário completo de indicadores analíticos do cliente.
    - `orders_history`: lista de pedidos do cliente ordenada cronologicamente,
      incluindo o intervalo em dias em relação ao pedido anterior.
    - `top_products`: produtos mais comprados pelo cliente (quantidade, pedidos, valor).
    - `cross_sell_opportunities`: recomendações de cross-sell para o cliente.
    """
    ready_db = ensure_database_ready(db_path)
    data = portfolio_data or load_full_analytical_portfolio(
        db_path=ready_db, reference_date=reference_date
    )

    target_metrics: Optional[dict[str, Any]] = None
    for c in data["customers"]:
        if int(c["cliente_id"]) == int(cliente_id):
            target_metrics = c
            break

    if target_metrics is None:
        return None

    orders_all = get_orders(db_path=ready_db, cliente_id=cliente_id, only_completed=False)
    orders_completed = [o for o in orders_all if o.get("status_pedido") == "Concluído"]

    # Calcula intervalo pedido a pedido para exibir na linha do tempo e gráfico
    orders_enriched: list[dict[str, Any]] = []
    prev_date: Optional[date] = None
    for idx, o in enumerate(orders_completed, start=1):
        curr_date = parse_iso_date(o["data_compra"])
        intervalo = (curr_date - prev_date).days if prev_date is not None else None
        prev_date = curr_date
        orders_enriched.append(
            {
                **o,
                "numero_sequencial": idx,
                "intervalo_desde_anterior_dias": intervalo,
            }
        )

    items = get_order_items_enriched(
        db_path=ready_db, cliente_id=cliente_id, only_completed=True
    )
    prod_agg: dict[int, dict[str, Any]] = {}
    for item in items:
        pid = int(item["produto_id"])
        if pid not in prod_agg:
            prod_agg[pid] = {
                "produto_id": pid,
                "produto_nome": item["produto_nome"],
                "categoria": item["produto_categoria"],
                "frequencia_pedidos": set(),
                "quantidade_total": 0,
                "valor_total_comprado": 0.0,
            }
        p_entry = prod_agg[pid]
        p_entry["frequencia_pedidos"].add(int(item["pedido_id"]))
        p_entry["quantidade_total"] += int(item["quantidade"])
        p_entry["valor_total_comprado"] = round(
            p_entry["valor_total_comprado"] + float(item["subtotal_item"]), 2
        )

    top_products: list[dict[str, Any]] = []
    for p_entry in prod_agg.values():
        top_products.append(
            {
                "produto_id": p_entry["produto_id"],
                "produto_nome": p_entry["produto_nome"],
                "categoria": p_entry["categoria"],
                "pedidos_com_item": len(p_entry["frequencia_pedidos"]),
                "quantidade_total": p_entry["quantidade_total"],
                "valor_total_comprado": p_entry["valor_total_comprado"],
            }
        )
    top_products.sort(
        key=lambda x: (x["valor_total_comprado"], x["pedidos_com_item"]), reverse=True
    )

    return {
        "metrics": target_metrics,
        "orders_history": orders_enriched,
        "all_orders_including_cancelled": orders_all,
        "top_products": top_products,
        "cross_sell_opportunities": target_metrics.get("oportunidades_cross_sell", []),
    }


def flatten_cross_sell_opportunities(
    customers: list[dict[str, Any]],
    cidades: Optional[list[str]] = None,
    segmentos: Optional[list[str]] = None,
    cliente_id: Optional[int] = None,
    produto_nome: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Retorna a lista plana de todas as oportunidades de cross-sell geradas pelo
    motor analítico, enriquecida com cidade, responsável e score do cliente.
    """
    rows: list[dict[str, Any]] = []
    for c in customers:
        if cidades and c.get("cidade") not in cidades:
            continue
        if segmentos and c.get("tipo_estabelecimento") not in segmentos:
            continue
        if cliente_id is not None and int(c["cliente_id"]) != int(cliente_id):
            continue

        for opp in c.get("oportunidades_cross_sell") or []:
            if produto_nome and opp.get("produto_sugerido") != produto_nome:
                continue
            rows.append(
                {
                    "cliente_id": c["cliente_id"],
                    "nome_fantasia": c["nome_fantasia"],
                    "cidade": c["cidade"],
                    "tipo_estabelecimento": c["tipo_estabelecimento"],
                    "responsavel_comercial": c["responsavel_comercial"],
                    "classificacao_risco": c["classificacao_risco"],
                    "score_prioridade": c["score_prioridade"],
                    "produto_id": opp["produto_id"],
                    "produto_sugerido": opp["produto_sugerido"],
                    "categoria_produto": opp["categoria_produto"],
                    "taxa_penetracao_segmento": opp["taxa_penetracao_segmento"],
                    "taxa_penetracao_pct": round(opp["taxa_penetracao_segmento"] * 100, 1),
                    "potencial_oportunidade_pedido": opp["potencial_oportunidade_pedido"],
                    "justificativa": opp["justificativa"],
                }
            )

    rows.sort(
        key=lambda x: (
            x["potencial_oportunidade_pedido"],
            x["taxa_penetracao_segmento"],
            x["score_prioridade"],
        ),
        reverse=True,
    )
    return rows


def get_period_filtered_historical_summary(
    customers: list[dict[str, Any]],
    db_path: Optional[Path | str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    cidades: Optional[list[str]] = None,
    segmentos: Optional[list[str]] = None,
    status_risco: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """
    Combina os indicadores estruturais do cliente (classificação de risco, ciclo
    habitual e receita mensal estimada, que pertencem à data de referência da
    carteira) com o faturamento histórico recortado pelo período selecionado
    (`start_date` a `end_date`), sem recalcular nem distorcer a previsão de recompra.
    """
    ready_db = ensure_database_ready(db_path)
    filtered_customers = filter_customer_records(
        customers=customers,
        cidades=cidades,
        segmentos=segmentos,
        status_risco=status_risco,
    )

    orders_in_period = get_orders(
        db_path=ready_db,
        only_completed=True,
        start_date=start_date,
        end_date=end_date,
    )

    period_agg: dict[int, dict[str, float | int]] = {}
    for o in orders_in_period:
        cid = int(o["cliente_id"])
        if cid not in period_agg:
            period_agg[cid] = {"pedidos_periodo": 0, "receita_periodo": 0.0}
        period_agg[cid]["pedidos_periodo"] = int(period_agg[cid]["pedidos_periodo"]) + 1
        period_agg[cid]["receita_periodo"] = round(
            float(period_agg[cid]["receita_periodo"]) + float(o["valor_total"]), 2
        )

    result: list[dict[str, Any]] = []
    for c in filtered_customers:
        cid = int(c["cliente_id"])
        p_info = period_agg.get(cid, {"pedidos_periodo": 0, "receita_periodo": 0.0})
        qtd_p = int(p_info["pedidos_periodo"])
        rec_p = float(p_info["receita_periodo"])
        ticket_p = round(rec_p / qtd_p, 2) if qtd_p > 0 else 0.0

        result.append(
            {
                **c,
                "pedidos_no_periodo": qtd_p,
                "receita_no_periodo": rec_p,
                "ticket_medio_no_periodo": ticket_p,
            }
        )

    return result


def convert_records_to_csv_bytes(
    records: list[dict[str, Any]],
    columns_map: Optional[dict[str, str]] = None,
) -> bytes:
    """
    Converte uma lista de dicionários para bytes CSV em codificação `utf-8-sig`
    (com BOM para abrir acentos perfeitamente no Microsoft Excel).
    """
    if not records:
        df = pd.DataFrame(columns=list(columns_map.values()) if columns_map else [])
    else:
        df = pd.DataFrame(records)
        if columns_map:
            existing_cols = [col for col in columns_map.keys() if col in df.columns]
            df = df[existing_cols].rename(columns=columns_map)

    buffer = io.StringIO()
    df.to_csv(buffer, index=False, sep=";", decimal=",")
    return buffer.getvalue().encode("utf-8-sig")
