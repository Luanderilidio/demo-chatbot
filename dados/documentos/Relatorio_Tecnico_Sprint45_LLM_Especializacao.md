# Relatório Técnico — Sprint 45
## Estratégias para Incorporação de Conhecimento de Domínio em LLMs para Chatbot Agrícola

**Projeto:** Chatbot Agrícola — Lenovo HPC  
**Sprint:** 45  
**Data:** Outubro / 2026  
**Status:** Investigação Técnica (Não Produtivo)  
**Classificação:** Uso Interno  

---

## 1. Objetivo

Este relatório apresenta a investigação técnica sobre estratégias para incorporar conhecimento especializado de domínio agrícola em modelos de linguagem de grande escala (LLMs) utilizados pelo chatbot. O estudo foca em avaliar alternativas arquiteturais, custos, manutenção, desempenho e governança, produzindo recomendações objetivas para os próximos refinamentos do produto.

> [!NOTE]
> Este documento **não** resulta em implementação em produção, treinamento de modelo ou alteração do comportamento atual do chatbot. Trata-se de material de suporte à tomada de decisão.

---

## 2. Contexto e Base de Conhecimento Disponível

Durante a Sprint 45, foram identificados os seguintes documentos técnicos como candidatos à base de conhecimento do chatbot:

| Documento | Fonte | Escopo | Páginas |
|-----------|-------|--------|---------|
| 500 Perguntas — Soja | Embrapa | Cultivo, pragas, manejo | ~300 |
| 500 Perguntas — Arroz | Embrapa | Cultivo, irrigação, colheita | ~300 |
| 500 Perguntas — Milho | Embrapa Milho e Sorgo | Produção, adubação, mecanização | 333 |
| 500 Perguntas — Hortaliças | Embrapa Hortaliças | Cultivo de hortaliças diversas | 243 |
| 500 Perguntas — Pós-Colheita de Hortaliças | Embrapa Hortaliças | Conservação, logística, qualidade | 256 |
| 50 Hortaliças — Como Comprar, Conservar e Consumir | Embrapa | Guia de consumo e conservação | — |

Esses documentos, produzidos pela **Embrapa** (Empresa Brasileira de Pesquisa Agropecuária), representam um corpus técnico-científico de alta confiabilidade, estruturado no formato de perguntas e respostas — formato naturalmente adequado para alimentar um chatbot especializado.

---

## 3. Abordagens Técnicas Investigadas

### 3.1 RAG — Retrieval Augmented Generation

**Descrição:**  
RAG é uma arquitetura que combina um modelo de recuperação de documentos com um LLM gerador. Em vez de treinar o modelo com todo o conhecimento do domínio, o sistema recupera trechos relevantes de uma base de conhecimento externa e os injeta no contexto do modelo antes de gerar a resposta.

**Fluxo Arquitetural Simplificado:**

```
[Usuário] 
    ↓ pergunta
[Módulo de Embedding / Query Encoder]
    ↓ vetor da consulta
[Base Vetorial (ex: Chroma, Qdrant, FAISS)]
    ↓ top-k chunks mais relevantes
[Prompt Enrichment: contexto + pergunta do usuário]
    ↓
[LLM (ex: Llama 3, Mistral, Gemma)]
    ↓ resposta gerada com embasamento documental
[Usuário]
```

