"""State files the user built up by hand. One that no longer reads is copied aside before it is written over."""
import json
import os
import time
from pathlib import Path


def schema_one(data):
    """Whether data is a JSON object in this version's schema 1."""
    try:
        value = json.loads(data.decode('utf-8'))
    except ValueError:
        return False
    return isinstance(value, dict) and value.get('schema') == 1


def keep_unreadable(path, readable=schema_one):
    """Copy path aside when it exists and readable(bytes) is False, so a fresh write loses nothing.
    Returns the copy's path. Raises OSError when the copy can't be made, and the caller then doesn't write."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    if readable(data):
        return None
    stamp = time.strftime('%Y%m%d-%H%M%S')
    for attempt in range(100):
        aside = path.with_name('%s.unreadable-%s%s%s' % (path.stem, stamp, '-%d' % attempt if attempt else '', path.suffix))
        try:
            fd = os.open(aside, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
        return aside
    raise FileExistsError('no free name to keep %s aside' % path.name)
