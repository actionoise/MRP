@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creo l'ambiente virtuale Python...
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo ERRORE: installa Python 3.10 o superiore da python.org.
  pause
  exit /b 1
)
echo Installo/controllo le dipendenze...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERRORE durante l'installazione delle dipendenze.
  pause
  exit /b 1
)
echo Avvio dashboard MRP su http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
pause
