"""ISO-8601 parsing that also accepts the variants Python 3.9's fromisoformat rejects."""
import re
from datetime import datetime

FRACTION = re.compile(r'(\d{2}:\d{2}:\d{2})[.,](\d+)')
OFFSET = re.compile(r'([+-]\d{2})(\d{2})$')


def parse_iso(value):
    """Logs and APIs emit a trailing Z, 1-9 fraction digits and +HHMM offsets."""
    text = str(value).strip()
    if text[-1:] in ('Z', 'z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    text = FRACTION.sub(lambda m: m.group(1) + '.' + (m.group(2) + '000000')[:6], text, count=1)
    if 'T' in text or ' ' in text:
        text = OFFSET.sub(r'\1:\2', text)
    return datetime.fromisoformat(text)
