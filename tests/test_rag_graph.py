"""Testes do LangGraph compilado com serviços controlados, sem rede/banco."""
import unittest
from langchain_core.documents import Document
from pydantic import ValidationError
from src.rag_graph import EvidenceDecision, build_rag_graph, initial_state, unresolved_reference


def decision(value="sufficient", ids=None, clarification=""):
    return EvidenceDecision(decision=value, evidence_ids=([1] if ids is None else ids),
                            reason="Resultado controlado do teste.", clarification=clarification)


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.doc = Document(page_content="Evidência controlada", metadata={"source": "teste", "pagina": 1})
        self.searches, self.generations, self.evaluations = [], [], []

    def graph(self, decisions, batches=None, rewritten="origem geográfica da soja"):
        grades = iter(decisions)
        batches = iter(batches if batches is not None else [[self.doc], [self.doc]])

        def retrieve(query, k, culture):
            self.searches.append((query, k, culture))
            return next(batches)

        def evaluate(question, docs, culture):
            self.evaluations.append((question, culture))
            return next(grades)

        def generate(question, docs):
            self.generations.append((question, docs))
            yield "Resposta "
            yield "[1]."

        return build_rag_graph(retrieve, evaluate, lambda *args: rewritten, generate)

    def run_stream(self, graph):
        return list(graph.stream(initial_state("Qual a origem da soja?", culture_filter="soja"),
                                 stream_mode="custom", config={"recursion_limit": 20}))

    def test_answer_first_search_streams_only_final_text(self):
        events = self.run_stream(self.graph([decision()]))
        self.assertEqual([e["node"] for e in events if e["type"] == "step"], ["buscar", "avaliar", "responder"])
        self.assertEqual("".join(e["content"] for e in events if e["type"] == "token"), "Resposta [1].")
        self.assertEqual(len(self.searches), 1)

    def test_retry_preserves_question_and_filter(self):
        events = self.run_stream(self.graph([decision("insufficient", []), decision()]))
        self.assertEqual(len(self.searches), 2)
        self.assertEqual(self.searches[1], ("Qual a origem da soja?\nTermos de busca: origem geográfica da soja", 4, "soja"))
        self.assertEqual(self.generations[0][0], "Qual a origem da soja?")
        self.assertTrue(all(q == "Qual a origem da soja?" and f == "soja" for q, f in self.evaluations))
        self.assertEqual([e["node"] for e in events if e["type"] == "step"],
                         ["buscar", "avaliar", "reformular", "buscar", "avaliar", "responder"])

    def test_insufficient_stops_after_two_searches(self):
        events = self.run_stream(self.graph([decision("insufficient", []), decision("insufficient", [])]))
        self.assertEqual(len(self.searches), 2)
        self.assertEqual(self.generations, [])
        self.assertIn("após duas buscas", events[-1]["content"])
        self.assertEqual([e["docs"] for e in events if e["type"] == "sources"], [[]])

    def test_clarification_without_answer_generation(self):
        graph = self.graph([decision("clarify", [], "Qual cultura e qual doença você quer abordar?")])
        events = self.run_stream(graph)
        self.assertIn("Qual cultura", events[-1]["content"])
        self.assertEqual(len(self.searches), 1)
        self.assertFalse(self.generations)

    def test_unresolved_reference_cannot_be_filled_by_retrieved_docs(self):
        graph = self.graph([decision()])  # um avaliador permissivo não deve ser chamado
        result = graph.invoke(initial_state("Como controlar essa doença?"))
        self.assertEqual(result["outcome"], "clarification")
        self.assertFalse(self.evaluations)
        self.assertFalse(self.generations)
        self.assertIn("cultura", result["answer"])

    def test_unresolved_reference_with_filter_still_needs_disease(self):
        graph = self.graph([decision()])
        result = graph.invoke(initial_state("Como tratar essa praga na soja?", culture_filter="soja"))
        self.assertEqual(result["outcome"], "clarification")
        self.assertFalse(self.generations)

    def test_named_disease_is_not_blocked_by_reference_rule(self):
        self.assertFalse(unresolved_reference("Como controlar a ferrugem na soja?"))
        self.assertFalse(unresolved_reference("A doença é ferrugem. Como controlar essa doença?"))

    def test_no_documents_never_calls_evaluator_or_generator(self):
        events = self.run_stream(self.graph([], batches=[[], []]))
        self.assertFalse(self.evaluations)
        self.assertFalse(self.generations)
        self.assertIn("após duas buscas", events[-1]["content"])

    def test_unsupported_evidence_id_fails_closed(self):
        events = self.run_stream(self.graph([decision(ids=[99])]))
        self.assertFalse(self.generations)
        self.assertIn("validar a avaliação", events[-1]["content"])

    def test_sufficient_without_ids_fails_closed(self):
        self.run_stream(self.graph([decision(ids=[])]))
        self.assertFalse(self.generations)

    def test_invalid_schema_fails_closed(self):
        events = self.run_stream(self.graph([{"decision": "talvez"}]))
        self.assertIn("validar a avaliação", events[-1]["content"])
        self.assertFalse(self.generations)

    def test_only_approved_documents_reach_generation(self):
        other = Document(page_content="Outra evidência", metadata={"source": "teste", "pagina": 1})
        events = self.run_stream(self.graph([decision(ids=[2, 2])], batches=[[self.doc, other]]))
        self.assertEqual(self.generations[0][1], [other])
        self.assertEqual([e["docs"] for e in events if e["type"] == "sources"], [[other]])

    def test_useless_rewrite_stops_without_repeating_query(self):
        events = self.run_stream(self.graph([decision("insufficient", [])], rewritten="Qual a origem da soja?"))
        self.assertEqual(len(self.searches), 1)
        self.assertFalse(self.generations)
        self.assertIn("nova busca", events[-1]["content"])

    def test_empty_rewrite_fails_closed(self):
        self.run_stream(self.graph([decision("insufficient", [])], rewritten=" "))
        self.assertEqual(len(self.searches), 1)
        self.assertFalse(self.generations)

    def test_rewrite_cannot_invent_year(self):
        events = self.run_stream(self.graph([decision("insufficient", [])], rewritten="origem da soja em 2023"))
        self.assertEqual(len(self.searches), 1)
        self.assertFalse(self.generations)
        self.assertIn("nova busca", events[-1]["content"])

    def test_infrastructure_error_is_not_reported_as_no_evidence(self):
        def fail(*args):
            raise ConnectionError("Ollama indisponível")
        graph = build_rag_graph(fail, fail, fail, fail)
        with self.assertRaises(ConnectionError):
            self.run_stream(graph)

    def test_state_does_not_leak_across_invocations(self):
        graph = self.graph([decision(), decision()])
        first = graph.invoke(initial_state("Pergunta A", culture_filter="soja"))
        second = graph.invoke(initial_state("Pergunta B", culture_filter="milho"))
        self.assertEqual(first["attempts"], 1)
        self.assertEqual(second["attempts"], 1)
        self.assertEqual(self.generations[1][0], "Pergunta B")
        self.assertEqual(self.searches[1][2], "milho")

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            initial_state(" ")
        with self.assertRaises(ValueError):
            initial_state("pergunta", k=0)


