import json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import swiftbar_claude_local as local


class LocalUsageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.state=self.root/'state';self.settings=self.root/'claude/settings.json'
  self.now=time.time();self.data={'rate_limits':{'five_hour':{'used_percentage':72,'resets_at':self.now+300},'seven_day':{'used_percentage':93,'resets_at':self.now+86400}},'transcript_path':'private-dialogue','api_key':'never-store','session_id':'never-store'}
 def test_only_quota_fields_persist_with_private_permissions(self):
  with patch.object(local.subprocess,'run') as network:
   local.publish(self.state,self.data,now=self.now);network.assert_not_called()
  p=self.state/local.SNAPSHOT;value=json.loads(p.read_text())
  self.assertEqual([w['used'] for w in value['windows']],[72,93])
  self.assertNotIn('never-store',p.read_text());self.assertNotIn('private-dialogue',p.read_text())
  self.assertEqual(p.stat().st_mode&0o777,0o600)
 def test_missing_limits_clear_previous_account_data_without_inventing_zero(self):
  local.publish(self.state,self.data,now=self.now)
  local.publish(self.state,{},now=self.now+1)
  self.assertEqual(local.snapshot(self.state,now=self.now+1)['windows'],[])
 def test_stale_or_reset_windows_are_marked_old(self):
  local.publish(self.state,self.data,now=self.now)
  self.assertFalse(local.snapshot(self.state,now=self.now+2)['stale'])
  self.assertTrue(local.snapshot(self.state,now=self.now+301)['stale'])
 def test_invalid_fields_and_spend_limit_are_not_subscription_usage(self):
  for value in (True,-1,101,float('nan')):
   self.data['rate_limits']['five_hour']['used_percentage']=value
   self.assertEqual(len(local.normalized(self.data,self.now)['windows']),1)
  self.assertEqual(local.normalized({'rate_limits':{'spend_limit':{'used_percentage':88}}},self.now)['windows'],[])
 def test_identical_callbacks_are_throttled(self):
  local.publish(self.state,self.data,now=self.now)
  local.publish(self.state,self.data,now=self.now+1)
  self.assertEqual(local.snapshot(self.state,now=self.now+1)['updatedAt'],self.now)
 def test_repeated_empty_callbacks_do_not_refresh_swiftbar_in_a_loop(self):
  with patch.object(local.subprocess,'run') as refresh:
   local.publish(self.state,{},now=self.now,refresh=True)
   local.publish(self.state,{},now=self.now+1,refresh=True)
   refresh.assert_called_once()
 def test_malformed_cache_recovers_without_blocking_the_statusline(self):
  local.write(self.state/local.SNAPSHOT,{'updatedAt':'invalid'})
  self.assertEqual(len(local.publish(self.state,self.data,now=self.now)['windows']),2)
  local.write(self.state/local.SNAPSHOT,{'schema':1,'source':'claude-code','updatedAt':self.now,'windows':None})
  self.assertIsNone(local.snapshot(self.state,now=self.now))
 def test_setup_preserves_statusline_and_other_settings_and_can_restore(self):
  original={'type':'command','command':'printf original','padding':1}
  local.write(self.settings,{'statusLine':original,'unrelated':True})
  local.install(self.state,self.settings)
  self.assertTrue(local.enabled(self.state));self.assertTrue(local.read(self.settings)['unrelated'])
  self.assertEqual(local.read(self.state/local.BACKUP)['original'],original)
  local.install(self.state,self.settings)
  self.assertEqual(local.read(self.state/local.BACKUP)['original'],original)
  local.uninstall(self.state)
  self.assertEqual(local.read(self.settings),{'statusLine':original,'unrelated':True})
 def test_uninstall_never_overwrites_user_replacement(self):
  local.install(self.state,self.settings)
  replacement={'statusLine':{'type':'command','command':'printf replaced'}}
  local.write(self.settings,replacement);local.uninstall(self.state)
  self.assertEqual(local.read(self.settings),replacement)
 def test_bad_settings_are_not_overwritten(self):
  self.settings.parent.mkdir();self.settings.write_text('not json')
  with self.assertRaises(ValueError):local.install(self.state,self.settings)
  self.assertEqual(self.settings.read_text(),'not json')

if __name__=='__main__':unittest.main()
