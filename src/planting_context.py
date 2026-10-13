"""Plano fictício de plantio: cadastro, estado do solo e janela de teste."""
from datetime import date, datetime, timezone, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from .weather_api import LOCAL_TZ


class PlantingPlan(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str
    fazendaId: str
    talhaoId: str
    cultura: str
    cultivar: str = Field(min_length=1)
    ciclo_dias: int = Field(ge=40, le=300)
    municipio: str
    uf: str
    simulado: Literal[True]
    solo_textura: str
    solo_observado_em: AwareDatetime
    umidade_volumetrica_pct: float | None = Field(default=None, ge=0, le=100)
    encharcado: bool | None = None
    trafegavel: bool | None = None
    umidade_min_demo_pct: float = Field(ge=0, le=100)
    umidade_max_demo_pct: float = Field(ge=0, le=100)
    janela_inicio: date
    janela_fim: date
    fonte_janela: Literal['SIMULACAO_NAO_ZARC']

    @model_validator(mode='after')
    def ordered(self):
        if self.janela_inicio > self.janela_fim or self.umidade_min_demo_pct >= self.umidade_max_demo_pct:
            raise ValueError('Intervalos invertidos no plano fictício')
        return self


def planting_issues(snapshot, now=None):
    plan = snapshot.get('planting')
    if plan is None:
        return [snapshot.get('planting_error', 'solo, cultivar e janela não cadastrados.')], []
    now = now or snapshot.get('checked_at') or datetime.now(timezone.utc)
    today = now.astimezone(LOCAL_TZ).date()
    age = now - plan.solo_observado_em
    current = (timedelta(0) <= age <= timedelta(hours=6)
               and plan.solo_observado_em.astimezone(LOCAL_TZ).date() == today)
    missing, blocks = [], []
    if not current:
        missing.append('observação atual do solo (registro antigo ou futuro)')
    if plan.umidade_volumetrica_pct is None:
        missing.append('umidade volumétrica do solo')
    elif current and not plan.umidade_min_demo_pct <= plan.umidade_volumetrica_pct <= plan.umidade_max_demo_pct:
        blocks.append('umidade fora do intervalo fictício de teste')
    for value, name, blocked in [(plan.encharcado, 'encharcamento', True), (plan.trafegavel, 'trafegabilidade', False)]:
        if value is None:
            missing.append(name)
        elif current and value == blocked:
            blocks.append('solo encharcado' if name == 'encharcamento' else 'solo sem trafegabilidade')
    inside = plan.janela_inicio <= today <= plan.janela_fim
    if not inside:
        blocks.append('data fora da janela fictícia cadastrada')
    return missing, blocks


def planting_text(snapshot, now=None):
    plan = snapshot.get('planting')
    if plan is None:
        return 'Plano de plantio indisponível: ' + snapshot.get('planting_error', 'solo, cultivar e janela não cadastrados.')
    now = now or snapshot.get('checked_at') or datetime.now(timezone.utc)
    inside = plan.janela_inicio <= now.astimezone(LOCAL_TZ).date() <= plan.janela_fim
    missing, blocks = planting_issues(snapshot, now)
    moisture = 'não informada' if plan.umidade_volumetrica_pct is None else f'{plan.umidade_volumetrica_pct:g}% volumétricos'
    yesno = lambda value: 'não informado' if value is None else ('sim' if value else 'não')
    lines = [f'Plano SIMULADO [PLANO]: {plan.talhaoId}, {plan.cultura}, {plan.municipio}/{plan.uf}.',
             f'Cultivar fictícia: {plan.cultivar}; ciclo cadastrado: {plan.ciclo_dias} dias.',
             f'Solo: {plan.solo_textura}. Umidade volumétrica do solo no talhão: {moisture}.',
             f'Encharcado: {yesno(plan.encharcado)}; trafegável: {yesno(plan.trafegavel)}.',
             'Observação do solo: ' + plan.solo_observado_em.astimezone(LOCAL_TZ).strftime('%d/%m/%Y %H:%M UTC−04:00') + '.',
             f'Janela FICTÍCIA: {plan.janela_inicio:%d/%m/%Y} a {plan.janela_fim:%d/%m/%Y}; hoje está ' + ('dentro.' if inside else 'fora.'),
             f'Regra de umidade somente para teste: {plan.umidade_min_demo_pct:g}–{plan.umidade_max_demo_pct:g}% volumétricos. Não é recomendação agronômica nem ZARC.']
    if missing:
        lines.append('Ainda faltam dados válidos: ' + '; '.join(missing) + '.')
    if blocks:
        lines.append('Restrições no cenário simulado: ' + '; '.join(blocks) + '.')
    if not missing and not blocks:
        lines.append('Solo e calendário atendem às regras FICTÍCIAS cadastradas para este cenário. Isso não confirma autorização de plantio real.')
    lines.append('Fonte [PLANO]: ' + snapshot.get('planting_url', 'API simulada'))
    return '\n'.join(lines)
