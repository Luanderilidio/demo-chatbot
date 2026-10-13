"""Cliente HTTP da API fictícia. Nunca inventa medições nem reutiliza cache."""
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen
from urllib.parse import urlencode, quote
from urllib.error import URLError, HTTPError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, AwareDatetime

LOCAL_TZ = timezone(timedelta(hours=-4))  # Fazenda demonstrativa em Cuiabá.


class Measurement(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str
    fazendaId: str
    talhaoId: str | None = None
    observado_em: AwareDatetime
    simulado: bool
    temperatura_ar_c: float | None = Field(default=None, ge=-60, le=65)
    umidade_ar_pct: float | None = Field(default=None, ge=0, le=100)
    chuva_24h_mm: float | None = Field(default=None, ge=0, le=2000)
    vento_kmh: float | None = Field(default=None, ge=0, le=400)
    temperatura_solo_c: float | None = Field(default=None, ge=-30, le=90)


class WeatherError(Exception):
    pass


class WeatherClient:
    def __init__(self, base_url=None, farm_id=None):
        self.base_url = (base_url or os.getenv('RAG_WEATHER_URL', 'http://127.0.0.1:3001')).rstrip('/')
        self.farm_id = farm_id or os.getenv('RAG_FARM_ID', 'demo')

    def _get(self, path):
        try:
            with urlopen(self.base_url + path, timeout=3) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404 and path.startswith('/planos_plantio?'):
                raise WeatherError(f'A API está ativa em {self.base_url}, mas não disponibiliza /planos_plantio. Reinicie a instância correspondente com .\\iniciar_api.bat.') from error
            raise WeatherError(f'A API respondeu HTTP {error.code} ao consultar {path.split("?")[0]}. Confira o cadastro e a versão do servidor.') from error
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise WeatherError('API meteorológica indisponível ou resposta inválida. Abra iniciar_api.bat e tente novamente.') from error

    def current(self, now=None):
        now = now or datetime.now(timezone.utc)
        farm = self._get('/fazendas/' + quote(self.farm_id, safe=''))
        rows = self._get('/medicoes?' + urlencode({'fazendaId': self.farm_id}))
        if not isinstance(farm, dict) or str(farm.get('id')) != self.farm_id or farm.get('fuso') != 'America/Cuiaba':
            raise WeatherError('Fazenda não encontrada ou fuso não suportado. Esta demonstração usa America/Cuiaba.')
        if not isinstance(rows, list) or not rows:
            raise WeatherError('A API não contém medições para a fazenda configurada.')
        try:
            readings = [Measurement.model_validate(row) for row in rows]
        except ValidationError as error:
            raise WeatherError('Medições inválidas: confira unidades, limites e horário com fuso no JSON.') from error
        if any(row.fazendaId != self.farm_id for row in readings):
            raise WeatherError('A API retornou uma medição de outra fazenda.')
        if len({row.talhaoId for row in readings}) > 1:
            raise WeatherError('Há medições de vários talhões. Configure um cadastro de demonstração com um único talhão; não vou escolher um arbitrariamente.')
        reading = max(readings, key=lambda row: row.observado_em)
        age = now - reading.observado_em
        fresh = (timedelta(0) <= age <= timedelta(hours=6)
                 and now.astimezone(LOCAL_TZ).date() == reading.observado_em.astimezone(LOCAL_TZ).date())
        return {'farm': farm, 'measurement': reading, 'fresh': fresh, 'checked_at': now,
                'url': self.base_url + '/medicoes/' + quote(reading.id, safe='')}

    def planting(self, snapshot, culture=None):
        from .planting_context import PlantingPlan
        try:
            filters = {'fazendaId': self.farm_id}
            if culture:
                filters['cultura'] = culture
            rows = self._get('/planos_plantio?' + urlencode(filters))
            if not isinstance(rows, list) or len(rows) != 1:
                raise WeatherError('É necessário exatamente um plano para a cultura/fazenda; cadastro ausente ou talhão ambíguo.')
            plan = PlantingPlan.model_validate(rows[0])
            farm = snapshot['farm']
            if (plan.fazendaId != self.farm_id or (culture and plan.cultura != culture)
                    or plan.municipio != farm.get('municipio') or plan.uf != farm.get('uf')
                    or plan.talhaoId != snapshot['measurement'].talhaoId):
                raise WeatherError('Plano não corresponde à fazenda, cultura ou município configurado.')
            return {**snapshot, 'planting': plan, 'planting_url': self.base_url + '/planos_plantio/' + quote(plan.id, safe='')}
        except ValidationError:
            return {**snapshot, 'planting': None, 'planting_error': 'Cadastro inválido: confira campos obrigatórios, datas, unidades e limites do plano.'}
        except WeatherError as error:
            return {**snapshot, 'planting': None, 'planting_error': str(error)}


def weather_text(snapshot):
    row = snapshot['measurement']
    # Este conector atende uma API fictícia, mesmo se alguém editar simulado=false.
    lines = ['DADOS SIMULADOS — não são leituras de uma estação real.',
             f"Fazenda configurada: {snapshot['farm'].get('nome', row.fazendaId)} ({row.fazendaId}).",
             'Última medição: ' + row.observado_em.astimezone(LOCAL_TZ).strftime('%d/%m/%Y %H:%M UTC−04:00') + '.']
    if not snapshot['fresh']:
        lines.append('ATENÇÃO: medição antiga ou com horário futuro; não representa as condições atuais. Renove os dados demonstrativos.')
    for name, label, unit in [
        ('temperatura_ar_c', 'Temperatura do ar', '°C'),
        ('umidade_ar_pct', 'Umidade relativa do ar', '%'),
        ('chuva_24h_mm', 'Chuva acumulada nas 24 h anteriores à medição', 'mm'),
        ('vento_kmh', 'Velocidade do vento', 'km/h'),
        ('temperatura_solo_c', 'Temperatura do solo', '°C'),
    ]:
        value = getattr(row, name)
        lines.append(f"{label}: {value:g} {unit}." if value is not None else f'{label}: não informada neste sensor.')
    lines.append('Fonte meteorológica [API]: ' + snapshot['url'])
    return '\n'.join(lines)
