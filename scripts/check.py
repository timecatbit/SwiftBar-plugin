#!/usr/bin/env python3
"""Syntax checks and isolated unit tests; does not run the live plugin."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
subprocess.run(['/bin/bash', '-n', str(ROOT / 'opencodex.30s.sh')], check=True)
with tempfile.TemporaryDirectory(prefix='swiftbar-token-tests-') as scratch:
    environment = os.environ.copy()
    environment['SWIFTBAR_PLUGIN_DATA_PATH'] = scratch
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s',
                    str(ROOT / 'tests'), '-p', 'test_*.py', '-v'],
                   check=True, env=environment)
