@echo off
chcp 65001 > nul
title 2 - Baixar Modelos do Ollama
cd /d "%~dp0.."

echo ==========================================================
echo  2. DOWNLOAD DOS MODELOS LOCAIS NO OLLAMA
echo ==========================================================
echo.
echo Verificando Ollama...
ollama --version
if errorlevel 1 (
    echo.
    echo [ERRO] Ollama não foi encontrado no sistema!
    echo Instale o Ollama pelo site oficial: https://ollama.com/download/windows
    echo.
    pause
    exit /b 1
)

echo.
echo [1/2] Baixando modelo LLM (llama3.2:3b)...
ollama pull llama3.2:3b
if errorlevel 1 goto :falha

echo.
echo [2/2] Baixando modelo de Embeddings (nomic-embed-text)...
ollama pull nomic-embed-text
if errorlevel 1 goto :falha

echo.
echo ==========================================================
echo [OK] Modelos baixados com sucesso no Ollama!
echo Agora execute iniciar_chatbot.bat na pasta principal.
echo ==========================================================
echo.
pause
exit /b 0

:falha
echo [ERRO] O download falhou. Confira a mensagem acima antes de continuar.
pause
exit /b 1
