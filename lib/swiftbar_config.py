"""Explicit connection overrides; no copied credentials or inferred monitor addresses."""
import os
from pathlib import Path
import re
import shlex
import tempfile
from urllib.parse import urlsplit

KEYS = {'OCX_HOME', 'OCX_BASE_URL', 'OCX_TOKEN_FILE', 'OCX_CHATGPT_HOME', 'KOMARI_BASE_URL', 'DEEPSEEK_API_KEY', 'DEEPSEEK_API_KEY_FILE',
        'XAI_MANAGEMENT_API_KEY', 'XAI_MANAGEMENT_API_KEY_FILE', 'XAI_TEAM_ID',
        'MINIMAX_API_KEY', 'MINIMAX_API_KEY_FILE', 'MINIMAX_REGION'}
HEADER = '''# 本机高级设置：仅本用户可读，不随插件上传或覆盖。
# 常用设置请用「主页模块 → 连接与数据」；本机客户端默认自动读取。
# 注释是说明，不代表已配置。无需填写即可使用已发现的本机客户端。
# API 连接只保存密钥文件路径；原始密钥留在您选择的文件中。
'''


def monitor_url(value):
    value = str(value or '').strip().rstrip('/')
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme not in ('http', 'https') or not host or parsed.username or
                parsed.password or parsed.query or parsed.fragment or
                host.endswith('.example') or host in ('example.com', 'example.org', 'your-komari.example')):
            return ''
        parsed.port  # Reject invalid ports as well.
        return value
    except ValueError:
        return ''


def write_overrides(directory, values):
    """Override only selected keys, preserving unrelated advanced shell settings."""
    if not values or not set(values) <= KEYS or not all(isinstance(v, str) and '\n' not in v and '\x00' not in v for v in values.values()):
        raise ValueError('invalid connection settings')
    root = Path(directory); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root/'config.local.sh'
    text = path.read_text() if path.exists() else HEADER
    # Keep earlier advanced expressions intact. Last export wins, including an explicit empty value.
    for key, value in values.items():
        text = re.sub(r'^export '+re.escape(key)+r'=.* # managed by SwiftBarToken\n?', '', text, flags=re.M)
        text = text.rstrip()+'\nexport '+key+'='+shlex.quote(value)+' # managed by SwiftBarToken\n'
    fd, temporary = tempfile.mkstemp(prefix='.config-', dir=root)
    try:
        with os.fdopen(fd, 'w') as out: out.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def ensure_file(directory):
    root = Path(directory); root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root/'config.local.sh'
    try:
        fd = os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    except FileExistsError:
        return path
    with os.fdopen(fd, 'w') as out: out.write(HEADER)
    return path


def migrate_config(destination, state, explicit=None):
    """An existing user file always wins. Never silently reimport checkout config."""
    target = Path(state)/'config.local.sh'
    legacy = Path(destination)/'.opencodex-panel/config.local.sh'
    source = Path(explicit).expanduser() if explicit else legacy
    if explicit and target.exists():
        raise ValueError('本机配置已存在；请在连接设置中修改，不覆盖现有文件。')
    if not target.exists() and source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(target, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as out: out.write(source.read_bytes())
    # Installer already backed up the legacy file before this migration.
    if legacy.exists(): legacy.unlink()
    return target
