# 📊 Praso Intelligence

**Plataforma de Inteligência Comercial, Previsão de Recompra e Retenção de Clientes B2B**

> *"Não basta identificar quanto a empresa vendeu. É preciso entender quem pode deixar de comprar, quando isso pode acontecer e o que podemos fazer para evitar essa perda."*

---

## 🎯 1. Contexto e Problema de Negócio

No atacado e distribuição B2B (atendendo padarias, restaurantes, lanchonetes, bares e mercadinhos), os clientes apresentam ciclos de reposição de estoque relativamente previsíveis. Quando um estabelecimento ultrapassa significativamente seu intervalo habitual de compras, aumenta o risco de migração silenciosa para concorrentes (*churn*).

O **Praso Intelligence** transforma o histórico transacional de pedidos em inteligência comercial acionável:
- Identifica o ciclo habitual de cada cliente (usando a **mediana** para resistir a compras atípicas).
- Classifica heuristicamente o risco de perda comparando o atraso atual com o ritmo do próprio cliente.
- Quantifica a receita histórica, o potencial mensal e a receita exposta ao risco.
- Mapeia oportunidades de **Cross-Sell** comparando o mix do cliente com o benchmark do seu segmento.
- Prioriza a fila de contatos comerciais por um score multicritério (0 a 100) transparente.

> ⚠️ **Nota sobre os Dados:** Todos os dados utilizados neste projeto são **100% sintéticos**, gerados deterministicamente (`seed=42`) com fins demonstrativos para simular operações em Recife e Fortaleza.

---

## 🏗️ 2. Arquitetura e Responsabilidade dos Módulos

```text
praso-intelligence/
├── database/
│   ├── connection.py           # Conexão SQLite com PRAGMA foreign_keys = ON e transações seguras
│   ├── schema.sql              # Modelagem relacional 3FN (clientes, produtos, pedidos, itens_pedido)
│   └── seed.py                 # Gerador determinístico de dados sintéticos B2B (data ref: 2026-11-05)
├── services/
│   ├── customer_service.py     # Camada de acesso a dados cadastrais e filtros de clientes
│   └── order_service.py        # Consultas de pedidos (sem duplicação por JOIN) e itens enriquecidos
├── analytics/
│   ├── __init__.py             # Centraliza DEFAULT_REFERENCE_DATE = date(2026, 11, 5)
│   ├── repurchase.py           # Cálculo de intervalos (média/mediana/desvio), ticket e próxima compra
│   ├── churn.py                # Classificação heurística de risco de abandono e tendência de ciclo
│   ├── revenue.py              # Receita histórica, potencial mensal, receita em risco e cortes por dimensão
│   ├── cross_sell.py           # Recomendações de produtos por penetração no segmento B2B
│   ├── prioritization.py       # Score de prioridade comercial (0 a 100), desempate e script WhatsApp
│   └── executive_summary.py    # Consolidação de KPIs gerenciais e diagnóstico executivo
├── tests/                      # Suíte de 25 testes automatizados (Pytest) em bancos isolados
└── requirements.txt            # Dependências do projeto
```

---

## 📐 3. Regras de Negócio, Fórmulas e Limitações

### 3.1. Análise de Recompra (`analytics/repurchase.py`)
- **Intervalos entre compras ($\Delta t$):** Calculados em dias corridos entre datas distintas e consecutivas de pedidos com status `'Concluído'`.
- **Ciclo Habitual ($\tilde{\Delta t}$):** Definido pela **mediana** dos intervalos ($\text{intervalo\_mediano\_dias}$), evitando que um único atraso antigo (ex.: férias ou reforma) distorça a previsão futura como ocorreria na média aritmética.
- **Próxima Recompra Estimada:**
  $$\text{Próxima Compra} = \text{Data da Última Compra} + \text{round}(\tilde{\Delta t})$$
- **Tratamento de Casos Especiais (`None` vs `0`):**
  - **0 pedidos:** `quantidade_pedidos = 0`, `valor_total_historico = 0.0`, mas `ticket_medio = None`, `intervalo_mediano_dias = None` e `proxima_compra_estimada = None`.
  - **1 único pedido:** Possui `ticket_medio` e `dias_desde_ultima_compra`, mas como não há par de datas para medir intervalo, `intervalo_mediano_dias = None` e `proxima_compra_estimada = None` (sem previsões artificiais).

