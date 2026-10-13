import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from langchain_core.documents import Document
from src.weather_api import WeatherClient, WeatherError, weather_text
from src.assistant_graph import build_assistant_graph, route_question
from src.rag_graph import EvidenceDecision

NOW = datetime(2026, 10, 13, 14, tzinfo=timezone.utc)


def client_fixture(**changes):
    row = dict(id='m1', fazendaId='demo', observado_em=NOW.isoformat(), simulado=True,
               temperatura_ar_c=28, chuva_24h_mm=12)
    row.update(changes)
    client = WeatherClient()
    client._get = Mock(side_effect=[{'id': 'demo', 'nome': 'Demo', 'fuso': 'America/Cuiaba'}, [row]])
    return client


def with_plan(snapshot, culture):
    from src.planting_context import PlantingPlan
    from tests.test_planting import plan_data
    return {**snapshot, 'planting': PlantingPlan(**plan_data())}


class WeatherTests(unittest.TestCase):
    def test_values_and_missing_soil(self):
        snapshot = client_fixture().current(NOW)
        self.assertTrue(snapshot['fresh'])
        self.assertIn('28 °C', weather_text(snapshot))
        self.assertNotIn('Umidade do solo', weather_text(snapshot))

    def test_stale_future_and_local_yesterday(self):
        for age in (timedelta(hours=7), timedelta(hours=-1)):
            self.assertFalse(client_fixture(observado_em=(NOW-age).isoformat()).current(NOW)['fresh'])
        midnight = NOW.replace(hour=4, minute=10)
        self.assertFalse(client_fixture(observado_em=(midnight-timedelta(minutes=20)).isoformat()).current(midnight)['fresh'])

    def test_invalid_and_other_farm(self):
        for change in ({'temperatura_ar_c': 200}, {'umidade_ar_pct': -2}, {'fazendaId': 'outra'}, {'observado_em': '2026-10-13'}):
            with self.subTest(change=change), self.assertRaises(WeatherError):
                client_fixture(**change).current(NOW)

    def test_timeout_is_reported(self):
        with patch('src.weather_api.urlopen', side_effect=TimeoutError), self.assertRaises(WeatherError):
            WeatherClient().current(NOW)

    def test_missing_plan_endpoint_reports_old_server(self):
        from urllib.error import HTTPError
        error = HTTPError('http://127.0.0.1:3001/planos_plantio', 404, 'Not Found', {}, None)
        with patch('src.weather_api.urlopen', side_effect=error):
            with self.assertRaisesRegex(WeatherError, 'API está ativa'):
                WeatherClient()._get('/planos_plantio?fazendaId=demo')

    def test_missing_farm_is_not_reported_as_server_offline(self):
        from urllib.error import HTTPError
        error = HTTPError('http://127.0.0.1:3001/fazendas/x', 404, 'Not Found', {}, None)
        with patch('src.weather_api.urlopen', side_effect=error):
            with self.assertRaisesRegex(WeatherError, 'HTTP 404'):
                WeatherClient()._get('/fazendas/x')

    def test_numeric_comparison_uses_document_limits(self):
        from src.rag_engine import AgriculturalRAG
        rag = AgriculturalRAG.__new__(AgriculturalRAG)
        rag.llm = Mock(side_effect=AssertionError('Não deve usar modelo nesta comparação'))
        # Faixa fictícia diferente daquela do documento real: prova que o
        # código não fixou valores agronômicos de 20–30.
        docs = [Document(page_content='A faixa de temperatura adequada para a semeadura de exemplo é de 10 ° C a 15 ° C.')]
        answer = ''.join(rag.generate_with_weather('Posso plantar hoje?', docs, client_fixture().current(NOW)))
        self.assertIn('fora desse intervalo [1]', answer)
        self.assertIn('[API]', answer)
        self.assertIn('não identifica explicitamente ar ou solo', answer)

    def test_document_route_does_not_call_api(self):
        rag, client = Mock(), Mock()
        rag.graph.stream.return_value = iter([{'type': 'token', 'content': 'Resposta documental'}])
        graph = build_assistant_graph(rag, client)
        events = list(graph.stream({'question': 'Qual é a origem da soja?', 'k': 4, 'culture': None}, stream_mode='custom'))
        client.current.assert_not_called()
        self.assertEqual(events[-1]['content'], 'Resposta documental')

    def test_missing_documents_does_not_generate_mixed_answer(self):
        rag, client = Mock(), Mock()
        rag.retrieve.return_value = []
        rag.rewrite_query.return_value = 'temperatura adequada semeadura soja'
        client.current.return_value = client_fixture().current(NOW)
        client.planting.side_effect = with_plan
        graph = build_assistant_graph(rag, client)
        events = list(graph.stream({'question': 'Posso plantar soja hoje?', 'k': 4, 'culture': None}, stream_mode='custom'))
        rag.generate_with_weather.assert_not_called()
        self.assertTrue(any('evidências suficientes' in e.get('content', '') for e in events))

    def test_routes(self):
        for q, expected in [
            ('Qual é a temperatura hoje da minha fazenda?', 'weather'),
            ('Quais condições climáticas hoje? Posso plantar soja?', 'mixed'),
            ('Posso plantar milho hoje?', 'mixed'),
            ('Qual a temperatura ideal para plantar soja?', 'documents'),
            ('Qual é a origem da soja?', 'documents'),
            ('Qual a importância da umidade do solo?', 'documents'),
            ('Como está a umidade do solo?', 'plan'),
            ('Qual é a janela de plantio na minha fazenda?', 'plan'),
            ('Posso plantar soja?', 'mixed'),
        ]:
            self.assertEqual(route_question(q), expected)

    def run_graph(self, question, snapshot=None, failure=None):
        rag = Mock()
        rag.retrieve.return_value = [Document(page_content='Trecho de requisitos de plantio.')]
        rag.evaluate.return_value = EvidenceDecision(decision='sufficient', evidence_ids=[1], reason='teste', clarification='')
        rag.generate_with_weather.return_value = iter(['Comparação com fontes [1] e [API].'])
        client = Mock()
        client.current.return_value = snapshot or client_fixture().current(NOW)
        client.planting.side_effect = with_plan
        client.current.side_effect = failure
        graph = build_assistant_graph(rag, client)
        events = list(graph.stream({'question': question, 'k': 4, 'culture': None}, stream_mode='custom'))
        text = ''.join(e['content'] for e in events if e['type'] == 'token')
        return rag, events, text

    def test_api_only_does_not_call_llm_or_retrieval(self):
        rag, events, text = self.run_graph('Qual temperatura hoje na fazenda?')
        rag.retrieve.assert_not_called()
        rag.generate_with_weather.assert_not_called()
        self.assertIn('28 °C', text)
        self.assertIn('SIMULADOS', text)

    def test_mixed_receives_api_and_documents(self):
        rag, events, text = self.run_graph('Posso plantar soja hoje?')
        rag.generate_with_weather.assert_called_once()
        question, docs, snapshot = rag.generate_with_weather.call_args.args
        self.assertEqual(question, 'Posso plantar soja hoje?')
        self.assertEqual(snapshot['measurement'].temperatura_ar_c, 28)
        self.assertTrue(docs)
        self.assertEqual(rag.retrieve.call_args.args[2], 'soja')
        self.assertIn('[API]', text)

    def test_stale_and_failed_api_never_generate_recommendation(self):
        stale = client_fixture(observado_em=(NOW-timedelta(days=1)).isoformat()).current(NOW)
        rag, _, text = self.run_graph('Posso plantar soja hoje?', snapshot=stale)
        rag.retrieve.assert_not_called()
        self.assertIn('não representa', text)
        rag, _, text = self.run_graph('Posso plantar soja hoje?', failure=WeatherError('API indisponível'))
        rag.generate_with_weather.assert_not_called()
        self.assertIn('Sem medições', text)

    def test_no_crop_or_forecast_does_not_generate(self):
        for question in ('Posso plantar hoje?', 'Posso plantar soja amanhã?'):
            rag, _, text = self.run_graph(question)
            rag.generate_with_weather.assert_not_called()


if __name__ == '__main__':
    unittest.main()
