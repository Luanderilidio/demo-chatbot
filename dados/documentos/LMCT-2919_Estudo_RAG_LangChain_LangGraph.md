# Estudo LMCT-2919 — Preparação para Implementação do RAG
## LangChain + LangGraph aplicados ao Chatbot Agrícola Embrapa

**Ticket:** LMCT-2919 · Sprint 45 · Outubro 2026  
**Objetivo:** Preparar o material e entender como implementar o RAG  
**Referências oficiais:**  
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)  
- [Build a custom RAG agent with LangGraph](https://docs.langchain.com/oss/python/langgraph/agentic-rag)

---

## 1. Ferramentas Necessárias

### Stack completa para o nosso caso

```
Python 3.11+
│
├── LangChain          → orquestração de chains e prompts
├── LangGraph          → grafo de estados para o agente RAG
├── langchain-chroma   → integração com ChromaDB
├── langchain-huggingface → modelos de embedding locais
├── langchain-ollama   → integração com LLM local via Ollama
│
├── pdfplumber         → extração de texto de PDFs (melhor que pypdf para PT-BR)
├── pypdf              → fallback de extração de PDFs
├── tiktoken           → contagem de tokens para chunking
│
├── chromadb           → banco vetorial local (persiste em pasta)
├── sentence-transformers → modelo de embedding multilingual
│
├── fastapi            → API REST (quando formos expor o RAG)
└── uvicorn            → servidor ASGI para FastAPI
```

### Checklist de instalação

```bash
pip install langchain langchain-community langgraph \
            langchain-chroma langchain-huggingface langchain-ollama \
            pdfplumber pypdf tiktoken \
            chromadb sentence-transformers \
            fastapi uvicorn
```

### LLM local — Ollama (instalar separadamente)

```
# Instalar Ollama: https://ollama.com
ollama pull llama3.1        # modelo 8B (~4.7 GB)
ollama pull mistral         # alternativa 7B (~4.1 GB)
ollama pull nomic-embed-text # modelo de embedding local
```

> [!NOTE]
> Ollama roda o LLM como servidor local na porta 11434. Não precisa de GPU obrigatoriamente, mas é muito mais rápido com ela.

---

## 2. O que é RAG — conceito simplificado

### Analogia

> Imagine que você precisa responder a um produtor de soja sobre uma doença específica.  
> Sem RAG: você tenta lembrar tudo que já aprendeu (LLM "de cabeça").  
> Com RAG: você primeiro **consulta a biblioteca** (os PDFs da Embrapa) e **usa o que encontrou** para formular a resposta.

### Por que isso é melhor?

| Sem RAG | Com RAG |
|---------|---------|
| Responde "de cabeça" — pode alucinar | Ancora a resposta em documentos reais |
| Conhecimento fixo no treino | Base atualizável sem retreinar |
| Não cita fonte | Pode citar documento + página |
| Sabe de tudo, pouco de nada específico | Especializado no corpus carregado |

---

## 3. Como o RAG funciona — passo a passo

### Fase 1: Construção da Base (offline, faz uma vez)

```
PDFs Embrapa
    │
    ▼ (1) Extração de texto
Texto por página
    │
    ▼ (2) Chunking — dividir em pedaços de ~600 caracteres
["Pergunta: Como controlar ferrugem asiática da soja?
  Resposta: A ferrugem asiática é causada pelo fungo..."]
    │
    ▼ (3) Embedding — transformar texto em números
[0.23, -0.87, 0.41, ..., 0.09]  ← vetor de 384 dimensões
    │
    ▼ (4) Persistir no ChromaDB
Banco vetorial salvo em disco
```

### Fase 2: Resposta em tempo real (toda consulta)

```
Usuário: "Como tratar ferrugem na soja?"
    │
    ▼ (1) Embedding da pergunta → vetor
    │
    ▼ (2) Busca semântica no ChromaDB
      "Quais chunks são mais parecidos com esse vetor?"
      → retorna top-5 trechos mais relevantes
    │
    ▼ (3) Montar o prompt:
      SISTEMA: Você é consultor agrícola da Embrapa...
      CONTEXTO: [trecho 1] [trecho 2] [trecho 3]...
      PERGUNTA: Como tratar ferrugem na soja?
    │
    ▼ (4) LLM gera resposta baseada no contexto
    │
    ▼ (5) Retornar resposta + citar fontes
```

---

## 4. O que é LangChain

**LangChain** é um framework Python que facilita construir aplicações com LLMs, fornecendo:

| Componente | O que faz | Nosso uso |
|-----------|-----------|-----------|
| `Document Loaders` | Carrega PDFs, textos, etc. | Carregar PDFs Embrapa |
| `Text Splitters` | Divide texto em chunks | Chunking dos documentos |
| `Embeddings` | Interface para modelos de embedding | HuggingFace local |
| `Vector Stores` | Interface para bancos vetoriais | ChromaDB |
| `Retrievers` | Busca documentos relevantes | Busca semântica |
| `Chains` | Liga componentes em sequência | Pipeline RAG simples |
| `Prompts` | Templates de prompt reutilizáveis | System prompt agrícola |

### Exemplo mínimo de chain RAG em LangChain

```python
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain.chains import RetrievalQA

# 1. Carregar base vetorial existente
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
vectorstore = Chroma(
    collection_name="embrapa_conhecimento",
    embedding_function=embeddings,
    persist_directory="./data/vectorstore"
)

# 2. Criar retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# 3. LLM local
llm = OllamaLLM(model="llama3.1")

# 4. Chain RAG
chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)

# 5. Responder
resposta = chain.invoke("Como controlar ferrugem asiática na soja?")
print(resposta)
```

> ⚠️ Esse é o RAG **linear e simples**. O LangGraph permite ir além com lógica condicional.

---

## 5. O que é LangGraph — e por que é melhor que Chain simples

**LangGraph** é uma extensão do LangChain que permite construir **agentes com lógica de grafo de estados**.

### Diferença fundamental

```
LangChain Chain (linear):
  Pergunta → Retrieve → Generate → Resposta
  (sempre o mesmo caminho, sem inteligência)

LangGraph (grafo de estados):
  Pergunta
    → Retrieve
        → Documentos relevantes? → SIM → Generate → Resposta
                                 → NÃO → Reformular pergunta → Retrieve (retry)
                                        → Ainda sem resultado → Resposta: "Não encontrei"
```

### Conceitos-chave do LangGraph

| Conceito | Analogia | Descrição |
|----------|----------|-----------|
| **State** | Memória da conversa | Dicionário Python que circula pelo grafo e vai sendo atualizado |
| **Node** | Etapa do processo | Função Python que recebe o State, faz algo, retorna o State atualizado |
| **Edge** | Caminho entre etapas | Define qual nó vem depois; pode ser condicional |
| **Graph** | O fluxo completo | Conjunto de nós + arestas compilado em um agente executável |
| **Conditional Edge** | Bifurcação | Decide qual caminho seguir com base no State atual |

### Diagrama do agente RAG com LangGraph

```
                    ┌─────────────────────────────┐
                    │         START               │
                    │  { pergunta: "...", docs: [] }│
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │   retrieve_documents        │
                    │  (busca no ChromaDB)        │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │   grade_documents           │
                    │  (os docs são relevantes?)  │
                    └──────┬──────────────┬───────┘
                           │              │
                    relevantes?      não relevantes?
                           │              │
              ┌────────────▼──┐    ┌──────▼──────────────┐
              │   generate    │    │  rewrite_query      │
              │ (LLM responde)│    │ (reformula pergunta)│
              └────────────┬──┘    └──────┬──────────────┘
                           │              │
                    ┌──────▼──┐           │ (volta pro retrieve)
                    │   END   │◄──────────┘
                    └─────────┘
```

### Pseudocódigo do grafo LangGraph para o nosso caso

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

# 1. Definir o State (o que circula pelo grafo)
class RAGState(TypedDict):
    pergunta: str
    documentos: List[str]
    resposta: str
    tentativas: int

# 2. Definir os nós (funções)
def retrieve(state: RAGState) -> RAGState:
    """Busca documentos relevantes na base Embrapa."""
    docs = vectorstore.similarity_search(state["pergunta"], k=5)
    return {**state, "documentos": docs}

def avaliar_relevancia(state: RAGState) -> str:
    """Decide se os documentos são suficientes."""
    if len(state["documentos"]) >= 2 and state["tentativas"] < 3:
        return "gerar_resposta"
    elif state["tentativas"] >= 3:
        return "sem_resultado"
    else:
        return "reformular"

def gerar_resposta(state: RAGState) -> RAGState:
    """Usa o LLM para gerar resposta com base nos documentos."""
    contexto = "\n\n".join([d.page_content for d in state["documentos"]])
    prompt = f"Contexto:\n{contexto}\n\nPergunta: {state['pergunta']}"
    resposta = llm.invoke(prompt)
    return {**state, "resposta": resposta}

def reformular_pergunta(state: RAGState) -> RAGState:
    """Reformula a pergunta para melhorar a busca."""
    nova_pergunta = llm.invoke(f"Reformule: {state['pergunta']}")
    return {**state, "pergunta": nova_pergunta, "tentativas": state["tentativas"] + 1}

# 3. Construir o grafo
grafo = StateGraph(RAGState)
grafo.add_node("retrieve", retrieve)
grafo.add_node("gerar_resposta", gerar_resposta)
grafo.add_node("reformular", reformular_pergunta)

grafo.set_entry_point("retrieve")
grafo.add_conditional_edges("retrieve", avaliar_relevancia, {
    "gerar_resposta": "gerar_resposta",
    "reformular": "reformular",
    "sem_resultado": END,
})
grafo.add_edge("gerar_resposta", END)
grafo.add_edge("reformular", "retrieve")  # volta pro retrieve

agente = grafo.compile()

# 4. Usar
resultado = agente.invoke({
    "pergunta": "Como controlar ferrugem asiática na soja?",
    "documentos": [],
    "resposta": "",
    "tentativas": 0,
})
print(resultado["resposta"])
```

---

## 6. Como tudo se encaixa no nosso projeto

```
┌──────────────────────────────────────────────────────────┐
│  PDFs Embrapa (soja, arroz, milho, hortaliças)           │
│              ↓  (pdfplumber)                             │
│  Texto extraído e limpo                                  │
│              ↓  (LangChain Text Splitter)                │
│  Chunks com metadados                                    │
│              ↓  (HuggingFace Embeddings — local)         │
│  Vetores numéricos                                       │
│              ↓  (ChromaDB)                               │
│  ┌──────────────────────┐                               │
│  │  BASE CIENTÍFICA     │  ← nossa base vetorial própria │
│  │  EMBRAPA             │                               │
│  └──────────────────────┘                               │
│              ↓  (LangGraph RAG Agent)                    │
│  retrieve → grade → generate → resposta                 │
│              ↓  (Ollama — LLM local)                     │
│  Resposta + citação da fonte Embrapa                    │
│              ↓  (FastAPI — sprint futura)                │
│  Endpoint REST consumido pelo Chatbot                   │
└──────────────────────────────────────────────────────────┘
```

---

## 7. Perguntas que o estudo do LMCT-2919 responde

| Pergunta do ticket | Resposta |
|-------------------|----------|
| O que é necessário em ferramentas? | LangChain, LangGraph, ChromaDB, HuggingFace Embeddings, Ollama (ver seção 1) |
| Como implementar o RAG? | Duas fases: ingestão offline + consulta em tempo real (ver seção 3) |
| O que é LangGraph? | Framework de agentes com grafo de estados — mais robusto que chain linear (ver seção 5) |
| Precisamos de GPU? | Para embedding: não. Para LLM (geração): sim, mas Ollama funciona em CPU também |
| Quanto custa? | Tudo 100% open source e local — custo só de infraestrutura (HPC Lenovo) |
| Atualização do conhecimento? | Basta reingerir os PDFs novos — sem retreinamento |

---

## 8. Links de Referência

| Recurso | URL |
|---------|-----|
| LangGraph overview | https://docs.langchain.com/oss/python/langgraph/overview |
| Custom RAG agent com LangGraph | https://docs.langchain.com/oss/python/langgraph/agentic-rag |
| LangChain RAG tutorial | https://python.langchain.com/docs/tutorials/rag/ |
| ChromaDB docs | https://docs.trychroma.com/ |
| Sentence Transformers (embeddings) | https://www.sbert.net/ |
| Ollama (LLM local) | https://ollama.com/ |
| RAGAS (avaliação de RAG) | https://docs.ragas.io/ |

---

*Estudo produzido para LMCT-2919 · Sprint 45 · Outubro 2026*  
*Lenovo HPC — Projeto Chatbot Agrícola*
