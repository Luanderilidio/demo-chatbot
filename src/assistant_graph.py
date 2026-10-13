"""LangGraph externo: documentos, API meteorológica ou combinação das fontes."""
import re
import unicodedata
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from .rag_graph import build_rag_graph, initial_state
from .weather_api import WeatherError, weather_text
from .planting_context import planting_text, planting_issues


def plain(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))


def unsupported_time(question):
    return bool(re.search(r'amanha|ontem|previsao|semana|proximos dias|vai chover|ira chover|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}', plain(question)))


def route_question(question):
    q = plain(question)
    local = bool(re.search(r'\b(hoje|agora|fazenda|atual|atuais|amanha|ontem)\b', q))
    weather = bool(re.search(r'temperatura|umidade|chuva|chov|vento|clima|climatic|meteorolog|previsao', q))
    action = bool(re.search(r'plantar|plantio|semear|semeadura|irrigar|irrigacao|pulverizar|pulverizacao', q))
    general = bool(re.search(r'ideal|adequad|recomend|exigencia|necessita|o que e|qual a importancia', q))
    if not local and general:
        return 'documents'
    if (local and action and re.search(r'posso|devo|pode|condic', q)) or (action and re.search(r'posso|devo|pode|favorave', q)):
        return 'mixed'
    if (local and re.search(r'cultivar|janela|condic.*solo', q)) or re.search(r'umidade.*solo', q):
        return 'plan'
    if local and action:
        return 'mixed'
    if weather and (local or not re.search(r'ideal|adequad|recomend|exigencia|necessita', q)):
        return 'weather'
    return 'documents'


class AssistantState(TypedDict):
    question: str
    k: int
    culture: str | None
    route: str
    snapshot: dict | None
    error: str


def build_assistant_graph(rag, weather_client):
    def event(node):
        get_stream_writer()({'type': 'step', 'node': node, 'attempt': 0})

    def emit(text):
        get_stream_writer()({'type': 'token', 'content': text})

    def classify(state):
        event('rotear')
        return {'route': route_question(state['question']), 'snapshot': None, 'error': ''}

    def consult(state):
        event('consultar_api')
        try:
            return {'snapshot': weather_client.current()}
        except WeatherError as error:
            return {'error': str(error)}

    def direct(state):
        event('responder_api')
        get_stream_writer()({'type': 'sources', 'docs': []})
        if state['error']:
            emit(state['error'] + '\nNão tenho medições disponíveis para responder sobre a fazenda.')
        else:
            emit(weather_text(state['snapshot']))
            if unsupported_time(state['question']):
                emit('\nEsta integração só consulta a última medição; não fornece previsão nem histórico para a data solicitada.')
                return {}
            if state['route'] == 'plan':
                crops = [c for c in ('soja', 'milho', 'arroz') if re.search(r'\b' + c + r'\b', plain(state['question']))]
                culture = crops[0] if len(crops) == 1 else state['culture']
                if len(crops) > 1:
                    emit('\nInforme uma única cultura para consultar o plano.')
                else:
                    emit('\n\n' + planting_text(weather_client.planting(state['snapshot'], culture)))
        return {}

    def documents(state):
        writer = get_stream_writer()
        for item in rag.graph.stream(initial_state(state['question'], state['k'], state['culture']), stream_mode='custom'):
            writer(item)
        return {}

    def mixed(state):
        event('combinar_fontes')
        writer = get_stream_writer()
        writer({'type': 'sources', 'docs': []})
        if state['error']:
            emit(state['error'] + '\nSem medições, não consigo avaliar as condições atuais da fazenda. Você pode perguntar pelos requisitos gerais da cultura.')
            return {}
        snapshot = state['snapshot']
        emit(weather_text(snapshot) + '\n\n')
        if not snapshot['fresh']:
            emit('Não vou usar essa medição para avaliar uma operação hoje.')
            return {}
        q = plain(state['question'])
        if unsupported_time(state['question']):
            emit('A última medição não é uma previsão nem um histórico. Não posso avaliar a operação na data solicitada.')
            return {}
        crops = [crop for crop in ('soja', 'milho', 'arroz') if re.search(r'\b' + crop + r'\b', q)]
        culture = crops[0] if len(crops) == 1 else state['culture']
        if len(crops) > 1 or not culture:
            emit('Informe uma cultura na pergunta completa ou use /filtro soja para consultar os requisitos nos documentos.')
            return {}
        if re.search(r'plantar|plantio|semear|semeadura', q):
            snapshot = weather_client.planting(snapshot, culture)
            emit(planting_text(snapshot) + '\n\n')
            missing, blocks = planting_issues(snapshot)
            if missing or blocks:
                emit('Não é possível considerar este cenário favorável ao plantio: resolva as pendências ou restrições do plano indicadas acima. A comparação isolada de temperatura não elimina esses problemas.')
                return {}
            # Uma consulta específica permite comparar a temperatura medida;
            # não transforma esse único critério em autorização de plantio.
            technical = f'Quais são as melhores condições de temperatura para a semeadura de {culture}?'
        else:
            technical = f'Quais requisitos meteorológicos devem ser considerados nesta operação com {culture}: {state["question"]}?'
        # Estado e contexto por chamada: medições não entram na base vetorial,
        # no avaliador documental ou em outra conversa.
        def combined_generate(_, docs):
            yield from rag.generate_with_weather(state['question'], docs, snapshot)
        graph = build_rag_graph(rag.retrieve, rag.evaluate, rag.rewrite_query, combined_generate)
        for item in graph.stream(initial_state(technical, state['k'], culture), stream_mode='custom'):
            writer(item)
        emit('\n\nAnálise demonstrativa com dados fictícios. Os documentos fornecem critérios técnicos, mas esta simulação não substitui a verificação real do talhão e do zoneamento aplicável. Não há previsão do tempo nesta API.')
        return {}

    graph = StateGraph(AssistantState)
    for name, fn in [('rotear', classify), ('consultar_api', consult), ('documentos', documents),
                     ('responder_api', direct), ('combinar_fontes', mixed)]:
        graph.add_node(name, fn)
    graph.add_edge(START, 'rotear')
    graph.add_conditional_edges('rotear', lambda s: 'documentos' if s['route'] == 'documents' else 'consultar_api')
    graph.add_conditional_edges('consultar_api', lambda s: 'combinar_fontes' if s['route'] == 'mixed' else 'responder_api')
    for name in ('documentos', 'responder_api', 'combinar_fontes'):
        graph.add_edge(name, END)
    return graph.compile()
