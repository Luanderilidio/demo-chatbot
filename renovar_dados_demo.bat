@echo off
cd /d "%~dp0"
set "RAG_NODE=node"
where node >nul 2>nul
if errorlevel 1 set "RAG_NODE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
"%RAG_NODE%" api\seed.cjs
pause
