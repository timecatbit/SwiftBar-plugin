#!/usr/bin/env python3
"""Build and ad-hoc sign the native AppKit helper on macOS."""
import argparse
import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def build(output, universal=False):
    if os.uname().sysname != 'Darwin':
        raise SystemExit('The AppKit helper must be built on macOS.')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = ROOT / 'build' / ('swift-module-cache-' + hashlib.sha256(os.fsencode(ROOT)).hexdigest()[:10])
    cache.mkdir(parents=True, exist_ok=True)
    # Sign outside File Provider folders, which may add disallowed Finder metadata.
    with tempfile.TemporaryDirectory(prefix='swiftbar-panel-') as temporary:
        app = Path(temporary) / 'OpenCodexPanel.app'
        binary = app / 'Contents' / 'MacOS' / 'OpenCodexPanel'
        binary.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'panel' / 'Info.plist', app / 'Contents' / 'Info.plist')
        environment = dict(os.environ, MACOSX_DEPLOYMENT_TARGET='13.0')
        command = ['xcrun', 'swiftc', '-O', '-module-cache-path', str(cache), str(ROOT / 'panel' / 'Panel.swift')]
        if universal:
            # Release packages run on Apple silicon and Intel Macs without a local compiler.
            slices = [Path(temporary) / arch for arch in ('arm64', 'x86_64')]
            for part in slices:
                subprocess.run(command + ['-target', part.name + '-apple-macos13.0', '-o', str(part)],
                               check=True, env=environment)
            subprocess.run(['lipo', '-create'] + [str(part) for part in slices] + ['-output', str(binary)], check=True)
        else:
            subprocess.run(command + ['-o', str(binary)], check=True, env=environment)
        subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        subprocess.run(['ditto', '--norsrc', '--noextattr', str(app), str(output)], check=True)
    print(output)
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build' / 'OpenCodexPanel.app')
    parser.add_argument('--universal', action='store_true', help='Build arm64 and x86_64 slices, as release packages do.')
    args = parser.parse_args()
    build(args.output, args.universal)
