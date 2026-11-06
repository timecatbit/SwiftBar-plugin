"""Claude desktop ownership, consent boundary and server response tests; no live login."""
import json,os,sys,tempfile,types,unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import swiftbar_claude as desktop
import swiftbar_claude_live as live
import swiftbar_preferences as preferences
SOURCE=Path(__file__).resolve().parents[1]/'opencodex.30s.sh'
CODE=SOURCE.read_text().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
ACCOUNT='11111111-1111-4111-8111-111111111111'
ORG='22222222-2222-4222-8222-222222222222'
SESSION='33333333-3333-4333-8333-333333333333'
OTHER='44444444-4444-4444-8444-444444444444'
class DesktopTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.home=Path(self.temp.name);self.root=desktop.default_root(self.home);self.root.mkdir(parents=True)
  self.registry=self.root/'claude-code-sessions'/ACCOUNT/ORG;self.registry.mkdir(parents=True)
  (self.root/'config.json').write_text(json.dumps({'lastKnownAccountUuid':ACCOUNT}))
  self.env=patch.dict(os.environ,{'HOME':str(self.home),'OCX_PLUGIN_PATH':str(SOURCE),'OCX_CACHE_DIR':str(self.home/'cache'),'SWIFTBAR_PLUGIN_DATA_PATH':str(self.home/'state')})
  self.env.start();self.addCleanup(self.env.stop)
  self.m=types.ModuleType('desktop_test');exec(compile(CODE,str(SOURCE),'exec'),self.m.__dict__)
  self.now=datetime(2026,11,5,12,tzinfo=ZoneInfo('Asia/Taipei'))
 def register(self,session=SESSION):
  (self.registry/(session+'.json')).write_text(json.dumps({'sessionId':session,'cliSessionId':session}))
 def transcript(self,session,subagent=False):
  p=self.home/'.claude/projects/project'
  p=p/session/'subagents'/'agent-1.jsonl' if subagent else p/(session+'.jsonl');p.parent.mkdir(parents=True,exist_ok=True)
  row={'type':'assistant','timestamp':'2026-11-05T01:00:00Z','sessionId':session,'requestId':'sub' if subagent else session,'message':{'id':'msg-'+('sub' if subagent else session),'model':'claude-opus-5-5','usage':{'input_tokens':100,'output_tokens':20}}}
  p.write_text(json.dumps(row)+'\n');return p
 def test_registry_allowlist_excludes_standalone_cli_and_includes_app_subagents(self):
  self.register();main=self.transcript(SESSION);sub=self.transcript(SESSION,True);self.transcript(OTHER)
  files,ids=desktop.transcript_files(self.root,self.home)
  self.assertEqual(set(files),{main,sub});self.assertEqual(ids,{SESSION})
  data,error=self.m.claude_usage_live(self.root,now=self.now)
  self.assertIsNone(error);self.assertEqual(data['summary']['requests'],2)
 def test_account_switch_and_removed_registration_exclude_indexed_old_sessions(self):
  self.register();self.register(OTHER);self.transcript(SESSION);self.transcript(OTHER)
  data,_=self.m.claude_usage_live(self.root,now=self.now);self.assertEqual(data['summary']['requests'],2)
  (self.registry/(OTHER+'.json')).unlink()
  data,_=self.m.claude_usage_live(self.root,now=self.now);self.assertEqual(data['summary']['requests'],1)
  (self.root/'config.json').write_text(json.dumps({'lastKnownAccountUuid':OTHER}))
  self.assertEqual(desktop.registered_ids(self.root),set())
 def test_cli_only_is_not_mislabeled_as_desktop_usage(self):
  self.transcript(OTHER)
  data,_=self.m.claude_usage_live(self.root,now=self.now)
  self.assertIn('暂无可读取',data['error']);self.assertNotIn('summary',data)
 def test_multiple_config_roots_keep_only_app_registered_sessions(self):
  self.register();owned=self.transcript(SESSION);cli=self.transcript(OTHER)
  xdg=self.home/'.config/claude/projects';xdg.mkdir(parents=True)
  (xdg/owned.name).write_bytes(owned.read_bytes());(xdg/cli.name).write_bytes(cli.read_bytes())
  files,_=desktop.transcript_files(self.root,self.home)
  self.assertEqual(len(files),2)
  with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':str(xdg)+','+str(xdg.parent)}):
   files,_=desktop.transcript_files(self.root,self.home);self.assertEqual(files,[xdg/owned.name])
  data,_=self.m.claude_usage_live(self.root,now=self.now)
  self.assertEqual(data['summary']['requests'],1)
 def test_legacy_cli_path_does_not_override_app_path(self):
  prefs=preferences.read(self.m.STATE_DIR);prefs['paths']['claude']=str(self.home/'.claude/projects');preferences.write(self.m.STATE_DIR,prefs)
  self.assertEqual(self.m.source_path('claude'),str(self.root))
  preferences.update(self.m.STATE_DIR,'path','claude',str(self.registry.resolve()))
  self.assertEqual(self.m.source_path('claude'),str(self.registry.resolve()))
  preferences.update(self.m.STATE_DIR,'auto-path','claude');self.assertEqual(self.m.source_path('claude'),str(self.root))
 def snapshot(self,samples):
  (self.root/'plan-usage-history.json').write_text(json.dumps({'version':2,'samples':samples}))
 def test_snapshot_staleness_and_wrong_org_are_not_current_usage(self):
  self.snapshot([{'t':1000000,'org':ORG,'u':{'sd':88,'fh':False,'sn':float('nan')}}])
  result=desktop.subscription(self.root,now=5000)
  self.assertTrue(result['stale']);self.assertEqual(result['windows'],[{'label':'本周','used':88}])
  self.snapshot([{'t':4999000,'org':OTHER,'u':{'sd':96}}]);self.assertEqual(desktop.subscription(self.root,now=5000)['windows'],[])
 def test_live_requires_explicit_consent_and_cancel_writes_nothing(self):
  with patch.object(live,'desktop_session') as session:
   self.assertIsNotNone(live.live_subscription(self.root)[1]);session.assert_not_called()
   self.m.claude_subscription_load();session.assert_not_called()
  before=preferences.read(self.m.STATE_DIR)
  with patch.object(self.m,'confirm',return_value=False),patch.object(self.m,'schedule_background_refresh') as schedule:
   self.m.run_action('set-claude-live',['true']);schedule.assert_not_called()
  self.assertEqual(preferences.read(self.m.STATE_DIR),before)
 def test_enable_and_revoke_invalidate_cache_and_stop_credential_access(self):
  before=self.m.connection_fingerprint('claude_subscription')
  with patch.object(self.m,'confirm',return_value=True),patch.object(self.m,'schedule_background_refresh'):
   self.m.run_action('set-claude-live',['true'])
   self.assertTrue(preferences.read(self.m.STATE_DIR)['claudeLiveUsage'])
   self.assertNotEqual(self.m.connection_fingerprint('claude_subscription'),before)
   self.m.run_action('set-claude-live',['false'])
  with patch.object(live,'desktop_session') as session:
   self.m.claude_subscription_load();session.assert_not_called()
 def test_real_time_rows_show_resets_and_no_claim_on_missing_credits(self):
  payload=live.parse_usage({'limits':[{'kind':'weekly','percent':88,'resets_at':'2026-11-05T14:00:00Z'},{'kind':'weekly','percent':96,'scope':{'model':{'display_name':'Fable'}}}]})
  with patch.object(self.m,'local_zone',return_value=ZoneInfo('Asia/Taipei')):
   lines='\n'.join(self.m.claude_subscription_lines({'claude_subscription':payload}))
  self.assertIn('88%',lines);self.assertIn('Fable',lines);self.assertIn('22:00',lines);self.assertNotIn('$0',lines)
 def test_live_balance_is_separate_and_reset_rounds_to_displayed_minute(self):
  payload=live.parse_usage({'limits':[{'kind':'weekly','percent':0,'resets_at':'2026-11-12T13:59:59.644073Z'}]},credits={'currency':'USD','balance':{'credits':{'amount_minor':1534,'exponent':2}}})
  with patch.object(self.m,'local_zone',return_value=ZoneInfo('Asia/Taipei')):
   lines='\n'.join(self.m.claude_subscription_lines({'claude_subscription':payload}))
  self.assertIn('22:00',lines);self.assertIn('$15.34',lines);self.assertIn('用量额度余额',lines)
  self.assertIn('0% 已用',lines);self.assertNotIn('刷新失败',lines)

