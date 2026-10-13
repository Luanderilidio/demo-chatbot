"""Reproduz a lógica de ingest.py com dependências simuladas, sem tocar no banco.

Execute com Python. Não instala pacotes nem chama Ollama. Os resultados demonstram
falhas de controle de fluxo, não a qualidade do modelo ou da busca vetorial.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import List

SOURCE = Path(__file__).resolve().parents[1] / "src" / "ingest.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"))
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_ingestion")
isolated = ast.Module(body=[function], type_ignores=[])


class Console:
    def __init__(self):
        self.messages = []

    def print(self, value):
        self.messages.append(str(value))


class Progress:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def add_task(self, *args, **kwargs):
        return 1

    def update(self, *args, **kwargs):
        pass


class Store:
    def __init__(self, records=(), fail_first_batch=False):
        self.records = list(records)
        self.fail_first_batch = fail_first_batch
        self._collection = self

    def count(self):
        return len(self.records)

    def add_documents(self, batch):
        if self.fail_first_batch and batch[0] == 0:
            raise RuntimeError("falha simulada antes da gravação")
        self.records.extend(batch)


def run_case(chunks, store):
    console = Console()
    empty_dir = SimpleNamespace(iterdir=lambda: [])
    env = {
        "List": List, "Document": object, "console": console,
        "DOCUMENTS_DIR": empty_dir, "DOC_METADATA_MAP": {},
        "CHROMA_DIR": "BANCO_SIMULADO", "COLLECTION_NAME": "simulado",
        "EMBEDDING_MODEL": "simulado",
        "RecursiveCharacterTextSplitter": lambda **kwargs: SimpleNamespace(split_documents=lambda docs: chunks),
        "OllamaEmbeddings": lambda **kwargs: None,
        "Chroma": lambda **kwargs: store,
        "Progress": Progress, "time": SimpleNamespace(sleep=lambda seconds: None),
    }
    for name in ("SpinnerColumn", "TextColumn", "BarColumn", "TimeElapsedColumn"):
        env[name] = lambda *args, **kwargs: None
    exec(compile(isolated, str(SOURCE), "exec"), env)
    env["run_ingestion"]()
    return console.messages


def main():
    stale = Store(["versao_antiga"])
    run_case(["versao_nova"], stale)
    assert stale.records == ["versao_antiga"]

    partial = Store(fail_first_batch=True)
    first_messages = run_case(list(range(120)), partial)
    assert partial.records == list(range(40, 120))
    assert any("[OK] Ingestão concluída" in text for text in first_messages)
    partial.fail_first_batch = False
    run_case(list(range(120)), partial)
    missing = sorted(set(range(120)) - set(partial.records))
    assert missing == list(range(40))
    assert len(partial.records) == 120
    assert len(set(partial.records)) == 80

    print(json.dumps({
        "metodo": "função original executada com banco, splitter e serviços simulados",
        "alteracao_com_mesma_contagem": "conteúdo antigo mantido; conteúdo novo ignorado",
        "lote_falho": {
            "primeira_execucao": "lote 0 falha; 80 itens gravados; mensagem final de sucesso",
            "apos_retomada": len(partial.records),
            "itens_distintos": len(set(partial.records)),
            "itens_ausentes": len(missing),
            "itens_duplicados": len(partial.records) - len(set(partial.records)),
        },
        "banco_original_alterado": False,
        "inferencia_executada": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
