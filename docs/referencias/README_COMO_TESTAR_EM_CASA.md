# 🌿 Guia Passo a Passo: Como Testar o Chatbot Agrícola em Casa

> Referência histórica recebida com o protótipo. Após a reorganização, siga o [README atual](../../README.md) para caminhos, ambiente Python e comandos.

Este guia foi feito para que qualquer colega consiga rodar e testar o **Chatbot Agrícola Embrapa (RAG + Ollama)** em outro computador de forma rápida e 100% offline/local.

---

## 📁 1. Arquivos que você deve enviar para o colega

Basta copiar a pasta **`Task ChatBot`** inteira (por exemplo, via pendrive ou arquivo `.zip`).

### O que tem nessa pasta:
* `chroma_db/` **(MUITO IMPORTANTE - ~34 MB):** É a base vetorial já pré-indexada com mais de **3.800 trechos** dos 6 livros da Embrapa. Se você enviar essa pasta, **ele NÃO precisa perder tempo processando os PDFs!**
* `chatbot_cli.py` & `rag_engine.py`: Código-fonte do assistente inteligente.
* `ingest.py`: Script para recriar a base vetorial do zero (opcional, só se quiser reindexar).
* `requirements.txt`: Lista de pacotes Python necessários.
* `1_instalar_dependencias.bat`: Instalador automático das bibliotecas.
* `2_baixar_modelos_ollama.bat`: Download automático dos modelos no Ollama.
* `3_iniciar_chatbot.bat`: Abre o chatbot diretamente no terminal.
* `OllamaSetup.exe` *(Opcional, 1.5 GB)*: Instalador offline do Ollama. Se preferir economizar espaço no pendrive/zip, o colega pode baixar direto pelo site [ollama.com](https://ollama.com).

---

## 💻 2. Pré-Requisitos no computador do colega

1. **Python 3.10 ou 3.11** instalado:
   * Download: [python.org/downloads](https://www.python.org/downloads/)
   * ⚠️ **Atenção:** Na primeira tela do instalador do Python, **marque a caixinha "Add python.exe to PATH"**.
2. **Ollama** instalado:
   * Se você enviou o arquivo `OllamaSetup.exe`, basta dar dois cliques nele para instalar.
   * Ou baixe gratuitamente pelo site oficial: [ollama.com](https://ollama.com).
   * O ícone da lhama do Ollama deve ficar visível na barra de tarefas (perto do relógio do Windows).

---

## 🚀 3. Passo a Passo para o Colega Rodar

Dentro da pasta do projeto, basta executar os scripts numerados em ordem:

### Passo 1: Instalar as bibliotecas Python
* Dê duplo-clique no arquivo: **`1_instalar_dependencias.bat`**
* *(Ou abra o terminal na pasta e digite: `pip install -r requirements.txt`)*

### Passo 2: Baixar os modelos de IA
* Dê duplo-clique no arquivo: **`2_baixar_modelos_ollama.bat`**
* *(Isso vai baixar no Ollama o LLM `llama3.2:3b` e o modelo de busca `nomic-embed-text`)*

### Passo 3: Abrir o Chatbot!
* Dê duplo-clique no arquivo: **`3_iniciar_chatbot.bat`**
* Pronto! O terminal interativo do Chatbot Agrícola vai se abrir e você já pode começar a conversar.

---

## 💬 4. Exemplos de Perguntas para Testar

* *"Como controlar a ferrugem asiática na soja?"*
* *"Qual a época recomendada para adubar o milho safrinha?"*
* *"Como conservar tomates na pós-colheita para evitar fungos?"*
* *"Quais os sintomas de deficiência de nitrogênio no arroz?"*

---

## 🛠️ 5. Comandos Úteis no Chatbot

| Comando | O que faz |
|---|---|
| `/filtro soja` | Restringe a pesquisa aos livros de Soja *(funciona também com `milho`, `arroz`, `hortalicas`, etc.)* |
| `/filtro off` | Volta a buscar em todos os livros da Embrapa simultaneamente |
| `/fontes` | Mostra os trechos brutos e citações extraídos dos PDFs |
| `/limpar` | Limpa a tela do terminal |
| `/ajuda` | Exibe o menu de instruções |
| `/sair` | Fecha o chatbot |

---

## ❓ 6. Perguntas Frequentes e Resolução de Problemas

* **Erro "Ollama connection refused" ou "Port 11434":**
  * Abra o menu iniciar do Windows e abra o programa **Ollama**. Verifique se o ícone do Ollama está rodando perto do relógio do Windows.
* **Erro "'python' não é reconhecido como comando interno":**
  * Reinstale o Python e lembre-se de marcar a opção **Add python.exe to PATH**.