class LiveSchemaTests(unittest.TestCase):
 def test_missing_cookie_store_does_not_open_keychain(self):
  with tempfile.TemporaryDirectory() as root,patch.object(live.subprocess,'run') as command:
   with self.assertRaises(live.UsageError):live.desktop_session(root)
   command.assert_not_called()
 def test_new_and_old_plan_formats(self):
  result=live.parse_usage({'limits':[{'kind':'seven_day','percent':88,'resets_at':'2026-11-05T14:00:00Z'},{'kind':'seven_day','percent':96,'scope':{'model':{'display_name':'Fable'}}}]},now=123)
  self.assertEqual([(w['label'],w['used']) for w in result['windows']],[('本周',88),('Fable',96)]);self.assertEqual(result['updatedAt'],123)
  self.assertEqual(live.parse_usage({'five_hour':{'utilization':23}})['windows'][0]['used'],23)
 def test_malformed_values_are_not_fabricated(self):
  for row in ({'percent':True},{'percent':float('nan')},{'percent':-1},{'percent':110},{'percent':88,'resets_at':{}}):
   with self.assertRaises(live.UsageError):live.parse_usage({'limits':[row]})
  self.assertEqual(live.parse_usage({'limits':[{'percent':50,'scope':42}]})['windows'][0]['used'],50)
 def test_no_error_secrets_exposed(self):
  with patch.object(live,'transport_client'),patch.object(live,'desktop_session',side_effect=RuntimeError('secret-value')):
   _,error=live.live_subscription('/unused',True)
  self.assertNotIn('secret-value',str(error))
 def client(self,status=200,headers=None,body=b'{"seven_day":{"utilization":88}}'):
  client=Mock()
  def get(*args,**kwargs):
   kwargs['content_callback'](body)
   return types.SimpleNamespace(status_code=status,headers=headers or {'content-type':'application/json'})
  client.get.side_effect=get;return client
 def test_request_only_uses_two_official_endpoints_and_cookie_allowlist(self):
  client=self.client();session={'sessionKeyV3':'test-not-real','lastActiveOrg':ORG,'trackingCookie':'never-send'}
  for resource in ('usage','prepaid/credits'):
   live.request_json(client,session,resource)
   args,kwargs=client.get.call_args
   self.assertEqual(args[0],'https://claude.ai/api/organizations/'+ORG+'/'+resource)
   self.assertFalse(kwargs['allow_redirects']);self.assertNotIn('trackingCookie',kwargs['cookies'])
   self.assertEqual(kwargs['cookies']['sessionKeyV3'],'test-not-real')
  for resource in ('https://example.com','../billing','prepaid/commits','usage?x=1'):
   with self.assertRaises(live.UsageError):live.request_json(client,session,resource)
 def test_redirect_challenge_login_network_and_oversize_have_safe_errors(self):
  session={'lastActiveOrg':ORG}
  cases=[(self.client(302,{'location':'https://example.com/secret'}),'跳转'),
         (self.client(403,{'cf-mitigated':'challenge'}),'浏览器验证'),
         (self.client(401),'重新登录'),(self.client(200,{'content-type':'text/html'}),'非用量页面'),
         (self.client(body=b'x'*(live.MAX_RESPONSE+1)),'过大')]
  for client,expected in cases:
   with self.assertRaisesRegex(live.UsageError,expected):live.request_json(client,session,'usage')
  client=Mock();client.get.side_effect=RuntimeError('secret-cookie-value')
  with self.assertRaisesRegex(live.UsageError,'连接失败'):live.request_json(client,session,'usage')
 def test_credit_balance_uses_exact_units_not_limit_or_rounded_credits(self):
  data={'currency':'USD','balance':{'money':None,'credits':{'amount_minor':1534,'exponent':2}},'balance_credits':15}
  self.assertEqual(live.parse_credits(data),{'amount':15.34,'currency':'USD','decimals':2})
  self.assertIsNone(live.parse_credits({'extra_usage':{'monthly_limit':2000,'used_credits':0},'spend':{'limit':2000}}))
  for minor,exponent in [(True,2),(-1,2),(float('nan'),2),(1534,True),(1534,100)]:
   data['balance']['credits']={'amount_minor':minor,'exponent':exponent};self.assertIsNone(live.parse_credits(data))
 def test_partial_failure_preserves_the_other_result_without_credentials(self):
  credits={'currency':'USD','balance':{'credits':{'amount_minor':0,'exponent':2}},'account_uuid':'never-cache'}
  result=live.parse_usage({},credits=credits,usage_error='用量服务暂不可用')
  self.assertEqual(result['creditBalance']['amount'],0);self.assertEqual(result['windows'],[])
  self.assertIn('usageError',result);self.assertNotIn('never-cache',json.dumps(result))
  result=live.parse_usage({'seven_day':{'utilization':88}},credits_error='余额服务暂不可用')
  self.assertEqual(result['windows'][0]['used'],88);self.assertNotIn('creditBalance',result)
  self.assertIn('creditsError',result)
 def test_live_reads_once_and_can_keep_balance_if_usage_fails(self):
  manager=Mock();manager.__enter__=Mock(return_value=Mock());manager.__exit__=Mock(return_value=False)
  with patch.object(live,'transport_client',return_value=manager),patch.object(live,'desktop_session',return_value={'lastActiveOrg':ORG}) as session,patch.object(live,'request_json',side_effect=[live.UsageError('用量暂不可用'),{'currency':'USD','balance':{'credits':{'amount_minor':1534,'exponent':2}}}]):
   data,error=live.live_subscription('/unused',True)
  session.assert_called_once();self.assertIsNone(error);self.assertEqual(data['creditBalance']['amount'],15.34)

if __name__=='__main__':unittest.main()
