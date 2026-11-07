"""
Módulo de Identificação de Oportunidades de Cross-Sell (`analytics/cross_sell.py`).

Analisa o histórico de itens comprados por cada estabelecimento em comparação
com o benchmark de estabelecimentos do mesmo segmento (`tipo_estabelecimento`).

Lógica Comercial e Regras de Negócio:
1. Taxa de Penetração no Segmento:
   Para cada segmento (ex.: `'Padaria & Confeitaria'`) e cada produto do catálogo,
   calculamos:
       taxa_penetracao = clientes_do_segmento_que_compram_produto / total_clientes_ativos_no_segmento
   (Um cliente é considerado comprador de um produto se já o adquiriu em pelo
   menos 1 pedido concluído; recomendações são feitas apenas para produtos com
   0 compras históricas naquele cliente).
2. Filtro de Amostra Mínima:
   Para evitar recomendações espúrias em segmentos com poucos clientes, exigimos
   que o segmento possua pelo menos `min_clientes_segmento` clientes ativos e que
   o produto seja comprado por pelo menos `min_clientes_compradores` estabelecimentos
   daquele segmento.
3. Critério de Recomendação para um Cliente:
   - O produto tem penetração >= `min_taxa_penetracao` (padrão 25%) no segmento do cliente;
   - O cliente NUNCA comprou esse produto (`pedidos_com_produto == 0`);
   - Calculamos o `potencial_estimado_por_pedido` com base na média de gasto por
     pedido daquele produto entre os pares do mesmo segmento.

Nota Metodológica:
- A afinidade por segmento reflete co-ocorrência/popularidade comercial entre
  estabelecimentos semelhantes, não implicando relação de causalidade.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from services.customer_service import get_all_customers
from services.order_service import get_all_products, get_order_items_enriched


@dataclass(frozen=True)
class CrossSellConfig:
    """Parâmetros configuráveis do motor de recomendação de Cross-Sell."""
    min_taxa_penetracao: float = 0.25
    min_clientes_segmento: int = 3
    min_clientes_compradores: int = 2
    max_recomendacoes_por_cliente: int = 4


DEFAULT_CROSS_SELL_CONFIG = CrossSellConfig()


def calculate_segment_product_benchmarks(
    customers: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Calcula a penetração e o gasto médio por pedido de cada produto dentro de
    cada segmento de estabelecimento (`tipo_estabelecimento`).

    Retorna um dicionário `{segmento: [lista_de_metricas_por_produto_ordenada]}`.
    """
    produtos_map = {int(p["id"]): p for p in products}

    # Identifica clientes com pelo menos 1 pedido concluído em cada segmento
    clientes_ativos_por_seg: dict[str, set[int]] = {}
    segmento_do_cliente: dict[int, str] = {}
    for c in customers:
        cid = int(c["id"])
        seg = str(c["tipo_estabelecimento"])
        segmento_do_cliente[cid] = seg
        if seg not in clientes_ativos_por_seg:
            clientes_ativos_por_seg[seg] = set()

    # Mapeia compras por (segmento, produto_id)
    compradores_por_seg_prod: dict[tuple[str, int], set[int]] = {}
    pedidos_por_seg_prod: dict[tuple[str, int], set[int]] = {}
    receita_por_seg_prod: dict[tuple[str, int], float] = {}
    qtd_unidades_por_seg_prod: dict[tuple[str, int], int] = {}

    for item in order_items:
        if item.get("status_pedido", "Concluído") != "Concluído":
            continue
        cid = int(item["cliente_id"])
        pid = int(item["produto_id"])
        order_id = int(item["pedido_id"])
        seg = str(item.get("tipo_estabelecimento") or segmento_do_cliente.get(cid, ""))
        if not seg:
            continue

        clientes_ativos_por_seg.setdefault(seg, set()).add(cid)

        key = (seg, pid)
        compradores_por_seg_prod.setdefault(key, set()).add(cid)
        pedidos_por_seg_prod.setdefault(key, set()).add(order_id)
        subtotal = float(item.get("subtotal_item") or (float(item["quantidade"]) * float(item["preco_praticado"])))
        receita_por_seg_prod[key] = receita_por_seg_prod.get(key, 0.0) + subtotal
        qtd_unidades_por_seg_prod[key] = qtd_unidades_por_seg_prod.get(key, 0) + int(item["quantidade"])

    benchmarks_por_segmento: dict[str, list[dict[str, Any]]] = {}

    for seg, clientes_ativos in clientes_ativos_por_seg.items():
        total_ativos_seg = len(clientes_ativos)
        lista_prods_seg: list[dict[str, Any]] = []

        if total_ativos_seg == 0:
            benchmarks_por_segmento[seg] = []
            continue

        for pid, prod_info in produtos_map.items():
            key = (seg, pid)
            compradores = compradores_por_seg_prod.get(key, set())
            qtd_compradores = len(compradores)
            if qtd_compradores == 0:
                continue

            pedidos_prod = pedidos_por_seg_prod.get(key, set())
            qtd_pedidos_prod = len(pedidos_prod)
            receita_total_prod = round(receita_por_seg_prod.get(key, 0.0), 2)
            unidades_totais = qtd_unidades_por_seg_prod.get(key, 0)

            taxa_penetracao = round(qtd_compradores / total_ativos_seg, 4)
            gasto_medio_por_pedido = (
                round(receita_total_prod / qtd_pedidos_prod, 2)
                if qtd_pedidos_prod > 0
                else float(prod_info["preco_unitario"])
            )

            lista_prods_seg.append(
                {
                    "segmento": seg,
                    "produto_id": pid,
                    "produto_nome": prod_info["nome"],
                    "categoria": prod_info["categoria"],
                    "preco_unitario": float(prod_info["preco_unitario"]),
                    "clientes_ativos_segmento": total_ativos_seg,
                    "clientes_compradores": qtd_compradores,
                    "taxa_penetracao_segmento": taxa_penetracao,
                    "quantidade_pedidos_segmento": qtd_pedidos_prod,
                    "unidades_vendidas_segmento": unidades_totais,
                    "receita_total_segmento": receita_total_prod,
                    "potencial_estimado_por_pedido": gasto_medio_por_pedido,
                }
            )

        # Ordena por penetração (mais populares primeiro) e depois por receita no segmento
        lista_prods_seg.sort(
            key=lambda x: (x["taxa_penetracao_segmento"], x["receita_total_segmento"]),
            reverse=True,
        )
        benchmarks_por_segmento[seg] = lista_prods_seg

    return benchmarks_por_segmento


