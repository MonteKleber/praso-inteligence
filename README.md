# 📊 Praso Intelligence

**Plataforma de Inteligência Comercial, Previsão de Recompra e Retenção de Clientes B2B**

> *"Não basta identificar quanto a empresa vendeu. É preciso entender quem pode deixar de comprar, quando isso pode acontecer e o que podemos fazer para evitar essa perda."*

---

## 🎯 Contexto e Problema de Negócio

Estabelecimentos B2B (padarias, restaurantes, lanchonetes, bares e mercadinhos) possuem ciclos relativamente previsíveis de reposição de estoque. Quando um cliente ultrapassa significativamente seu intervalo habitual de compras, aumenta o risco de *churn* (migração para concorrentes).

O **Praso Intelligence** transforma o histórico transacional de pedidos em inteligência acionável para o time comercial:
1. **Análise de Ciclo de Recompra (`analytics/repurchase.py`):** Cálculo do intervalo médio, mediano e previsão da próxima compra por cliente.
2. **Classificação Heurística de Risco de Churn (`analytics/churn.py`):** Identificação de clientes em dia (*Saudável*), *Atenção*, *Risco moderado*, *Alto risco* ou *Dados insuficientes* com base na razão `dias_sem_comprar / intervalo_mediano`.
3. **Estimativa de Receita em Risco (`analytics/revenue.py`):** Separação transparente entre Receita Histórica, Receita Potencial Mensal e Receita Estimada em Risco.
4. **Motor de Cross-Sell por Segmento (`analytics/cross_sell.py`):** Recomendação de produtos com alta penetração no segmento do cliente que ainda não fazem parte do seu mix.
5. **Priorização Comercial (`analytics/prioritization.py`):** Ranking multicritério (0 a 100) combinando risco, ticket médio, potencial financeiro e cross-sell, com geração de abordagem consultiva para WhatsApp.
6. **Resumo Executivo (`analytics/executive_summary.py`):** Diagnóstico consolidado da carteira para tomada de decisão gerencial.

---

## 🏗️ Estrutura do Projeto

```text
praso-intelligence/
├── database/
│   ├── connection.py           # Gerenciador de conexão SQLite (PRAGMA foreign_keys = ON)
│   ├── schema.sql              # Modelagem relacional (clientes, produtos, pedidos, itens_pedido)
│   └── seed.py                 # Gerador determinístico de dados sintéticos B2B (Recife e Fortaleza)
├── services/
│   ├── customer_service.py     # Consultas e filtros de clientes
│   └── order_service.py        # Consultas de pedidos, produtos e itens enriquecidos
├── analytics/
│   ├── repurchase.py           # Cálculo de intervalos (média/mediana), ticket médio e próxima compra
│   ├── churn.py                # Classificação heurística de risco de abandono
│   ├── revenue.py              # Receita histórica, potencial mensal e receita em risco
│   ├── cross_sell.py           # Oportunidades de venda cruzada por benchmark de segmento
│   ├── prioritization.py       # Score de prioridade comercial e sugestões de abordagem
│   └── executive_summary.py    # Consolidação de KPIs e diagnóstico executivo
├── tests/                      # Suíte de testes automatizados com Pytest (25 testes)
└── requirements.txt            # Dependências do projeto
```

---

## 🚀 Como Configurar no Novo Ambiente de Trabalho

```bash
# 1. Clonar o repositório
git clone https://github.com/MonteKleber/praso-inteligence.git
cd praso-inteligence

# 2. Criar e ativar o ambiente virtual
python -m venv .venv
# No Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Popular o banco de dados SQLite com a base sintética (seed=42)
python -m database.seed

# 5. Executar a suíte de testes automatizados
pytest tests/ -v
```

---

## 📌 Status do Desenvolvimento

- [x] **Etapa 1:** Planejamento e definição das regras de negócio
- [x] **Etapa 2:** Modelagem do banco de dados relacional SQLite
- [x] **Etapa 3:** Geração de dados sintéticos reproduzíveis (Recife e Fortaleza)
- [x] **Etapa 4:** Motor de análise e inteligência comercial + 25 testes automatizados
- [ ] **Etapa 5:** Desenvolvimento do Dashboard em Streamlit (`app.py` e `pages/`)
- [ ] **Etapa 6:** Implementação das recomendações comerciais na interface
- [ ] **Etapa 7:** Testes integrados finais e validação
- [ ] **Etapa 8:** Documentação executiva final e roteiro de apresentação de 5 minutos
