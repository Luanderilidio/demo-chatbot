# RAG para um chatbot agronômico

Material inicial de estudo e planejamento — 12/10/2026.

Nota: este roteiro foi escrito antes de receber o protótipo. Já existem documentos e uma base indexada; veja o [README atual](../../README.md). O catálogo está em `dados/catalogo_documentos.csv` e o modelo de avaliação em `tests/avaliacao_perguntas.csv`, relativos à raiz do projeto.

Para começar com um exercício sem instalação, consulte [Aula 1 — Do documento à resposta verificável](AULA_01_RAG_NA_PRATICA.md). Ela inclui uma consulta resolvida, casos sem evidência, um fluxo proposto e perguntas com gabarito.

Situação: a pasta estava vazia. Este guia prepara o trabalho; ainda não há documentos agronômicos processados, índice ou chatbot implementado. As escolhas abaixo são propostas para um primeiro experimento, ajustáveis ao seu nível de Python e aos seus documentos.

## 1. Entender o mecanismo

RAG significa geração aumentada por recuperação. Antes de escrever uma resposta, o sistema busca informações em uma base e entrega os trechos encontrados ao modelo de linguagem. Isso não treina novamente o modelo. Atualizar a base permite consultar novos materiais, mas não garante que a busca ou a resposta estejam corretas.

Há duas etapas separadas:

**Preparação:** documentos → extração de conteúdo → trechos com identificação da origem → representações numéricas → índice de busca.

**Consulta:** pergunta → busca de trechos → seleção de evidências → modelo escreve a resposta → apresentação das fontes.

Um embedding é uma representação numérica do texto usada para comparar proximidade de significado. Um chunk é um trecho recuperável. Metadados são informações que acompanham esse trecho, como título, página e cultura. O retriever é o componente que faz a busca. O modelo de linguagem transforma pergunta e evidências em resposta.

Exemplo de funcionamento, sem afirmar uma recomendação técnica: alguém pergunta quais condições favorecem uma doença de uma cultura. O sistema identifica a cultura e a doença, busca os trechos correspondentes e responde com as condições descritas nas fontes. Se a fonte trata de outra cultura ou não contém a informação, o chatbot precisa explicitar essa limitação ou pedir esclarecimentos.

