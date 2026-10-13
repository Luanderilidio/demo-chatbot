"""Entrada da preparação da base. Leia docs/FLUXO_DO_PROJETO.md antes de executar."""
import time
from src.ingest import console, run_ingestion

if __name__ == "__main__":
    started = time.time()
    run_ingestion()
    console.print(f"Tempo total de ingestão: {time.time() - started:.1f} segundos.")
