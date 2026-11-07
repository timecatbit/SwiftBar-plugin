import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from datetime import timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import swiftbar_sources as sources
import swiftbar_accounts as accounts


class ExtendedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cache=self.root/'index'
    def write(self,path,records):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(''.join(json.dumps(r)+'\n' for r in records))
    def test_workbuddy_inclusive_counters_and_duplicate_tool_calls(self):
        def record(id):return {'type':'function_call','id':id,'sessionId':'s','timestamp':1700000000000,'providerData':{'messageId':'response','model':'deepseek-v4','rawUsage':{'credit':99}},'message':{'usage':{'input_tokens':100,'output_tokens':30,'cache_read_input_tokens':80,'reasoning_tokens':20}},'content':'PRIVATE'}
        self.write(self.root/'.workbuddy/projects/project/a.jsonl',[record('a'),record('b')])
        self.write(self.root/'.workbuddy-ai/projects/project/b.jsonl',[record('copied')])
        result=sources.jsonl_usage('workbuddy',self.root,self.cache,0,9999999999,timezone.utc)
        self.assertEqual(result['summary']['requests'],1)
        self.assertEqual(result['summary']['totalTokens'],130)
        self.assertEqual(result['summary']['cachedInputTokens'],80)
        self.assertEqual(result['summary']['unpricedRequests'],1)
        for f in self.cache.glob('*.sqlite3'):self.assertNotIn(b'PRIVATE',f.read_bytes())
    def qoder(self,id,usage,model='qfmodel',session='s1',ts='2026-11-04T08:00:00.000Z'):
        return {'type':'assistant','timestamp':ts,'uuid':'row-'+id,'sessionId':session,'cwd':'/tmp/p',
                'message':{'id':id,'role':'assistant','model':model,'content':[{'type':'text','text':'PRIVATE'}],'usage':usage}}
    def test_qoder_plan_credits_byok_tokens_rewrites_and_subagent_copies(self):
        plan={'credits':0.73,'original_credits':0.9,'billable':False,'input_tokens':0,'output_tokens':0,'cache_read_input_tokens':0,'cache_creation_input_tokens':0}
        byok={'input_tokens':100,'output_tokens':30,'cache_read_input_tokens':50,'cache_creation_input_tokens':20,'billable':True}
        main=self.root/'projects/slug/s1.jsonl'
        self.write(main,[{'type':'user','message':{'content':'PRIVATE'}},
                         self.qoder('m1',dict(plan,credits=0.5)),self.qoder('m1',plan),
                         self.qoder('m2',byok,model='qoder-custom-e603-42d2/glm-5.3-flash'),
                         self.qoder('m3',{'input_tokens':0,'output_tokens':0}),self.qoder('m4',None,model='auto'),
                         self.qoder('m5',plan,ts='not a time')])
        self.write(self.root/'projects/slug/s1/subagents/agent-1.jsonl',[self.qoder('m1',plan),self.qoder('a1',dict(plan,credits=2))])
        result=sources.jsonl_usage('qoder',self.root,self.cache,0,9999999999,timezone.utc)
        summary=result['summary']
        self.assertEqual(summary['requests'],3);self.assertAlmostEqual(summary['credits'],2.73)
        self.assertEqual(summary['totalTokens'],200);self.assertEqual(summary['cachedInputTokens'],50)
        models={m['model']:m for m in result['models']}
        self.assertEqual(set(models),{'qfmodel','glm-5.3-flash'});self.assertAlmostEqual(models['qfmodel']['credits'],2.73)
        self.assertEqual(models['qfmodel']['totalTokens'],0)
        for f in self.cache.glob('*.sqlite3'):self.assertNotIn(b'PRIVATE',f.read_bytes())
        # A config directory without projects/ is read as the projects folder itself.
        self.assertEqual(sources.jsonl_usage('qoder',self.root/'projects',self.root/'other',0,9999999999,timezone.utc)['summary']['requests'],3)
    def gemini(self,id='one'):
        return {'id':id,'type':'gemini','timestamp':'2026-11-04T00:01:00Z','model':'gemini-test','tokens':{'input':100,'cached':60,'output':20,'thoughts':10,'tool':5,'total':135},'content':'PRIVATE'}
    def read_gemini(self):return sources.gemini_usage(self.root,self.cache,0,9999999999,timezone.utc)
    def test_gemini_migration_duplicate_and_rewound_usage(self):
        root=self.root/'tmp/project/chats';root.mkdir(parents=True)
        (root/'session-one.json').write_text(json.dumps({'sessionId':'s','messages':[self.gemini()]}))
        self.write(root/'session-one.jsonl',[{'sessionId':'s','projectHash':'p'},self.gemini(),{'$rewindTo':'one'},self.gemini('two'),{'$set':{'messages':[self.gemini('two')]}}])
        result=self.read_gemini();self.assertEqual(result['summary']['requests'],2);self.assertEqual(result['summary']['totalTokens'],270)
        self.assertEqual(result['summary']['outputTokens'],60);self.assertEqual(result['summary']['cachedInputTokens'],120)
        self.assertEqual(self.read_gemini()['summary'],result['summary'])
        for f in self.cache.glob('*.sqlite3'):self.assertNotIn(b'PRIVATE',f.read_bytes())
    def test_moonshot_balance_uses_region_currency_and_keeps_arrears(self):
        data={'code':0,'status':True,'data':{'available_balance':49.5,'voucher_balance':50,'cash_balance':-0.5}}
        self.assertEqual(accounts.moonshot_balance(data,'CNY'),{'balance':49.5,'currency':'CNY','state':'已同步','voucher':50.0,'cash':-0.5})
        self.assertEqual(accounts.moonshot_balance({'code':1,'status':False},'USD')['state'],'凭据或地区待检查')
        self.assertNotIn('balance',accounts.moonshot_balance({'code':0,'data':{'available_balance':'NaN'}},'USD'))
        seen=[]
        with patch.dict(os.environ,{'MOONSHOT_API_KEY':'sk-test','MOONSHOT_REGION':'international'}),patch.object(accounts,'get_json',side_effect=lambda url,key:seen.append(url) or data):
            self.assertEqual(accounts.account('kimi-api')['currency'],'USD')
        self.assertEqual(seen,['https://api.moonshot.ai/v1/users/me/balance'])
    def test_key_check_maps_status_without_reading_a_balance(self):
        import urllib.error
        def failing(code):
            def opener(*args):
                raise urllib.error.HTTPError('https://example.invalid',code,'x',{},None)
            return types.SimpleNamespace(open=lambda *a,**k:opener())
        for code,state,valid in [(401,'Key 无效或无权限',False),(400,'Key 无效或无权限',False),(429,'暂时限流，稍后再试',None),(500,'服务暂不可用',None)]:
            with patch.object(accounts.urllib.request,'build_opener',return_value=failing(code)):
                self.assertEqual(accounts.check_key('gemini-api','key'),{'valid':valid,'state':state})
        requests=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,n):return b'{}'
        with patch.object(accounts.urllib.request,'build_opener',return_value=types.SimpleNamespace(open=lambda request,timeout:requests.append(request) or Response())):
            self.assertEqual(accounts.check_key('claude-api','sk-ant-key'),{'valid':True,'state':'Key 有效'})
        self.assertEqual(requests[0].get_method(),'GET');self.assertEqual(requests[0].headers.get('X-api-key'),'sk-ant-key')
    def responder(self,pages,seen):
        class Response:
            def __init__(self,body):self.body=json.dumps(body).encode()
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,n):return self.body
        bodies=iter(pages)
        return types.SimpleNamespace(open=lambda request,timeout:seen.append(request) or Response(next(bodies)))
    def test_anthropic_cost_sums_month_and_utc_today_in_cents_across_pages(self):
        from datetime import datetime,timezone
        now=datetime(2026,11,6,5,tzinfo=timezone.utc);seen=[]
        pages=[{'data':[{'starting_at':'2026-11-01T00:00:00Z','results':[{'currency':'USD','amount':'1050.000000'}]}],'has_more':True,'next_page':'p2'},
               {'data':[{'starting_at':'2026-11-06T00:00:00Z','results':[{'currency':'USD','amount':'234.5'},{'amount':'100'}]}],'has_more':False,'next_page':None}]
        with patch.object(accounts.urllib.request,'build_opener',return_value=self.responder(pages,seen)):
            cost=accounts.anthropic_cost('sk-ant-admin01-test',now)
        self.assertAlmostEqual(cost['monthCost'],13.845);self.assertAlmostEqual(cost['todayCost'],3.345);self.assertEqual(cost['month'],'2026-11')
        self.assertIn('starting_at=2026-11-01T00%3A00%3A00Z',seen[0].full_url);self.assertIn('bucket_width=1d',seen[0].full_url)
        self.assertIn('page=p2',seen[1].full_url);self.assertEqual(seen[0].headers.get('X-api-key'),'sk-ant-admin01-test')
        import urllib.error
        def denied(*a,**k):raise urllib.error.HTTPError('https://api.anthropic.com',403,'x',{},None)
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'sk-ant-usr-test'}),patch.object(accounts,'anthropic_cost',side_effect=denied):
            self.assertEqual(accounts.account('claude-api'),{'state':'Key 所属账户没有查看花费的权限','permission':False,'reason':'role'})
        import io
        def workspace_key(*a,**k):
            raise urllib.error.HTTPError('https://api.anthropic.com',401,'x',{},io.BytesIO(b'{"error":{"type":"authentication_error","message":"The Admin API requires an Admin API key or an organization-scoped API key."}}'))
        def invalid(*a,**k):
            raise urllib.error.HTTPError('https://api.anthropic.com',401,'x',{},io.BytesIO(b'{"error":{"type":"authentication_error","message":"invalid x-api-key"}}'))
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'sk-ant-usr-test'}):
            with patch.object(accounts,'anthropic_cost',side_effect=workspace_key):
                self.assertEqual(accounts.account('claude-api')['reason'],'workspace')
            with patch.object(accounts,'anthropic_cost',side_effect=invalid):
                self.assertEqual(accounts.account('claude-api'),{'state':'凭据或查询权限待检查'})
    def test_claude_key_check_accepts_personal_keys_and_proves_admin_keys(self):
        import io,urllib.error
        def workspace(*a,**k):
            raise urllib.error.HTTPError('https://api.anthropic.com',400,'x',{},io.BytesIO(json.dumps({'error':{'type':'invalid_request_error','message':'This API key is not scoped to a workspace, so this request must include the anthropic-workspace-id header'}}).encode()))
        with patch.object(accounts.urllib.request,'build_opener',return_value=types.SimpleNamespace(open=workspace)):
            self.assertEqual(accounts.check_key('claude-api','sk-ant-usr-test'),{'valid':True,'state':'Key 有效 · 个人 Key'})
        seen=[]
        with patch.object(accounts.urllib.request,'build_opener',return_value=self.responder([{'id':'org'}],seen)):
            self.assertEqual(accounts.check_key('claude-api','sk-ant-admin01-test'),{'valid':True,'state':'管理员 Key 有效'})
        self.assertEqual(seen[0].full_url,'https://api.anthropic.com/v1/organizations/me')
    def test_gemini_deleted_session_stops_counting(self):
        root=self.root/'tmp/project/chats';self.write(root/'session-one.jsonl',[{'sessionId':'s'},self.gemini()]);self.write(root/'session-two.jsonl',[{'sessionId':'t'},self.gemini('two')])
        self.assertEqual(self.read_gemini()['summary']['requests'],2)
        (root/'session-two.jsonl').unlink();self.assertEqual(self.read_gemini()['summary']['requests'],1)
    def test_gemini_updated_message_and_partial_tail(self):
        f=self.root/'session-one.jsonl';row=self.gemini()
        self.write(f,[{'sessionId':'s'},dict(row,tokens=None)])
        partial=json.dumps(row)
        with f.open('a') as out:out.write(partial[:30])
        self.assertEqual(self.read_gemini()['summary']['requests'],0)
        with f.open('a') as out:out.write(partial[30:]+'\n')
        self.assertEqual(self.read_gemini()['summary']['totalTokens'],135)
    def test_account_modules_require_explicit_configuration(self):
        with patch.dict(os.environ,{},clear=True),patch.object(accounts,'get_json') as fetch:
            self.assertIn('未配置',accounts.account('grok')['state']);self.assertIn('未配置',accounts.account('minimax')['state']);fetch.assert_not_called()
    def test_xai_ledger_sign_cents_and_private_fields(self):
        result=accounts.xai_balance({'total':{'val':'-12345'},'changes':[{'teamId':'PRIVATE'}]})
        self.assertEqual(result['balance'],123.45);self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertEqual(accounts.xai_balance({'total':{'val':'500'}})['balance'],-5)
        self.assertNotIn('balance',accounts.xai_balance({}))
    def test_minimax_explicit_percent_legacy_and_unavailable_plan(self):
        result=accounts.minimax_quota({'base_resp':{'status_code':0},'model_remains':[
            {'model_name':'text','current_interval_total_count':100,'current_interval_usage_count':90,'current_interval_remaining_percent':10,'end_time':1800000000000},
            {'model_name':'old','current_interval_total_count':100,'current_interval_usage_count':70},
            {'model_name':'not-in-plan','current_interval_total_count':0,'current_interval_status':3,'current_interval_remaining_percent':100,'current_weekly_total_count':0,'current_weekly_status':3,'current_weekly_remaining_percent':100}]})
        self.assertEqual([w['remaining'] for w in result['windows']],[10,70]);self.assertEqual(result['windows'][0]['resetsAt'],1800000000)
        self.assertFalse(accounts.minimax_quota({'base_resp':{'status_code':1004}})['windows'])
        bounded=accounts.minimax_quota({'base_resp':{'status_code':0},'model_remains':[{'model_name':'general','current_interval_remaining_percent':60,'start_time':1799982000000,'end_time':1800000000000,
                                       'current_weekly_remaining_percent':90,'weekly_start_time':1799395200,'weekly_end_time':1800000000}]})['windows']
        self.assertEqual([(w['startsAt'],w['resetsAt']) for w in bounded],[(1799982000,1800000000),(1799395200,1800000000)])
    def test_account_requests_are_scoped_and_credentials_not_returned(self):
        with patch.dict(os.environ,{'XAI_MANAGEMENT_API_KEY':'private-key','XAI_TEAM_ID':'team/id'},clear=True),patch.object(accounts,'get_json',return_value={'total':{'val':'-100'}}) as fetch:
            value=accounts.account('grok');self.assertNotIn('private-key',json.dumps(value));self.assertEqual(fetch.call_args.args[0],'https://management-api.x.ai/v1/billing/teams/team%2Fid/prepaid/balance')
        self.assertIsNone(accounts.NoRedirect().redirect_request(None,None,302,'',{},'https://other.test'))

if __name__=='__main__':unittest.main()
