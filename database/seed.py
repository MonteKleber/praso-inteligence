"""
Gerador e povoador de dados sintéticos B2B do Praso Intelligence.

Simula 12 meses de operação de uma distribuidora atacadista atendendo 100
estabelecimentos comerciais (Padarias, Restaurantes, Hamburguerias/Lanchonetes,
Bares e Mercadinhos) nas cidades de Recife e Fortaleza.

Características principais:
1. Reprodutibilidade total via `random.Random(seed)` isolado (sem afetar estado global).
2. Separação clara entre Geração em Memória (`generate_synthetic_dataset`) e
   Persistência Transacional (`seed_database`).
3. Idempotência: executar o seed múltiplas vezes limpa e recria os registros
   sem gerar duplicações.
4. Padrões de compra realistas (recorrentes, desaceleração, risco de abandono,
   novos e sazonais) embutidos nas datas de compra para que o motor analítico
   descubra os comportamentos matematicamente.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
import random
from typing import Any, Optional

from database.connection import DEFAULT_DB_PATH, db_session, init_db

# Configuracoes padrao de referencia da simulacao (12 meses de historico)
DEFAULT_SEED = 42
REFERENCE_DATE = date(2026, 11, 5)
START_DATE = REFERENCE_DATE - timedelta(days=365)


@dataclass(frozen=True)
class ProductSpec:
    """Especificação de um produto do catálogo B2B."""
    id: int
    nome: str
    categoria: str
    preco_unitario: float
    custo_unitario: float


# ============================================================================
# 1. CATÁLOGO DE 20 PRODUTOS B2B (Preços e custos plausíveis de atacado)
# ============================================================================
CATALOGO_PRODUTOS: list[ProductSpec] = [
    # Farináceos & Panificação (IDs 1 a 4)
    ProductSpec(1, "Farinha de Trigo Especial Sacaria 25kg", "Farináceos & Panificação", 112.00, 84.00),
    ProductSpec(2, "Mistura para Pão Francês 25kg", "Farináceos & Panificação", 128.50, 95.00),
    ProductSpec(3, "Fermento Biológico Seco Instantâneo Cx 10x500g", "Farináceos & Panificação", 145.00, 104.00),
    ProductSpec(4, "Açúcar Cristal Fardo 30kg", "Farináceos & Panificação", 118.00, 91.00),

    # Laticínios & Frios (IDs 5 a 7)
    ProductSpec(5, "Queijo Mussarela Peça Inteira 4kg", "Laticínios & Frios", 156.00, 121.00),
    ProductSpec(6, "Manteiga Extra sem Sal Bloco 5kg", "Laticínios & Frios", 189.00, 142.00),
    ProductSpec(7, "Leite Condensado Bag Profissional 5kg", "Laticínios & Frios", 94.00, 70.50),

    # Óleos, Gorduras & Conservas (IDs 8 a 10)
    ProductSpec(8, "Óleo de Algodão Especial Fritura Balde 15L", "Óleos, Gorduras & Conservas", 164.00, 125.00),
    ProductSpec(9, "Margarina Folhada Uso Culinário Balde 15kg", "Óleos, Gorduras & Conservas", 172.00, 129.00),
    ProductSpec(10, "Maionese Foodservice Balde 3kg", "Óleos, Gorduras & Conservas", 46.00, 33.00),

    # Carnes, Aves & Congelados (IDs 11 a 13)
    ProductSpec(11, "Batata Pré-Frita Palito Congelada Cx 10kg", "Carnes, Aves & Congelados", 138.00, 102.00),
    ProductSpec(12, "Hambúrguer Bovino Artesanal 150g Cx 36 un", "Carnes, Aves & Congelados", 198.00, 148.00),
    ProductSpec(13, "Filé de Peito de Frango IQF Cx 15kg", "Carnes, Aves & Congelados", 245.00, 192.00),

    # Bebidas & Xaropes (IDs 14 a 15)
    ProductSpec(14, "Refrigerante Cola Lata 350ml Fardo 12 un", "Bebidas & Xaropes", 38.40, 29.50),
    ProductSpec(15, "Água Mineral sem Gás 500ml Fardo 12 un", "Bebidas & Xaropes", 16.80, 11.20),

    # Embalagens & Descartáveis (IDs 16 a 18)
    ProductSpec(16, "Embalagem Térmica Delivery Kraft Cx 100 un", "Embalagens & Descartáveis", 88.00, 61.00),
    ProductSpec(17, "Saco de Papel Kraft Pão 5kg Milheiro", "Embalagens & Descartáveis", 74.00, 51.00),
    ProductSpec(18, "Bobina Plástica Picotada Fundo Estrela 5kg", "Embalagens & Descartáveis", 69.00, 48.00),

    # Limpeza & Higiene Profissional (ID 19)
    ProductSpec(19, "Detergente Neutro Concentrado Galão 5L", "Limpeza & Higiene Profissional", 34.50, 22.00),

    # Mercearia Seca & Grãos (ID 20)
    ProductSpec(20, "Arroz Parboilizado Tipo 1 Fardo 30kg", "Mercearia Seca & Grãos", 159.00, 126.00),
]


# ============================================================================
# 2. CONFIGURAÇÃO DE AFINIDADE COMERCIAL POR SEGMENTO DE ESTABELECIMENTO
# ============================================================================
# Define os produtos principais (alta recorrencia), produtos complementares
# (oportunidades naturais de cross-sell) e faixa de quantidades por item.
PERFIL_SEGMENTOS: dict[str, dict[str, Any]] = {
    "Padaria & Confeitaria": {
        "prefixos_nome": ["Padaria", "Panificadora", "Confeitaria", "Delicatessen"],
        "produtos_base": [1, 2, 3, 4, 6, 9],
        "produtos_complementares": [5, 7, 17, 18, 19],
        "qtd_min_max": (2, 6),
        "itens_por_pedido": (3, 6),
        "ciclos_tipicos": [5, 7, 10],
    },
    "Restaurante": {
        "prefixos_nome": ["Restaurante", "Sabor", "Cozinha", "Bistrô", "Cantina"],
        "produtos_base": [8, 11, 13, 20, 5, 6],
        "produtos_complementares": [10, 14, 15, 16, 19],
        "qtd_min_max": (2, 5),
        "itens_por_pedido": (3, 6),
        "ciclos_tipicos": [7, 10, 14],
    },
    "Hamburgueria & Lanchonete": {
        "prefixos_nome": ["Burger", "Lanchonete", "Chapa Quente", "Point do Lanche", "Estação Burger"],
        "produtos_base": [5, 8, 10, 11, 12, 14],
        "produtos_complementares": [15, 16, 19],
        "qtd_min_max": (2, 6),
        "itens_por_pedido": (3, 5),
        "ciclos_tipicos": [6, 8, 12],
    },
    "Bar & Petiscaria": {
        "prefixos_nome": ["Bar", "Boteco", "Petiscaria", "Espetinho", "Arena Bar"],
        "produtos_base": [8, 11, 13, 14, 15],
        "produtos_complementares": [5, 10, 16, 19],
        "qtd_min_max": (3, 8),
        "itens_por_pedido": (2, 5),
        "ciclos_tipicos": [7, 12, 15],
    },
    "Mercadinho & Mercearia": {
        "prefixos_nome": ["Mercadinho", "Mercearia", "Mini Box", "Super Box", "Empório"],
        "produtos_base": [1, 4, 5, 14, 15, 20],
        "produtos_complementares": [7, 8, 10, 18, 19],
        "qtd_min_max": (3, 10),
        "itens_por_pedido": (4, 7),
        "ciclos_tipicos": [10, 15, 21],
    },
}

BAIRROS_LOCAIS: dict[str, list[str]] = {
    "Recife": [
        "Boa Viagem", "Casa Amarela", "Boa Vista", "Espinheiro", "Afogados",
        "Pina", "Graças", "Cordeiro", "Encruzilhada", "Madalena",
        "Imbiribeira", "Torre", "Várzea", "Parnamirim", "Santo Amaro",
        "Caxangá", "Setúbal", "Arruda", "Tamarineira", "Ipsep",
    ],
    "Fortaleza": [
        "Aldeota", "Meireles", "Messejana", "Parangaba", "Fátima",
        "Benfica", "Montese", "Papicu", "Cocó", "Maraponga",
        "Iracema", "Varjota", "Dionísio Torres", "Passaré", "Mucuripe",
        "São Gerardo", "Cambeba", "Cidade dos Funcionários", "Joaquim Távora", "Praia do Futuro",
    ],
}

COMPLEMENTOS_NOME: list[str] = [
    "Real", "Imperial", "São José", "Bom Gosto", "Estrela", "Sol Nascente",
    "Tradição", "Prime", "Nordeste", "Ouro Preto", "Central", "Família",
    "Alvorada", "Beira Mar", "Sertão", "Prata", "Boa Mesa", "Ideal",
    "Tropical", "Avenida",
]

RESPONSAVEIS_COMERCIAIS: dict[str, list[str]] = {
    "Recife": ["Ana Beatriz Silva", "Carlos Eduardo Mendes", "Fernanda Cavalcanti"],
    "Fortaleza": ["Lucas Oliveira", "Mariana Costa", "Rafael Nogueira"],
}


def _generate_order_dates_for_behavior(
    rng: random.Random,
    behavior_type: str,
    base_cycle: int,
    start_date: date,
    ref_date: date,
) -> tuple[date, list[date]]:
    """
    Simula a linha do tempo de compras de um cliente de acordo com seu arquétipo
    comportamental, sem usar rótulos prontos — apenas construindo as datas reais
    para que o motor analítico descubra o padrão depois.

    Arquétipos simulados:
    - 'recorrente': compra regularmente até próximo à data de referência.
    - 'atencao_desaceleracao': comprava regularmente, mas os últimos 2 pedidos
      espaçaram e o tempo atual sem comprar está entre 1.2x e 1.5x do ciclo.
    - 'risco_moderado': parou de comprar há cerca de 1.6x a 2.3x do seu ciclo.
    - 'alto_risco': parou de comprar há mais de 2.6x a 4.5x do seu ciclo.
    - 'novo_1_compra': cadastrou recentemente e realizou apenas 1 pedido.
    - 'novo_pouco_historico': cadastrou há cerca de 1 a 2 meses e fez 2 ou 3 pedidos.
    - 'sazonal': compra ao longo do ano, mas duplica a frequência em meses de pico
      (junho/São João e dezembro/verão) e está dentro do ciclo atualmente.
    """
    if behavior_type == "novo_1_compra":
        days_ago = rng.randint(4, 18)
        order_date = ref_date - timedelta(days=days_ago)
        reg_date = order_date - timedelta(days=rng.randint(1, 5))
        return reg_date, [order_date]

    if behavior_type == "novo_pouco_historico":
        num_orders = rng.choice([2, 3])
        days_since_last = rng.randint(2, int(base_cycle * 0.9))
        last_order = ref_date - timedelta(days=days_since_last)
        dates = [last_order]
        curr = last_order
        for _ in range(num_orders - 1):
            step = max(3, base_cycle + rng.randint(-1, 2))
            curr = curr - timedelta(days=step)
            dates.append(curr)
        dates.sort()
        reg_date = dates[0] - timedelta(days=rng.randint(2, 7))
        return reg_date, dates

    # Para os perfis com histórico longo (6 a 12 meses), caminhamos para trás a partir
    # da última compra definida pelo comportamento atual do cliente:
    if behavior_type == "recorrente":
        # Última compra ocorreu dentro do ciclo esperado (0.15x a 1.05x do ciclo)
        days_since_last = rng.randint(1, max(2, int(base_cycle * 1.05)))
    elif behavior_type == "atencao_desaceleracao":
        # Atraso leve: 1.20x a 1.45x do ciclo habitual
        days_since_last = rng.randint(int(base_cycle * 1.22) + 1, int(base_cycle * 1.48) + 1)
    elif behavior_type == "risco_moderado":
        # Atraso moderado: 1.60x a 2.35x do ciclo habitual
        days_since_last = rng.randint(int(base_cycle * 1.62) + 1, int(base_cycle * 2.35) + 1)
    elif behavior_type == "alto_risco":
        # Atraso severo: 2.70x a 5.00x do ciclo habitual
        days_since_last = rng.randint(int(base_cycle * 2.75) + 2, int(base_cycle * 5.00) + 5)
    elif behavior_type == "sazonal":
        # Cliente ativo que tem variações sazonais no histórico
        days_since_last = rng.randint(2, max(3, int(base_cycle * 1.0)))
    else:
        days_since_last = rng.randint(2, base_cycle)

    last_order_date = ref_date - timedelta(days=days_since_last)
    earliest_allowed = start_date + timedelta(days=rng.randint(0, 75))

    order_dates = [last_order_date]
    current_date = last_order_date
    step_idx = 0

    while True:
        # Calcula o intervalo entre este pedido e o anterior
        jitter = rng.choice([-1, 0, 0, 0, 1])
        interval = max(3, base_cycle + jitter)

        # Se for perfil em desaceleração, os 2 últimos intervalos antes de hoje foram maiores
        if behavior_type == "atencao_desaceleracao" and step_idx == 0:
            interval = int(base_cycle * 1.35)

        # Se for perfil sazonal, em meses de alta (Dezembro=12, Janeiro=1, Junho=6) compra mais rápido
        if behavior_type == "sazonal" and current_date.month in (12, 1, 6):
            interval = max(3, int(base_cycle * 0.6))

        prev_date = current_date - timedelta(days=interval)
        if prev_date < earliest_allowed or len(order_dates) >= 12:
            break
        order_dates.append(prev_date)
        current_date = prev_date
        step_idx += 1

    order_dates.sort()
    reg_date = max(start_date, order_dates[0] - timedelta(days=rng.randint(2, 14)))
    return reg_date, order_dates


def generate_synthetic_dataset(seed: int = DEFAULT_SEED) -> dict[str, list[dict[str, Any]]]:
    """
    Gera em memória os 4 conjuntos de dados relacionais (clientes, produtos,
    pedidos e itens_pedido) de maneira determinística a partir de `seed`.

    Retorna um dicionário com as chaves:
    - 'produtos' (20 registros)
    - 'clientes' (100 registros)
    - 'pedidos' (~1.000 registros)
    - 'itens_pedido' (~3.800 registros)
    """
    rng = random.Random(seed)

    # 1. Produtos (20 SKUs)
    produtos_data = [
        {
            "id": p.id,
            "nome": p.nome,
            "categoria": p.categoria,
            "preco_unitario": p.preco_unitario,
            "custo_unitario": p.custo_unitario,
        }
        for p in CATALOGO_PRODUTOS
    ]
    produtos_map = {p.id: p for p in CATALOGO_PRODUTOS}

    # 2. Distribuicao dos 100 clientes pelos 5 segmentos solicitados (20 de cada)
    segmentos_lista = [
        "Padaria & Confeitaria",
        "Restaurante",
        "Hamburgueria & Lanchonete",
        "Bar & Petiscaria",
        "Mercadinho & Mercearia",
    ]

    # Distribuicao dos arquetipos comportamentais nos 100 clientes:
    # 42 recorrentes, 16 em desaceleracao/atencao, 14 risco moderado,
    # 14 alto risco, 8 sazonais, 4 novos (pouco historico), 2 novos (1 unica compra)
    arquetipos_pool = (
        ["recorrente"] * 42
        + ["atencao_desaceleracao"] * 16
        + ["risco_moderado"] * 14
        + ["alto_risco"] * 14
        + ["sazonal"] * 8
        + ["novo_pouco_historico"] * 4
        + ["novo_1_compra"] * 2
    )
    rng.shuffle(arquetipos_pool)

    clientes_data: list[dict[str, Any]] = []
    pedidos_data: list[dict[str, Any]] = []
    itens_pedido_data: list[dict[str, Any]] = []

    pedido_id_counter = 1
    item_id_counter = 1

    for idx in range(100):
        cliente_id = idx + 1
        cidade = "Recife" if idx < 52 else "Fortaleza"
        segmento = segmentos_lista[idx % len(segmentos_lista)]
        spec_seg = PERFIL_SEGMENTOS[segmento]

        prefixo = spec_seg["prefixos_nome"][idx % len(spec_seg["prefixos_nome"])]
        complemento = COMPLEMENTOS_NOME[idx % len(COMPLEMENTOS_NOME)]
        bairro = BAIRROS_LOCAIS[cidade][idx % len(BAIRROS_LOCAIS[cidade])]

        # Nome fantasia unico e identificavel como sintetico B2B
        nome_fantasia = f"{prefixo} {complemento} {bairro} #{cliente_id:03d}"
        responsavel = RESPONSAVEIS_COMERCIAIS[cidade][idx % len(RESPONSAVEIS_COMERCIAIS[cidade])]

        behavior = arquetipos_pool[idx]
        # Ajuste fino do ciclo base (em torno de 11 a 21 dias) para totalizar ~1.000 pedidos no ano
        base_cycle = rng.choice(spec_seg["ciclos_tipicos"]) + rng.choice([3, 5, 7])

        reg_date, order_dates = _generate_order_dates_for_behavior(
            rng=rng,
            behavior_type=behavior,
            base_cycle=base_cycle,
            start_date=START_DATE,
            ref_date=REFERENCE_DATE,
        )

        # Define um status cadastral coerente na tabela clientes
        if behavior in ("novo_1_compra", "novo_pouco_historico"):
            status_rel = "Novo"
        elif behavior == "alto_risco":
            status_rel = rng.choice(["Em Risco", "Inativo"])
        elif behavior in ("risco_moderado", "atencao_desaceleracao"):
            status_rel = "Em Risco"
        else:
            status_rel = "Ativo"

        clientes_data.append(
            {
                "id": cliente_id,
                "nome_fantasia": nome_fantasia,
                "tipo_estabelecimento": segmento,
                "cidade": cidade,
                "data_cadastro": reg_date.isoformat(),
                "status_relacionamento": status_rel,
                "responsavel_comercial": responsavel,
            }
        )

        # Define a cesta de produtos que este cliente costuma comprar.
        # Importante para Cross-Sell: cerca de 65% dos clientes compram os itens complementares
        # do seu segmento, enquanto 35% NUNCA compraram 1 ou 2 itens complementares populares!
        base_prods = list(spec_seg["produtos_base"])
        comp_prods = list(spec_seg["produtos_complementares"])

        # Escolhe quais complementares este cliente adota (deixando pelo menos 1 ou 2 de fora
        # em parte dos clientes para gerar oportunidades reais de cross-sell)
        num_comp_adotados = rng.randint(1, max(1, len(comp_prods) - 1))
        adotados_comp = rng.sample(comp_prods, k=num_comp_adotados)
        cesta_cliente = base_prods + adotados_comp

        # Fator de porte do cliente (pequeno, medio, grande dentro do segmento)
        fator_porte = rng.choice([0.8, 1.0, 1.0, 1.3, 1.7])

        for o_date in order_dates:
            min_itens, max_itens = spec_seg["itens_por_pedido"]
            qtd_skus = rng.randint(min_itens, min(max_itens, len(cesta_cliente)))
            skus_escolhidos = rng.sample(cesta_cliente, k=qtd_skus)

            valor_total_pedido = 0.0
            qtd_total_unidades = 0

            for prod_id in sorted(skus_escolhidos):
                prod = produtos_map[prod_id]
                q_min, q_max = spec_seg["qtd_min_max"]
                quantidade = max(1, int(round(rng.randint(q_min, q_max) * fator_porte)))

                # Pequena variacao comercial de preco praticado (-4% a +2% sobre tabela)
                desconto_fator = rng.choice([0.96, 0.98, 1.00, 1.00, 1.00, 1.02])
                preco_praticado = round(prod.preco_unitario * desconto_fator, 2)
                # Garante respeito ao CHECK (preco_praticado > 0)
                subtotal = round(quantidade * preco_praticado, 2)

                valor_total_pedido = round(valor_total_pedido + subtotal, 2)
                qtd_total_unidades += quantidade

                itens_pedido_data.append(
                    {
                        "id": item_id_counter,
                        "pedido_id": pedido_id_counter,
                        "produto_id": prod_id,
                        "quantidade": quantidade,
                        "preco_praticado": preco_praticado,
                    }
                )
                item_id_counter += 1

            # 97% dos pedidos sao 'Concluído', ~3% 'Cancelado' (nunca o unico pedido de um cliente novo)
            if len(order_dates) > 2 and rng.random() < 0.03:
                status_pedido = "Cancelado"
            else:
                status_pedido = "Concluído"

            pedidos_data.append(
                {
                    "id": pedido_id_counter,
                    "cliente_id": cliente_id,
                    "data_compra": o_date.isoformat(),
                    "valor_total": valor_total_pedido,
                    "quantidade_produtos": qtd_total_unidades,
                    "status_pedido": status_pedido,
                }
            )
            pedido_id_counter += 1

    return {
        "produtos": produtos_data,
        "clientes": clientes_data,
        "pedidos": pedidos_data,
        "itens_pedido": itens_pedido_data,
    }


def seed_database(
    db_path: Optional[Path | str] = None,
    seed: int = DEFAULT_SEED,
) -> dict[str, int]:
    """
    Inicializa o banco SQLite (caso ainda não exista) e popula todas as tabelas
    de forma transacional e idempotente (limpando dados anteriores do banco alvo
    antes de inserir para evitar duplicações em reexecuções).

    Retorna um dicionário com a contagem de registros inseridos em cada tabela.
    """
    target_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    init_db(target_path)

    dataset = generate_synthetic_dataset(seed=seed)

    with db_session(target_path) as conn:
        # Limpeza segura na ordem inversa das chaves estrangeiras (idempotencia)
        conn.execute("DELETE FROM itens_pedido;")
        conn.execute("DELETE FROM pedidos;")
        conn.execute("DELETE FROM clientes;")
        conn.execute("DELETE FROM produtos;")

        # Reseta contadores de autoincremento do SQLite se a tabela sqlite_sequence existir
        conn.execute(
            "DELETE FROM sqlite_sequence WHERE name IN ('clientes', 'produtos', 'pedidos', 'itens_pedido');"
        )

        # 1. Inserir Produtos
        conn.executemany(
            """
            INSERT INTO produtos (id, nome, categoria, preco_unitario, custo_unitario)
            VALUES (:id, :nome, :categoria, :preco_unitario, :custo_unitario);
            """,
            dataset["produtos"],
        )

        # 2. Inserir Clientes
        conn.executemany(
            """
            INSERT INTO clientes (
                id, nome_fantasia, tipo_estabelecimento, cidade,
                data_cadastro, status_relacionamento, responsavel_comercial
            )
            VALUES (
                :id, :nome_fantasia, :tipo_estabelecimento, :cidade,
                :data_cadastro, :status_relacionamento, :responsavel_comercial
            );
            """,
            dataset["clientes"],
        )

        # 3. Inserir Pedidos
        conn.executemany(
            """
            INSERT INTO pedidos (
                id, cliente_id, data_compra, valor_total,
                quantidade_produtos, status_pedido
            )
            VALUES (
                :id, :cliente_id, :data_compra, :valor_total,
                :quantidade_produtos, :status_pedido
            );
            """,
            dataset["pedidos"],
        )

        # 4. Inserir Itens dos Pedidos
        conn.executemany(
            """
            INSERT INTO itens_pedido (
                id, pedido_id, produto_id, quantidade, preco_praticado
            )
            VALUES (
                :id, :pedido_id, :produto_id, :quantidade, :preco_praticado
            );
            """,
            dataset["itens_pedido"],
        )

    return {
        "clientes": len(dataset["clientes"]),
        "produtos": len(dataset["produtos"]),
        "pedidos": len(dataset["pedidos"]),
        "itens_pedido": len(dataset["itens_pedido"]),
    }


if __name__ == "__main__":
    counts = seed_database()
    print("=" * 65)
    print("PRASO INTELLIGENCE - POVOAMENTO SINTETICO CONCLUIDO COM SUCESSO")
    print("=" * 65)
    print(f"Banco de dados : {DEFAULT_DB_PATH}")
    print(f"Seed utilizada : {DEFAULT_SEED}")
    print(f"Data referencia: {REFERENCE_DATE.isoformat()}")
    print("-" * 65)
    print(f"Clientes inseridos      : {counts['clientes']}")
    print(f"Produtos no catalogo    : {counts['produtos']}")
    print(f"Pedidos gerados         : {counts['pedidos']}")
    print(f"Itens de pedido gerados : {counts['itens_pedido']}")
    print("=" * 65)
