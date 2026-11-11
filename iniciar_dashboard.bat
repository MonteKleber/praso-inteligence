@echo off
cd /d "C:\Users\klebe\OneDrive\Documentos\praso-intelligence"
echo =================================================================
echo INICIANDO PRASO INTELLIGENCE DASHBOARD (http://localhost:8501)
echo Mantenha esta janela aberta enquanto utiliza o sistema.
echo =================================================================
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless false
pause
