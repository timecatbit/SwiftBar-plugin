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
    private_prefixes = ('OCX_', 'KOMARI_', 'DEEPSEEK_', 'XAI_', 'MINIMAX_', 'CLAUDE_',
                        'CODEX_', 'GEMINI_', 'WORKBUDDY_', 'OPENCODE_', 'DSH_')
    environment = {k:v for k,v in os.environ.items() if not k.startswith(private_prefixes)}
    isolated_home = Path(scratch) / 'home'
    isolated_home.mkdir()
    environment['HOME'] = str(isolated_home)
    environment['SWIFTBAR_PLUGIN_DATA_PATH'] = scratch
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s',
                    str(ROOT / 'tests'), '-p', 'test_*.py', '-v'],
                   check=True, env=environment)
    if os.uname().sysname == 'Darwin':
        declarations=(ROOT/'panel/Panel.swift').read_text().split('// Application entry point.',1)[0]
        test_main=Path(scratch)/'main.swift'
        test_main.write_text(declarations+'\n'+(ROOT/'tests/PanelInteractionTests.swift').read_text())
        binary=Path(scratch)/'panel-interaction-tests'
        cache=ROOT/'build/swift-module-cache';cache.mkdir(parents=True,exist_ok=True)
        subprocess.run(['xcrun','swiftc','-module-cache-path',str(cache),str(test_main),'-o',str(binary)],check=True,env=environment)
        subprocess.run([str(binary)],check=True,env=environment)