Referência: [Recuperação e arquiteturas RAG](https://docs.langchain.com/oss/python/deepagents/retrieval).

## 2. O papel das ferramentas

| Componente | Proposta inicial | Para que serve |
|---|---|---|
| Linguagem e ambiente | Python, ambiente virtual e editor | Escrever e executar cada etapa isoladamente |
| Integração | LangChain | Conectar documentos, busca e modelos |
| Extração | Leitor compatível com o formato; OCR quando necessário | Transformar conteúdo em texto verificável |
| Divisão | langchain-text-splitters | Criar trechos preservando significado e origem |
| Embeddings | Um modelo com desempenho avaliado em português | Representar documentos e perguntas para busca |
| Índice inicial | InMemoryVectorStore | Experimentar em uma sessão, sem infraestrutura de banco |
| Persistência, na etapa seguinte | Chroma local | Manter o índice entre execuções |
| Geração | Um modelo de linguagem por API ou local | Produzir a resposta a partir dos trechos |
| Fluxo com decisões | LangGraph, depois do RAG básico | Controlar etapas, estado e caminhos condicionais |
| Inspeção e avaliação | Registros locais; LangSmith opcional | Investigar buscas, respostas, tempo e custo |

LangChain oferece componentes e integrações. LangGraph controla o fluxo: o estado guarda informações do atendimento, os nós executam etapas e as arestas determinam o próximo passo. É possível usar LangGraph sem LangChain. Fonte: [Visão geral do LangGraph](https://docs.langchain.com/oss/python/langgraph/overview).

O tutorial fornecido usa um índice em memória, embeddings e um modelo por API. Para acompanhá-lo, os pacotes estão na seção Setup da [documentação oficial](https://docs.langchain.com/oss/python/langgraph/agentic-rag). Escolher esse caminho exige uma credencial e considerar os custos do provedor. Não é necessário contratar hospedagem para estudar localmente. Um modelo local exige verificar a capacidade do computador.

Chroma é uma opção posterior de persistência; a integração documenta armazenamento local com persist_directory. Fonte: [Integração Chroma](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma).

Minha proposta: aprender com um único modelo de embeddings, um único modelo de resposta e poucos documentos. Registrar as versões das dependências que funcionarem. Não escolher a infraestrutura definitiva antes de medir a qualidade da busca.

## 3. Preparar o material agronômico

Começar com um recorte: uma cultura, um tema e uma região de aplicação. Selecionar de 5 a 10 documentos para o piloto é uma sugestão de escala, não um requisito técnico.

1. **Inventariar:** preencher catalogo_documentos.csv com título, instituição, origem, edição, ano, cultura, tema e região. Registrar autorização ou condições de uso e responsável pela revisão.
2. **Selecionar:** preferir materiais com autoria e escopo identificáveis. Publicações técnicas de instituições de pesquisa e extensão podem ser candidatas; cada documento precisa ser examinado quanto à pertinência e à atualização.
3. **Preservar:** guardar os originais sem alterações. Manter identificação da versão e, na implementação, um hash para detectar arquivos repetidos ou alterados.
4. **Extrair:** verificar se o PDF contém texto ou páginas digitalizadas. Usar OCR para digitalizações. Conferir visualmente algumas páginas, sobretudo números, acentos e símbolos.
5. **Limpar:** remover cabeçalhos repetidos e corrigir quebras indevidas. Preservar nomes científicos, unidades, referências, exceções e condições de aplicação.
6. **Tratar tabelas e imagens:** manter cabeçalhos, unidades, notas e relações entre linhas e colunas. Não indexar uma tabela como números soltos. Gráficos ou imagens com informação essencial exigem tratamento próprio e validação; extração de texto simples pode omiti-los.
7. **Dividir:** começar pelas seções do documento. Manter cada recomendação junto das condições e ressalvas que a limitam. Experimentar trechos de 400–800 tokens e sobreposição de 50–100 como hipótese inicial, comparando resultados. Esses valores não são universais e não equivalem a caracteres.
8. **Identificar:** cada trecho deve carregar documento, versão, página ou seção e metadados de aplicação. Diferenciar o índice de página do PDF da numeração impressa.
9. **Revisar:** comparar trechos com os originais antes de gerar o índice. Marcar conteúdo ambíguo ou desatualizado para revisão.
10. **Atualizar:** quando entrar uma versão nova, retirar ou marcar os trechos substituídos para evitar respostas que misturem edições incompatíveis.

Campos mínimos por trecho: chunk_id, documento_id, texto, titulo, instituicao, origem, ano, versao, pagina_ou_secao, cultura, tema, regiao e status_revisao. Ausência de informação deve aparecer como desconhecida, sem preenchimento por suposição.

Cuidados propostos para o chatbot: filtrar cultura e região quando houver contexto suficiente; pedir dados relevantes que estejam faltando; mostrar divergências entre fontes; preservar unidades e restrições; exigir evidência aplicável para afirmações técnicas. A semelhança vetorial não representa uma probabilidade de a resposta estar correta.

## 4. Sequência de estudo com entregas verificáveis

| Etapa | Estudar | Exercício | Critério de conclusão |
|---|---|---|---|
| 1. Fundamentos | Python básico, funções, listas, dicionários, arquivos e APIs | Ler um arquivo e separar texto de metadados | Explicar o que o programa recebeu e produziu |
| 2. RAG | Trechos, embeddings, recuperação e geração | Desenhar o caminho de uma pergunta até sua fonte | Distinguir falha de busca de falha de resposta |
| 3. Documentos | Extração, limpeza e divisão | Processar um documento e conferir cinco trechos | Cada trecho mantém sentido e origem verificável |
| 4. Busca | Índice, retriever e filtros | Fazer dez perguntas e inspecionar os resultados sem gerar respostas | Identificar quando a busca trouxe a evidência correta |
| 5. RAG básico | Prompt com contexto e citações | Gerar respostas usando apenas os trechos recuperados | Verificar suporte às afirmações e comportamento sem evidência |
| 6. LangGraph | Estado, nós, arestas e caminhos condicionais | Modelar buscar → verificar → responder ou pedir contexto | Explicar cada transição e executar os caminhos alternativos |
| 7. RAG com agente | Uso de ferramentas e reformulação da busca | Adaptar o tutorial oficial ao mesmo conjunto de perguntas | Comparar qualidade, latência e custo com o RAG básico |

Ordem de leitura: [fundamentos de recuperação](https://docs.langchain.com/oss/python/deepagents/retrieval), [visão geral do LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) e [tutorial de RAG com LangGraph](https://docs.langchain.com/oss/python/langgraph/agentic-rag).

No tutorial, observe a preparação dos documentos, a ferramenta de busca, a decisão de consultá-la, a avaliação de relevância, a reformulação da pergunta e a geração. Para adaptar ao chatbot, minha proposta é tornar a busca obrigatória para respostas técnicas, manter a pergunta atual separada do histórico, carregar as fontes até a resposta e limitar tentativas de busca. Relevância temática, sozinha, não demonstra que a evidência é suficiente. Ao atingir o limite, pedir informação ou declarar que a base não sustenta a resposta.

## 5. Avaliar antes de aumentar a complexidade

Preencher avaliacao_perguntas.csv depois de selecionar os documentos. Elaborar inicialmente 20 perguntas: 10 respondíveis, 5 sem resposta na base e 5 com contexto ausente ou ambíguo. Essa divisão é uma proposta didática.

Para as perguntas respondíveis, registrar previamente a evidência e a resposta esperada, revisadas por alguém com domínio agronômico. Para as demais, registrar a abstenção ou o esclarecimento esperado.

Medir separadamente:

- Recuperação: em quantas perguntas respondíveis a evidência esperada apareceu entre os primeiros k resultados? Registrar o k usado; começar com 4 é apenas um experimento.
- Fidelidade: as afirmações da resposta são sustentadas pelos trechos?
- Citações: documento e localização existem e sustentam a afirmação associada?
- Aplicabilidade: cultura, região, período, unidades e condições foram respeitados?
- Ausência de evidência: o chatbot evita completar lacunas com suposições?
- Operação: tempo por pergunta e custo de indexação e consulta.

Comparar as versões com as mesmas perguntas e os mesmos documentos. Se a evidência correta não chega ao modelo, investigar extração, divisão, filtros e busca. Se ela chega e a resposta falha, investigar instruções e geração. Reservar novas perguntas para conferir se as melhorias generalizam.

## 6. Próximo exercício

Escolher uma cultura e um tema, reunir três documentos iniciais e preencher o catálogo. Criar cinco perguntas cuja resposta você consegue localizar nesses documentos, anotando páginas ou seções. Esse exercício torna possível avaliar o primeiro protótipo sem depender da impressão de que a resposta parece boa.

Pendências para personalização: nível de Python, cultura/tema, formatos e quantidade de documentos, existência de um chatbot e preferência por execução local ou por API. A preparação real da base depende de receber ou localizar esses materiais; o aprendizado e a implementação ainda estão em andamento.
