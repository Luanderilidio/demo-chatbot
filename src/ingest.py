"""
Script de Ingestao de Documentos Embrapa para o Chatbot Agricola (RAG)
Projeto Lenovo HPC - Sprint 45
"""

import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Garante suporte UTF-8 no Windows Console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import pypdf
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from .rag_config import CHROMA_DIR, DOCUMENTS_DIR

console = Console(legacy_windows=False)

COLLECTION_NAME = "embrapa_conhecimento"
EMBEDDING_MODEL = "nomic-embed-text"

DOC_METADATA_MAP = {
    "500perguntas-soja.pdf": {
        "cultura": "soja",
        "titulo": "500 Perguntas, 500 Respostas - Soja (Embrapa)",
    },
    "500perguntasarroz.pdf": {
        "cultura": "arroz",
        "titulo": "500 Perguntas, 500 Respostas - Arroz (Embrapa)",
    },
    "500perguntasmilho.pdf": {
        "cultura": "milho",
        "titulo": "500 Perguntas, 500 Respostas - Milho (Embrapa Milho e Sorgo)",
    },
    "500perguntashortas.pdf": {
        "cultura": "hortalicas",
        "titulo": "500 Perguntas, 500 Respostas - Hortaliças (Embrapa Hortaliças)",
    },
    "500perguntasposcolheitahortalicas.pdf": {
        "cultura": "pos-colheita",
        "titulo": "500 Perguntas, 500 Respostas - Pós-Colheita de Hortaliças (Embrapa Hortaliças)",
    },
    "50-HORTALICAS-COMO-COMPRAR-CONSERVAR-E-CONSUMIR.pdf": {
        "cultura": "hortalicas-guia",
        "titulo": "50 Hortaliças: Como Comprar, Conservar e Consumir (Embrapa)",
    },
    "LMCT-2919_Estudo_RAG_LangChain_LangGraph.md": {
        "cultura": "estudo-tecnico",
        "titulo": "LMCT-2919: Estudo RAG LangChain e LangGraph (Lenovo HPC)",
    },
    "Relatorio_Tecnico_Sprint45_LLM_Especializacao.md": {
        "cultura": "estudo-tecnico",
        "titulo": "Relatório Técnico Sprint 45: LLM e Especialização de Domínio (Lenovo HPC)",
    },
}

def clean_text(text: str) -> str:
    """Limpa e normaliza o texto extraido de PDFs."""
    if not text:
        return ""
    # Conecta palavras hifenizadas no final da linha (ex: produ-\ncao -> producao)
    text = re.sub(r'(\b\w+)-\s*\n\s*(\w+\b)', r'\1\2', text)
    # Remove quebras de linha excessivas mantendo paragrafos
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove espacos duplos
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()

def extract_pdf_documents(file_path: Path, meta_info: Dict[str, str]) -> List[Document]:
    """Extrai texto de um PDF pagina por pagina."""
    documents = []
    reader = pypdf.PdfReader(str(file_path))
    total_pages = len(reader.pages)
    
    for page_idx, page in enumerate(reader.pages):
        raw_text = page.extract_text() or ""
        cleaned = clean_text(raw_text)
        
        # Ignora paginas muito curtas (capa, branco, etc.)
        if len(cleaned) < 50:
            continue
            
        doc = Document(
            page_content=cleaned,
            metadata={
                "source": file_path.name,
                "titulo": meta_info.get("titulo", file_path.name),
                "cultura": meta_info.get("cultura", "geral"),
                "pagina": page_idx + 1,
                "total_paginas": total_pages,
            }
        )
        documents.append(doc)
    return documents