**Requisitos de Dados:**
- Corpus textual dos documentos Embrapa (PDFs já disponíveis)
- Pipeline de ingestão: extração de texto → chunking → geração de embeddings → armazenamento
- Modelo de embedding (ex: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`)

**Vantagens:**
- ✅ Não requer retreinamento do modelo base
- ✅ Atualização da base de conhecimento sem downtime
- ✅ Alta rastreabilidade: resposta pode citar o documento fonte
- ✅ Reduz alucinações ao ancorar a resposta em documentos reais
- ✅ Compatível com modelos open source (requisito Lenovo)
- ✅ Custo operacional controlado

**Limitações:**
- ⚠️ Qualidade da resposta depende da qualidade do chunking e do embedding
- ⚠️ Pode recuperar trechos irrelevantes se a query for ambígua
- ⚠️ Latência adicional pela etapa de recuperação (~100–500ms)
- ⚠️ Custo de infraestrutura para manter a base vetorial

**Riscos:**
- Chunking inadequado pode fragmentar contexto essencial
- Documentos desatualizados podem introduzir informações obsoletas

---

### 3.2 Fine-tuning Supervisionado (SFT)

**Descrição:**  
O fine-tuning consiste em continuar o treinamento de um modelo pré-treinado usando pares de (instrução, resposta) do domínio agrícola, adaptando os pesos do modelo ao vocabulário e padrões de resposta desejados.

**Fluxo Arquitetural Simplificado:**

```
[Dataset de Fine-tuning]
(pares pergunta-resposta extraídos dos documentos Embrapa)
    ↓
[Modelo Base (ex: Llama 3.1 8B / Mistral 7B)]
    ↓ fine-tuning com LoRA / QLoRA
[Modelo Especializado Agrícola]
    ↓ deploy no HPC Lenovo
[Chatbot com conhecimento embutido nos pesos]
```

**Requisitos de Dados:**
- Dataset estruturado em formato JSONL: `{"instruction": "...", "output": "..."}`
- Mínimo recomendado: 1.000–10.000 pares de alta qualidade
- Os 500 pares de perguntas/respostas por cultura são candidatos naturais
- Curadoria e validação humana dos pares de dados

**Vantagens:**
- ✅ Resposta mais fluída e natural ao domínio específico
- ✅ Menor latência em inferência (sem etapa de recuperação)
- ✅ Pode capturar nuances do vocabulário técnico agrícola

**Limitações:**
- ⚠️ Requer curadoria intensiva do dataset de treino
- ⚠️ Retreinamento necessário para incorporar novo conhecimento
- ⚠️ Custo elevado de GPU para treinamento
- ⚠️ Risco de catastrophic forgetting (perda de capacidades gerais)
- ⚠️ Menor rastreabilidade: difícil identificar de onde vem cada resposta

**Riscos:**
- Dataset de baixa qualidade resulta em modelo com vieses
- Modelo pode "memorizar" respostas em vez de raciocinar

---

### 3.3 Prompt Engineering e System Prompts Especializados

**Descrição:**  
Consiste em estruturar cuidadosamente o prompt do sistema (system prompt) para guiar o comportamento do LLM sem alterar seus pesos. Pode incluir instruções de persona, escopo de atuação, formato de resposta e exemplos few-shot.

**Fluxo Arquitetural Simplificado:**

```
[System Prompt Especializado]
├── Persona: "Você é um consultor agrícola..."
├── Restrições: "Responda apenas sobre culturas agrícolas..."
├── Formato: "Sempre cite a fonte consultada..."
└── Exemplos few-shot (3–5 pares Q&A)
    ↓
[LLM Base]
    ↓
[Resposta Contextualizada]
```

**Requisitos de Dados:**
- Exemplos representativos do domínio (few-shot examples)
- Definição clara do escopo e comportamento esperado
- Iteração e avaliação contínua do prompt

**Vantagens:**
- ✅ Implementação imediata e baixo custo
- ✅ Fácil de iterar e ajustar
- ✅ Não requer infraestrutura adicional
- ✅ Complementar a qualquer outra abordagem

**Limitações:**
- ⚠️ Contexto limitado pelo tamanho da janela do modelo
- ⚠️ Não escala para grandes volumes de conhecimento
- ⚠️ Comportamento pode ser inconsistente entre sessões
- ⚠️ Depende fortemente da capacidade de seguir instruções do modelo base

**Riscos:**
- Prompt injection por usuários maliciosos
- Perda de eficácia com modelos menores

---

### 3.4 Bases Vetoriais e Busca Semântica

**Descrição:**  
Componente de infraestrutura central para abordagens RAG. Bases vetoriais armazenam representações numéricas (embeddings) de documentos e permitem busca por similaridade semântica, indo além da busca por palavras-chave.

**Principais soluções open source avaliadas:**

| Solução | Tipo | Destaque | Compatibilidade HPC |
|---------|------|----------|---------------------|
| **FAISS** (Meta) | Biblioteca | Alta performance, local | ✅ Excelente |
| **Chroma** | Servidor leve | Fácil integração, persistência | ✅ Boa |
| **Qdrant** | Servidor dedicado | Filtros avançados, payload | ✅ Boa |
| **Weaviate** | Servidor completo | GraphQL, multimodal | ⚠️ Requer infra dedicada |
| **Milvus** | Distribuído | Alta escala | ⚠️ Complexo para iniciar |

**Fluxo de Ingestão:**

```
[PDF Embrapa]
    ↓ extração de texto (pypdf / pdfplumber)
[Texto Bruto]
    ↓ chunking (ex: 512 tokens, sobreposição de 50)
[Chunks Textuais]
    ↓ modelo de embedding multilingual
[Vetores (ex: 384 ou 768 dimensões)]
    ↓ armazenamento com metadados (fonte, cultura, capítulo)
[Base Vetorial]
```

**Requisitos de Infraestrutura:**
- RAM mínima: 8GB para corpus atual (~1.400 páginas)
- Storage: ~500MB para vetores (embedding 384-dim)
- GPU: opcional para embedding, necessária para inferência do LLM

---

### 3.5 Combinação de Dados Estruturados e Não Estruturados

**Descrição:**  
O corpus documental pode ser enriquecido com dados estruturados (tabelas de culturas, tabelas de adubação, calendários agrícolas) combinados com os textos não estruturados dos PDFs.

**Fluxo Arquitetural:**

```
[Dados Estruturados]           [Dados Não Estruturados]
(tabelas, planilhas, APIs)     (PDFs, artigos, manuais)
        ↓                              ↓
[Transformação / ETL]          [Extração e Chunking]
        ↓                              ↓
        └──────────┬───────────────────┘
                   ↓
           [Base Vetorial Unificada]
                   ↓
               [RAG + LLM]
                   ↓
            [Resposta ao Usuário]
```

**Vantagens:**
- ✅ Respostas mais completas e precisas
- ✅ Permite responder perguntas quantitativas (dosagem, época de plantio)

**Limitações:**
- ⚠️ Maior complexidade de ETL e manutenção
- ⚠️ Dados estruturados exigem padronização e governança

---

## 4. Análise Comparativa

| Critério | RAG | Fine-tuning | Prompt Engineering | Combinação Estruturada |
|----------|-----|-------------|-------------------|----------------------|
| **Custo de Implementação** | Médio | Alto | Baixo | Alto |
| **Custo Operacional** | Médio | Baixo (pós-treino) | Mínimo | Médio-Alto |
| **Atualização do Conhecimento** | ✅ Fácil | ❌ Retreinamento | ✅ Imediata | ✅ Moderada |
| **Rastreabilidade** | ✅ Alta | ❌ Baixa | ⚠️ Parcial | ✅ Alta |
| **Redução de Alucinações** | ✅ Alta | ⚠️ Moderada | ⚠️ Moderada | ✅ Alta |
| **Escalabilidade** | ✅ Alta | ⚠️ Limitada | ❌ Baixa | ✅ Alta |
| **Compatibilidade Open Source** | ✅ Total | ✅ Total | ✅ Total | ✅ Total |
| **Governança de Dados** | ✅ Boa | ⚠️ Complexa | ✅ Simples | ⚠️ Complexa |
| **Tempo para MVP** | Semanas | Meses | Dias | Meses |
| **Requer GPU HPC** | Parcial | ✅ Sim | ❌ Não | Parcial |

---

## 5. Dependências Técnicas e de Infraestrutura

### 5.1 Para RAG

```
- Python 3.10+
- LangChain ou LlamaIndex (orquestração RAG)
- pypdf / pdfplumber (extração de texto)
- sentence-transformers (geração de embeddings)
- FAISS ou Chroma (base vetorial)
- LLM local: Llama 3.1, Mistral 7B ou Gemma 2 (via Ollama ou vLLM)
- Hardware: CPU adequado para embedding; GPU para inferência
```

### 5.2 Para Fine-tuning

```
- PyTorch + CUDA
- Hugging Face Transformers + PEFT (LoRA/QLoRA)
- Datasets (Hugging Face)
- GPU com mínimo 16GB VRAM (recomendado: 40GB+ para modelos 13B+)
- Pipeline de curadoria de dados (anotação humana)
- MLflow ou W&B para rastreamento de experimentos
```

### 5.3 Para Base Vetorial em Produção

```
- Chroma ou Qdrant (modo servidor)
- Pipeline de atualização incremental (batch ingestão)
- Monitoramento de qualidade de recuperação (MRR, NDCG)
- Backup e versionamento da base vetorial
```

---

## 6. Considerações de Governança e Segurança

> [!IMPORTANT]
> Os documentos Embrapa são publicações públicas, porém em produção devem ser observados:

- **Licenciamento:** Verificar termos de redistribuição das publicações Embrapa para uso em sistema comercial/interno
- **Rastreabilidade:** Toda resposta gerada deve poder ser associada ao(s) documento(s) fonte utilizados
- **Controle de acesso:** Documentos sensíveis (dados proprietários futuros) devem ter controle de ACL na base vetorial
- **Privacidade dos dados de usuário:** Perguntas dos usuários não devem ser usadas para retreinamento sem consentimento explícito
- **Auditoria:** Logs de consulta e recuperação devem ser mantidos para auditoria
- **Atualização:** Documentos desatualizados devem ser versionados e retirados de circulação de forma controlada

---

## 7. Estratégias para Redução de Alucinações

| Estratégia | Aplicável em | Impacto |
|------------|-------------|---------|
| Ancoragem documental (RAG) | RAG | Alto |
| Temperature baixa (0.1–0.3) | Todas | Médio |
| Instrução de "não sabe" no system prompt | Prompt Eng. | Médio |
| Re-ranking dos documentos recuperados | RAG | Alto |
| Verificação de fatos pós-geração (self-check) | Todas | Médio |
| Limitar o modelo a responder apenas com base no contexto | RAG | Alto |

---

## 8. Recomendações para Evolução Futura

> [!TIP]
> A recomendação principal é adotar **RAG como arquitetura base**, com **Prompt Engineering como complemento imediato**.

### Fase 1 — Curto Prazo (1–2 Sprints)
- Implementar pipeline de ingestão dos PDFs Embrapa (chunking + embedding)
- Configurar base vetorial FAISS ou Chroma (local, no HPC)
- Criar system prompt especializado para chatbot agrícola
- Validar qualidade de recuperação com perguntas-teste dos documentos

### Fase 2 — Médio Prazo (3–6 Sprints)
- Evoluir para Chroma/Qdrant em modo servidor com atualização incremental
- Adicionar dados estruturados (tabelas, calendários agrícolas)
- Implementar re-ranking dos resultados recuperados
- Avaliar métricas de qualidade: RAGAS, MRR, Faithfulness

### Fase 3 — Longo Prazo (futura sprint de IA)
- Avaliar fine-tuning de modelo especializado agrícola (usando corpus acumulado)
- Explorar modelos multilinguais otimizados para português
- Considerar integração com APIs de dados agrícolas em tempo real

### Arquitetura Recomendada (RAG + Prompt Engineering)

```
┌─────────────────────────────────────────────────────────────┐
│                    CHATBOT AGRÍCOLA LENOVO                  │
├─────────────────────────────────────────────────────────────┤
│  [Interface de Usuário]                                     │
│       ↓ pergunta do produtor                               │
│  [Query Encoder] → embedding da pergunta                    │
│       ↓                                                     │
│  [Base Vetorial - Corpus Embrapa]                           │
│  (FAISS/Chroma + metadados: cultura, documento, página)     │
│       ↓ top-k chunks relevantes                             │
│  [Prompt Builder]                                           │
│  ├── System Prompt (persona + regras)                       │
│  ├── Contexto Recuperado (trechos Embrapa)                  │
│  └── Pergunta do Usuário                                    │
│       ↓                                                     │
│  [LLM Local - Llama 3.1 / Mistral (via vLLM/Ollama)]       │
│       ↓ resposta + citação da fonte                         │
│  [Usuário] ← resposta contextualizada e rastreável          │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Riscos e Impedimentos Mapeados

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Alinhamento de segurança e privacidade | Média | Alto | Envolver time de segurança antes da implementação |
| Dificuldade de comparação de custos entre abordagens | Alta | Médio | PoC comparativo com métricas definidas previamente |
| Qualidade de extração dos PDFs (encoding) | Alta | Médio | Usar pdfplumber + correção de encoding UTF-8 |
| Chunking inadequado fragmentando contexto | Média | Alto | Testar diferentes estratégias (fixed, semantic, recursive) |
| Modelo base com suporte limitado ao português | Média | Alto | Priorizar modelos multilinguais ou treinados em PT-BR |

---

## 10. Conclusão

A investigação técnica realizada nesta sprint identificou **RAG (Retrieval Augmented Generation)** como a abordagem mais adequada para o contexto do chatbot agrícola Lenovo, considerando:

- ✅ Compatibilidade com requisitos open source
- ✅ Atualização de conhecimento sem retreinamento
- ✅ Alta rastreabilidade das respostas
- ✅ Redução efetiva de alucinações
- ✅ Escalabilidade para novos domínios agrícolas
- ✅ Custo-benefício favorável no curto e médio prazo

O corpus Embrapa disponível (aproximadamente 1.400 páginas em 6 documentos) constitui uma base de conhecimento de alta qualidade, com estrutura de perguntas e respostas naturalmente alinhada ao chatbot.

**Fine-tuning** permanece como opção complementar para o longo prazo, após acúmulo de dados de interação reais com usuários produtores.

**Prompt Engineering** deve ser adotado imediatamente como primeira camada de especialização, independentemente da abordagem de recuperação escolhida.

---

## Referências Bibliográficas

- **Embrapa Hortaliças.** 500 Perguntas, 500 Respostas: O Produtor Pergunta, a Embrapa Responde — Hortaliças. Brasília: Embrapa Informação Tecnológica, 2009. 243p.
- **Embrapa Milho e Sorgo.** 500 Perguntas, 500 Respostas: O Produtor Pergunta, a Embrapa Responde — Milho. Brasília: Embrapa Informação Tecnológica, 2011. 333p.
- **Embrapa Hortaliças.** 500 Perguntas, 500 Respostas: Pós-Colheita de Hortaliças. Brasília: Embrapa Informação Tecnológica, 2011. 256p.
- **Embrapa.** 500 Perguntas, 500 Respostas — Soja. Embrapa Soja.
- **Embrapa.** 500 Perguntas, 500 Respostas — Arroz. Embrapa.
- **Embrapa.** 50 Hortaliças: Como Comprar, Conservar e Consumir. Embrapa.
- **Lewis, P. et al.** Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS 2020.
- **Hu, E. et al.** LoRA: Low-Rank Adaptation of Large Language Models. ICLR 2022.

---

*Documento produzido pela equipe técnica — Sprint 45 / Outubro 2026*  
*Lenovo HPC — Projeto Chatbot Agrícola*
