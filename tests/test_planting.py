import unittest
from datetime import timedelta
from unittest.mock import Mock
from pydantic import ValidationError
from src.planting_context import PlantingPlan, planting_text
from src.assistant_graph import build_assistant_graph
from tests.test_weather import NOW, client_fixture


def plan_data(**changes):
    data = dict(id='p1', fazendaId='demo', talhaoId='t1', cultura='soja', cultivar='DEMO', ciclo_dias=115,
        municipio='Cuiabá', uf='MT', simulado=True, solo_textura='argilosa', solo_observado_em=NOW,
        umidade_volumetrica_pct=28, encharcado=False, trafegavel=True,
        umidade_min_demo_pct=20, umidade_max_demo_pct=35, janela_inicio='2026-10-01',
        janela_fim='2026-11-30', fonte_janela='SIMULACAO_NAO_ZARC')
    data.update(changes)
    return data


class PlantingTests(unittest.TestCase):
    def test_graph_blocks_missing_stale_and_adverse_plan(self):
        for changes in (None, {'encharcado': True}, {'umidade_volumetrica_pct': None},
                        {'solo_observado_em': NOW-timedelta(days=1)}, {'janela_fim': '2026-10-02'}):
            with self.subTest(changes=changes):
                rag, client = Mock(), Mock()
                snapshot = client_fixture().current(NOW)
                client.current.return_value = snapshot
                client.planting.return_value = {**snapshot, 'planting': PlantingPlan(**plan_data(**changes)) if changes is not None else None}
                events = list(build_assistant_graph(rag, client).stream(
                    {'question': 'Posso plantar soja hoje?', 'k': 4, 'culture': None}, stream_mode='custom'))
                rag.retrieve.assert_not_called()
                rag.generate_with_weather.assert_not_called()
                self.assertIn('Não é possível considerar', ''.join(e.get('content', '') for e in events))

    def test_soil_question_without_crop_reads_unique_plan_once(self):
        rag, client = Mock(), Mock()
        snapshot = client_fixture().current(NOW)
        client.current.return_value = snapshot
        client.planting.return_value = {**snapshot, 'planting': PlantingPlan(**plan_data())}
        events = list(build_assistant_graph(rag, client).stream(
            {'question': 'Qual a umidade do solo hoje?', 'k': 4, 'culture': None}, stream_mode='custom'))
        text = ''.join(e.get('content', '') for e in events)
        self.assertEqual(text.count('28% volumétricos'), 1)
        self.assertNotIn('não informada neste sensor', text.split('Fonte meteorológica')[1])
        client.planting.assert_called_once_with(snapshot, None)
        rag.retrieve.assert_not_called()

    def test_missing_soil_stays_missing_not_filled_from_legacy_field(self):
        snapshot = client_fixture(umidade_solo_pct=99).current(NOW)
        snapshot['planting'] = PlantingPlan(**plan_data(umidade_volumetrica_pct=None))
        self.assertIn('não informada', planting_text(snapshot))
        self.assertNotIn('99%', planting_text(snapshot))

    def text(self, **changes):
        return planting_text({'planting': PlantingPlan(**plan_data(**changes))}, NOW)

    def test_complete_plan_does_not_claim_missing(self):
        text = self.text()
        self.assertIn('atendem às regras FICTÍCIAS', text)
        self.assertNotIn('Ainda faltam', text)

    def test_adverse_conditions_and_window(self):
        for changes, expected in [({'encharcado': True}, 'solo encharcado'),
            ({'trafegavel': False}, 'sem trafegabilidade'),
            ({'umidade_volumetrica_pct': 10}, 'umidade fora'),
            ({'janela_inicio': '2026-11-01'}, 'fora da janela')]:
            self.assertIn(expected, self.text(**changes))

    def test_missing_and_old_soil(self):
        self.assertIn('Ainda faltam', self.text(umidade_volumetrica_pct=None))
        self.assertIn('registro antigo ou futuro', self.text(solo_observado_em=NOW-timedelta(days=1)))
        self.assertNotIn('atendem às regras', self.text(solo_observado_em=NOW+timedelta(hours=1)))

    def test_rejects_bad_ranges_and_fake_official_source(self):
        for changes in ({'janela_fim': '2026-09-01'}, {'umidade_max_demo_pct': 5},
                        {'fonte_janela': 'ZARC'}, {'umidade_volumetrica_pct': 120}):
            with self.assertRaises(ValidationError):
                PlantingPlan(**plan_data(**changes))

    def test_api_plan_binding_missing_and_ambiguity(self):
        client = client_fixture(talhaoId='t1')
        snapshot = client.current(NOW)
        snapshot['farm'].update(municipio='Cuiabá', uf='MT')
        for rows, valid in [([plan_data()], True), ([], False),
            ([plan_data(), plan_data()], False), ([plan_data(talhaoId='outra')], False),
            ([plan_data(cultura='milho')], False), ([plan_data(municipio='Outro')], False)]:
            client._get = Mock(return_value=rows)
            result = client.planting(snapshot, 'soja')
            self.assertEqual(result['planting'] is not None, valid)


if __name__ == '__main__':
    unittest.main()
