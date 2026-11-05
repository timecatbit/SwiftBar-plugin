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
 def row(self,version='2.1.318'):
  return {'id':'claude-code','name':'Claude Code','latest':version,'current':'2.1.308','available':True,'checkedAt':time.time()}
 def test_numeric_versions_and_unknown_values(self):
  self.assertTrue(self.m.newer_release('4.16336.0','4.4212.0'))
  self.assertFalse(self.m.newer_release('2.1.99','2.1.308'))
  self.assertFalse(self.m.newer_release('garbage 999','2.1.308'))
  self.assertFalse(self.m.newer_release('2.1.318',None))
 def test_notifications_deduplicate_across_cache_refresh_and_restart(self):
  with patch.object(self.m,'send_update_notification',return_value=True) as send:
   self.m.notify_app_updates([self.row()]);self.m.notify_app_updates([self.row()])
   send.assert_called_once()
   self.m.notify_app_updates([self.row('2.1.319')]);self.assertEqual(send.call_count,2)
  state=json.loads(Path(self.tmp.name,'updates-notified.json').read_text())
  self.assertEqual(state['claude-code'],['2.1.318','2.1.319'])
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
 def test_sparkle_uses_build_and_filters_other_architecture(self):
  xml=b'''<rss xmlns:s="http://www.andymatuschak.org/xml-namespaces/sparkle"><channel><item><s:shortVersionString>26.1029.61003</s:shortVersionString><s:version>24614</s:version><s:hardwareRequirements>arm64</s:hardwareRequirements></item><item><s:shortVersionString>99.0.0</s:shortVersionString><s:version>99999</s:version><s:hardwareRequirements>x64</s:hardwareRequirements></item></channel></rss>'''
  with patch.object(self.m.platform,'machine',return_value='arm64'):
   self.assertEqual(self.m.sparkle_release(xml),('26.1029.61003','24614'))
 def test_installed_desktop_update_immediately_clears_old_alert(self):
  row=dict(self.row(),id='claude',latest='4.16336.0')
  with patch.object(self.m,'app_info',return_value={'CFBundleShortVersionString':'4.16336.0'}):
   rows=self.m.update_rows({'app_updates':{'apps':[row]}})
  self.assertFalse(next(r for r in rows if r['id']=='claude')['available'])
 def test_home_balances_are_visible_and_not_nested_under_management(self):
  data={'healthz':{'version':'2.97.0'},'provider_quotas':{'reports':[{'provider':'deepseek','quota':{'customWindows':[{'label':'¥229.61'}]}}]},'accounts':{'accounts':[{'id':'a','logLabel':'main'}]},'quota':{'quotas':{'a':{'weeklyPercent':76}}}}
  with patch.object(self.m,'deepseek_logo_image',return_value=None):
   entries=self.m.panel_entries(self.m.management_lines(data))
  self.assertIn('229.61',entries[0]['value']);self.assertIn('main 24%',entries[1]['value'])
  management=next(e for e in entries if e['label']=='OpenCodex 管理')
  self.assertFalse(any('DeepSeek' in e['label'] for e in management['children']))
if __name__=='__main__':unittest.main()
