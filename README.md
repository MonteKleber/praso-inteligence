# 📊 Praso Intelligence

**Plataforma de Inteligência Comercial, Previsão de Recompra e Retenção de Clientes B2B**

> *"Não basta identificar quanto a empresa vendeu. É preciso entender quem pode deixar de comprar, quando isso pode acontecer e o que podemos fazer para evitar essa perda."*

---

## 🎯 1. Contexto e Objetivo da Solução

No atacado e distribuição B2B (atendendo padarias, restaurantes, lanchonetes, bares e mercadinhos), os estabelecimentos apresentam ciclos de reposição de estoque relativamente previsíveis. Quando um cliente ultrapassa significativamente seu intervalo habitual de compras, aumenta o risco de migração silenciosa para concorrentes (*churn*).

O **Praso Intelligence** é uma aplicação de **Business Intelligence B2B** construída em Python, SQLite, Pandas, Plotly e Streamlit que transforma o histórico transacional de pedidos em inteligência comercial acionável para as áreas de Planejamento e Vendas:
- Identifica o ciclo habitual de cada cliente (usando a **mediana** para resistir a compras atípicas).
- Classifica heuristicamente o risco de perda comparando o atraso atual com o ritmo do próprio cliente.
- Quantifica a receita histórica, o potencial mensal e a receita exposta ao risco.
- Mapeia oportunidades de **Cross-Sell** comparando o mix do cliente com o benchmark do seu segmento.
- Prioriza a fila de contatos comerciais por um score multicritério (0 a 100) transparente e gera roteiros consultivos para WhatsApp.

> ⚠️ **Aviso Importante sobre os Dados Sintéticos:** Esta plataforma é um **projeto demonstrativo independente** de portfólio (não oficial da Praso). Todos os clientes, produtos, pedidos e valores utilizados são **100% sintéticos**, gerados deterministicamente (`seed=42`, data de referência analítica fixada em `05/11/2026`) para simular operações em Recife e Fortaleza.

---

## 🛠️ 2. Tecnologias Utilizadas

- **Linguagem:** Python 3
- **Interface & Dashboard Web:** Streamlit (arquitetura multipágina corporativa)
- **Banco de Dados:** SQLite 3 (com integridade referencial ativa via `PRAGMA foreign_keys = ON`)
- **Manipulação e Exportação de Dados:** Pandas
- **Visualização Interativa:** Plotly Express & Plotly Graph Objects
- **Testes Automatizados:** Pytest (36 testes cobrindo schema, seed, motor analítico, auditoria matemática e integração do dashboard)

---

## 🖥️ 3. Funcionalidades das Cinco Páginas do Dashboard

1. **Página 1 — Visão Geral (`pages/1_Visao_Geral.py`):**
   - 9 Cartões de Indicadores (Total de clientes, Saudáveis, Atenção, Risco moderado, Alto risco, Receita histórica, Receita mensal estimada, Receita em risco e Ticket médio).
   - **Resumo Executivo Dinâmico** com diagnósticos e recomendações calculados em tempo real sobre o recorte selecionado.
   - 5 Gráficos interativos: distribuição por classificação de risco, proporção saudáveis vs. em risco, receita histórica vs. receita em risco por segmento, comparativo financeiro por cidade e evolução mensal de pedidos e faturamento.
2. **Página 2 — Radar de Clientes (`pages/2_Radar_de_Clientes.py`):**
   - Fila interativa de priorização comercial com filtros combinados por Cidade, Segmento, Classificação de Risco, Faixa de Score (0 a 100) e pesquisa textual por nome/ID.
   - Destaque explicativo do cliente Top #1 no filtro atual, detalhando a nota de cada pilar do score.
   - Navegação direta em 1 clique para abrir o Perfil 360º do estabelecimento selecionado.
