MRP — Project Work 27 · Nuova versione JSON indipendente
Software Python per pianificazione dei fabbisogni di materiali (MRP) su distinta base multilivello, con dashboard Streamlit, tabelle pandas e grafici interattivi Plotly. È pronto con l'esempio della centralina BLE/Wi-Fi ESP32 + scheda relè.

1. Installazione e avvio su Windows
Requisito: installare Python 3.10 o successivo (preferibilmente 3.11 o 3.12) e avere una connessione Internet durante la prima installazione delle librerie.

Estrai completamente il file ZIP in una cartella, per esempio Documenti\MRP_PW27.
Fai doppio clic su AVVIA_WINDOWS.bat. Il programma prepara l'ambiente e installa le librerie richieste.
Si apre la dashboard nel browser. Se non si apre automaticamente, visita http://localhost:8501.
Per interrompere l'applicazione chiudi il terminale o premi Ctrl+C.
In alternativa: avvio manuale dal terminale
Da PowerShell o dal terminale integrato di Visual Studio Code, nella cartella estratta:

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
