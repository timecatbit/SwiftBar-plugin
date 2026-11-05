#!/usr/bin/env python3
"""Build and ad-hoc sign the native AppKit helper on macOS."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def build(output):
    if os.uname().sysname != 'Darwin':
        raise SystemExit('The AppKit helper must be built on macOS.')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = ROOT / 'build' / 'swift-module-cache'
    cache.mkdir(parents=True, exist_ok=True)
    # Sign outside File Provider folders, which may add disallowed Finder metadata.
    with tempfile.TemporaryDirectory(prefix='swiftbar-panel-') as temporary:
        app = Path(temporary) / 'OpenCodexPanel.app'
        binary = app / 'Contents' / 'MacOS' / 'OpenCodexPanel'
        binary.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'panel' / 'Info.plist', app / 'Contents' / 'Info.plist')
        environment = dict(os.environ, MACOSX_DEPLOYMENT_TARGET='13.0')
        subprocess.run(['xcrun', 'swiftc', '-O', '-module-cache-path', str(cache),
                        str(ROOT / 'panel' / 'Panel.swift'), '-o', str(binary)],
                       check=True, env=environment)
        subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        subprocess.run(['ditto', '--norsrc', '--noextattr', str(app), str(output)], check=True)
    print(output)
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build' / 'OpenCodexPanel.app')
    build(parser.parse_args().output)
