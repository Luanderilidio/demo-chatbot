# Protótipo de chatbot agronômico com RAG

O programa prepara documentos para busca e usa os trechos recuperados para apoiar respostas de um modelo local.

**API meteorológica simulada:** abra `iniciar_api.bat` e depois `iniciar_chatbot.bat`. Pergunte “Qual é a temperatura hoje da minha fazenda?” ou “Quais as condições climáticas hoje? Posso plantar a soja?”. O primeiro consulta a API; o segundo combina medições e documentos. Consulte [o guia da API, dados e exemplos](docs/API_METEOROLOGICA.md). Para renovar dados fictícios antigos, pare a API, execute `renovar_dados_demo.bat` e reinicie a API.

No PowerShell, execute os atalhos com ` .\iniciar_api.bat` e ` .\iniciar_chatbot.bat`. Para parar a API inclusive em segundo plano, use ` .\parar_api.bat`. A umidade do solo é mantida apenas no plano de plantio; o servidor atualizado recarrega edições do JSON automaticamente.

O fluxo de consulta agora usa **LangGraph**: busca → avaliação das evidências → resposta, esclarecimento ou uma nova busca (máximo de duas). Leia [a implementação com exemplos](docs/LANGGRAPH_IMPLEMENTACAO.md).

## Mapa das pastas

```text
drive-download-20261012T142134Z-1-001/
├── README.md                    ← comece aqui
├── chatbot_cli.py               ← comando para iniciar a conversa
├── iniciar_chatbot.bat          ← atalho que usa .venv312
├── ingest.py                    ← comando de preparação da base
├── requirements.txt             ← bibliotecas necessárias
├── src/                         ← implementação Python
│   ├── chatbot_cli.py           ← interface e comandos
│   ├── rag_engine.py            ← busca, contexto e resposta
│   ├── rag_graph.py             ← estado, decisões e limite de buscas
│   ├── ingest.py                ← extração e indexação
│   └── rag_config.py            ← caminhos compartilhados
├── config/
│   └── chroma_path.txt          ← localização do banco ativo
├── dados/
│   ├── documentos/             ← 7 PDFs e 2 relatórios Markdown
│   ├── catalogo_documentos.csv  ← modelo de catálogo ainda a preencher
│   └── backup/chroma_db/        ← base original recebida; não é a ativa
├── docs/
│   ├── FLUXO_DO_PROJETO.md      ← percurso de uma pergunta e ordem de leitura
│   ├── estudos/                ← guia de RAG e aula prática
│   ├── revisao/                ← análise técnica anterior
│   └── referencias/            ← instruções originais recebidas
├── scripts/                    ← auxiliares de instalação e execução
├── tests/
│   ├── verificar_ingestao.py    ← reprodução das falhas já identificadas
│   ├── test_rag_graph.py        ← testes do grafo com serviços simulados
│   ├── executar_exemplos_langgraph.py ← exemplos reais com Ollama
│   └── avaliacao_perguntas.csv  ← modelo para avaliar respostas
├── .venv312/                   ← ambiente Python em uso
└── .venv/                      ← ambiente anterior, preservado
```

## Executar

Na pasta deste README, com o Ollama disponível:

```powershell
.\.venv312\Scripts\python.exe chatbot_cli.py
```

Ou abra `iniciar_chatbot.bat`. Se já ativou `.venv312`, continua válido:

```powershell
python chatbot_cli.py
```

Os arquivos de entrada na raiz encaminham a execução para `src`. Não execute `src/chatbot_cli.py` diretamente; ele é parte de um pacote. Também é possível usar `python -m src.chatbot_cli` a partir da raiz.

No chatbot, `/fluxo` mostra as etapas executadas e `/fontes` mostra as evidências selecionadas. Se o chatbot pedir um esclarecimento, envie a pergunta completa com o detalhe solicitado: cada consulta tem estado próprio e não há histórico persistente.

## Verificar o LangGraph

```powershell
.\.venv312\Scripts\python.exe -m unittest discover -s tests -p "test_rag_graph.py" -v
```

Esses testes executam o grafo real com busca e modelos simulados. Para os exemplos com o banco e os modelos locais:

```powershell
.\.venv312\Scripts\python.exe -m tests.executar_exemplos_langgraph
```

Os resultados são salvos em `tests/resultados_langgraph.json`. Respostas reais variam e a avaliação do modelo não substitui revisão agronômica.

## Banco ativo

`config/chroma_path.txt` aponta para:

```text
C:\Users\luand_trlroan\Documents\RAG_Dados\prototipo_20261012\chroma_db
```

Esse caminho externo sem acentos é necessário nesta instalação para evitar o erro de abertura do índice HNSW. A variável `RAG_CHROMA_DIR`, se definida, tem prioridade sobre o arquivo. Em outro computador, configure um caminho sem acentos e copie uma base válida para ele.

`dados/backup/chroma_db` é a cópia recebida do colega, preservada para referência. Não use esse caminho com acentos como banco ativo nesta instalação.

## Preparação e estudo

Leia [o fluxo](docs/FLUXO_DO_PROJETO.md), o [guia de estudo](docs/estudos/GUIA_RAG_AGRONOMICO.md) e a [análise técnica](docs/revisao/ANALISE_DO_PROTOTIPO.md).

A base ativa já está preenchida. A reorganização não reindexou documentos. A lista `DOC_METADATA_MAP`, em `src/ingest.py`, continua selecionando os arquivos: o manual de hortaliças tradicionais está disponível, mas ainda não faz parte dessa lista. Os dois relatórios sobre IA continuam entre as fontes selecionadas.

As falhas de retomada/atualização identificadas na revisão ainda precisam ser corrigidas antes de uma nova ingestão. `tests/verificar_ingestao.py` reproduz essas falhas com serviços simulados; seu sucesso significa que o diagnóstico foi reproduzido, não que a ingestão foi corrigida.

As instruções em `docs/referencias` são históricas. Use este README para os caminhos e comandos atuais.
