#!/usr/bin/env python3
"""Install this plugin into a selected SwiftBar directory, with a local backup."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]

def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        subprocess.run(['ditto', '--norsrc', '--noextattr', str(source), str(target)], check=True)
    else:
        shutil.copy2(source, target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', required=True, type=Path)
    parser.add_argument('--config', type=Path, default=ROOT / 'config.local.sh')
    args = parser.parse_args()
    destination = args.plugin_dir.expanduser().resolve()
    if destination == ROOT:
        parser.error('Use the SwiftBar runtime directory, not the source directory.')
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build.py')], check=True)
    relative_app = Path('.opencodex-panel/OpenCodexPanel.app')
    local_config = Path('.opencodex-panel/config.local.sh')
    paths = [Path('opencodex.30s.sh'), relative_app, Path('assets/deepseek-logo.svg'), local_config]
    previous = [p for p in paths if (destination / p).exists()]
    if previous:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        backup = Path.home() / 'Library/Application Support/SwiftBarToken/backups' / stamp
        backup.mkdir(parents=True, mode=0o700)
        for relative in previous:
            copy(destination / relative, backup / relative)
        print('Backup:', backup)
    # Only close an already running helper. Never launch SwiftBar via AppleScript.
    subprocess.run(['osascript', '-e',
                    'if application id "cc.opencodex.swiftbar.panel" is running then tell application id "cc.opencodex.swiftbar.panel" to quit'],
                   capture_output=True, timeout=8, check=False)
    copy(ROOT / 'build/OpenCodexPanel.app', destination / relative_app)
    subprocess.run(['codesign', '--verify', '--deep', str(destination / relative_app)], check=True)
    copy(ROOT / 'assets/deepseek-logo.svg', destination / 'assets/deepseek-logo.svg')
    if args.config.exists():
        copy(args.config, destination / local_config)
        (destination / local_config).chmod(0o600)
    # Publish the script last; other plugins and runtime state are preserved.
    destination.mkdir(parents=True, exist_ok=True)
    temporary = destination / '.opencodex-install.tmp'
    shutil.copyfile(ROOT / 'opencodex.30s.sh', temporary)
    temporary.chmod(0o755)
    os.replace(temporary, destination / 'opencodex.30s.sh')
    subprocess.run(['open', '-g', 'swiftbar://refreshplugin?name=opencodex.30s.sh'], check=True)
    print('Installed:', destination / 'opencodex.30s.sh')

if __name__ == '__main__':
    main()
