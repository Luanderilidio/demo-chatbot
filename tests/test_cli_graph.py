"""Verifica comandos e eventos na interface, sem rede nem banco."""
import io
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from rich.console import Console
from src import chatbot_cli


class CLIGraphTests(unittest.TestCase):
    def test_flow_sources_and_streaming_keep_same_source_numbers(self):
        output = io.StringIO()
        console = Console(file=output, width=120, force_terminal=False, color_system=None)
        docs = [Document(page_content=text, metadata={"titulo": "Manual", "pagina": 4, "cultura": "soja"})
                for text in ("Trecho A", "Trecho B")]
        events = [
            {"type": "step", "node": "buscar"},
            {"type": "step", "node": "avaliar"},
            {"type": "step", "node": "responder"},
            {"type": "sources", "docs": docs},
            {"type": "token", "content": "Resposta com fonte [2]."},
        ]
        with patch.object(chatbot_cli, "console", console), \
             patch.object(chatbot_cli, "CHROMA_DIR") as directory, \
             patch.object(chatbot_cli, "AgriculturalRAG") as rag, \
             patch("builtins.input", side_effect=["/fluxo", "/fontes", "/filtro soja", "Pergunta?", "/sair"]), \
             patch("sys.stdout", output):
            directory.exists.return_value = True
            rag.return_value.stream_answer.return_value = iter(events)
            chatbot_cli.main()
            rag.return_value.stream_answer.assert_called_once_with("Pergunta?", k=4, cultura_filtro="soja")
        text = output.getvalue()
        self.assertIn("buscar → avaliar → responder", text)
        self.assertIn("Resposta com fonte [2].", text)
        self.assertIn("Trecho #1", text)
        self.assertIn("Trecho #2", text)
        self.assertRegex(text, r"2\s+Manual\s+4\s+SOJA")

    def test_clarification_does_not_display_evidence_table(self):
        output = io.StringIO()
        console = Console(file=output, width=120, force_terminal=False, color_system=None)
        with patch.object(chatbot_cli, "console", console), \
             patch.object(chatbot_cli, "CHROMA_DIR") as directory, \
             patch.object(chatbot_cli, "AgriculturalRAG") as rag, \
             patch("builtins.input", side_effect=["Pergunta?", "/sair"]), \
             patch("sys.stdout", output):
            directory.exists.return_value = True
            rag.return_value.stream_answer.return_value = iter([
                {"type": "sources", "docs": []},
                {"type": "token", "content": "Qual cultura?"},
            ])
            chatbot_cli.main()
        self.assertIn("Qual cultura?", output.getvalue())
        self.assertNotIn("Evidências selecionadas", output.getvalue())


if __name__ == "__main__":
    unittest.main()
