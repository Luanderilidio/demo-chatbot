"""Exemplos reais com Ollama/Chroma. Execute da raiz: python -m tests.executar_exemplos_langgraph.

Não altera documentos nem reindexa a base. Salva respostas, caminhos e tempos
para inspeção humana; não é uma medição de precisão agronômica.
"""
import json
import argparse
from pathlib import Path
from time import perf_counter
from datetime import datetime, timezone

from src.rag_engine import AgriculturalRAG, LLM_MODEL, EMBEDDING_MODEL
from src.rag_graph import initial_state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("resultados_langgraph.json"))
    args = parser.parse_args()
    rag = AgriculturalRAG()
    output = args.output
    report = {
        "executado_em_utc": datetime.now(timezone.utc).isoformat(),
        "llm": LLM_MODEL, "embedding": EMBEDDING_MODEL,
        "avaliacao": "exemplos reais para inspeção, sem nota de precisão",
        "cases": [],
    }
    cases = [
        ("origem", "Qual é a origem da soja?", "soja", "answered"),
        ("ausente", "Qual é o preço da soja hoje em Cuiabá?", "soja", "insufficient"),
        ("ambigua", "Como controlar essa doença?", None, "clarification"),
    ]
    for name, question, culture, expected in cases:
        print(f"INICIO {name}", flush=True)
        start = perf_counter()
        record = {"caso": name, "pergunta": question, "filtro": culture, "etapas": [], "resposta": "", "fontes": []}
        try:
            for mode, event in rag.graph.stream(initial_state(question, culture_filter=culture),
                                                 stream_mode=["custom", "updates"],
                                                 config={"recursion_limit": 20}):
                if mode == "custom":
                    if event["type"] == "step":
                        record["etapas"].append({**event, "inicio_segundos": round(perf_counter() - start, 3)})
                        print(f"  {event['node']}", flush=True)
                    elif event["type"] == "token":
                        record["resposta"] += event["content"]
                    elif event["type"] == "sources":
                        record["fontes"] = [d.metadata for d in event["docs"]]
                else:
                    for update in event.values():
                        if update.get("assessment"):
                            record.setdefault("avaliacoes", []).append(update["assessment"].model_dump())
                        if "outcome" in update:
                            record["resultado"] = update["outcome"]
        except Exception as error:
            record["erro"] = f"{type(error).__name__}: {error}"
        record["segundos"] = round(perf_counter() - start, 2)
        record["resultado_esperado"] = expected
        record["caminho_esperado_ok"] = record.get("resultado") == expected
        report["cases"].append(record)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"FIM {name}: {record.get('resultado', record.get('erro'))}; {record['segundos']}s", flush=True)
    if any("erro" in record or not record["caminho_esperado_ok"] for record in report["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
