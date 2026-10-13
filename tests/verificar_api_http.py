"""Integração HTTP isolada: python -m tests.verificar_api_http (requer Node)."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[1]


class RealJSONServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.db = Path(cls.folder.name) / 'db.json'
        cls.data = {'medicoes': [{'id': 'm1', 'temperatura_ar_c': 28}], 'planos_plantio': []}
        cls.db.write_text(json.dumps(cls.data), encoding='utf-8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.url = f'http://127.0.0.1:{port}'
        cls.process = subprocess.Popen([shutil.which('node'), str(ROOT / 'api/server.cjs')],
            env={**os.environ, 'RAG_WEATHER_PORT': str(port), 'RAG_WEATHER_DB': str(cls.db)},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(100):
            try:
                with urlopen(cls.url + '/health', timeout=1) as response:
                    if json.load(response)['version'] == 2:
                        return
            except URLError:
                time.sleep(.1)
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.folder.cleanup()
        raise AssertionError('Servidor de teste não iniciou')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)
        cls.folder.cleanup()

    def setUp(self):
        self.db.write_text(json.dumps(self.data), encoding='utf-8')

    def get(self, path):
        with urlopen(self.url + path, timeout=3) as response:
            return json.load(response)

    def test_external_edit_is_visible_without_restart(self):
        self.assertEqual(self.get('/medicoes/m1')['temperatura_ar_c'], 28)
        updated = {**self.data, 'medicoes': [{'id': 'm1', 'temperatura_ar_c': 31}]}
        self.db.write_text(json.dumps(updated), encoding='utf-8')
        self.assertEqual(self.get('/medicoes/m1')['temperatura_ar_c'], 31)

    def test_new_resource_is_loaded_without_restart(self):
        updated = {**self.data, 'novo_recurso': [{'id': 'p1', 'simulado': True}]}
        self.db.write_text(json.dumps(updated), encoding='utf-8')
        self.assertTrue(self.get('/novo_recurso/p1')['simulado'])

    def test_invalid_json_does_not_serve_stale_values_and_recovers(self):
        self.get('/medicoes/m1')
        self.db.write_text('{broken', encoding='utf-8')
        with self.assertRaises(HTTPError) as context:
            self.get('/medicoes/m1')
        self.assertEqual(context.exception.code, 503)
        self.db.write_text(json.dumps(self.data), encoding='utf-8')
        self.assertEqual(self.get('/medicoes/m1')['temperatura_ar_c'], 28)

    def test_patch_is_persisted_and_not_lost_on_reload(self):
        request = Request(self.url + '/medicoes/m1', data=b'{"temperatura_ar_c": 33}',
                          headers={'Content-Type': 'application/json'}, method='PATCH')
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(self.get('/medicoes/m1')['temperatura_ar_c'], 33)
        self.assertEqual(json.loads(self.db.read_text(encoding='utf-8'))['medicoes'][0]['temperatura_ar_c'], 33)


if __name__ == '__main__':
    unittest.main()
