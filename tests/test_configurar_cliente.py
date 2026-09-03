import tempfile
import unittest
from pathlib import Path

from configurar_cliente import build_environment, write_environment


class ConfigureClientTests(unittest.TestCase):
    def test_builds_environment_without_service_role_key(self):
        content = build_environment(
            "https://example-project.supabase.co",
            "public-key",
            "PDV-001",
            "LIC-001",
            "128e130e-e32f-4321-9e71-89d89774b5bd",
        )

        self.assertIn("COLEGIO_ID=128e130e-e32f-4321-9e71-89d89774b5bd", content)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", content)

    def test_refuses_to_overwrite_existing_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("existing", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                write_environment("new", env_path)