class EvidenceAttributionTests(unittest.TestCase):
    def test_compact_output_derives_ids_and_still_checks_quotes(self):
        from unittest.mock import Mock
        from src.rag_engine import AgriculturalRAG
        from src.rag_graph import CompactAssessment, EvidenceQuote
        rag = AgriculturalRAG.__new__(AgriculturalRAG)
        text = "A ficha está no capítulo três do manual."
        rag.evaluator = Mock()
        rag.evaluator.invoke.return_value = CompactAssessment(
            decision="sufficient", clarification="",
            evidence_quotes=[EvidenceQuote(source_id=i, text=text) for i in [1, 2]],
        )
        result = rag.evaluate("Onde está a ficha?", [Document(page_content=text), Document(page_content="Outra informação.")], None)
        self.assertEqual(result.decision, "sufficient")
        self.assertEqual(result.evidence_ids, [1])

    def test_quote_normalization_preserves_numbers_and_negation(self):
        from unittest.mock import Mock
        from src.rag_engine import AgriculturalRAG
        from src.rag_graph import CompactAssessment, EvidenceQuote
        rag = AgriculturalRAG.__new__(AgriculturalRAG)
        rag.evaluator = Mock()
        doc = Document(page_content="A ficha NÃO está na seção 12 do manual.")
        for quote, expected in [
            ("A ficha não está na secao 12 do manual.", "sufficient"),
            ("A ficha está na seção 12 do manual.", "insufficient"),
            ("A ficha não está na seção 13 do manual.", "insufficient"),
        ]:
            with self.subTest(quote=quote):
                rag.evaluator.invoke.return_value = CompactAssessment(
                    decision="sufficient", clarification="",
                    evidence_quotes=[EvidenceQuote(source_id=1, text=quote)],
                )
                self.assertEqual(rag.evaluate("Onde está a ficha?", [doc], None).decision, expected)

    def test_pdf_word_break_does_not_discard_valid_quote(self):
        from unittest.mock import Mock
        from src.rag_engine import AgriculturalRAG
        from src.rag_graph import EvidenceAssessment, EvidenceQuote
        rag = AgriculturalRAG.__new__(AgriculturalRAG)
        rag.evaluator = Mock()
        rag.evaluator.invoke.return_value = EvidenceAssessment(
            decision="sufficient", evidence_ids=[1], reason="teste", clarification="",
            evidence_quotes=[EvidenceQuote(source_id=1, text="Surgiu como uma planta ras-teira, muito distinta.")],
        )
        docs = [Document(page_content="Surgiu como uma planta ras -\nteira, muito distinta.")]
        self.assertEqual(rag.evaluate("Como surgiu?", docs, None).evidence_ids, [1])

    def test_quote_from_wrong_source_is_excluded(self):
        from unittest.mock import Mock
        from src.rag_engine import AgriculturalRAG
        from src.rag_graph import EvidenceAssessment, EvidenceQuote
        rag = AgriculturalRAG.__new__(AgriculturalRAG)
        text = "A ficha está no capítulo três do manual."
        rag.evaluator = Mock()
        rag.evaluator.invoke.return_value = EvidenceAssessment(
            decision="sufficient", evidence_ids=[1, 2], reason="teste", clarification="",
            evidence_quotes=[EvidenceQuote(source_id=i, text=text) for i in [1, 2]],
        )
        docs = [Document(page_content=text), Document(page_content="Outra informação sem ficha.")]
        self.assertEqual(rag.evaluate("Onde está a ficha?", docs, None).evidence_ids, [1])

    def test_invented_quote_is_not_accepted(self):
        from unittest.mock import Mock
        from src.rag_engine import AgriculturalRAG
        from src.rag_graph import EvidenceAssessment, EvidenceQuote
        rag = AgriculturalRAG.__new__(AgriculturalRAG)
        rag.evaluator = Mock()
        rag.evaluator.invoke.return_value = EvidenceAssessment(
            decision="sufficient", evidence_ids=[1], reason="teste", clarification="",
            evidence_quotes=[EvidenceQuote(source_id=1, text="Passagem que não existe nos documentos.")],
        )
        result = rag.evaluate("Pergunta", [Document(page_content="Conteúdo diferente")], None)
        self.assertEqual(result.decision, "insufficient")
        self.assertEqual(result.evidence_ids, [])


if __name__ == "__main__":
    unittest.main()
