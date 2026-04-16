@echo off
REM Lanceur pour Mix Analyzer
REM Double-clique sur ce fichier pour ouvrir l'interface graphique
py mix_analyzer.py
if errorlevel 1 (
    echo.
    echo ERREUR: Le script n'a pas pu se lancer.
    echo Verifie que Python est installe et que les dependances sont presentes:
    echo     pip install -r requirements.txt
    echo.
    pause
)
