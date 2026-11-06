"""
Testes automatizados do Módulo de Resumo Executivo (`analytics/executive_summary.py`).
Valida a integração completa dos módulos sobre um banco temporário populado com o seed.
"""

from pathlib import Path
from analytics.executive_summary import generate_executive_summary
from database.seed import DEFAULT_SEED, REFERENCE_DATE, seed_database


def test_resumo_executivo_integrado_com_banco_temporario(tmp_path: Path) -> None:
    """
    Popula um banco SQLite temporário e verifica se o Resumo Executivo consolida
    todos os 100 clientes sem inconsistências matemáticas.
    """
    db_file = tmp_path / "test_exec_summary.db"
    seed_database(db_path=db_file, seed=DEFAULT_SEED)

    resumo = generate_executive_summary(
        db_path=db_file,
        reference_date=REFERENCE_DATE,
        top_n_priority=5,
    )

    assert resumo["data_referencia"] == "2026-11-05"
    assert resumo["total_clientes_analisados"] == 100

    soma_status = (
        resumo["clientes_recorrentes_saudaveis"]
        + resumo["clientes_em_atencao"]
        + resumo["clientes_em_risco_moderado"]
        + resumo["clientes_em_alto_risco"]
        + resumo["clientes_com_dados_insuficientes"]
    )
    assert soma_status == 100

    assert resumo["receita_historica_total"] > 0
    assert resumo["receita_estimada_em_risco"] > 0
    assert resumo["quantidade_oportunidades_cross_sell"] > 0
    assert len(resumo["clientes_prioritarios_contato"]) == 5
    assert len(resumo["principais_problemas_identificados"]) >= 2
    assert len(resumo["acoes_comerciais_recomendadas"]) >= 2
    assert isinstance(resumo["relatorio_textual_executivo"], str)
