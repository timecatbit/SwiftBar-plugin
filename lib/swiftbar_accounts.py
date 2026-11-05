"""Read-only provider account resources. No credentials or raw responses cached."""
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward an Authorization header to another endpoint.


def credential(name):
    value = os.environ.get(name, '').strip()
    if value: return value
    filename = os.environ.get(name+'_FILE', '')
    if not filename: return ''
    try: return Path(filename).expanduser().read_text().strip()
    except OSError: return ''


def get_json(url, key):
    request = urllib.request.Request(url, headers={'Authorization':'Bearer '+key, 'Accept':'application/json'}, method='GET')
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=8) as response:
        data=json.loads(response.read(2*1024*1024))
        if not isinstance(data,dict):raise ValueError('invalid account response')
        return data


def percent(value):
    if isinstance(value,bool):return None
    try:
        result=float(value)
        return result if math.isfinite(result) and 0<=result<=100 else None
    except (ValueError,TypeError):return None


def xai_balance(data):
    try:
        # The billing ledger is debit-positive: a $10 purchase has total -1000.
        amount=-Decimal(str(data['total']['val']))/100
        if not amount.is_finite():raise ValueError()
        return {'balance':float(amount),'currency':'USD','state':'已同步'}
    except (KeyError,TypeError,InvalidOperation,ValueError):return {'state':'余额格式待检查'}


def minimax_quota(data):
    base=data.get('base_resp') or {}
    if base.get('status_code') != 0:return {'state':'套餐凭据或地区待检查','windows':[]}
    windows=[]
    for row in data.get('model_remains') or []:
        if not isinstance(row,dict):continue
        model=str(row.get('model_name') or '套餐')
        if all(row.get('current_'+span+'_total_count')==0 and row.get('current_'+span+'_status')==3 for span in ('interval','weekly')):
            continue  # Not included in this plan, not 100% available.
        for span,label,reset in [('interval','滚动额度','end_time'),('weekly','本周额度','weekly_end_time')]:
            status=row.get('current_'+span+'_status');total=row.get('current_'+span+'_total_count')
            remaining=percent(row.get('current_'+span+'_remaining_percent'))
            if span=='weekly' and status==3:continue  # unlimited, no finite percentage
            if remaining is None:
                count=row.get('current_'+span+'_usage_count')
                # Legacy API used usage_count for REMAINING. Explicit current
                # percentages are authoritative when present (official CLI).
                if isinstance(total,(int,float)) and total>0 and isinstance(count,(int,float)) and 0<=count<=total:
                    remaining=100*count/total
            if remaining is None:continue
            ends=row.get(reset)
            ends=ends/1000 if isinstance(ends,(int,float)) and ends>1e11 else ends if isinstance(ends,(int,float)) else None
            windows.append({'name':model+' · '+label,'remaining':remaining,'resetsAt':ends})
    return {'state':'已同步' if windows else '暂无可读取的套餐额度','windows':windows}


def account(source):
    """Only explicitly configured provider credentials are used."""
    try:
        if source=='grok':
            key=credential('XAI_MANAGEMENT_API_KEY');team=os.environ.get('XAI_TEAM_ID','').strip()
            if not key or not team:return {'state':'未配置 xAI 管理密钥与 Team ID'}
            url='https://management-api.x.ai/v1/billing/teams/'+urllib.parse.quote(team,safe='')+'/prepaid/balance'
            return xai_balance(get_json(url,key))
        if source=='minimax':
            key=credential('MINIMAX_API_KEY')
            if not key:return {'state':'未配置 MiniMax 套餐密钥','windows':[]}
            region=os.environ.get('MINIMAX_REGION','international')
            if region not in ('international','china'):return {'state':'MiniMax 地区配置待检查','windows':[]}
            host='https://www.minimax.io' if region=='international' else 'https://api.minimaxi.com'
            return minimax_quota(get_json(host+'/v1/token_plan/remains',key))
        return {'state':'不支持的账户来源'}
    except urllib.error.HTTPError as error:
        return {'state':'凭据或查询权限待检查' if error.code in (401,403) else '服务暂不可用'}
    except (OSError,ValueError,TypeError,KeyError):return {'state':'暂时无法读取'}
