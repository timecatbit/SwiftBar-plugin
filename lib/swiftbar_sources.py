"""Read-only local harness adapters. Persist only usage counters, never message bodies."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import select
import shutil
import sqlite3
import subprocess
import threading
import time
from datetime import datetime


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else 0
    except (TypeError, ValueError):
        return 0


def stamp(value):
    if isinstance(value, (int, float)):
        return value / 1000 if value > 1e11 else value
    return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()


def identity(*values):
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def metrics(model, inputs, output, cached=0, writes=0, cost=None):
    return {'model': str(model or '未知模型'), 'input': number(inputs), 'output': number(output),
            'cached': number(cached), 'writes': number(writes),
            'cost': number(cost) if isinstance(cost, (int, float)) and math.isfinite(cost) and cost >= 0 else None}


def codex_event(row, state):
    kind = row.get('type'); data = row.get('payload') or {}
    if kind == 'session_meta':
        state.update(session=str(data.get('id') or data.get('session_id') or state['session']),
                     provider=str(data.get('model_provider') or ''))
    elif kind == 'turn_context':
        state['model'] = str(data.get('model') or state.get('model') or '未知模型')
    elif kind == 'event_msg' and data.get('type') == 'token_count':
        info = data.get('info') or {}; total = info.get('total_token_usage') or {}
        last = info.get('last_token_usage') or {}
        if not total or not last:
            return None
        previous = state.get('total')
        state['total'] = total
        if previous == total:
            return None
        fields = ['input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens']
        # A copied/forked history may start with inherited cumulative counters.
        # The first sample contributes only its last request, never that inheritance.
        values = last if not previous or number(total.get('total_tokens')) < number(previous.get('total_tokens')) else {
            key: max(0, number(total.get(key)) - number(previous.get(key))) for key in fields}
        inputs = number(values.get('input_tokens')); cached = min(inputs, number(values.get('cached_input_tokens')))
        result = metrics(state.get('model'), inputs - cached, values.get('output_tokens'), cached)
        if inputs + result['output'] <= 0:
            return None
        result.update(id=identity('codex', state['session'], total), session=identity(state['session']),
                      timestamp=stamp(row['timestamp']), provider=state.get('provider', ''))
        return result
    return None


def deepseek_event(row, state):
    kind = row.get('type'); data = row.get('data') or {}
    if kind == 'session':
        version = int(row.get('version', 0))
        if version not in (2, 3, 4):
            raise ValueError('不支持的 Harness 日志版本')
        state.update(session=str(row.get('id') or state['session']), isSeeded=bool(row.get('isSeeded')), seeded=bool(row.get('isSeeded')),
                     seedLength=int(row.get('seedLength', 0)))
    elif kind == 'session/end-seed' and data.get('inherited'):
        state['seeded'] = False
    elif kind == 'request/header':
        header = data.get('header') or {}; config = header.get('config') or header
        state['model'] = config.get('model', state.get('model'))
        state['provider'] = config.get('provider', state.get('provider', ''))
    elif kind == 'llm/retry-started':
        state['attempt'] = int(state.get('attempt', 0)) + 1
    elif kind in ('assistant/message', 'assistant/attempt'):
        if state.get('seeded') or number(row.get('seq')) < state.get('seedLength', 0):
            return None
        usage = data.get('usage') if kind == 'assistant/message' else None
        if usage is None:
            for chunk in data.get('stream') or []:
                chunk = chunk.get('chunk', chunk) if isinstance(chunk, dict) else {}
                if chunk.get('type') == 'usage':
                    usage = chunk.get('usage')
        if not isinstance(usage, dict):
            return None
        message = data.get('message') or {}
        result = metrics(message.get('model') or state.get('model'), usage.get('inputTokens'),
                         usage.get('outputTokens'), usage.get('cacheReadTokens'), usage.get('cacheWriteTokens'))
        result.update(id=identity('dsh', state['session'], data.get('turn'), data.get('step'), state.get('attempt', 0)),
                      session=identity(state['session']), timestamp=stamp(row['time']),
                      provider=message.get('provider') or state.get('provider', ''))
        return result
    return None


def _jsonl_files(root, source):
    if source == 'codex':
        roots = [root/name for name in ('sessions', 'archived_sessions') if (root/name).is_dir()]
        return sorted(path for folder in (roots or [root]) for path in folder.rglob('*.jsonl'))
    if source == 'workbuddy':
        roots = [root/name/'projects' for name in ('.workbuddy-ai','.workbuddy') if (root/name/'projects').is_dir()]
        if not roots and root==Path.home():return []
        if not roots: roots = [root/'projects' if (root/'projects').is_dir() else root]
        return sorted({path for folder in roots for path in folder.rglob('*.jsonl')})
    # Only one physical generation of each DSH session is authoritative.
    chosen = {}
    for path in root.rglob('session*.jsonl*'):
        match = re.fullmatch(r'session(?:\.v(\d+))?\.jsonl(?:\.zstd)?', path.name)
        if match:
            generation = int(match.group(1) or 0)
            if path.parent not in chosen or generation > chosen[path.parent][0]:
                chosen[path.parent] = (generation, path)
    return [value[1] for value in chosen.values()]


def _stream(path):
    if path.suffix != '.zstd':
        return path.open('rb'), None, None
    binary = shutil.which('zstd')
    if binary:
        command = [binary, '-dc', '--', str(path)]
    elif shutil.which('node'):
        command = [shutil.which('node'), '-e', "require('fs').createReadStream(process.argv[1]).pipe(require('zlib').createZstdDecompress()).pipe(process.stdout)", str(path)]
    else:
        raise RuntimeError('读取压缩日志需要 zstd 或支持 Zstandard 的 Node.js')
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    timer = threading.Timer(30, process.kill); timer.daemon = True; timer.start()
    return process.stdout, process, timer


def jsonl_usage(source, root, cache, start, end, zone, exclude_proxy=False):
    root = Path(root).expanduser()
    if not root.is_dir():
        return {'error': '未找到记录目录'}
    db = Path(cache) / ('harness-' + source + '-' + identity(str(root.resolve()))[:12] + '.sqlite3')
    db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(db, timeout=10); os.chmod(db, 0o600)
    try:
        conn.executescript('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, inode INTEGER, size INTEGER, mtime INTEGER, offset INTEGER, state TEXT); CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, file TEXT, ts REAL, data TEXT); CREATE INDEX IF NOT EXISTS events_ts ON events(ts);')
        parser = {'codex':codex_event,'deepseek-harness':deepseek_event,'workbuddy':workbuddy_event}[source]
        errors = 0
        paths = _jsonl_files(root, source)
        for path in paths:
            try:
                st = path.stat(); file_key = identity(str(path))
                previous = conn.execute('SELECT inode,size,mtime,offset,state FROM files WHERE path=?', (file_key,)).fetchone()
                if not previous and st.st_mtime < start:
                    continue
                if previous and previous[:3] == (st.st_ino, st.st_size, st.st_mtime_ns):
                    continue
                incremental = previous and previous[0] == st.st_ino and previous[1] <= st.st_size and path.suffix != '.zstd'
                state = json.loads(previous[4]) if incremental else {'session': path.stem}
                offset = previous[3] if incremental else 0
                stream, process, timer = _stream(path)
                conn.execute('SAVEPOINT source_file')
                try:
                    if not incremental:
                        conn.execute('DELETE FROM events WHERE file=?', (file_key,))
                    if offset:
                        stream.seek(offset)
                    while True:
                        line = stream.readline(32 * 1024 * 1024)
                        if not line or not line.endswith(b'\n'):
                            break  # Never checkpoint an incomplete tail.
                        offset += len(line)
                        # Avoid parsing full tool/message content unless it carries usage or metadata.
                        if source == 'codex' and not any(key in line for key in (b'"token_count"', b'"session_meta"', b'"turn_context"')):
                            continue
                        try:
                            row = json.loads(line)
                            if not isinstance(row, dict):
                                continue
                            if source != 'codex' and state.get('isSeeded') and row.get('type')=='session/end-seed' and (row.get('data') or {}).get('inherited'):
                                conn.execute('DELETE FROM events WHERE file=?', (file_key,))
                            event = parser(row, state)
                            if event:
                                conn.execute('INSERT OR REPLACE INTO events VALUES (?,?,?,?)', (event['id'], file_key, event['timestamp'], json.dumps(event)))
                        except (KeyError, TypeError, json.JSONDecodeError):
                            continue
                    if process and process.wait(timeout=2) != 0:
                        raise RuntimeError('压缩日志读取失败')
                    conn.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?,?)', (file_key, st.st_ino, st.st_size, st.st_mtime_ns, offset, json.dumps(state)))
                    conn.execute('RELEASE source_file')
                except Exception:
                    conn.execute('ROLLBACK TO source_file'); conn.execute('RELEASE source_file'); raise
                finally:
                    stream.close()
                    if timer: timer.cancel()
                    if process and process.poll() is None: process.kill(); process.wait()
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                errors += 1
        conn.commit()
        events = (json.loads(row[0]) for row in conn.execute('SELECT data FROM events WHERE ts>=? AND ts<=?', (start, end)))
        result = aggregate(events, start, end, zone, exclude_proxy)
        if errors:
            result['warning'] = '部分记录无法读取'
            result['partial'] = True
            if not result['summary']['requests']: result['error'] = '记录格式或权限待检查'
        if not paths:
            return {'error': '暂无用量记录'}
        return result
    finally:
        conn.close()


def aggregate(events, start, end, zone, exclude_proxy=False):
    def empty():
        return dict(totalTokens=0, inputTokens=0, outputTokens=0, cachedInputTokens=0,
                    requests=0, estimatedCostUsd=0, unpricedRequests=0)
    summary = empty(); models = {}; days = {}; hours = {}; sessions = set(); first = None; excluded = 0
    for event in events:
        ts = event['timestamp']
        if not start <= ts <= end: continue
        if exclude_proxy and str(event.get('provider', '')).lower() in ('opencodex', 'ocx'):
            excluded += 1; continue
        i, o, r, w = [number(event.get(k)) for k in ('input', 'output', 'cached', 'writes')]
        if i + o + r + w <= 0: continue
        first = ts if first is None else min(first, ts)
        day = datetime.fromtimestamp(ts, zone).date().isoformat()
        sessions.add(event.get('session'))
        for target in [summary, models.setdefault(event['model'], empty()), days.setdefault(day, empty()), hours.setdefault(int(ts//3600)*3600, empty())]:
            target['totalTokens'] += i + o + r + w; target['inputTokens'] += i + r + w
            target['outputTokens'] += o; target['cachedInputTokens'] += r; target['requests'] += 1
            if event.get('cost') is None: target['unpricedRequests'] += 1
            else: target['estimatedCostUsd'] += event['cost']
    summary['sessions'] = len(sessions)
    summary['coverageRatio'] = (summary['requests'] - summary['unpricedRequests']) / max(1, summary['requests'])
    return {'summary': summary, 'models': [dict(v, model=k) for k,v in models.items()],
            'days': [dict(v, date=k) for k,v in sorted(days.items())],
            'hours': [dict(v, timestamp=k) for k,v in sorted(hours.items())],
            'firstActivityAt': first, 'excludedProxyRequests': excluded}


def opencode_usage(root, start, end, zone, exclude_proxy=False):
    root = Path(root).expanduser(); database = root if root.is_file() else root/'opencode.db'
    if not database.is_file(): return {'error': '未找到 OpenCode 数据库'}
    conn = sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True, timeout=4)
    try:
        conn.execute('PRAGMA query_only=ON')
        rows = conn.execute("SELECT id,session_id,time_created,data FROM message WHERE time_created>=? AND time_created<=? AND json_extract(data,'$.role')='assistant'", (int(start*1000), int(end*1000)))
        def events():
            for key, session, created, raw in rows:
                try:
                    data = json.loads(raw); usage = data.get('tokens') or {}; cached = usage.get('cache') or {}
                    event = metrics(data.get('modelID'), usage.get('input'), usage.get('output'), cached.get('read'), cached.get('write'), data.get('cost'))
                    event.update(id=identity(key), session=identity(session), timestamp=created/1000, provider=data.get('providerID',''))
                    yield event
                except (ValueError, TypeError, AttributeError): continue
        return aggregate(events(), start, end, zone, exclude_proxy)
    finally:
        conn.close()


def chatgpt_account(binary=None, home=None):
    """Use official read-only App Server methods; never refresh/login or invoke a model."""
    binary = binary or shutil.which('codex')
    if not binary: return {'state': '未安装 ChatGPT 编程客户端', 'windows': []}
    environment = os.environ.copy()
    if home: environment['CODEX_HOME'] = str(home)
    process = subprocess.Popen([binary, 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment)
    buffer = b''; sequence = 0; deadline = time.monotonic()+12
    def send(value):
        process.stdin.write((json.dumps(value)+'\n').encode()); process.stdin.flush()
    def call(method, params=None):
        nonlocal buffer, sequence
        sequence += 1; request_id = sequence
        send({'id':request_id, 'method':method, 'params':params or {}})
        while time.monotonic() < deadline:
            if b'\n' not in buffer:
                if not select.select([process.stdout], [], [], max(0, deadline-time.monotonic()))[0]: break
                data = os.read(process.stdout.fileno(), 65536)
                if not data: break
                buffer += data
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n',1)
                try: response = json.loads(line)
                except ValueError: continue
                if response.get('id') == request_id:
                    return response.get('result')
        return None
    try:
        if call('initialize', {'clientInfo': {'name':'swiftbar_token_monitor','title':'SwiftBar Token Monitor','version':'5.0.0'}}) is None:
            return {'state':'客户端接口不可用','windows':[]}
        send({'method':'initialized'})
        account = call('account/read', {'refreshToken':False}) or {}
        if (account.get('account') or {}).get('type') not in ('chatgpt', 'chatgptAuthTokens'):
            return {'state':'需 ChatGPT 账户登录','windows':[]}
        result = call('account/rateLimits/read') or {}; buckets = result.get('rateLimitsByLimitId') or {}
        if not buckets and result.get('rateLimits'): buckets = {'codex': result['rateLimits']}
        windows = []
        for key,bucket in buckets.items():
            if not isinstance(bucket,dict): continue
            for slot in ('primary','secondary'):
                window=bucket.get(slot)
                if not isinstance(window,dict) or not isinstance(window.get('usedPercent'),(int,float)): continue
                windows.append({'name':str(bucket.get('limitName') or key), 'slot':slot,
                                'remaining':max(0,min(100,100-window['usedPercent'])),
                                'minutes':number(window.get('windowDurationMins')), 'resetsAt':number(window.get('resetsAt'))})
        return {'state':'已同步' if windows else '暂无可读取额度','windows':windows,
                'plan':str((account.get('account') or {}).get('planType') or '')}
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'state':'额度暂不可用','windows':[]}
    finally:
        if process.poll() is None: process.terminate()
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
        process.stdin.close(); process.stdout.close()

def workbuddy_event(row, state):
    """WorkBuddy project transcripts, including tool calls with the same response ID."""
    if row.get('type') not in ('message', 'function_call', 'assistant'):
        return None
    message = row.get('message') or {}; provider = row.get('providerData') or {}
    if row.get('role', message.get('role')) not in (None, 'assistant'):
        return None
    usage = message.get('usage') or provider.get('usage') or {}
    if not isinstance(usage, dict) or not usage:
        return None
    inputs = number(usage.get('input_tokens'))
    cached = min(inputs, number(usage.get('cache_read_input_tokens')))
    # WorkBuddy normalizes inclusive prompt/output counters. Cache and reasoning
    # are already part of them; rawUsage.credit is not a USD cost.
    event = metrics(provider.get('model') or message.get('model'), inputs-cached,
                    usage.get('output_tokens'), cached)
    response = provider.get('messageId') or message.get('id') or row.get('id')
    if not response: return None
    event.update(id=identity('workbuddy', response), session=identity(row.get('sessionId') or state['session']),
                 timestamp=stamp(row['timestamp']), provider=provider.get('provider', ''))
    return event


def gemini_event(row, state):
    if row.get('sessionId'):
        state['session'] = str(row['sessionId'])
    if row.get('type') != 'gemini' or not isinstance(row.get('tokens'), dict) or not row.get('id'):
        return None
    usage = row['tokens']; inputs = number(usage.get('input')); cached = min(inputs, number(usage.get('cached')))
    # Gemini returns thoughts separately from candidate output. Prefer its
    # authoritative total so fields cannot accidentally count a token twice.
    output = number(usage.get('output')) + number(usage.get('thoughts'))
    total = number(usage.get('total')); tool = number(usage.get('tool'))
    if total >= inputs and total > 0:
        tool=min(tool,total-inputs)
        output=total-inputs-tool
    result = metrics(row.get('model'), inputs-cached+tool, output, cached)
    result.update(id=identity('gemini', row['id']), session=identity(state['session']),
                  timestamp=stamp(row['timestamp']), provider='google')
    return result


def gemini_usage(root, cache, start, end, zone, exclude_proxy=False):
    """JSON/JSONL Gemini CLI sessions. Index usage only, including spent rewinds."""
    root = Path(root).expanduser()
    if not root.is_dir(): return {'error':'未找到 Gemini CLI 记录'}
    folders = [root/'tmp'] if (root/'tmp').is_dir() else [root]
    paths = sorted({p for folder in folders for p in folder.rglob('session-*.json*') if p.suffix in ('.json','.jsonl')})
    # New subagents may use UUID filenames instead of session-*.
    paths = sorted(set(paths) | {p for folder in folders for p in folder.rglob('chats/**/*.jsonl')})
    if not paths: return {'error':'暂无 Gemini CLI 记录'}
    target = Path(cache)/('harness-gemini-'+identity(str(root.resolve()))[:12]+'.sqlite3')
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    db = sqlite3.connect(target,timeout=10);os.chmod(target,0o600)
    try:
        db.executescript('CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,size INTEGER,mtime INTEGER); CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,file TEXT,ts REAL,data TEXT); CREATE INDEX IF NOT EXISTS events_ts ON events(ts);')
        errors=0
        for path in paths:
            file_id=identity(str(path));st=path.stat()
            if db.execute('SELECT size,mtime FROM files WHERE path=?',(file_id,)).fetchone()==(st.st_size,st.st_mtime_ns):continue
            if st.st_mtime<start:continue
            state={'session':path.stem};events=[]
            try:
                with path.open() as handle:
                    if path.suffix=='.json':
                        data=json.load(handle);state['session']=str(data.get('sessionId') or state['session']);records=data.get('messages') or []
                    else:
                        def lines():
                            for line in handle:
                                if not line.endswith('\n'):break
                                try:yield json.loads(line)
                                except ValueError:continue
                        records=lines()
                    for row in records:
                        if not isinstance(row,dict):continue
                        if row.get('sessionId'):state['session']=str(row['sessionId'])
                        # Legacy full-history checkpoints and repeated message
                        # records share IDs. Rewinds don't refund spent tokens.
                        checkpoint=(row.get('$set') or {}).get('messages',[]) if isinstance(row.get('$set',{}),dict) else []
                        for item in [row]+checkpoint:
                            event=gemini_event(item,state)
                            if event:events.append(event)
                with db:
                    db.execute('DELETE FROM events WHERE file=?',(file_id,))
                    for e in events:db.execute('INSERT OR REPLACE INTO events VALUES (?,?,?,?)',(e['id'],file_id,e['timestamp'],json.dumps(e)))
                    db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?)',(file_id,st.st_size,st.st_mtime_ns))
            except (OSError,ValueError,TypeError,KeyError):errors+=1
        result=aggregate((json.loads(r[0]) for r in db.execute('SELECT data FROM events WHERE ts>=? AND ts<=?',(start,end))),start,end,zone,exclude_proxy)
        if errors:
            result['partial']=True
            if not result['summary']['requests']:result['error']='Gemini 记录格式待检查'
        return result
    finally:db.close()
