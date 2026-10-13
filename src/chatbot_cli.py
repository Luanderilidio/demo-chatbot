"""
Interface CLI Interativa do Chatbot Agricola Embrapa (RAG + Ollama)
Projeto Lenovo HPC - Sprint 45
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional

# Garante suporte UTF-8 no Windows Console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

from .rag_engine import AgriculturalRAG, CHROMA_DIR, LLM_MODEL, EMBEDDING_MODEL

console = Console(legacy_windows=False)

def show_banner():
    banner_text = (
        "[bold green]CHATBOT AGRÍCOLA INTELIGENTE — EMBRAPA & LENOVO HPC[/bold green]\n"
        "[dim]RAG com LangGraph: busca, avaliação e resposta com modelo local (Ollama)[/dim]\n\n"
        "[yellow]Meteorologia: API com dados SIMULADOS da fazenda configurada.[/yellow]\n\n"
        "[bold white]Culturas & Documentos Indexados:[/bold white]\n"
        "  • [yellow]Soja[/yellow] (500 Perguntas)\n"
        "  • [yellow]Milho[/yellow] (500 Perguntas)\n"
        "  • [yellow]Arroz[/yellow] (500 Perguntas)\n"
        "  • [yellow]Hortaliças & Pós-Colheita[/yellow] (500 Perguntas + Guia das 50 Hortaliças)\n"
        "  • [yellow]Estudo Técnico LMCT-2919[/yellow] (Arquitetura RAG & LLMs Sprint 45)\n\n"
        "[dim]Comandos: /ajuda | /filtro <cultura> | /fontes | /fluxo | /limpar | /sair[/dim]"
    )
    console.print(Panel(banner_text, border_style="green", expand=False))

def show_help():
    table = Table(title="Comandos do Chatbot", border_style="cyan")
    table.add_column("Comando", style="bold yellow", no_wrap=True)
    table.add_column("Descrição", style="white")
    table.add_row("/ajuda", "Mostra esta lista de instruções e comandos.")
    table.add_row("/filtro <cultura>", "Filtra a busca por cultura: soja, milho, arroz, hortalicas, pos-colheita ou off.")
    table.add_row("/fontes", "Ativa ou desativa a exibição dos trechos completos recuperados da Embrapa.")
    table.add_row("/fluxo", "Mostra as etapas percorridas: busca, avaliação, nova busca ou resposta.")
    table.add_row("/limpar", "Limpa a tela do terminal.")
    table.add_row("/sair", "Encerra o chatbot.")
    console.print(table)

def main():
    if not CHROMA_DIR.exists():
        console.print("[bold red][ERRO][/bold red] A base vetorial não foi encontrada!")
        console.print(f"Por favor, execute primeiro o script de ingestão: [bold yellow]python ingest.py[/bold yellow]")
        sys.exit(1)

    console.clear()
    show_banner()
    
    with console.status("[bold green]Carregando base vetorial e conectando ao Ollama...", spinner="dots"):
        try:
            rag = AgriculturalRAG()
        except Exception as e:
            console.print(f"[bold red][ERRO ao inicializar RAG]:[/bold red] {e}")
            console.print("[yellow]Verifique se o Ollama está rodando ('ollama list').[/yellow]")
            sys.exit(1)
            
    console.print(f"[bold green][OK][/bold green] Conectado ao LLM local ([bold cyan]{LLM_MODEL}[/bold cyan]) e embeddings ([bold cyan]{EMBEDDING_MODEL}[/bold cyan]).\n")

    mostrar_fontes_completas = False
    mostrar_fluxo = False
    cultura_ativa: Optional[str] = None

    while True:
        try:
            prompt_label = "Você"
            if cultura_ativa:
                prompt_label += f" [{cultura_ativa.upper()}]"
            
            console.print(f"[bold green]{prompt_label} >[/bold green] ", end="")
            user_input = input().strip()
            
            if not user_input:
                continue

            # Comandos
            lower_input = user_input.lower()
            if lower_input in ["/sair", "sair", "exit", "quit"]:
                console.print("\n[bold yellow]Encerrando o Chatbot Agrícola. Até logo![/bold yellow]\n")
                break
                
            elif lower_input in ["/ajuda", "ajuda", "help", "/help"]:
                show_help()
                continue
                
            elif lower_input in ["/limpar", "clear", "cls"]:
                console.clear()
                show_banner()
                continue
                
            elif lower_input == "/fontes":
                mostrar_fontes_completas = not mostrar_fontes_completas
                status = "[green]ATIVADA[/green]" if mostrar_fontes_completas else "[yellow]DESATIVADA[/yellow]"
                console.print(f"Exibição detalhada de trechos de fontes: {status}")
                continue
                
            elif lower_input == "/fluxo":
                mostrar_fluxo = not mostrar_fluxo
                console.print("Exibição do fluxo " + ("ativada." if mostrar_fluxo else "desativada."))
                continue

            elif lower_input.startswith("/filtro"):
                partes = user_input.split(maxsplit=1)
                if len(partes) > 1 and partes[1].lower() not in ["off", "nenhum", "todas", "geral"]:
                    cultura_ativa = partes[1].lower().strip()
                    console.print(f"[green]Filtro de busca definido para a cultura:[/green] [bold yellow]{cultura_ativa.upper()}[/bold yellow]")
                else:
                    cultura_ativa = None
                    console.print("[yellow]Filtro por cultura desativado. Buscando em todo o corpus.[/yellow]")
                continue

            # Processamento de Pergunta
            console.print(f"\n[bold cyan]Assistente Embrapa >[/bold cyan] ", end="")
            sys.stdout.flush()

            docs_recuperados = []
            resposta_completa = []
            etapas = []

            generator = rag.stream_answer(user_input, k=4, cultura_filtro=cultura_ativa)
            
            mensagens = {
                "rotear": "Identificando as fontes necessárias...",
                "consultar_api": "Consultando a API meteorológica simulada...",
                "responder_api": "Apresentando as medições...",
                "combinar_fontes": "Relacionando medições e documentos...",
                "buscar": "Buscando nos documentos...",
                "avaliar": "Verificando se os trechos permitem responder...",
                "reformular": "Preparando uma nova busca...",
                "responder": "Preparando a resposta...",
                "esclarecer": "Preparando um pedido de esclarecimento...",
                "sem_evidencia": "Finalizando a consulta...",
            }
            status = console.status("Consultando a base...", spinner="dots")
            status.start()
            try:
                for item in generator:
                    if item["type"] == "step":
                        etapas.append(item["node"])
                        status.update(mensagens.get(item["node"], "Consultando..."))
                    elif item["type"] == "sources":
                        docs_recuperados = item["docs"]
                    elif item["type"] == "token":
                        status.stop()
                        token = item["content"]
                        resposta_completa.append(token)
                        print(token, end="", flush=True)
            finally:
                status.stop()

            print("\n")
            if mostrar_fluxo:
                console.print("Fluxo: " + " → ".join(etapas), style="dim", markup=False)

            # Exibe tabela de fontes resumida
            if docs_recuperados:
                fontes_table = Table(title="Evidências selecionadas para a resposta", border_style="dim", box=None)
                fontes_table.add_column("#", style="dim", width=3)
                fontes_table.add_column("Publicação", style="green")
                fontes_table.add_column("Página", style="yellow", justify="center")
                fontes_table.add_column("Cultura", style="cyan")

                # Mesmos identificadores do prompt, inclusive quando dois trechos
                # pertencem à mesma página: não renumerar por deduplicação.
                for idx, d in enumerate(docs_recuperados, 1):
                    meta = d.metadata
                    titulo = meta.get("titulo", meta.get("source", "Documento"))
                    pag = str(meta.get("pagina", "-"))
                    cul = meta.get("cultura", "-").upper()
                    fontes_table.add_row(str(idx), titulo, pag, cul)
                
                console.print(fontes_table)

            # Se ativado, exibe os trechos brutos
            if mostrar_fontes_completas and docs_recuperados:
                console.print("\n[dim]=== TRECHOS BRUTOS EXTRAÍDOS ===[/dim]")
                for i, doc in enumerate(docs_recuperados, 1):
                    p = Panel(
                        doc.page_content,
                        title=f"Trecho #{i} - {doc.metadata.get('titulo')} (pág. {doc.metadata.get('pagina')})",
                        border_style="dim"
                    )
                    console.print(p)

            console.print("-" * 60 + "\n")

        except (KeyboardInterrupt, EOFError):
            console.print("\n\n[bold yellow]Interrompido pelo usuário. Até logo![/bold yellow]\n")
            break
        except Exception as e:
            console.print(f"\n[bold red][Erro ao processar consulta]:[/bold red] {e}\n")

if __name__ == "__main__":
    main()
