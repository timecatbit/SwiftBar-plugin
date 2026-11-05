"""Opt-in Claude Desktop session reuse, limited to Claude's official usage API.

Credentials stay in memory. Callers must obtain explicit consent first. Discovery
and snapshot reading never call this module's credential functions.
"""
import ctypes
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ORIGIN='https://claude.ai'
UUID=re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',re.I)


class UsageError(Exception):
    pass


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        target=urlsplit(newurl)
        if target.scheme!='https' or target.netloc!='claude.ai':raise UsageError('用量接口跳转异常')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def desktop_session(root):
    """Only called after consent; neither keychain password nor cookie is returned to UI."""
    if not (Path(root)/'Cookies').is_file():raise UsageError('请先在 Claude App 登录')
    process=subprocess.run(['/usr/bin/security','find-generic-password','-s','Claude Safe Storage','-w'],
                           capture_output=True,timeout=10)
    if process.returncode:raise UsageError('无法读取 Claude 登录，请检查钥匙串授权')
    key=hashlib.pbkdf2_hmac('sha1',process.stdout.rstrip(b'\r\n'),b'saltysalt',1003,16)
    crypto=ctypes.CDLL('/usr/lib/system/libcommonCrypto.dylib')
    crypto.CCCrypt.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p,ctypes.c_size_t,
                           ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    crypto.CCCrypt.restype=ctypes.c_int
    conn=sqlite3.connect((Path(root)/'Cookies').resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    try:
        version=conn.execute("SELECT value FROM meta WHERE key='version'").fetchone()
        bound=bool(version and int(version[0])>=24)
        rows=conn.execute("SELECT name,host_key,encrypted_value,value FROM cookies WHERE host_key IN ('.claude.ai','claude.ai') AND name IN ('sessionKey','lastActiveOrg')").fetchall()
    finally:conn.close()
    values={}
    for name,host,raw,plain in rows:
        if raw:
            if not raw.startswith(b'v10'):raise UsageError('Claude 登录加密格式尚未支持')
            raw=raw[3:];output=ctypes.create_string_buffer(len(raw)+16);written=ctypes.c_size_t()
            if crypto.CCCrypt(1,0,1,key,len(key),b' '*16,raw,len(raw),output,len(output),ctypes.byref(written)):
                raise UsageError('无法解密 Claude 登录')
            clear=output.raw[:written.value]
            if bound:
                if not clear.startswith(hashlib.sha256(host.encode()).digest()):raise UsageError('Claude 登录来源校验失败')
                clear=clear[32:]
            plain=clear.decode('utf-8')
        if plain and not any(c in plain for c in '\r\n;'):values[name]=plain
    if not values.get('sessionKey') or not UUID.fullmatch(values.get('lastActiveOrg','')):
        raise UsageError('请先在 Claude App 登录')
    return values


def request_usage(session):
    if not UUID.fullmatch(session.get('lastActiveOrg','')):raise UsageError('Claude 组织格式异常')
    request=urllib.request.Request(ORIGIN+'/api/organizations/'+session['lastActiveOrg']+'/usage',
        headers={'Accept':'application/json','User-Agent':'Mozilla/5.0',
                 'Cookie':'; '.join(k+'='+session[k] for k in ('sessionKey','lastActiveOrg'))})
    opener=urllib.request.build_opener(SameOriginRedirect())
    with opener.open(request,timeout=12) as response:
        raw=response.read(1024*1024+1)
    if len(raw)>1024*1024:raise UsageError('用量响应过大')
    return json.loads(raw)


def parse_usage(data,now=None):
    if not isinstance(data,dict):raise UsageError('用量格式尚未支持')
    windows=[];seen=set()
    def add(label,percent,reset):
        if type(percent) not in (int,float) or not math.isfinite(percent) or not 0<=percent<=100:return
        if reset is not None and not isinstance(reset,str):return
        if not isinstance(label,str) or not label or (label,reset) in seen:return
        seen.add((label,reset));windows.append({'label':label[:80],'used':percent,'resetsAt':reset})
    # New plan API exposes model/surface limits instead of fixed five_hour keys.
    limits=data.get('limits')
    if isinstance(limits,list):
        for row in limits:
            if not isinstance(row,dict):continue
            scope=row.get('scope') if isinstance(row.get('scope'),dict) else {}
            model=scope.get('model') if isinstance(scope.get('model'),dict) else {}
            surface=scope.get('surface') if isinstance(scope.get('surface'),dict) else {}
            label=model.get('display_name') or surface.get('display_name')
            if not label:
                group=str(row.get('group',''));kind=str(row.get('kind',''))
                label='本周' if any(x in (group+' '+kind).lower() for x in ('week','seven_day')) else '当前周期'
            add(label,row.get('percent'),row.get('resets_at'))
    if not windows:
        for key,label in [('five_hour','5 小时'),('seven_day','本周'),('seven_day_opus','Opus 本周'),('seven_day_sonnet','Sonnet 本周')]:
            row=data.get(key)
            if isinstance(row,dict):add(label,row.get('utilization'),row.get('resets_at'))
    if not windows:raise UsageError('尚未返回可识别的订阅用量')
    return {'windows':windows,'updatedAt':time.time() if now is None else now,'stale':False,'state':'实时用量','source':'live'}


def live_subscription(root,consent=False):
    if consent is not True:return None,(0,'尚未授权读取 Claude 登录',None)
    try:return parse_usage(request_usage(desktop_session(root))),None
    except UsageError as error:return None,(0,str(error),None)
    except urllib.error.HTTPError as error:
        return None,(0,'Claude 登录需要更新' if error.code in (401,403) else 'Claude 用量服务暂不可用',None)
    except Exception:return None,(0,'Claude 用量读取失败，稍后重试',None)
