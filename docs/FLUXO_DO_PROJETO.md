# Entenda o fluxo do projeto

## 1. Preparação da base

```text
dados/documentos/
       ↓
ingest.py (entrada na raiz)
       ↓
src/ingest.py
  selecionar arquivos → extrair texto → limpar → dividir em trechos
       ↓
nomic-embed-text, executado pelo Ollama
       ↓
Chroma: textos + vetores + metadados
```

Essa fase já foi realizada na base recebida. Os documentos originais ficam em `dados/documentos`; os arquivos do banco são uma representação processada desses documentos, armazenada no caminho de `config/chroma_path.txt`.

Na implementação atual, cada página de PDF vira um documento intermediário com origem, título, cultura e posição da página. O texto é dividido em até 750 caracteres, com sobreposição alvo de 120. O modelo gera os vetores e o Chroma persiste os registros.

Copiar um arquivo para `dados/documentos` não basta: ele precisa estar no catálogo `DOC_METADATA_MAP` do código e passar pela ingestão. Antes de reexecutar essa etapa, corrigir as falhas descritas na revisão.

## 2. Consulta do usuário

```text
python chatbot_cli.py
       ↓
src/chatbot_cli.py: receber pergunta ou comando
       ↓
src/rag_engine.py: stream_answer()
       ↓
src/rag_graph.py: executar o grafo LangGraph
  buscar → avaliar → responder, esclarecer ou reformular
     ↑                              ↓
     └──── nova busca, máximo 2 ─────┘
       ↓
terminal: resposta em fragmentos + tabela de fontes
```

O primeiro modelo (`nomic-embed-text`) representa textos para busca; o segundo (`llama3.2:3b`) escreve a resposta. A biblioteca LangChain conecta os componentes. O Chroma armazena e recupera os trechos. A interface Rich apenas apresenta os resultados.

O código usa LangGraph para controlar as decisões e LangChain para executar as operações. A avaliação de suficiência usa saída estruturada do modelo. Somente os trechos selecionados entram na geração. O estado é restrito a uma consulta: não há histórico persistente nem aprendizado com perguntas. Detalhes em [LangGraph: implementação e exemplos](LANGGRAPH_IMPLEMENTACAO.md).

## 3. Configuração

`src/rag_config.py` centraliza o diretório dos documentos e o caminho do banco. A prioridade do banco é:

1. Variável `RAG_CHROMA_DIR`, quando preenchida.
2. Arquivo `config/chroma_path.txt`.
3. Na ausência dos dois, `dados/chroma_db` na raiz do projeto.

Nesta máquina, use a configuração externa sem acentos já preenchida. A alternativa padrão não resolve a limitação de acentos no Windows.

## 4. Ordem sugerida para ler o código

| Ordem | Arquivo | O que observar |
|---|---|---|
| 1 | `src/rag_config.py` | Onde ficam documentos e banco |
| 2 | `src/ingest.py` | Como documentos viram trechos pesquisáveis |
| 3 | `src/rag_engine.py` | Como a pergunta vira busca e depois resposta |
| 4 | `src/rag_graph.py` | Como estado, avaliação e limite de duas buscas controlam a resposta |
| 5 | `src/chatbot_cli.py` | Como o usuário interage e vê as fontes |

## 5. Exercício para acompanhar o fluxo

Abra o chatbot, ative `/filtro soja`, `/fontes` e `/fluxo`, e pergunte `Qual é a origem da soja?`. Observe as etapas, os trechos e compare cada afirmação da resposta com as evidências exibidas. O filtro restringe a categoria de busca; `/fontes` e `/fluxo` mudam apenas a exibição. `/limpar` limpa a tela.

## 6. Onde guardar cada material novo

- Publicações que serão candidatas à base: `dados/documentos`.
- Textos para seu aprendizado, sem indexação automática: `docs/estudos`.
- Resultados de revisão: `docs/revisao`.
- Perguntas e evidências esperadas: `tests/avaliacao_perguntas.csv`.
- Código do aplicativo: `src`.

Os relatórios técnicos recebidos permanecem em `dados/documentos` porque já fazem parte do catálogo indexado. Separá-los da base agronômica é uma decisão posterior, com atualização controlada do índice.
