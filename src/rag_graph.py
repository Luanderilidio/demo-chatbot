"""Grafo de consulta RAG: buscar, avaliar, reformular e responder.

O grafo recebe operações como funções para permitir testes sem Ollama/Chroma.
Cada consulta tem seu próprio estado; não há memória entre mensagens.
"""
from collections.abc import Callable, Iterator
import re
from typing import Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

MAX_SEARCHES = 2


class EvidenceDecision(BaseModel):
    """Resultado estruturado da avaliação, sem raciocínio interno do modelo."""
    model_config = ConfigDict(extra="forbid")

    decision: Literal["sufficient", "insufficient", "clarify"]
    evidence_ids: list[StrictInt] = Field(description="Números das fontes que sustentam a resposta; vazio se insuficiente.")
    reason: str = Field(max_length=600, description="Breve identificação da evidência ou da informação ausente.")
    clarification: str = Field(max_length=400, description="Pergunta de esclarecimento em português; vazia nas outras decisões.")


class SearchRewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=1000)


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: StrictInt
    text: str = Field(min_length=20, max_length=300, description="Cópia literal curta do trecho que responde à pergunta.")


class EvidenceAssessment(EvidenceDecision):
    reason: str = Field(max_length=120, description="Uma frase curta identificando evidência ou lacuna.")
    evidence_quotes: list[EvidenceQuote] = Field(description="Para cada fonte suficiente, copie uma passagem literal e informe seu número. Lista vazia quando insuficiente ou ambígua.")


class CompactAssessment(BaseModel):
    """Contrato curto do modelo; a aplicação deriva IDs e justificativa de estado."""
    model_config = ConfigDict(extra="forbid")
    decision: Literal["sufficient", "insufficient", "clarify"]
    evidence_quotes: list[EvidenceQuote] = Field(max_length=2, description="Uma ou duas passagens que respondem diretamente; vazia se insuficiente.")
    clarification: str = Field(max_length=180, description="Vazia, exceto quando faltar um detalhe do usuário.")


class RAGState(TypedDict):
    original_question: str
    search_query: str
    culture_filter: str | None
    k: int
    attempts: int
    documents: list[Document]
    approved_documents: list[Document]
    assessment: EvidenceDecision | None
    error: str
    answer: str
    outcome: str


def initial_state(question: str, k: int = 4, culture_filter: str | None = None) -> RAGState:
    if not question.strip():
        raise ValueError("Digite uma pergunta antes de consultar.")
    if not isinstance(k, int) or isinstance(k, bool) or k < 1:
        raise ValueError("k deve ser um inteiro positivo.")
    return {
        "original_question": question.strip(), "search_query": question.strip(),
        "culture_filter": culture_filter, "k": k, "attempts": 0,
        "documents": [], "approved_documents": [], "assessment": None,
        "error": "", "answer": "", "outcome": "",
    }


def unresolved_reference(question: str) -> bool:
    """Detecta pedidos curtos sem o referente; não tenta resolver toda ambiguidade."""
    return bool(re.fullmatch(
        r"\s*(?:como|o que fazer para)\s+(?:controlar|tratar|combater)\s+"
        r"(?:essa|esta|aquela|esse|este|aquele)\s+(?:doença|doenca|praga|problema)"
        r"(?:\s+(?:na|no|em)\s+[\w -]+)?\s*[?!.]*\s*",
        question, flags=re.IGNORECASE,
    ))


