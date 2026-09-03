import unittest

import app


class AppSmokeTests(unittest.TestCase):
    protected_routes = (
        '/',
        '/inventario',
        '/sessoes',
        '/sessoes/registrar',
        '/sessoes/devolucao',
        '/historico/devolucoes',
        '/historico_geral',
        '/manutencao/dashboard',
        '/manutencao/historico',
        '/almoxarifado/',
        '/almoxarifado/produtos',
        '/agendamentos/historico',
    )

    def setUp(self):
        self.client = app.app.test_client()

    def test_protected_pages_redirect_to_login_without_session(self):
        for route in self.protected_routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/login', response.headers['Location'])

    def test_admin_can_load_operational_pages(self):
        admin_session = {
            'user_id': 1,
            'username': 'admin',
            'perm_movimentacao': 1,
            'perm_cadastro': 1,
            'perm_config': 1,
            'perm_kiosk': 1,
            'perm_chamados': 1,
            'perm_ajuda': 1,
            'perm_almoxarifado': 1,
            'modules': {
                'iot': True,
                'helpdesk': True,
                'storeroom': True,
            },
        }
        with self.client.session_transaction() as session:
            session.update(admin_session)

        for route in self.protected_routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)

    def test_availability_api_returns_items_for_authenticated_user(self):
        with self.client.session_transaction() as session:
            session.update({
                'user_id': 1,
                'username': 'admin',
                'perm_movimentacao': 1,
            })

        response = self.client.get(
            '/api/disponibilidade?data=2026-08-28&'
            'hora_inicio=17:00&hora_fim=21:00'
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsInstance(payload, dict)
        self.assertIn('items', payload)
        self.assertIsInstance(payload['items'], list)
        if payload['items']:
            self.assertIn('id', payload['items'][0])
            self.assertIn('status_visual', payload['items'][0])

    def test_sync_status_api_returns_queue_state(self):
        with self.client.session_transaction() as session:
            session.update({'user_id': 1, 'username': 'admin'})

        response = self.client.get('/api/sincronizacao/status')

        self.assertEqual(response.status_code, 200)
        self.assertIn('pending_count', response.get_json())
        self.assertIn('is_synced', response.get_json())

    def test_asset_edit_page_builds_cancel_link(self):
        with self.client.session_transaction() as session:
            session.update({
                'user_id': 1,
                'username': 'admin',
                'perm_cadastro': 1,
            })

        response = self.client.get('/editar/99999')

        self.assertNotEqual(response.status_code, 500)


if __name__ == '__main__':
    unittest.main()
