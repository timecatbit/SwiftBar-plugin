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
 def test_cross_origin_redirect_is_blocked_and_no_error_secrets_exposed(self):
  redirect=live.SameOriginRedirect()
  for url in ('http://claude.ai/a','https://example.com/a','https://claude.ai.example.com/a'):
   with self.assertRaises(live.UsageError):redirect.redirect_request(None,None,302,'',{},url)
  with patch.object(live,'desktop_session',side_effect=RuntimeError('secret-value')):
   _,error=live.live_subscription('/unused',True)
  self.assertNotIn('secret-value',str(error))
 def test_request_only_uses_official_organization_endpoint(self):
  response=Mock();response.read.return_value=b'{"seven_day":{"utilization":88}}'
  context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
  opener=Mock();opener.open.return_value=context
  with patch.object(live.urllib.request,'build_opener',return_value=opener):
   live.request_usage({'sessionKey':'test-not-real','lastActiveOrg':ORG})
  request=opener.open.call_args.args[0]
  self.assertEqual(request.full_url,'https://claude.ai/api/organizations/'+ORG+'/usage')
  self.assertEqual(request.get_method(),'GET')

if __name__=='__main__':unittest.main()
