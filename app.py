"""
Ponto de entrada principal da aplicação Streamlit (`app.py`).

Configura o layout amplo, o menu de navegação estruturado entre as 5 páginas
corporativas do Praso Intelligence e renderiza a visão inicial quando acessado.
"""

import streamlit as st

st.set_page_config(
    page_title="Praso Intelligence | Inteligência Comercial B2B",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation(
    [
        st.Page(
            "pages/1_Visao_Geral.py",
            title="1. Visão Geral",
            icon=":material/analytics:",
            default=True,
        ),
        st.Page(
            "pages/2_Radar_de_Clientes.py",
            title="2. Radar de Clientes",
            icon=":material/radar:",
        ),
        st.Page(
            "pages/3_Perfil_do_Cliente.py",
            title="3. Perfil do Cliente",
            icon=":material/storefront:",
        ),
        st.Page(
            "pages/4_Oportunidades.py",
            title="4. Central de Oportunidades",
            icon=":material/trending_up:",
        ),
        st.Page(
            "pages/5_Relatorios.py",
            title="5. Relatórios e Exportação",
            icon=":material/summarize:",
        ),
    ]
)

pg.run()
