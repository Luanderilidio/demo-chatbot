// Execução explícita: recria somente os dados demonstrativos desta API.
const fs = require('node:fs');
const path = require('node:path');
const now = new Date();
const year = Number(new Intl.DateTimeFormat('en', {year:'numeric', timeZone:'America/Cuiaba'}).format(now));
const db = {
  fazendas: [{id: 'demo', nome: 'Fazenda Demonstração', municipio: 'Cuiabá',
    uf: 'MT', fuso: 'America/Cuiaba', simulado: true}],
  medicoes: [{id: 'demo-atual', fazendaId: 'demo', talhaoId: 'talhao-demo-01', observado_em: new Date().toISOString(),
    simulado: true, temperatura_ar_c: 28, umidade_ar_pct: 68,
    chuva_24h_mm: 12, vento_kmh: 8, temperatura_solo_c: 25}],
  planos_plantio: [{id: 'demo-soja', fazendaId: 'demo', talhaoId: 'talhao-demo-01',
    cultura: 'soja', cultivar: 'SOJA-DEMO-001 (fictícia)', ciclo_dias: 115,
    municipio: 'Cuiabá', uf: 'MT', simulado: true, solo_textura: 'argilosa (simulada)',
    solo_observado_em: now.toISOString(), umidade_volumetrica_pct: 28,
    encharcado: false, trafegavel: true,
    umidade_min_demo_pct: 20, umidade_max_demo_pct: 35,
    janela_inicio: `${year}-10-01`, janela_fim: `${year}-11-30`,
    fonte_janela: 'SIMULACAO_NAO_ZARC'}]
};
fs.writeFileSync(path.join(__dirname, 'db.json'), JSON.stringify(db, null, 2) + '\n');
console.log('Dados FICTÍCIOS recriados com horário atual. Nenhuma estação real foi consultada.');
