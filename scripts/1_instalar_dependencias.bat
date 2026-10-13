@echo off
chcp 65001 > nul
title 1 - Instalar Dependências Python
cd /d "%~dp0.."

echo ==========================================================
echo  1. INSTALAÇÃO DAS DEPENDÊNCIAS PYTHON DO CHATBOT
echo ==========================================================
echo.
echo Verificando Python...
if not exist ".venv312\Scripts\python.exe" (
    echo [ERRO] Crie o ambiente com: py -3.12 -m venv .venv312
    pause
    exit /b 1
)
".venv312\Scripts\python.exe" --version
if errorlevel 1 (
    echo.
    echo [ERRO] Python não foi encontrado no sistema!
    echo Por favor, instale o Python 3.10 ou superior e marque a opção
    echo "Add python.exe to PATH" durante a instalação.
    echo.
    pause
    exit /b 1
)

echo.
echo Instalando bibliotecas do requirements.txt...
".venv312\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao instalar algumas dependências.
    echo.
) else (
    echo.
    echo ==========================================================
    echo [OK] Dependências instaladas com sucesso!
    echo Agora execute o passo 2: scripts\2_baixar_modelos_ollama.bat
    echo ==========================================================
)
echo.
pause