def extract_markdown_documents(file_path: Path, meta_info: Dict[str, str]) -> List[Document]:
    """Extrai texto de um arquivo Markdown."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = file_path.read_text(encoding="latin-1")
        
    cleaned = clean_text(content)
    if not cleaned:
        return []
        
    return [
        Document(
            page_content=cleaned,
            metadata={
                "source": file_path.name,
                "titulo": meta_info.get("titulo", file_path.name),
                "cultura": meta_info.get("cultura", "tecnico"),
                "pagina": 1,
                "total_paginas": 1,
            }
        )
    ]

def run_ingestion(batch_size: int = 100):
    console.print("[bold green]=====================================================[/bold green]")
    console.print("[bold green]  INGESTÃO DE DOCUMENTOS EMBRAPA - CHATBOT RAG     [/bold green]")
    console.print("[bold green]  Lenovo HPC - Sprint 45                            [/bold green]")
    console.print("[bold green]=====================================================[/bold green]\n")

    # 1. Carregar documentos
    all_raw_docs: List[Document] = []
    files_to_process = [
        f for f in DOCUMENTS_DIR.iterdir()
        if f.name in DOC_METADATA_MAP
    ]

    console.print(f"[bold cyan]Encontrados {len(files_to_process)} documentos para indexação.[/bold cyan]\n")

    for file_path in files_to_process:
        meta = DOC_METADATA_MAP[file_path.name]
        console.print(f"[*] Processando: [bold yellow]{file_path.name}[/bold yellow] ({meta['titulo']})...")
        
        if file_path.suffix.lower() == ".pdf":
            docs = extract_pdf_documents(file_path, meta)
        elif file_path.suffix.lower() == ".md":
            docs = extract_markdown_documents(file_path, meta)
        else:
            continue
            
        console.print(f"   -> {len(docs)} páginas/seções extraídas com conteúdo útil.")
        all_raw_docs.extend(docs)

    console.print(f"\n[bold green]Total de páginas/documentos úteis:[/bold green] {len(all_raw_docs)}")

    # 2. Dividir em chunks (Chunking)
    console.print("\n[+] [bold cyan]Executando chunking dos documentos...[/bold cyan]")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=750,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""]
    )
    chunks = text_splitter.split_documents(all_raw_docs)
    console.print(f"   -> [bold green]Total de chunks gerados:[/bold green] {len(chunks)} chunks.")

    # 3. Inicializar Embeddings e ChromaDB
    console.print(f"\n[+] [bold cyan]Inicializando modelo de embedding local ([white]{EMBEDDING_MODEL}[/white])...[/bold cyan]")
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)

    console.print(f"[+] [bold cyan]Persistindo no ChromaDB ([white]{CHROMA_DIR}[/white])...[/bold cyan]")
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR)
    )

    # 4. Inserção em lotes com suporte a retomar de onde parou e retry
    total_chunks = len(chunks)
    current_count = vectorstore._collection.count()
    console.print(f"[+] Total de chunks: {total_chunks}. Já indexados anteriormente: {current_count}")
    
    if current_count >= total_chunks:
        console.print("[bold green][OK] Todos os chunks já foram indexados![/bold green]")
        return

    remaining_chunks = chunks[current_count:]
    batch_size = 40
    console.print(f"[+] [bold cyan]Indexando os {len(remaining_chunks)} chunks restantes em lotes de {batch_size}...[/bold cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[green]Indexando chunks...", total=len(remaining_chunks))
        
        for i in range(0, len(remaining_chunks), batch_size):
            batch = remaining_chunks[i : i + batch_size]
            sucesso = False
            for tentativa in range(4):
                try:
                    vectorstore.add_documents(batch)
                    sucesso = True
                    break
                except Exception as err:
                    time.sleep(2 * (tentativa + 1))
            if not sucesso:
                console.print(f"[bold red][Erro no lote {i}]:[/bold red] Não foi possível indexar após várias tentativas.")
            progress.update(task, advance=len(batch))

    total_final = vectorstore._collection.count()
    console.print(f"\n[bold green][OK] Ingestão concluída! Total de documentos no banco: {total_final}[/bold green]")
    console.print(f"[bold white]Banco de dados vetorial pronto em:[/bold white] {CHROMA_DIR}\n")

if __name__ == "__main__":
    t0 = time.time()
    run_ingestion()
    console.print(f"Tempo total de ingestão: {time.time() - t0:.1f} segundos.")