3. **Página 3 — Perfil 360º do Cliente (`pages/3_Perfil_do_Cliente.py`):**
   - Dossiê individual com indicadores de ciclo mediano, primeira e última compra, tendência de intervalo e exposição financeira.
   - **Seção de Interpretação Comercial** respondendo objetivamente às perguntas de negócio (comportamento habitual, atraso, justificativa da classificação e cautela analítica).
   - Gráficos de linha do tempo de valores por pedido, comparação de intervalos históricos vs. janela atual sem comprar e mix de produtos adquiridos.
4. **Página 4 — Central de Oportunidades (`pages/4_Oportunidades.py`):**
   - **Aba A (Cross-Sell):** Recomendações de produtos baseadas na taxa de penetração do segmento B2B (`>= 25%`) para itens nunca adquiridos pelo cliente, com filtros por Cidade, Segmento, Cliente e Produto.
   - **Aba B (Recompra e WhatsApp):** Lista priorizada de clientes com recompra atrasada ou próxima (`<= 5 dias`) e gerador de mensagem consultiva para WhatsApp.
5. **Página 5 — Relatórios e Exportação (`pages/5_Relatorios.py`):**
   - Análises comparativas por Segmento, Cidade, Classificação de Risco e Consultor Comercial.
   - Filtro de período para faturamento histórico realizado (preservando intactos os indicadores comportamentais de ciclo e previsão de recompra).
   - **Central de Exportação CSV (`UTF-8-SIG`)** compatível diretamente com Microsoft Excel.

---

## 🏗️ 4. Estrutura Completa do Projeto

```text
praso-intelligence/
├── app.py                          # Entrada principal e roteador multipágina do Streamlit
├── requirements.txt                # Dependências do projeto
├── README.md                       # Documentação técnica e de negócios
├── .streamlit/
│   └── config.toml                 # Tema corporativo (paleta SaaS B2B)
├── assets/
│   └── style.css                   # Folha de estilo CSS customizada (sidebar escura e KPI cards)
├── pages/
│   ├── 1_Visao_Geral.py            # Página 1: Visão Geral e Resumo Executivo
│   ├── 2_Radar_de_Clientes.py      # Página 2: Radar e Fila de Priorização
│   ├── 3_Perfil_do_Cliente.py      # Página 3: Dossiê 360º do Estabelecimento
│   ├── 4_Oportunidades.py          # Página 4: Cross-Sell, Recompra e WhatsApp
│   └── 5_Relatorios.py             # Página 5: Relatórios Dimensionais e Exportação CSV
├── components/
│   ├── __init__.py
│   ├── sidebar.py                  # Barra lateral, cache seguro e filtros em session_state
│   ├── kpi_cards.py                # Cartões de KPI, cabeçalhos e badges de risco
│   ├── charts.py                   # Gráficos Plotly padronizados
│   └── tables.py                   # Formatação de tabelas em português brasileiro
├── services/
│   ├── __init__.py
│   ├── customer_service.py         # Consultas SQL de clientes
│   ├── order_service.py            # Consultas SQL de pedidos, produtos e itens
│   └── dashboard_service.py        # Camada de integração entre UI, serviços e analytics
├── analytics/
│   ├── __init__.py                 # Centraliza DEFAULT_REFERENCE_DATE = date(2026, 11, 5)
│   ├── repurchase.py               # Cálculo de intervalos (média/mediana), ticket e próxima compra
│   ├── churn.py                    # Classificação heurística de risco de abandono
│   ├── revenue.py                  # Receita histórica, potencial mensal e receita em risco
│   ├── cross_sell.py               # Recomendações de produtos por penetração no segmento
│   ├── prioritization.py           # Score de prioridade comercial (0 a 100) e desempate
│   └── executive_summary.py        # Consolidação de KPIs gerenciais e diagnóstico executivo
├── database/
│   ├── __init__.py
│   ├── connection.py               # Conexão SQLite transacional
│   ├── schema.sql                  # DDL Relacional (clientes, produtos, pedidos, itens_pedido)
│   └── seed.py                     # Gerador determinístico de dados sintéticos (seed=42)
└── tests/                          # Suíte de 36 testes automatizados (Pytest)
```

