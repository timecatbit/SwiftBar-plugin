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
sys.path.insert(0, str(ROOT / 'lib'))
from swiftbar_config import migrate_config
from install_transport import prepare as prepare_transport
import swiftbar_claude_local as claude_local

def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        subprocess.run(['ditto', '--norsrc', '--noextattr', str(source), str(target)], check=True)
    else:
        shutil.copy2(source, target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin-dir', type=Path, help='Defaults to the folder configured in SwiftBar.')
    parser.add_argument('--no-refresh', action='store_true', help='Copy files without closing the panel or refreshing SwiftBar.')
    parser.add_argument('--skip-build', action='store_true', help='Install an already built helper.')
    parser.add_argument('--config', type=Path, help='Explicit first-install config import; existing user settings are never overwritten.')
    args = parser.parse_args()
    if args.plugin_dir is None:
        detected = subprocess.run(['defaults', 'read', 'com.ameba.SwiftBar', 'PluginDirectory'], capture_output=True, text=True)
        if detected.returncode or not detected.stdout.strip():
            parser.error('Set a plugin folder in SwiftBar first, or pass --plugin-dir PATH.')
        args.plugin_dir = Path(detected.stdout.strip())
    destination = args.plugin_dir.expanduser().resolve()
    if destination == ROOT:
        parser.error('Use the SwiftBar runtime directory, not the source directory.')
    if args.config and (Path.home() / 'Library/Application Support/SwiftBarToken/config.local.sh').exists():
        parser.error('User config already exists; edit it through connection settings.')
    if args.config and not args.config.expanduser().is_file():
        parser.error('--config must name an existing file.')
    if not args.skip_build:
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build.py')], check=True)
    # Ask the shell entry point so OCX_PYTHON and its PATH match the running plugin.
    python = subprocess.run(['/bin/bash',str(ROOT/'opencodex.30s.sh'),'--python-path'],
                            capture_output=True,text=True,check=True).stdout.strip()
    if not Path(python).is_file():parser.error('The plugin Python interpreter is unavailable.')
    transport = prepare_transport(ROOT,python)
    relative_app = Path('.opencodex-panel/OpenCodexPanel.app')
    local_config = Path('.opencodex-panel/config.local.sh')
    relative_transport=Path('.opencodex-panel/python')/transport.name
    paths = [Path('opencodex.30s.sh'), relative_app, Path('assets/deepseek-logo.svg'), local_config, Path('.opencodex-panel/lib'),relative_transport]
    previous = [p for p in paths if (destination / p).exists()]
    if previous:
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
        backup = Path.home() / 'Library/Application Support/SwiftBarToken/backups' / stamp
        backup.mkdir(parents=True, mode=0o700)
        for relative in previous:
            copy(destination / relative, backup / relative)
        print('Backup:', backup)
    # Only close an already running helper. Never launch SwiftBar via AppleScript.
    if not args.no_refresh:
        subprocess.run(['osascript', '-e',
                    'if application id "cc.opencodex.swiftbar.panel" is running then tell application id "cc.opencodex.swiftbar.panel" to quit'],
                   capture_output=True, timeout=8, check=False)
    copy(ROOT / 'build/OpenCodexPanel.app', destination / relative_app)
    subprocess.run(['codesign', '--verify', '--deep', str(destination / relative_app)], check=True)
    copy(ROOT / 'assets/deepseek-logo.svg', destination / 'assets/deepseek-logo.svg')
    shutil.copytree(ROOT / 'lib', destination / '.opencodex-panel/lib', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    copy(transport,destination/relative_transport)
    migrate_config(destination, Path.home() / 'Library/Application Support/SwiftBarToken', args.config)
    state=Path.home()/'Library/Application Support/SwiftBarToken'
    if claude_local.enabled(state):claude_local.install(state)
    # Publish the script last; other plugins and runtime state are preserved.
    destination.mkdir(parents=True, exist_ok=True)
    temporary = destination / '.opencodex-install.tmp'
    shutil.copyfile(ROOT / 'opencodex.30s.sh', temporary)
    temporary.chmod(0o755)
    os.replace(temporary, destination / 'opencodex.30s.sh')
    detected = subprocess.run(['/bin/bash', str(destination / 'opencodex.30s.sh'), '--initialize-modules'],
                              capture_output=True, text=True, timeout=30)
    if detected.returncode:
        print('Module detection could not finish; choose modules from the right-click menu.')
    else:
        print(detected.stdout.strip())
    if not args.no_refresh:
        subprocess.run(['open', '-g', 'swiftbar://refreshplugin?name=opencodex.30s.sh'], check=True)
    print('Installed:', destination / 'opencodex.30s.sh')

if __name__ == '__main__':
    main()
