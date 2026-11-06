-- ============================================================================
-- PRASO INTELLIGENCE — MODELO DE DADOS RELACIONAL (SQLite)
-- Plataforma de Inteligência Comercial, Previsão de Recompra e Retenção B2B
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. TABELA DE CLIENTES (Estabelecimentos B2B atendidos pela distribuidora)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_fantasia TEXT NOT NULL,
    tipo_estabelecimento TEXT NOT NULL CHECK (
        tipo_estabelecimento IN (
            'Padaria & Confeitaria',
            'Restaurante',
            'Hamburgueria & Lanchonete',
            'Bar & Petiscaria',
            'Pizzaria',
            'Mercadinho & Mercearia'
        )
    ),
    cidade TEXT NOT NULL CHECK (cidade IN ('Recife', 'Fortaleza')),
    data_cadastro TEXT NOT NULL, -- Formato ISO 8601: YYYY-MM-DD
    status_relacionamento TEXT NOT NULL DEFAULT 'Ativo' CHECK (
        status_relacionamento IN ('Ativo', 'Inativo', 'Novo', 'Em Risco')
    ),
    responsavel_comercial TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- 2. TABELA DE PRODUTOS (Catálogo de insumos B2B da distribuidora)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    categoria TEXT NOT NULL CHECK (
        categoria IN (
            'Farináceos & Panificação',
            'Laticínios & Frios',
            'Óleos, Gorduras & Conservas',
            'Carnes, Aves & Congelados',
            'Bebidas & Xaropes',
            'Embalagens & Descartáveis',
            'Limpeza & Higiene Profissional',
            'Mercearia Seca & Grãos'
        )
    ),
    preco_unitario REAL NOT NULL CHECK (preco_unitario > 0),
    custo_unitario REAL NOT NULL CHECK (custo_unitario > 0 AND custo_unitario <= preco_unitario)
);

-- ----------------------------------------------------------------------------
-- 3. TABELA DE PEDIDOS (Cabeçalho das transações comerciais)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    data_compra TEXT NOT NULL, -- Formato ISO 8601: YYYY-MM-DD
    valor_total REAL NOT NULL CHECK (valor_total >= 0),
    quantidade_produtos INTEGER NOT NULL CHECK (quantidade_produtos > 0),
    status_pedido TEXT NOT NULL DEFAULT 'Concluído' CHECK (
        status_pedido IN ('Concluído', 'Cancelado', 'Em Processamento')
    ),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- ----------------------------------------------------------------------------
-- 4. TABELA DE ITENS DOS PEDIDOS (Detalhamento de SKUs comprados por pedido)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS itens_pedido (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL,
    produto_id INTEGER NOT NULL,
    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
    preco_praticado REAL NOT NULL CHECK (preco_praticado > 0),
    FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    -- Evita duplicação do mesmo produto em linhas separadas dentro do mesmo pedido:
    UNIQUE (pedido_id, produto_id)
);

-- ============================================================================
-- ÍNDICES DE PERFORMANCE PARA ANÁLISE COMERCIAL E CONSULTAS AGREGADAS
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_pedidos_cliente_data ON pedidos(cliente_id, data_compra);
CREATE INDEX IF NOT EXISTS idx_pedidos_status_data ON pedidos(status_pedido, data_compra);
CREATE INDEX IF NOT EXISTS idx_clientes_cidade_tipo ON clientes(cidade, tipo_estabelecimento);
CREATE INDEX IF NOT EXISTS idx_itens_pedido_pedido ON itens_pedido(pedido_id);
CREATE INDEX IF NOT EXISTS idx_itens_pedido_produto ON itens_pedido(produto_id);