def build_rag_graph(
    retrieve: Callable[[str, int, str | None], list[Document]],
    evaluate: Callable[[str, list[Document], str | None], EvidenceDecision],
    rewrite: Callable[[str, str, str | None], str],
    generate: Callable[[str, list[Document]], Iterator[str]],
):
    """Compila o fluxo. Erros de infraestrutura propagam até a interface."""

    def notify(node: str, state: RAGState, **details):
        get_stream_writer()({"type": "step", "node": node, "attempt": state["attempts"], **details})

    def search(state: RAGState):
        attempt = state["attempts"] + 1
        notify("buscar", state, search_number=attempt, query=state["search_query"])
        docs = retrieve(state["search_query"], state["k"], state["culture_filter"])
        return {"documents": docs, "approved_documents": [], "attempts": attempt, "assessment": None}

    def grade(state: RAGState):
        notify("avaliar", state)
        if unresolved_reference(state["original_question"]):
            # Sem histórico de conversa, o referente não pode ser inferido dos
            # documentos recuperados (um livro encontrado não revela a intenção).
            detail = "Qual doença, praga ou problema você quer abordar?"
            if not state["culture_filter"]:
                detail += " Informe também a cultura."
            decision = EvidenceDecision(decision="clarify", evidence_ids=[],
                                        reason="Referência não identificada na pergunta atual.", clarification=detail)
        elif not state["documents"]:
            decision = EvidenceDecision(decision="insufficient", evidence_ids=[], reason="A busca não retornou trechos.", clarification="")
        else:
            try:
                decision = EvidenceDecision.model_validate(
                    evaluate(state["original_question"], state["documents"], state["culture_filter"])
                )
            except (OutputParserException, ValidationError):
                return {"error": "evaluation", "approved_documents": []}

        approved = []
        if decision.decision == "sufficient":
            ids = list(dict.fromkeys(decision.evidence_ids))
            if not ids or any(index < 1 or index > len(state["documents"]) for index in ids):
                return {"error": "evaluation", "approved_documents": []}
            approved = [state["documents"][index - 1] for index in ids]
        if decision.decision == "clarify" and not decision.clarification.strip():
            return {"error": "evaluation", "approved_documents": []}
        return {"assessment": decision, "approved_documents": approved}

    def after_grade(state: RAGState):
        if state["error"]:
            return "sem_evidencia"
        decision = state["assessment"].decision
        if decision == "sufficient":
            return "responder"
        if decision == "clarify":
            return "esclarecer"
        return "reformular" if state["attempts"] < MAX_SEARCHES else "sem_evidencia"

    def rephrase(state: RAGState):
        notify("reformular", state)
        try:
            query = rewrite(state["original_question"], state["search_query"], state["culture_filter"])
            query = SearchRewrite(query=query).query.strip()
        except (OutputParserException, ValidationError):
            return {"error": "rewrite"}
        if not query or query.casefold() == state["search_query"].casefold():
            return {"error": "rewrite"}
        original_numbers = set(re.findall(r"\d+", state["original_question"]))
        if set(re.findall(r"\d+", query)) - original_numbers:
            return {"error": "rewrite"}
        # Pergunta original, k e filtro permanecem intactos.
        # Ancorar a busca na pergunta original também preserva local e restrições
        # textuais caso o modelo os omita na expansão. A intenção ainda é
        # reavaliada contra a pergunta ORIGINAL após a busca.
        return {"search_query": state["original_question"] + "\nTermos de busca: " + query}

    def answer(state: RAGState):
        notify("responder", state)
        writer = get_stream_writer()
        writer({"type": "sources", "docs": state["approved_documents"]})
        parts = []
        for token in generate(state["original_question"], state["approved_documents"]):
            parts.append(token)
            writer({"type": "token", "content": token})
        return {"answer": "".join(parts), "outcome": "answered"}

    def finish(state: RAGState, node: str, text: str, outcome: str):
        notify(node, state)
        writer = get_stream_writer()
        writer({"type": "sources", "docs": []})
        writer({"type": "token", "content": text})
        return {"answer": text, "outcome": outcome, "approved_documents": []}

    def clarify(state: RAGState):
        question = state["assessment"].clarification.strip()
        text = question + "\nEnvie a pergunta completa incluindo esse detalhe para uma nova consulta."
        return finish(state, "esclarecer", text, "clarification")

    def abstain(state: RAGState):
        if state["error"] == "evaluation":
            text = "Não consegui validar a avaliação dos trechos. Tente novamente; não vou gerar uma orientação sem essa verificação."
            outcome = "evaluation_error"
        elif state["error"] == "rewrite":
            text = "Os trechos encontrados não foram suficientes e não consegui preparar uma nova busca. Reformule a pergunta ou acrescente detalhes."
            outcome = "rewrite_error"
        else:
            text = "Não encontrei evidências suficientes nos trechos consultados após duas buscas. Isso não prova que a informação não exista no acervo. Reformule a pergunta ou indique uma fonte mais específica."
            outcome = "insufficient"
        return finish(state, "sem_evidencia", text, outcome)

    graph = StateGraph(RAGState)
    for name, node in {
        "buscar": search, "avaliar": grade, "reformular": rephrase,
        "responder": answer, "esclarecer": clarify, "sem_evidencia": abstain,
    }.items():
        graph.add_node(name, node)
    graph.add_edge(START, "buscar")
    graph.add_edge("buscar", "avaliar")
    graph.add_conditional_edges("avaliar", after_grade, {
        name: name for name in ("responder", "esclarecer", "reformular", "sem_evidencia")
    })
    graph.add_conditional_edges("reformular", lambda s: "sem_evidencia" if s["error"] else "buscar",
                                {"buscar": "buscar", "sem_evidencia": "sem_evidencia"})
    for terminal in ("responder", "esclarecer", "sem_evidencia"):
        graph.add_edge(terminal, END)
    return graph.compile()
