import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'opencodex.30s.sh'
CODE = (SOURCE.parent / 'lib/swiftbar_plugin.py').read_text()

class LocalConfigTests(unittest.TestCase):
    def test_unconfigured_monitor_makes_no_network_request(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'KOMARI_BASE_URL': '', 'OCX_CACHE_DIR': directory,
                                         'OS_APPEARANCE': 'Dark', 'OCX_PLUGIN_PATH': str(SOURCE)}):
                module = types.ModuleType('config_test')
                exec(compile(CODE, str(SOURCE.parent / 'lib/swiftbar_plugin.py'), 'exec'), module.__dict__)
            with patch.object(module, 'komari_snapshot_live') as remote:
                payload, error = module.komari_snapshot()
                remote.assert_not_called()
            self.assertFalse(payload['configured'])
            self.assertIsNone(error)
            self.assertIn('未配置', module.komari_lines({})[0])

    def test_shell_uses_user_config_and_ignores_legacy_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / 'plugin with spaces.sh'
            plugin.write_bytes(SOURCE.read_bytes())
            observed = root / 'observed'
            spy = root / 'python spy'
            spy.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nimport os\n'
                           + 'Path(' + repr(str(observed)) + ').write_text(os.environ["KOMARI_BASE_URL"])\n')
            spy.chmod(0o755)
            legacy = root / '.opencodex-panel/config.local.sh'
            legacy.parent.mkdir()
            legacy.write_text('export KOMARI_BASE_URL=https://old.invalid\n')
            config = root / 'settings/config.local.sh'
            config.parent.mkdir()
            config.write_text('export KOMARI_BASE_URL=https://komari.example.test\n'
                              + 'export OCX_PYTHON=' + shlex.quote(str(spy)) + '\n')
            subprocess.run(['/bin/bash', str(plugin), '--refresh'], check=True, capture_output=True, env=dict(os.environ, OCX_STATE_DIR=str(config.parent)))
            self.assertEqual(observed.read_text(), 'https://komari.example.test')

if __name__ == '__main__':
    unittest.main()
