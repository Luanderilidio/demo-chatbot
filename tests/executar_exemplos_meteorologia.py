"""Teste real: iniciar_api.bat e Ollama devem estar ativos. Não altera a API."""
import json
from pathlib import Path
from time import perf_counter
from src.rag_engine import AgriculturalRAG


def main():
    rag = AgriculturalRAG()
    records = []
    for question in ['Qual é a temperatura hoje da minha fazenda?',
                     'Quais as condições climáticas hoje? Posso plantar a soja?']:
        start = perf_counter()
        record = {'pergunta': question, 'etapas': [], 'resposta': '', 'fontes_documentais': []}
        for event in rag.stream_answer(question):
            if event['type'] == 'step':
                record['etapas'].append(event['node'])
                print(event['node'], flush=True)
            elif event['type'] == 'token':
                record['resposta'] += event['content']
            elif event['type'] == 'sources':
                record['fontes_documentais'] = [d.metadata for d in event['docs']]
        record['segundos'] = round(perf_counter()-start, 2)
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        Path('tests/resultados_meteorologia.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
