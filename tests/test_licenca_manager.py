import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from database_local import LocalDatabase
from licenca_manager import LicencaManager


class LicencaManagerOfflineTests(unittest.TestCase):
    def setUp(self):
        self.db = LocalDatabase(':memory:')
        self.manager = LicencaManager(
            db=self.db,
            serial_pdv='PDV-TESTE-001',
            chave_ativacao='LIC-TESTE-123',
            colegio_id='colegio-123'
        )

    def test_offline_with_recent_valid_license_is_allowed(self):
        self.db.salvar_estado(
            serial_pdv='PDV-TESTE-001',
            chave_ativacao='LIC-TESTE-123',
            colegio_id='colegio-123',
            status='ativa',
            ultima_checagem=datetime.now(timezone.utc),
            ultima_validacao_sucesso=datetime.now(timezone.utc),
            bloqueado=0,
        )

        self.assertTrue(self.manager.validar_licenca_local())

    def test_offline_after_three_days_is_blocked(self):
        old_date = datetime.now(timezone.utc) - timedelta(days=4)

        self.db.salvar_estado(
            serial_pdv='PDV-TESTE-001',
            chave_ativacao='LIC-TESTE-123',
            colegio_id='colegio-123',
            status='ativa',
            ultima_checagem=old_date,
            ultima_validacao_sucesso=old_date,
            bloqueado=0,
        )

        self.assertFalse(self.manager.validar_licenca_local())

    def test_application_uses_supabase_license_when_configured(self):
        import app

        previous_enabled = app.app.config['SUPABASE_ENABLED']
        app.app.config['SUPABASE_ENABLED'] = True
        app._license_cache = {'time': 0, 'data': None}
        with patch('app.get_saas_license_info', return_value=('VALID', 0, {'iot': True})):
            try:
                self.assertEqual(app.get_license_info(force_revalidate=True)[0], 'VALID')
            finally:
                app.app.config['SUPABASE_ENABLED'] = previous_enabled
                app._license_cache = {'time': 0, 'data': None}


if __name__ == '__main__':
    unittest.main()
