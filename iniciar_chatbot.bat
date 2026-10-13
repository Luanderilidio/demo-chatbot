@echo off
chcp 65001 > nul
title Chatbot Agrícola Embrapa - Lenovo HPC
cd /d "%~dp0"
if not exist ".venv312\Scripts\python.exe" (
    echo [ERRO] Ambiente .venv312 nao encontrado. Consulte README.md.
    pause
    exit /b 1
)
".venv312\Scripts\python.exe" chatbot_cli.py
pause