---

## 📐 5. Regras de Negócio, Fórmulas e Limitações Conhecidas

### 5.1. Análise de Recompra (`analytics/repurchase.py`)
- **Ciclo Habitual (`intervalo_mediano_dias`):** Mediana dos intervalos em dias corridos entre datas distintas e consecutivas de pedidos concluídos, evitando que um único atraso antigo (ex.: férias ou reforma) distorça a previsão futura como ocorreria na média aritmética.
- **Próxima Recompra Estimada:**
  ```text
  proxima_compra_estimada = ultima_compra + round(intervalo_mediano_dias)
  ```
- **Tratamento de `None` vs `0`:** Clientes com 0 ou 1 pedido não possuem intervalo entre compras calculável (`intervalo_mediano_dias = None`, `proxima_compra_estimada = None`), evitando previsões artificiais.

### 5.2. Classificação Heurística de Risco de Churn (`analytics/churn.py`)
Baseada no **Índice de Atraso (`indice_atraso`)** calculado na data de referência `2026-11-05`:
```text
indice_atraso = dias_desde_ultima_compra / intervalo_mediano_dias
```

| Faixa de Classificação | Critério Configurável (`indice_atraso`) | Interpretação Comercial |
| :--- | :--- | :--- |
| **Saudável (Em dia)** | `indice_atraso <= 1.15` | Dentro do ciclo esperado (com até 15% de tolerância operacional). |
| **Atenção** | `1.15 < indice_atraso <= 1.50` | Janela habitual ultrapassada; requer contato preventivo de reposição. |
| **Risco moderado** | `1.50 < indice_atraso <= 2.50` | Atraso significativo (1,5 a 2,5 ciclos sem comprar). |
| **Alto risco** | `indice_atraso > 2.50` | Atraso severo (> 2,5 ciclos); exige ação imediata de recuperação. |
| **Dados insuficientes** | `< 2 datas de compra` | Cliente novo ou sem histórico; **nunca** é rotulado automaticamente como churn. |

### 5.3. Receita e Priorização Comercial (`analytics/revenue.py` e `analytics/prioritization.py`)
- **Receita Mensal Estimada:**
  ```text
  receita_mensal_estimada = ticket_medio * (30 / max(3.0, intervalo_mediano_dias))
  ```
- **Exposição Financeira em Risco:** `Saudável` = 0%, `Atenção` = 30%, `Risco moderado` = 70%, `Alto risco` = 100%. *(O peso de 100% no Alto Risco representa exposição financeira estimada segundo regra de negócio, e não probabilidade estatística de perda de 100%).*
- **Score de Priorização (0 a 100):** Combina Urgência/Risco (45 pts), Ticket Médio (25 pts), Potencial Mensal (20 pts) e Cross-Sell (10 pts). *(Pesos heurísticos iniciais, ainda não calibrados com dados reais de conversão).*
- **Limitação de Sazonalidade:** O cálculo do ciclo habitual utiliza a mediana histórica global sem ajuste explícito por calendário sazonal, exigindo leitura contextual do consultor após períodos de alta temporada.

---

## 🚀 6. Como Instalar, Inicializar o Banco, Executar o Dashboard e Rodar os Testes

No Windows PowerShell, execute:

```powershell
# 1. Acessar o diretório do projeto
cd C:\Users\klebe\OneDrive\Documentos\praso-intelligence

# 2. Criar e ativar o ambiente virtual (caso ainda não exista)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar as dependências
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 4. Inicializar e popular o banco SQLite sintético (seed=42)
.\.venv\Scripts\python.exe -m database.seed

# 5. Executar a aplicação Streamlit
.\.venv\Scripts\python.exe -m streamlit run app.py

# 6. Executar toda a suíte de 36 testes automatizados
.\.venv\Scripts\python.exe -m pytest tests\ -v
```
