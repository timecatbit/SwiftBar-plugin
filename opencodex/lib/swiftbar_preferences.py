"""Local presentation preferences. No credentials or usage data live here."""
import json
import os
import tempfile
from pathlib import Path

MODULES = (
    ('summary', 'Summary', '概览'),
    ('opencodex', 'OpenCodex', '用量统计'),
    ('claude', 'Claude Code', '用量统计'),
    ('codex', 'Codex 本机用量', '用量统计'),
    ('opencode', 'OpenCode', '用量统计'),
    ('deepseek-harness', 'DeepSeek Harness', '用量统计'),
    ('workbuddy', 'WorkBuddy', '用量统计'),
    ('gemini', 'Gemini CLI', '用量统计'),
    ('deepseek', 'DeepSeek API 余额', '余额与额度'),
    ('chatgpt', 'ChatGPT / Codex 额度', '余额与额度'),
    ('codex-quota', 'OpenCodex 账户额度', '余额与额度'),
    ('grok', 'Grok API 余额', '余额与额度'),
    ('minimax', 'MiniMax 套餐额度', '余额与额度'),
    ('komari', 'Komari 监控', '监控与更新'),
    ('updates', '应用更新', '监控与更新'),
)
DEFAULT_VISIBLE = ['summary', 'opencodex', 'claude', 'deepseek', 'codex-quota', 'komari', 'updates']
KNOWN = {row[0] for row in MODULES}
USAGE = ('opencodex', 'claude', 'codex', 'opencode', 'deepseek-harness', 'workbuddy', 'gemini')


def read(directory):
    defaults = {'schema': 1, 'visible': list(DEFAULT_VISIBLE), 'appearance': 'glass', 'paths': {}, 'allowCollapse': True, 'expandedProvider': ''}
    try:
        value = json.loads((Path(directory) / 'preferences.json').read_text())
        if not isinstance(value, dict) or value.get('schema') != 1:
            return defaults
        visible = value.get('visible')
        if isinstance(visible, list) and all(isinstance(v, str) for v in visible):
            defaults['visible'] = list(dict.fromkeys(v for v in visible if v in KNOWN))
        if value.get('appearance') in ('glass', 'solid'):
            defaults['appearance'] = value['appearance']
        if isinstance(value.get('allowCollapse'),bool):defaults['allowCollapse']=value['allowCollapse']
        if value.get('expandedProvider') in USAGE or value.get('expandedProvider')=='':defaults['expandedProvider']=value['expandedProvider']
        paths = value.get('paths')
        if isinstance(paths, dict):
            defaults['paths'] = {k: v for k, v in paths.items() if k in USAGE and isinstance(v, str) and v}
    except (OSError, ValueError, TypeError):
        pass
    return defaults


def write(directory, value):
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
        if key not in KNOWN or value not in ('true', 'false'):
            raise ValueError('invalid module preference')
        visible = set(current['visible'])
        visible.add(key) if value == 'true' else visible.discard(key)
        current['visible'] = [m[0] for m in MODULES if m[0] in visible]
    elif kind == 'appearance':
        if key not in ('glass', 'solid'):
            raise ValueError('invalid appearance')
        current['appearance'] = key
    elif kind == 'collapse':
        if key not in ('true','false'):raise ValueError('invalid collapse setting')
        current['allowCollapse']=key=='true'
    elif kind == 'expanded':
        if key not in USAGE and key!='':raise ValueError('invalid provider')
        current['expandedProvider']=key
    elif kind == 'reset':
        current['visible'] = list(DEFAULT_VISIBLE)
        current['appearance'] = 'glass'
        current['allowCollapse']=True;current['expandedProvider']=''
    elif kind == 'path':
        if key not in USAGE or not value or not Path(value).expanduser().exists():
            raise ValueError('invalid data directory')
        current['paths'][key] = str(Path(value).expanduser().resolve())
    else:
        raise ValueError('invalid preference action')
    write(directory, current)
    return current
