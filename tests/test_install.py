"""Installer staging and rollback, without SwiftBar or a real plugin folder."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('install_script',ROOT/'scripts/install.py')
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.dest=Path(self.temp.name)/'plugins';self.panel=self.dest/'.opencodex-panel'
        (self.panel/'lib').mkdir(parents=True);(self.panel/'lib/old.py').write_text('old')
        (self.panel/'OpenCodexPanel.app').mkdir();(self.panel/'OpenCodexPanel.app/old-file').write_text('old')
        self.transport=Path(self.temp.name)/'cp39-macosx';self.transport.mkdir();(self.transport/'pkg.py').write_text('new')
        # A package tree of its own: the real helper isn't built yet when the unit tests run.
        package=Path(self.temp.name)/'package'
        for name in ('build/OpenCodexPanel.app/Contents/Info.plist','assets/logo.svg','lib/swiftbar_plugin.py'):
            (package/name).parent.mkdir(parents=True,exist_ok=True);(package/name).write_text('new')
        root=patch.object(install,'ROOT',package);root.start();self.addCleanup(root.stop)
        self.signature_ok=True;real=subprocess.run
        def run(command,*args,**kwargs):
            if command[0]=='codesign':
                if not self.signature_ok:raise subprocess.CalledProcessError(1,command)
                return subprocess.CompletedProcess(command,0)
            return real(command,*args,**kwargs)
        signed=patch.object(install.subprocess,'run',side_effect=run);signed.start();self.addCleanup(signed.stop)
    def test_a_helper_that_fails_its_signature_check_changes_nothing(self):
        self.signature_ok=False
        with self.assertRaises(subprocess.CalledProcessError):install.stage(self.dest,self.transport)
        self.assertEqual(sorted(p.name for p in self.panel.iterdir()),['OpenCodexPanel.app','lib'])
        self.assertEqual((self.panel/'OpenCodexPanel.app/old-file').read_text(),'old')
    def test_parts_are_replaced_whole_and_put_back_when_a_later_step_fails(self):
        staging=install.stage(self.dest,self.transport)
        self.assertTrue((staging/'lib/swiftbar_plugin.py').is_file());self.assertTrue((staging/'python/cp39-macosx/pkg.py').is_file())
        pairs=[(staging/'OpenCodexPanel.app',self.panel/'OpenCodexPanel.app'),(staging/'lib',self.panel/'lib'),
               (staging/'python/cp39-macosx',self.panel/'python/cp39-macosx')]
        moved=[];install.swap(pairs,staging,moved)
        # Whole parts: a file the new version dropped doesn't linger beside it.
        self.assertFalse((self.panel/'lib/old.py').exists());self.assertFalse((self.panel/'OpenCodexPanel.app/old-file').exists())
        install.restore(moved)
        self.assertEqual((self.panel/'lib/old.py').read_text(),'old');self.assertEqual((self.panel/'OpenCodexPanel.app/old-file').read_text(),'old')
        self.assertFalse((self.panel/'python/cp39-macosx').exists())  # It wasn't there before.
        self.assertFalse((self.panel/'lib/swiftbar_plugin.py').exists())
    def test_a_rename_that_fails_midway_undoes_the_parts_already_moved(self):
        staging=install.stage(self.dest,self.transport)
        pairs=[(staging/'lib',self.panel/'lib'),(staging/'missing',self.panel/'OpenCodexPanel.app')]
        moved=[]
        with self.assertRaises(FileNotFoundError):install.swap(pairs,staging,moved)
        install.restore(moved)
        self.assertEqual((self.panel/'lib/old.py').read_text(),'old');self.assertEqual((self.panel/'OpenCodexPanel.app/old-file').read_text(),'old')


if __name__=='__main__':
    unittest.main()
