import json,os,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
SOURCE=Path(__file__).resolve().parents[1]/'opencodex.30s.sh'
CODE=(SOURCE.parent/'lib/swiftbar_plugin.py').read_text()

class AutomaticUpdateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  env=patch.dict(os.environ,{'OCX_CACHE_DIR':self.tmp.name,'SWIFTBAR_PLUGIN_DATA_PATH':self.tmp.name,'OCX_PLUGIN_PATH':str(SOURCE.resolve())});env.start();self.addCleanup(env.stop)
  self.m=types.ModuleType('automatic_update');exec(compile(CODE,str(SOURCE.parent/'lib/swiftbar_plugin.py'),'exec'),self.m.__dict__)
  self.badge={'currentVersion':'2.97.0','latestVersion':'2.98.0','updateAvailable':True,'canUpdate':True}
  self.cache();self.calls=[];self.current='2.97.0';self.job={};self.post_error=None
  probe=patch.object(self.m,'request',side_effect=self.request);probe.start();self.addCleanup(probe.stop)
  notification=patch.object(self.m,'notify');self.notice=notification.start();self.addCleanup(notification.stop)
 def cache(self,age=0):
  self.m.write_json_cache(self.m.cache_path('badge'),{'schema':1,'payload':self.badge,'fetchedAt':time.time()-age})
 def request(self,route,**kwargs):
  self.calls.append((route,kwargs))
  if route=='/healthz':return {'version':self.current},None
  if route.startswith('/api/update/status'):return ({'job':self.job},None) if self.job else (None,(404,'no job',None))
  if route=='/api/update/run':
   # Durable intent must already exist before calling the installer.
   self.assertEqual(self.m.auto_update_state()['status'],'running')
   if self.post_error:return None,self.post_error
   self.job={'id':'job-1','latestVersion':'2.98.0','status':'running'}
   return {'job':self.job},None
  self.fail('Unexpected API '+route)
 def posts(self):return [kw for route,kw in self.calls if route=='/api/update/run']
 def test_install_is_stable_channel_and_never_submitted_twice(self):
  self.m.auto_update_opencodex();self.m.auto_update_opencodex()
  self.assertEqual(len(self.posts()),1);self.assertEqual(self.posts()[0]['body'],{'tag':'latest','restart':True})
 def test_timeout_reconciles_without_repeating_install(self):
  self.post_error=(0,'timeout',None)
  self.m.auto_update_opencodex();self.m.auto_update_opencodex()
  self.assertEqual(len(self.posts()),1);self.assertEqual(self.m.auto_update_state()['status'],'running')
 def test_completed_job_requires_new_healthy_version(self):
  self.m.auto_update_opencodex();self.job['status']='succeeded';self.m.auto_update_opencodex()
  self.assertEqual(self.m.auto_update_state()['status'],'running');self.notice.assert_not_called()
  self.current='2.98.0';self.m.auto_update_opencodex();self.m.auto_update_opencodex()
  self.assertEqual(self.m.auto_update_state()['status'],'succeeded');self.notice.assert_called_once()
 def test_failure_backs_off_and_only_notifies_once(self):
  self.m.auto_update_opencodex();self.job['status']='failed';self.m.auto_update_opencodex();self.m.auto_update_opencodex()
  self.assertEqual(self.m.auto_update_state()['status'],'failed');self.assertEqual(len(self.posts()),1);self.notice.assert_called_once()
 def test_existing_installer_is_adopted(self):
  self.job={'id':'external-job','latestVersion':'2.98.0','status':'restarting'}
  self.m.auto_update_opencodex();self.assertEqual(self.posts(),[])
  self.assertEqual(self.m.auto_update_state()['jobId'],'external-job')
 def test_stale_checks_and_current_version_do_not_install(self):
  self.cache(age=7200);self.m.auto_update_opencodex();self.assertEqual(self.calls,[])
  self.cache();self.current='2.98.0';self.m.auto_update_opencodex();self.assertEqual(self.posts(),[])
 def test_unsupported_installer_has_visible_attention(self):
  self.badge['canUpdate']=False;self.cache();self.m.auto_update_opencodex()
  self.assertEqual(self.posts(),[]);self.assertEqual(self.m.auto_update_state()['status'],'blocked')
  row=self.m.update_rows({})[0];self.assertTrue(row['needsAttention']);self.assertEqual(self.m.update_attention_count([row]),1)
 def test_other_apps_only_notify_and_count_excludes_automatic_update(self):
  rows=[{'id':'opencodex','automatic':True,'available':True},{'id':'claude','available':True},{'id':'chatgpt','available':True}]
  self.assertEqual(self.m.update_attention_count(rows),2)
  with patch.object(self.m,'send_update_notification') as send:
   self.m.notify_app_updates([dict(rows[0],latest='2.98.0',checkedAt=time.time())]);send.assert_not_called()
 def test_failed_state_persistence_prevents_install(self):
  with patch.object(self.m,"write_json_cache"):
   self.m.auto_update_opencodex()
  self.assertEqual(self.posts(),[])
 def test_native_colors_follow_system_even_for_submenus(self):
  value=self.m.native_menu_line('应用更新 | color="#111,#ddd" sfcolor=blue badge="3 项待更新" panelattention=true')
  self.assertNotIn('color=',value);self.assertNotIn('panelattention',value);self.assertIn('badge=',value)

 def test_deselected_opencodex_does_not_start_or_check_update(self):
  self.m.preferences.update(self.m.STATE_DIR,'module','opencodex','false')
  self.m.auto_update_opencodex()
  self.assertEqual(self.calls,[]);self.assertNotIn('badge',self.m.external_loaders())
 def test_deselected_running_update_reconciles_without_reinstall_or_notification(self):
  self.m.auto_update_opencodex()
  self.m.preferences.update(self.m.STATE_DIR,'module','opencodex','false')
  self.current='2.98.0';self.job['status']='succeeded';self.m.auto_update_opencodex()
  self.assertEqual(len(self.posts()),1);self.notice.assert_not_called()
  self.assertEqual(self.m.auto_update_state()['status'],'succeeded')

if __name__=='__main__':unittest.main()