def identify_customer_cross_sell_opportunities(
    customer: dict[str, Any],
    customer_order_items: list[dict[str, Any]],
    segment_benchmarks: list[dict[str, Any]],
    config: CrossSellConfig = DEFAULT_CROSS_SELL_CONFIG,
) -> list[dict[str, Any]]:
    """
    Identifica produtos relevantes do segmento que o cliente ainda NÃO comprou.

    Regras:
    - Clientes sem nenhum pedido concluído (`customer_order_items` vazio) não
      recebem recomendação de cross-sell (precisam primeiro da 1ª venda/ativação).
    - Produtos que o cliente já comprou são excluídos das sugestões de novos SKUs.
    """
    completed_items = [
        i for i in customer_order_items if i.get("status_pedido", "Concluído") == "Concluído"
    ]
    if not completed_items:
        return []

    produtos_ja_comprados = {int(i["produto_id"]) for i in completed_items}
    segmento = str(customer.get("tipo_estabelecimento", ""))

    oportunidades: list[dict[str, Any]] = []

    for bench in segment_benchmarks:
        if bench["clientes_ativos_segmento"] < config.min_clientes_segmento:
            continue
        if bench["clientes_compradores"] < config.min_clientes_compradores:
            continue
        if bench["taxa_penetracao_segmento"] < config.min_taxa_penetracao:
            continue

        pid = int(bench["produto_id"])
        if pid in produtos_ja_comprados:
            continue

        pct_formatado = int(round(bench["taxa_penetracao_segmento"] * 100))
        potencial_pedido = bench["potencial_estimado_por_pedido"]

        justificativa = (
            f"Adquirido por {pct_formatado}% dos estabelecimentos do segmento "
            f"'{segmento}' ({bench['clientes_compradores']} de {bench['clientes_ativos_segmento']} clientes), "
            f"mas ainda ausente no mix deste cliente. "
            f"Potencial estimado de R$ {potencial_pedido:.2f} por pedido."
        )

        oportunidades.append(
            {
                "cliente_id": int(customer["id"]),
                "nome_fantasia": customer.get("nome_fantasia", ""),
                "tipo_estabelecimento": segmento,
                "produto_id": pid,
                "produto_sugerido": bench["produto_nome"],
                "categoria_produto": bench["categoria"],
                "preco_unitario_catalogo": bench["preco_unitario"],
                "taxa_penetracao_segmento": bench["taxa_penetracao_segmento"],
                "clientes_compradores_segmento": bench["clientes_compradores"],
                "total_clientes_segmento": bench["clientes_ativos_segmento"],
                "potencial_oportunidade_pedido": potencial_pedido,
                "justificativa": justificativa,
            }
        )

    oportunidades.sort(
        key=lambda x: (x["taxa_penetracao_segmento"], x["potencial_oportunidade_pedido"]),
        reverse=True,
    )
    return oportunidades[: config.max_recomendacoes_por_cliente]


def analyze_all_customers_cross_sell(
    db_path: Optional[Path | str] = None,
    config: CrossSellConfig = DEFAULT_CROSS_SELL_CONFIG,
) -> dict[int, list[dict[str, Any]]]:
    """
    Executa a análise de oportunidades de cross-sell para todos os clientes do banco.
    Retorna um dicionário `{cliente_id: [lista_de_oportunidades]}`.
    """
    customers = get_all_customers(db_path=db_path)
    products = get_all_products(db_path=db_path)
    all_items = get_order_items_enriched(db_path=db_path, only_completed=True)

    benchmarks = calculate_segment_product_benchmarks(
        customers=customers,
        order_items=all_items,
        products=products,
    )

    items_by_customer: dict[int, list[dict[str, Any]]] = {}
    for item in all_items:
        cid = int(item["cliente_id"])
        items_by_customer.setdefault(cid, []).append(item)

    result: dict[int, list[dict[str, Any]]] = {}
    for customer in customers:
        cid = int(customer["id"])
        seg = str(customer["tipo_estabelecimento"])
        cust_items = items_by_customer.get(cid, [])
        seg_bench = benchmarks.get(seg, [])
        result[cid] = identify_customer_cross_sell_opportunities(
            customer=customer,
            customer_order_items=cust_items,
            segment_benchmarks=seg_bench,
            config=config,
        )

    return result
