"""Incremental usage-only Claude transcript reader.

Response deduplication, advisor records and cache-duration accounting are adapted
from ccusage (MIT), commit 615bd802. See CCUSAGE_LICENSE. This collector never
reads credentials and never persists message text, paths or raw response IDs.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
from datetime import datetime


def digest(*values):
    return hashlib.sha256(json.dumps(values,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def counter(value):
    if value is None:return 0
    if type(value) is not int or not 0<=value<2**63:raise ValueError('invalid token counter')
    return value


def normalize(usage):
    if not isinstance(usage,dict):raise ValueError('invalid usage')
    breakdown=usage.get('cache_creation')
    if isinstance(breakdown,dict):
        w5=counter(breakdown.get('ephemeral_5m_input_tokens'))
        w1=counter(breakdown.get('ephemeral_1h_input_tokens'))
    else:w5,w1=counter(usage.get('cache_creation_input_tokens')),0
    return [counter(usage.get('input_tokens')),counter(usage.get('output_tokens')),
            w5,w1,counter(usage.get('cache_read_input_tokens'))]


def records(row,session_fallback,location):
    if not isinstance(row,dict) or row.get('type')!='assistant':return []
    message=row.get('message');usage=message.get('usage') if isinstance(message,dict) else None
    if not isinstance(usage,dict):return []
    model=message.get('model')
    if not isinstance(model,str) or not model or model in ('<synthetic>','synthetic'):return []
    session=row.get('sessionId') or session_fallback
    if not isinstance(session,str):return []
    timestamp=datetime.fromisoformat(str(row.get('timestamp','')).replace('Z','+00:00'))
    if timestamp.tzinfo is None:raise ValueError('timestamp needs timezone')
    stamp=timestamp.timestamp();request=row.get('requestId');message_id=message.get('id')
    if request is not None and (not isinstance(request,str) or not request):return []
    if message_id is not None and (not isinstance(message_id,str) or not message_id):return []
    parts=[(model,usage,row.get('costUSD'))]
    iterations=usage.get('iterations')
    if isinstance(iterations,list):
        parts.extend((r['model'],r,None) for r in iterations if isinstance(r,dict) and
                     r.get('type')=='advisor_message' and isinstance(r.get('model'),str) and r['model'])
    output=[]
    for slot,(model,counts,cost) in enumerate(parts):
        try:metrics=normalize(counts)
        except ValueError:continue
        stored=cost if type(cost) in (int,float) and math.isfinite(cost) and cost>=0 else None
        if not sum(metrics) and stored is None:continue
        identifier=(message_id+(':advisor:'+str(slot) if slot else '')) if message_id else None
        # Without a request ID, gateway placeholders are scoped to session + time.
        # msg_/resp_ IDs represent one streamed response across content blocks.
        key=digest(identifier,request) if request and identifier else (
            digest(identifier,session,None if message_id.startswith(('msg_','resp_')) else stamp)
            if identifier else digest('location',location,slot))
        output.append({'key':key,'message':digest(identifier) if identifier else None,
                       'request':digest(request) if request else None,'session':digest(session),
                       'ts':stamp,'model':model,'metrics':metrics,'cost':stored,
                       'sidechain':row.get('isSidechain') is True,
                       'speed':counts.get('speed') if isinstance(counts.get('speed'),str) else None,
                       'geo':counts.get('inference_geo') if isinstance(counts.get('inference_geo'),str) else 'global',
                       'tier':counts.get('service_tier') if isinstance(counts.get('service_tier'),str) else 'standard',
                       'slot':slot})
    return output


def deduplicate(events):
    """Keep complete responses; parent entries win over sidechain replays."""
    output=[];exact={};routes={}
    def rank(row):return (not row['sidechain'],sum(row['metrics']),row['speed'] is not None,row['cost'] is not None,-row['ts'])
    for row in events:
        found=exact.get(row['key']);route=(row['message'],row['session'])
        if found is None and row['message']:
            for index in routes.get(route,()):
                other=output[index]
                if (row['sidechain'] or other['sidechain']) and (
                    row['ts']==other['ts'] or (row['request'] is None and other['request'] is None)):
                    found=index;break
        if found is None:
            found=len(output);output.append(row)
        elif rank(row)>rank(output[found]):
            output[found]=row
        exact[row['key']]=found
        if row['message']:
            indexes=routes.setdefault(route,[])
            if found not in indexes:indexes.append(found)
    return output


def read_events(files,db_path,allowed_sessions=None,start=0,end=float('inf')):
    """Reindex only changed files; retain only normalized counters and hashed IDs."""
    db_path=Path(db_path);db_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    conn=sqlite3.connect(db_path,timeout=10);os.chmod(db_path,0o600)
    failures=0;changed=False
    try:
        conn.executescript('''CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,inode INTEGER,size INTEGER,mtime INTEGER,offset INTEGER);
          CREATE TABLE IF NOT EXISTS records(file TEXT,offset INTEGER,slot INTEGER,session TEXT,data TEXT,PRIMARY KEY(file,offset,slot));
          CREATE INDEX IF NOT EXISTS records_session ON records(session);
          CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
          CREATE TABLE IF NOT EXISTS canonical(id INTEGER PRIMARY KEY,ts REAL,model TEXT,i INTEGER,o INTEGER,w5 INTEGER,w1 INTEGER,r INTEGER,cost REAL,speed TEXT,geo TEXT,tier TEXT,session TEXT);
          CREATE INDEX IF NOT EXISTS canonical_ts ON canonical(ts);''')
        conn.execute('BEGIN')
        paths=sorted({Path(p).resolve() for p in files});active={digest(str(p)) for p in paths}
        for (key,) in conn.execute('SELECT path FROM files').fetchall():
            if key not in active:
                changed=True
                conn.execute('DELETE FROM records WHERE file=?',(key,));conn.execute('DELETE FROM files WHERE path=?',(key,))
        for path in paths:
            key=digest(str(path))
            try:
                stat=path.stat();old=conn.execute('SELECT inode,size,mtime,offset FROM files WHERE path=?',(key,)).fetchone()
                if old and old[:3]==(stat.st_ino,stat.st_size,stat.st_mtime_ns):continue
                incremental=bool(old and old[0]==stat.st_ino and stat.st_size>old[1])
                offset=old[3] if incremental else 0
                fallback=next((part for part in reversed(path.parts) if allowed_sessions and part in allowed_sessions),path.stem)
                conn.execute('SAVEPOINT source')
                try:
                    if not incremental:conn.execute('DELETE FROM records WHERE file=?',(key,))
                    with path.open('rb') as handle:
                        handle.seek(offset)
                        while True:
                            start=handle.tell();line=handle.readline(32*1024*1024)
                            if not line:break
                            if not line.endswith(b'\n'):
                                handle.seek(start);break
                            if b'"usage"' not in line or b'"assistant"' not in line:continue
                            try:
                                for event in records(json.loads(line),fallback,(key,start)):
                                    conn.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?,?)',
                                                 (key,start,event['slot'],event['session'],json.dumps(event,separators=(',',':'))))
                            except (ValueError,TypeError,OverflowError):continue
                        offset=handle.tell()
                    conn.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?,?)',(key,stat.st_ino,stat.st_size,stat.st_mtime_ns,offset))
                    conn.execute('RELEASE source')
                    changed=True
                except Exception:
                    conn.execute('ROLLBACK TO source');conn.execute('RELEASE source');raise
            except (OSError,ValueError):failures+=1
        allowed={digest(s) for s in allowed_sessions} if allowed_sessions is not None else None
        scope=digest(sorted(allowed) if allowed is not None else None)
        old_scope=conn.execute("SELECT value FROM metadata WHERE key='dedupe-scope'").fetchone()
        if changed or not old_scope or old_scope[0]!=scope:
            # Deduplicate before date filtering, once per file/ownership change.
            events=(json.loads(data) for session,data in conn.execute('SELECT session,data FROM records ORDER BY file,offset,slot')
                    if allowed is None or session in allowed)
            unique=deduplicate(events)
            conn.execute('DELETE FROM canonical')
            conn.executemany('INSERT INTO canonical VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ((index,row['ts'],row['model'],*row['metrics'],row['cost'],row['speed'],row['geo'],row['tier'],row['session']) for index,row in enumerate(unique)))
            conn.execute("INSERT OR REPLACE INTO metadata VALUES ('dedupe-scope',?)",(scope,))
        conn.commit()
        events=[{'ts':ts,'model':model,'metrics':[i,o,w5,w1,r],'cost':cost,'speed':speed,'geo':geo,'tier':tier,'session':session}
                for ts,model,i,o,w5,w1,r,cost,speed,geo,tier,session in conn.execute(
                    'SELECT ts,model,i,o,w5,w1,r,cost,speed,geo,tier,session FROM canonical WHERE ts>=? AND ts<=?',(start,end))]
        return events,failures
    finally:conn.close()
