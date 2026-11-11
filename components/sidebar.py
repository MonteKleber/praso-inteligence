"""
Componente de Barra Lateral e Gerenciamento de Estado / Cache (`components/sidebar.py`).

Centraliza o carregamento em cache dos dados analíticos (garantindo que a data de
referência `2026-11-05` e o caminho do banco façam parte da chave do cache) e
mantém os filtros globais sincronizados em `st.session_state`.
"""

from pathlib import Path
from typing import Any, Optional
import streamlit as st

from analytics import DEFAULT_REFERENCE_DATE
from database.connection import DEFAULT_DB_PATH
from services.dashboard_service import format_date_br, load_full_analytical_portfolio


@st.cache_data(show_spinner=False)
def get_cached_portfolio_data(
    db_path_str: str,
    reference_date_iso: str,
    db_mtime: float,
) -> dict[str, Any]:
    """
    Carrega os dados analíticos da carteira com cache invalidado automaticamente
    se o arquivo SQLite sofrer alteração (`db_mtime`), se o caminho do banco mudar
    ou se a data de referência mudar.
    """
    _ = db_mtime  # Utilizado na chave de invalidação do @st.cache_data
    return load_full_analytical_portfolio(
        db_path=Path(db_path_str),
        reference_date=reference_date_iso,
    )


def load_portfolio_state(db_path: Optional[Path] = None) -> dict[str, Any]:
    """
    Obtém os dados analíticos usando o cache seguro do Streamlit.
    """
    target_db = db_path or DEFAULT_DB_PATH
    mtime = target_db.stat().st_mtime if target_db.exists() else 0.0
    ref_iso = DEFAULT_REFERENCE_DATE.isoformat()
    return get_cached_portfolio_data(
        db_path_str=str(target_db),
        reference_date_iso=ref_iso,
        db_mtime=mtime,
    )


def init_session_filters(filter_options: dict[str, list[str]]) -> None:
    """
    Inicializa em `st.session_state` os filtros persistentes entre páginas
    para que o usuário não perca sua seleção ao navegar.
    """
    if "filtro_cidades" not in st.session_state:
        st.session_state["filtro_cidades"] = list(filter_options.get("cidades", []))
    if "filtro_segmentos" not in st.session_state:
        st.session_state["filtro_segmentos"] = list(
            filter_options.get("tipos_estabelecimento", [])
        )
    if "filtro_status_risco" not in st.session_state:
        st.session_state["filtro_status_risco"] = list(
            filter_options.get("status_risco", [])
        )
    if "cliente_selecionado_id" not in st.session_state:
        st.session_state["cliente_selecionado_id"] = 25  # Top #1 prioritário inicial


def render_sidebar_context(
    portfolio_data: dict[str, Any],
    show_global_filters: bool = True,
) -> dict[str, Any]:
    """
    Renderiza a barra lateral corporativa com identificação do sistema, data de
    referência analítica e filtros globais opcionais sincronizados em `session_state`.
    """
    filter_opts = portfolio_data["filter_options"]
    init_session_filters(filter_opts)

    with st.sidebar:
        st.markdown("### PRASO INTELLIGENCE")
        st.caption("Plataforma B2B de Retenção, Recompra e Expansão de Carteira")
        st.markdown("---")

        ref_br = format_date_br(portfolio_data["reference_date"])
        st.markdown(f"**Data de Referência Analítica:** `{ref_br}`")
        st.caption(
            "Base sintética demonstrativa (Recife e Fortaleza — 100 estabelecimentos)."
        )

        selected_cidades = list(filter_opts["cidades"])
        selected_segmentos = list(filter_opts["tipos_estabelecimento"])

        if show_global_filters:
            st.markdown("---")
            st.markdown("#### Filtros de Carteira")

            cidades_sel = st.multiselect(
                "Cidades de Operação",
                options=filter_opts["cidades"],
                default=st.session_state["filtro_cidades"],
                key="sidebar_multiselect_cidades",
            )
            st.session_state["filtro_cidades"] = cidades_sel
            selected_cidades = cidades_sel

            segmentos_sel = st.multiselect(
                "Segmentos B2B",
                options=filter_opts["tipos_estabelecimento"],
                default=st.session_state["filtro_segmentos"],
                key="sidebar_multiselect_segmentos",
            )
            st.session_state["filtro_segmentos"] = segmentos_sel
            selected_segmentos = segmentos_sel

            if st.button("Restaurar Filtros Padrão", width="stretch"):
                st.session_state["filtro_cidades"] = list(filter_opts["cidades"])
                st.session_state["filtro_segmentos"] = list(
                    filter_opts["tipos_estabelecimento"]
                )
                st.session_state["filtro_status_risco"] = list(
                    filter_opts["status_risco"]
                )
                st.rerun()

        st.markdown("---")
        st.caption("Projeto Demonstrativo — Processo Seletivo Trainee")

    return {
        "cidades": selected_cidades,
        "segmentos": selected_segmentos,
    }
