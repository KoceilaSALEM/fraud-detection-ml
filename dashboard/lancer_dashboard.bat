@echo off
chcp 65001 > nul
echo.
echo  ================================================
echo   Orange Money — Fraud Monitor Dashboard M1
echo   Isolation Forest v2
echo  ================================================
echo.

:: Vérification Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installé ou pas dans le PATH.
    pause
    exit /b 1
)

:: Vérification des fichiers nécessaires
set MISSING=0
if not exist "outputs\M1_fraude_v2\M1_scored_v2.parquet" (
    echo [MANQUANT] outputs\M1_fraude_v2\M1_scored_v2.parquet
    set MISSING=1
)
if not exist "outputs\M1_fraude_v2\M1_isolation_forest_v2.pkl" (
    echo [MANQUANT] outputs\M1_fraude_v2\M1_isolation_forest_v2.pkl
    set MISSING=1
)
if not exist "outputs\M1_fraude_v2\M1_scaler_v2.pkl" (
    echo [MANQUANT] outputs\M1_fraude_v2\M1_scaler_v2.pkl
    set MISSING=1
)
if not exist "outputs\M1_fraude_v2\M1_params_v2.json" (
    echo [MANQUANT] outputs\M1_fraude_v2\M1_params_v2.json
    set MISSING=1
)

if %MISSING%==1 (
    echo.
    echo [ATTENTION] Certains fichiers sont manquants.
    echo Exécute d'abord le notebook : 02_M1_isolation_forest_v2.ipynb
    echo.
    pause
)

:: Installation des dépendances si nécessaire
echo Vérification des dépendances...
pip show streamlit > nul 2>&1
if errorlevel 1 (
    echo Installation des dépendances...
    pip install -r requirements.txt
)

:: Lancement
echo.
echo  Démarrage du dashboard sur http://localhost:8501
echo  Ctrl+C pour arrêter
echo.
streamlit run app.py --server.port 8501 --server.headless false

pause
