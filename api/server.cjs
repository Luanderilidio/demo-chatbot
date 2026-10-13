const jsonServer = require('json-server');
const path = require('node:path');
const fs = require('node:fs');
const dbPath = process.env.RAG_WEATHER_DB || path.join(__dirname, 'db.json');
if (!fs.existsSync(dbPath)) {
  if (process.env.RAG_WEATHER_DB) throw new Error('RAG_WEATHER_DB aponta para um arquivo inexistente.');
  require('./seed.cjs');
}
const server = jsonServer.create();
server.use(jsonServer.defaults({static: path.join(__dirname, 'public')}));
server.use((req, res, next) => {
  res.setHeader('X-Dados-Simulados', 'true');
  res.setHeader('Cache-Control', 'no-store');
  next();
});
server.use(jsonServer.bodyParser);
// Recarrega edições externas (inclusive seed) antes de atender. Nunca mantém
// silenciosamente dados antigos em memória nem serve a última versão válida
// quando o JSON atual está quebrado.
let router;
let lastContents;
server.get('/health', (_req, res) => res.json({service: 'rag-fazenda-demo', version: 2, simulado: true}));
server.use((req, res, next) => {
  try {
    const contents = fs.readFileSync(dbPath, 'utf8');
    JSON.parse(contents);
    if (!router || contents !== lastContents) {
      router = jsonServer.router(dbPath);
      lastContents = contents;
    }
  } catch (_error) {
    return res.status(503).json({error: 'db.json inválido ou indisponível. Corrija o arquivo; dados antigos não serão utilizados.'});
  }
  return router(req, res, next);
});
const port = Number(process.env.RAG_WEATHER_PORT || 3001);
const listener = server.listen(port, '127.0.0.1', () => {
  console.log(`API FICTÍCIA: http://127.0.0.1:${port}/fazendas, /medicoes e /planos_plantio`);
  console.log('Horários não são atualizados automaticamente. Use seed.cjs para renovar a simulação.');
});
listener.on('error', (error) => {
  if (error.code === 'EADDRINUSE') {
    console.error(`A porta ${port} já está ocupada por outra API. Esta nova instância NÃO foi iniciada. Encerre a anterior com Ctrl+C e tente novamente.`);
    process.exitCode = 1;
  } else {
    console.error(error);
    process.exitCode = 1;
  }
});
