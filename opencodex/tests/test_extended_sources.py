import json
import os
from pathlib import Path
import sys
import tempfile
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
    def test_account_requests_are_scoped_and_credentials_not_returned(self):
        with patch.dict(os.environ,{'XAI_MANAGEMENT_API_KEY':'private-key','XAI_TEAM_ID':'team/id'},clear=True),patch.object(accounts,'get_json',return_value={'total':{'val':'-100'}}) as fetch:
            value=accounts.account('grok');self.assertNotIn('private-key',json.dumps(value));self.assertEqual(fetch.call_args.args[0],'https://management-api.x.ai/v1/billing/teams/team%2Fid/prepaid/balance')
        self.assertIsNone(accounts.NoRedirect().redirect_request(None,None,302,'',{},'https://other.test'))

if __name__=='__main__':unittest.main()
