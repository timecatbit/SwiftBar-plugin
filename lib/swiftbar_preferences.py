"""Local presentation preferences. No credentials or usage data live here."""
import json
import os
import tempfile
import time
from pathlib import Path
import swiftbar_catalog as catalog

MODULES = (
    ('summary', 'Summary', '概览'),
    ('opencodex', 'OpenCodex', 'Harness'),
    ('claude', 'Claude', 'Harness'),
    ('codex', 'ChatGPT 本机用量', 'Harness'),
    ('opencode', 'OpenCode', 'Harness'),
    ('deepseek-harness', 'DeepSeek Harness', 'Harness'),
    ('workbuddy', 'WorkBuddy', 'Harness'),
    ('qoder', 'Qoder CN', 'Harness'),
    ('gemini', 'Gemini CLI', 'Harness'),
) + tuple((s.key, s.label, s.category) for s in catalog.SERVICES) + (
    ('komari', 'Komari 监控', '其他'),
    ('updates', 'Harness 更新', '其他'),
)
DEFAULT_VISIBLE = ['summary', 'opencodex', 'claude', 'deepseek', 'chatgpt', 'komari', 'updates']
KNOWN = {row[0] for row in MODULES}
USAGE = ('opencodex', 'claude', 'codex', 'opencode', 'deepseek-harness', 'workbuddy', 'qoder', 'gemini')


def read(directory):
    defaults = {'schema': 1, 'visible': list(DEFAULT_VISIBLE), 'appearance': 'glass', 'paths': {}, 'allowCollapse': False, 'expandedProviders': [], 'revision': 0, 'configuredSubscriptions': [], 'claudeLiveUsage': False, 'claudeOAuthUsage': False}
    try:
        value = json.loads((Path(directory) / 'preferences.json').read_text())
        if not isinstance(value, dict) or value.get('schema') != 1:
            return defaults
        visible = value.get('visible')
        if isinstance(visible, list) and all(isinstance(v, str) for v in visible):
            # The ChatGPT subscription source now follows the OpenCodex selection; no separate choice.
            defaults['visible'] = list(dict.fromkeys('chatgpt' if v == 'codex-quota' else v for v in visible if v in KNOWN or v == 'codex-quota'))
        subscriptions = value.get('configuredSubscriptions')
        if isinstance(subscriptions, list):
            defaults['configuredSubscriptions'] = [k for k in catalog.MANUAL_SUBSCRIPTIONS if k in subscriptions]
        if value.get('appearance') in ('glass', 'solid'):
            defaults['appearance'] = value['appearance']
        if isinstance(value.get('allowCollapse'),bool):defaults['allowCollapse']=value['allowCollapse']
        if isinstance(value.get('claudeLiveUsage'),bool):defaults['claudeLiveUsage']=value['claudeLiveUsage']
        if isinstance(value.get('claudeOAuthUsage'),bool):defaults['claudeOAuthUsage']=value['claudeOAuthUsage']
        expanded=value.get('expandedProviders')
        if isinstance(expanded,list):
            defaults['expandedProviders']=[k for k in USAGE if k in expanded]
        elif value.get('expandedProvider') in USAGE:
            defaults['expandedProviders']=[value['expandedProvider']]  # Migrate 5.1.0 without losing the open section.
        revision=value.get('revision')
        if isinstance(revision,int) and 0<=revision<2**63:defaults['revision']=revision
        paths = value.get('paths')
        if isinstance(paths, dict):
            defaults['paths'] = {k: v for k, v in paths.items() if k in (*USAGE,'claude-app') and isinstance(v, str) and v}
    except (OSError, ValueError, TypeError):
        pass
    return defaults


def write(directory, value):
    value=dict(value,revision=max(time.time_ns(),read(directory)['revision']+1))
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.preferences-', dir=root)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, ensure_ascii=False)
        os.replace(temporary, root / 'preferences.json')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update(directory, kind, key=None, value=None):
    current = read(directory)
    if kind == 'module':
        if key == 'codex-quota': key = 'chatgpt'  # Existing queued callbacks remain valid.
        if key not in KNOWN or value not in ('true', 'false'):
            raise ValueError('invalid module preference')
        visible = set(current['visible'])
        visible.add(key) if value == 'true' else visible.discard(key)
        current['visible'] = [m[0] for m in MODULES if m[0] in visible]
    elif kind == 'claude-live':
        if key not in ('true','false'):raise ValueError('invalid Claude live usage setting')
        current['claudeLiveUsage']=key=='true'
    elif kind == 'claude-oauth':
        if key not in ('true','false'):raise ValueError('invalid Claude OAuth setting')
        current['claudeOAuthUsage']=key=='true'
    elif kind == 'subscription':
        if key not in catalog.MANUAL_SUBSCRIPTIONS or value not in ('true', 'false'): raise ValueError('invalid subscription')
        chosen = set(current['configuredSubscriptions'])
        chosen.add(key) if value == 'true' else chosen.discard(key)
        current['configuredSubscriptions'] = [k for k in catalog.MANUAL_SUBSCRIPTIONS if k in chosen]
    elif kind == 'appearance':
        if key not in ('glass', 'solid'):
            raise ValueError('invalid appearance')
        current['appearance'] = key
    elif kind == 'collapse':
        if key not in ('true','false'):raise ValueError('invalid collapse setting')
        current['allowCollapse']=key=='true'
        # Turning folding on starts with every card folded.
        if key=='true':current['expandedProviders']=[]
    elif kind == 'expanded':
        if key not in USAGE or value not in ('true','false'):raise ValueError('invalid expansion preference')
        expanded=set(current['expandedProviders'])
        expanded.add(key) if value=='true' else expanded.discard(key)
        current['expandedProviders']=[k for k in USAGE if k in expanded]
    elif kind == 'reset':
        current['visible'] = list(DEFAULT_VISIBLE)
        current['appearance'] = 'glass'
        current['allowCollapse']=False;current['expandedProviders']=[]
    elif kind == 'auto-path':
        if key not in USAGE:raise ValueError('invalid data source')
        current['paths'].pop('claude-app' if key=='claude' else key,None)
    elif kind == 'path':
        if key not in USAGE or not value or not Path(value).expanduser().exists():
            raise ValueError('invalid data directory')
        current['paths']['claude-app' if key=='claude' else key] = str(Path(value).expanduser().resolve())
    else:
        raise ValueError('invalid preference action')
    write(directory, current)
    return read(directory)