### 3.2. Classificação Heurística de Risco de Churn (`analytics/churn.py`)
Baseada no **Índice de Atraso ($I_{atraso}$)** calculado na data de referência (`2026-11-05`):
$$I_{atraso} = \frac{\text{dias\_desde\_ultima\_compra}}{\text{intervalo\_mediano\_dias}}$$

| Faixa de Classificação | Critério Configurável ($I_{atraso}$) | Interpretação Comercial |
| :--- | :--- | :--- |
| **Saudável (Em dia)** | $I_{atraso} \le 1.15$ | Dentro do ciclo esperado (com até 15% de tolerância operacional). |
| **Atenção** | $1.15 < I_{atraso} \le 1.50$ | Janela habitual ultrapassada; requer contato preventivo de reposição. |
| **Risco moderado** | $1.50 < I_{atraso} \le 2.50$ | Atraso significativo (1,5 a 2,5 ciclos sem comprar). |
| **Alto risco** | $I_{atraso} > 2.50$ | Atraso severo (> 2,5 ciclos); exige ação imediata de recuperação. |
| **Dados insuficientes** | $< 2$ datas de compra | Cliente novo ou sem histórico; **nunca** é rotulado automaticamente como churn. |

### 3.3. Análise de Receita (`analytics/revenue.py`)
Separa rigorosamente três grandezas financeiras (sem jamais duplicar valores de pedidos em `JOIN` com itens):
1. **Receita Histórica (`receita_historica`):** Soma efetiva dos pedidos concluídos no passado, incluindo o recorte de **Receita Histórica Associada a Clientes em Risco (`receita_historica_clientes_em_risco`)**.
2. **Receita Mensal Estimada (`receita_mensal_estimada`):** Projeção para uma janela de 30 dias baseada no ritmo mediano do cliente:
   $$\text{Receita Mensal Estimada} = \text{Ticket Médio} \times \left(\frac{30}{\text{Intervalo Mediano}}\right)$$
3. **Receita em Risco Estimada (`receita_em_risco`):** Parcela da receita mensal estimada ponderada pelo fator de exposição do risco atual (`Saudável` = 0%, `Atenção` = 30%, `Risco moderado` = 70%, `Alto risco` = 100%).

### 3.4. Motor de Cross-Sell (`analytics/cross_sell.py`)
- Calcula a **Taxa de Penetração no Segmento**: proporção de estabelecimentos ativos do mesmo `tipo_estabelecimento` que compram determinado produto.
- Sugere produtos com penetração $\ge 25\%$ no segmento (respeitando amostra mínima de clientes e compradores) que o cliente analisado **ainda nunca comprou**.
- Estima o potencial financeiro por pedido com base no gasto médio daquele SKU entre os pares do segmento.

### 3.5. Priorização Comercial (`analytics/prioritization.py`)
Calcula o `score_prioridade` (0 a 100) combinando 4 componentes normalizados:
- **Urgência / Risco de Churn:** até **45 pontos**
- **Ticket Médio:** até **25 pontos**
- **Potencial Mensal / Receita Histórica:** até **20 pontos**
- **Potencial de Cross-Sell:** até **10 pontos**
- **Desempate determinístico:** 1º Maior Receita em Risco $\rightarrow$ 2º Maior Ticket Médio $\rightarrow$ 3º Maior Dias sem Comprar $\rightarrow$ 4º Menor `cliente_id`.

---

## 📈 4. Exemplo de Resultados na Base Sintética (`2026-11-05`)

- **Carteira Analisada:** 100 clientes (52 em Recife, 48 em Fortaleza) e 1.092 pedidos concluídos.
- **Distribuição de Risco:** 50 Saudáveis, 14 em Atenção, 20 em Risco Moderado, 14 em Alto Risco e 2 com Dados Insuficientes (1ª compra).
- **Receita Histórica Total:** R$ 3.066.466,34 (sendo R$ 1.448.329,63 gerados historicamente pelos 48 clientes hoje em risco).
- **Receita Mensal Estimada em Risco (próximos 30 dias):** R$ 168.188,72.
- **Oportunidades de Cross-Sell:** 238 recomendações identificadas.

---

## 🚀 5. Como Executar Localmente e Rodar os Testes

```powershell
# 1. Clonar o repositório
git clone https://github.com/MonteKleber/praso-inteligence.git
cd praso-inteligence

# 2. Criar e ativar o ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Popular o banco SQLite com dados sintéticos (seed=42)
python -m database.seed

# 5. Executar todos os 25 testes automatizados
pytest tests/ -v
```
