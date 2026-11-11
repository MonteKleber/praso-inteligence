"""
Componentes de Cartões de Indicadores (KPI Cards), Cabeçalhos e Badges (`components/kpi_cards.py`).
"""

from pathlib import Path
import streamlit as st

from analytics.churn import (
    STATUS_ALTO_RISCO,
    STATUS_ATENCAO,
    STATUS_DADOS_INSUFICIENTES,
    STATUS_RISCO_MODERADO,
    STATUS_SAUDAVEL,
)

ASSETS_CSS_PATH = Path(__file__).resolve().parent.parent / "assets" / "style.css"


def inject_custom_css() -> None:
    """Injeta a folha de estilo corporativa `assets/style.css` na página atual."""
    if ASSETS_CSS_PATH.exists():
        css_content = ASSETS_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str) -> None:
    """Renderiza o cabeçalho padronizado azul-marinho no topo da página."""
    st.markdown(
        f"""
        <div class="praso-page-header">
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(
    title: str,
    value: str,
    subtitle: str = "",
    color_variant: str = "blue",
) -> None:
    """
    Renderiza um cartão de indicador corporativo com hierarquia visual clara.
    `color_variant` aceita: `'blue'`, `'green'`, `'amber'`, `'orange'`, `'red'`.
    """
    variant_class = f"kpi-{color_variant}"
    st.markdown(
        f"""
        <div class="praso-kpi-card {variant_class}">
            <div>
                <div class="praso-kpi-title">{title}</div>
                <div class="praso-kpi-value">{value}</div>
            </div>
            <div class="praso-kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_risk_badge_html(status_risco: str) -> str:
    """Retorna um badge HTML colorido correspondente à classificação de risco."""
    mapping = {
        STATUS_SAUDAVEL: ("badge-saudavel", "Saudável (Em dia)"),
        STATUS_ATENCAO: ("badge-atencao", "Atenção"),
        STATUS_RISCO_MODERADO: ("badge-moderado", "Risco moderado"),
        STATUS_ALTO_RISCO: ("badge-alto", "Alto risco"),
        STATUS_DADOS_INSUFICIENTES: ("badge-insuficiente", "Dados insuficientes"),
    }
    css_cls, label = mapping.get(status_risco, ("badge-insuficiente", status_risco))
    return f'<span class="praso-badge {css_cls}">{label}</span>'


def render_synthetic_disclaimer_footer(reference_date_str: str = "05/11/2026") -> None:
    """Renderiza o aviso metodológico e de base sintética no rodapé da página."""
    st.markdown(
        f"""
        <div class="praso-synthetic-banner">
            <strong>Nota Metodológica e de Dados Sintéticos:</strong>
            Esta plataforma é um projeto demonstrativo independente de Inteligência Comercial B2B
            (não oficial da Praso). Todos os estabelecimentos, pedidos e valores são
            <strong>100% sintéticos</strong> (seed=42, data de referência analítica fixada em
            <strong>{reference_date_str}</strong>). As classificações de risco de churn e scores de
            priorização são indicadores heurísticos de apoio à decisão comercial.
        </div>
        """,
        unsafe_allow_html=True,
    )
