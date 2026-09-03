import os
import unittest

from auth import DeviceTenantMismatchError, _permissions_for_role, _validate_device_tenant


class AuthPermissionTests(unittest.TestCase):
    def test_general_admin_has_all_operational_permissions(self):
        permissions = _permissions_for_role('admin_geral')

        self.assertTrue(all(permissions.values()))

    def test_teacher_cannot_access_operational_modules(self):
        permissions = _permissions_for_role('professor')

        self.assertTrue(permissions['perm_ajuda'])
        self.assertFalse(permissions['perm_config'])
        self.assertFalse(permissions['perm_cadastro'])
        self.assertFalse(permissions['perm_chamados'])

    def test_device_rejects_profile_from_another_tenant(self):
        original_tenant = os.environ.get('COLEGIO_ID')
        os.environ['COLEGIO_ID'] = 'tenant-local'
        try:
            with self.assertRaises(DeviceTenantMismatchError):
                _validate_device_tenant({'colegio_id': 'tenant-other'})
        finally:
            if original_tenant is None:
                os.environ.pop('COLEGIO_ID', None)
            else:
                os.environ['COLEGIO_ID'] = original_tenant