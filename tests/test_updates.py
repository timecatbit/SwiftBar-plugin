import json,os,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
SOURCE=Path(__file__).resolve().parents[1]/'opencodex.30s.sh'
CODE=SOURCE.read_text().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
class UpdateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  env=patch.dict(os.environ,{'KOMARI_BASE_URL':'https://komari.example.test','OS_APPEARANCE':'Dark','OCX_CACHE_DIR':self.tmp.name,'SWIFTBAR_PLUGIN_DATA_PATH':self.tmp.name,'OCX_PLUGIN_PATH':str(SOURCE.resolve())});env.start();self.addCleanup(env.stop)
  self.m=types.ModuleType('updates_test');exec(compile(CODE,str(SOURCE),'exec'),self.m.__dict__)
  configured=patch.object(self.m,'ocx_configured',return_value=False);configured.start();self.addCleanup(configured.stop)
  installed=patch.object(self.m,'app_info',return_value={});installed.start();self.addCleanup(installed.stop)
 def row(self,version='4.16336.0'):
  return {'id':'claude','name':'Claude','latest':version,'current':'4.4212.0','available':True,'checkedAt':time.time()}
 def test_numeric_versions_and_unknown_values(self):
  self.assertTrue(self.m.newer_release('4.16336.0','4.4212.0'))
  self.assertFalse(self.m.newer_release('2.1.99','2.1.308'))
  self.assertFalse(self.m.newer_release('garbage 999','2.1.308'))
  self.assertFalse(self.m.newer_release('2.1.318',None))
 def test_notifications_deduplicate_across_cache_refresh_and_restart(self):
  with patch.object(self.m,'send_update_notification',return_value=True) as send:
   self.m.notify_app_updates([self.row()]);self.m.notify_app_updates([self.row()])
   send.assert_called_once()
   self.m.notify_app_updates([self.row('4.16337.0')]);self.assertEqual(send.call_count,2)
  state=json.loads(Path(self.tmp.name,'updates-notified.json').read_text())
  self.assertEqual(state['claude'],['4.16336.0','4.16337.0'])
  with patch.object(self.m,'send_update_notification') as send:
   self.m.notify_app_updates([self.row()]);send.assert_not_called()
 def test_failed_delivery_is_retryable(self):
  with patch.object(self.m,'send_update_notification',return_value=False) as send:
   self.m.notify_app_updates([self.row()]);self.m.notify_app_updates([self.row()]);self.assertEqual(send.call_count,2)
 def test_stale_or_failed_checks_do_not_notify(self):
  stale=dict(self.row(),checkedAt=time.time()-30000);failed=dict(self.row(),available=False)
  with patch.object(self.m,'send_update_notification') as send:
   self.m.notify_app_updates([stale,failed]);send.assert_not_called()
 def test_network_error_does_not_claim_current_version_is_latest(self):
  with patch.object(self.m,'app_info',return_value={'CFBundleShortVersionString':'4.4212.0'}),patch.object(self.m,'release_body',side_effect=TimeoutError):
   row=self.m.app_update_probe('claude')
  self.assertFalse(row['available']);self.assertIn('失败',row['status'])
 def test_claude_checks_the_desktop_app_and_official_desktop_feed(self):
  with patch.object(self.m,'app_info',return_value={'CFBundleShortVersionString':'4.4212.0'}) as info,patch.object(self.m,'release_body',return_value=b'{"currentRelease":"4.16336.0"}') as release,patch.object(self.m.subprocess,'run') as command:
   row=self.m.app_update_probe('claude')
  info.assert_called_once_with('Claude');command.assert_not_called()
  self.assertIn('/api/desktop/darwin/universal/squirrel/update?',release.call_args.args[0])
  self.assertEqual(row['name'],'Claude');self.assertEqual(row['current'],'4.4212.0');self.assertTrue(row['available'])
 def test_missing_claude_app_does_not_fall_back_to_cli(self):
  with patch.object(self.m,'release_body') as release,patch.object(self.m.subprocess,'run') as command:
   row=self.m.app_update_probe('claude')
  self.assertEqual(row['status'],'未安装');release.assert_not_called();command.assert_not_called()
 def test_claude_selection_includes_code_update_and_notification(self):
  self.select('claude')
  cli=dict(self.row(),id='claude-code',name='Claude Code')
  rows=self.m.update_rows({'app_updates':{'apps':[cli]}})
  self.assertEqual([r['id'] for r in rows],['claude','claude-code']);self.assertEqual(self.m.update_attention_count(rows),1)
  with patch.object(self.m,'send_update_notification',return_value=True) as send:
   self.m.notify_app_updates([cli]);send.assert_called_once()
 def test_sparkle_uses_build_and_filters_other_architecture(self):
  xml=b'''<rss xmlns:s="http://www.andymatuschak.org/xml-namespaces/sparkle"><channel><item><s:shortVersionString>26.1029.61003</s:shortVersionString><s:version>24614</s:version><s:hardwareRequirements>arm64</s:hardwareRequirements></item><item><s:shortVersionString>99.0.0</s:shortVersionString><s:version>99999</s:version><s:hardwareRequirements>x64</s:hardwareRequirements></item></channel></rss>'''
  with patch.object(self.m.platform,'machine',return_value='arm64'):
   self.assertEqual(self.m.sparkle_release(xml),('26.1029.61003','24614'))
 def test_installed_desktop_update_immediately_clears_old_alert(self):
  self.m.preferences.update(self.m.STATE_DIR,'module','codex','true')
  row=dict(self.row(),id='chatgpt',latest='4.16336.0')
  with patch.object(self.m,'app_info',return_value={'CFBundleShortVersionString':'4.16336.0'}):
   rows=self.m.update_rows({'app_updates':{'apps':[row]}})
  self.assertFalse(next(r for r in rows if r['id']=='chatgpt')['available'])
 def test_home_balances_are_visible_and_not_nested_under_management(self):
  data={'healthz':{'version':'2.97.0'},'provider_quotas':{'reports':[{'provider':'deepseek','quota':{'customWindows':[{'label':'¥229.61'}]}}]},'accounts':{'accounts':[{'id':'a','logLabel':'main'}]},'quota':{'quotas':{'a':{'weeklyPercent':76}}}}
  with patch.object(self.m,'deepseek_logo_image',return_value=None),patch.object(self.m,'chatgpt_source',return_value='proxy'):
   entries=self.m.panel_entries(self.m.management_lines(data))
  by_name={e['label']:e for e in entries}
  self.assertIn('229.61',by_name['DeepSeek API']['value']);self.assertIn('main 24%',by_name['ChatGPT 订阅']['value'])
  management=next(e for e in entries if e['label']=='OpenCodex 管理')
  self.assertFalse(any('DeepSeek' in e['label'] for e in management['children']))
 def select(self,*harnesses,updates=True):
  settings=self.m.preferences.read(self.m.STATE_DIR)
  settings['visible']=list(harnesses)+(['updates'] if updates else [])
  self.m.preferences.write(self.m.STATE_DIR,settings)
 def test_default_updates_follow_only_selected_harnesses(self):
  self.assertEqual(self.m.selected_update_ids(),['opencodex','claude','claude-code','chatgpt','codex-cli'])
  self.assertEqual([r['id'] for r in self.m.update_rows({})],['opencodex','claude','claude-code','chatgpt','codex-cli'])
 def test_configured_opencodex_also_checks_chatgpt_without_changing_home_selection(self):
  self.select('claude')
  before=self.m.preferences.read(self.m.STATE_DIR)
  with patch.object(self.m,'ocx_configured',return_value=True),patch.object(self.m,'app_info',return_value={}),patch.object(self.m,'app_update_probe',side_effect=lambda key:dict(self.row(),id=key,href=self.m.UPDATE_LINKS[key],status='有新版本')) as probe:
   self.assertEqual(self.m.selected_update_ids(),['claude','claude-code','chatgpt','codex-cli'])
   self.m.app_updates_cached()
   self.assertCountEqual([c.args[0] for c in probe.call_args_list],['claude','claude-code','chatgpt','codex-cli'])
   self.assertNotIn('badge',self.m.external_loaders())
   self.assertIn('按 Harness 勾选及客户端联动规则检查','\n'.join(self.m.app_update_lines({})))
  self.assertEqual(self.m.preferences.read(self.m.STATE_DIR),before)
 def test_configured_opencodex_adds_chatgpt_once_even_with_no_selected_harness(self):
  with patch.object(self.m,'ocx_configured',return_value=True):
   for selected in ((),('codex',)):
    self.select(*selected)
    self.assertEqual(self.m.selected_update_ids(),['chatgpt','codex-cli'])
    with patch.object(self.m,'app_info',return_value={}):
     self.assertEqual([r['id'] for r in self.m.update_rows({})],['chatgpt','codex-cli'])
 def test_opencodex_presence_changes_invalidate_cache_and_remove_unselected_chatgpt_alerts(self):
  self.select('claude')
  with patch.object(self.m,'ocx_configured',return_value=False) as configured,patch.object(self.m,'app_update_probe',side_effect=lambda key:dict(self.row(),id=key,href='https://example.test',status='有新版本')) as probe:
   self.m.app_updates_cached()
   configured.return_value=True
   self.assertEqual(self.m.read_cache('app_updates'),{})
   self.m.app_updates_cached()
   self.assertCountEqual([c.args[0] for c in probe.call_args_list],['claude','claude-code','claude','claude-code','chatgpt','codex-cli'])
   payload=self.m.read_cache('app_updates')['payload']
   linked=[r for r in payload['apps'] if r['id']=='chatgpt']
   with patch.object(self.m,'send_update_notification',return_value=True) as send:
    self.m.notify_app_updates(linked);send.assert_called_once()
   configured.return_value=False
   self.assertEqual(self.m.read_cache('app_updates'),{})
   rows=self.m.update_rows({'app_updates':payload})
   self.assertEqual([r['id'] for r in rows],['claude','claude-code'])
   self.assertEqual(self.m.update_attention_count(rows),2)
   with patch.object(self.m,'send_update_notification') as send:
    self.m.notify_app_updates([dict(linked[0],latest='99.0.0')]);send.assert_not_called()
 def test_subscription_and_api_choices_do_not_select_app_updates(self):
  self.select('chatgpt','claude-subscription','deepseek','gemini-api')
  with patch.object(self.m,'app_update_probe') as probe,patch.object(self.m,'update_status_cached') as proxy:
   self.assertEqual(self.m.selected_update_ids(),[])
   self.assertEqual(self.m.update_rows({}),[])
   self.m.app_updates_cached();loaders=self.m.external_loaders()
  probe.assert_not_called();proxy.assert_not_called()
  self.assertNotIn('app_updates',loaders);self.assertNotIn('badge',loaders)
  self.assertIn('尚未勾选 Harness','\n'.join(self.m.app_update_lines({})))
 def test_selected_harness_is_the_only_network_probe(self):
  self.select('claude')
  with patch.object(self.m,'app_update_probe',return_value=self.row()) as probe:
   self.m.app_updates_cached()
  self.assertCountEqual([c.args[0] for c in probe.call_args_list],['claude','claude-code'])
 def test_switching_harness_invalidates_recent_update_cache(self):
  self.select('claude')
  def row(key):return dict(self.row(),id=key)
  with patch.object(self.m,'app_update_probe',side_effect=row) as probe:
   self.m.app_updates_cached();self.select('codex');self.m.app_updates_cached()
  self.assertCountEqual([c.args[0] for c in probe.call_args_list],['claude','claude-code','chatgpt','codex-cli'])
 def test_deselected_cached_update_is_hidden_from_list_badge_and_notification(self):
  self.select('codex')
  with patch.object(self.m,'app_info',return_value={}):rows=self.m.update_rows({'app_updates':{'apps':[self.row()]}})
  self.assertEqual([r['id'] for r in rows],['chatgpt','codex-cli'])
  self.assertEqual(self.m.update_attention_count(rows),0)
  with patch.object(self.m,'send_update_notification') as send:self.m.notify_app_updates([self.row()])
  send.assert_not_called()
 def test_turning_off_update_module_stops_checks_and_notifications(self):
  self.select('claude',updates=False)
  with patch.object(self.m,'ocx_configured',return_value=True),patch.object(self.m,'app_update_probe') as probe,patch.object(self.m,'send_update_notification') as send:
   self.m.app_updates_cached();self.m.notify_app_updates([self.row(),dict(self.row(),id='chatgpt')])
   self.assertNotIn('app_updates',self.m.external_loaders())
  probe.assert_not_called();send.assert_not_called()
 def test_selected_sources_without_auto_check_have_honest_official_entries(self):
  self.select('opencode','gemini')
  with patch.object(self.m,'app_update_probe') as probe:
   rows=self.m.update_rows({});self.m.app_updates_cached()
  self.assertEqual([r['id'] for r in rows],['opencode','gemini']);probe.assert_not_called()
  self.assertTrue(all(r['manual'] and not r['available'] for r in rows))
  self.assertNotIn('已是最新','\n'.join(self.m.app_update_lines({})))
 def test_selection_changed_in_flight_cannot_publish_a_fresh_wrong_scope(self):
  self.select('claude')
  def change_while_loading(key):
   self.select('codex');return self.row()
  with patch.object(self.m,'app_update_probe',side_effect=change_while_loading):self.m.app_updates_cached()
  self.assertEqual(self.m.read_cache('app_updates'),{})
  with patch.object(self.m,'app_update_probe',return_value=dict(self.row(),id='chatgpt')) as probe:self.m.app_updates_cached()
  self.assertCountEqual([c.args[0] for c in probe.call_args_list],['chatgpt','codex-cli'])
 def test_cli_release_sources_and_missing_install(self):
  cases=[('claude-code','2.1.308 (Claude Code)','2.1.310','claude.ai/claude-code-releases/latest'),('codex-cli','codex-cli 0.164.0','0.166.0','registry.npmjs.org/@openai/codex/latest')]
  for key,current,latest,url in cases:
   body=latest.encode() if key=='claude-code' else json.dumps({'version':latest}).encode()
   with patch.object(self.m.shutil,'which',return_value='/test/bin/tool'),patch.object(self.m.subprocess,'run',return_value=types.SimpleNamespace(stdout=current)),patch.object(self.m,'release_body',return_value=body) as release,patch.object(self.m.update_channels,'codex_channel',return_value={'channel':'npm','channelId':'npm','releaseURL':'https://registry.npmjs.org/@openai/codex/latest'}):
    row=self.m.app_update_probe(key)
   self.assertTrue(row['available']);self.assertEqual(row['latest'],latest);self.assertIn(url,release.call_args.args[0])
  with patch.object(self.m.shutil,'which',return_value=None),patch.object(self.m,'release_body') as release:
   self.assertEqual(self.m.app_update_probe('codex-cli')['status'],'未安装');release.assert_not_called()
 def test_brew_current_version_never_uses_npm_ahead_of_its_channel(self):
  channel={'channel':'Homebrew Cask','channelId':'brew-cask','releaseURL':'https://formulae.brew.sh/api/cask/codex.json'}
  with patch.object(self.m.shutil,'which',return_value='/test/bin/codex'),patch.object(self.m.subprocess,'run',return_value=types.SimpleNamespace(stdout='codex-cli 0.166.0')),patch.object(self.m.update_channels,'codex_channel',return_value=channel),patch.object(self.m,'release_body',return_value=b'{"version":"0.166.0"}') as release:
   row=self.m.app_update_probe('codex-cli')
  release.assert_called_once_with(channel['releaseURL'])
  self.assertEqual(row['channel'],'Homebrew Cask');self.assertFalse(row['available']);self.assertEqual(row['latest'],'0.166.0')
 def test_cli_update_runs_the_requested_command_with_safe_quoting(self):
  self.select('claude','codex')
  for key,command in [('claude-code','claude'),('codex-cli','codex')]:
   binary='/Applications/Tools With Spaces/'+command
   with patch.object(self.m.shutil,'which',return_value=binary),patch.object(self.m.subprocess,'run',return_value=types.SimpleNamespace(stdout='  update Update the CLI')),patch.object(self.m,'terminal') as terminal:
    self.m.run_action('update-cli',[key])
   self.assertIn("'"+binary+"' update 2>&1",terminal.call_args.args[0])
   self.assertIn('swiftbar://refreshplugin?',terminal.call_args.args[0])
   self.assertIn('token_update_status=${PIPESTATUS[0]}',terminal.call_args.args[0])
   self.assertIn('更新成功',terminal.call_args.args[0]);self.assertIn('更新失败',terminal.call_args.args[0])
 def test_cli_update_refuses_unselected_or_unsupported_command(self):
  self.select('claude')
  with patch.object(self.m,'terminal') as terminal:
   with self.assertRaises(ValueError):self.m.run_action('update-cli',['codex-cli'])
   with patch.object(self.m.shutil,'which',return_value='/test/claude'),patch.object(self.m.subprocess,'run',return_value=types.SimpleNamespace(stdout='  chat Start chat')),patch.object(self.m,'applescript'):
    self.m.run_action('update-cli',['claude-code'])
   terminal.assert_not_called()
 def test_cli_install_change_invalidates_update_cache(self):
  self.select('codex')
  binary=Path(self.tmp.name,'codex');binary.write_text('old')
  with patch.object(self.m.shutil,'which',return_value=str(binary)):
   before=self.m.connection_fingerprint('app_updates');binary.write_text('new installed release')
   self.assertNotEqual(before,self.m.connection_fingerprint('app_updates'))
if __name__=='__main__':unittest.main()
