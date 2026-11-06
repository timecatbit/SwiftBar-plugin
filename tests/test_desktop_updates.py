import json,plistlib,sqlite3,sys,tempfile,time,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import swiftbar_desktop_updates as desktop


class DesktopUpdateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.home=Path(self.tmp.name);self.root=self.home/'Library/Caches/com.openai.codex';self.root.mkdir(parents=True)
  self.parse=Mock(return_value=('26.1103.31037','25241'))
 def stage(self,bundle=desktop.BUNDLE,build='25241'):
  path=self.root/'org.sparkle-project.Sparkle/Installation/job/staged/ChatGPT.app/Contents/Info.plist';path.parent.mkdir(parents=True,exist_ok=True)
  path.write_bytes(plistlib.dumps({'CFBundleIdentifier':bundle,'CFBundleShortVersionString':'26.1103.31037','CFBundleVersion':build}))
 def cache(self,url='https://persistent.oaistatic.com/codex-app-prod/appcast-26.1103.31037.xml',on_disk=False,body=b'<rss/>',age=0):
  c=sqlite3.connect(self.root/'Cache.db')
  c.executescript('CREATE TABLE cfurl_cache_response(entry_ID INTEGER,request_key TEXT,time_stamp TEXT);CREATE TABLE cfurl_cache_receiver_data(entry_ID INTEGER,isDataOnFS INTEGER,receiver_data BLOB);')
  stamp=datetime.fromtimestamp(time.time()-age,timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
  c.execute('INSERT INTO cfurl_cache_response VALUES(1,?,?)',(url,stamp));c.execute('INSERT INTO cfurl_cache_receiver_data VALUES(1,?,?)',(on_disk,body));c.commit();c.close()
 def test_staged_native_update_is_found_without_network_or_credentials(self):
  self.stage();row=desktop.chatgpt_release(self.home,desktop.BUNDLE,self.parse)
  self.assertEqual((row['latest'],row['build'],row['releaseSource']),('26.1103.31037','25241','client-download'))
  self.assertNotIn(str(self.home),json.dumps(row));self.parse.assert_not_called()
 def test_wrong_bundle_and_invalid_version_are_not_updates(self):
  self.stage(bundle='another.app');self.assertIsNone(desktop.chatgpt_release(self.home,desktop.BUNDLE,self.parse))
  self.stage(build='not-a-version');self.assertIsNone(desktop.chatgpt_release(self.home,desktop.BUNDLE,self.parse))
 def test_appcast_on_disk_uses_only_official_cached_release(self):
  self.cache(on_disk=True,body=b'cache-file');folder=self.root/'fsCachedData';folder.mkdir();(folder/'cache-file').write_bytes(b'<rss/>')
  row=desktop.chatgpt_release(self.home,desktop.BUNDLE,self.parse)
  self.assertEqual(row['releaseSource'],'client-feed');self.parse.assert_called_once_with(b'<rss/>')
 def test_cache_path_traversal_is_rejected(self):
  self.cache(on_disk=True,body=b'../../private')
  self.assertIsNone(desktop.chatgpt_release(self.home,desktop.BUNDLE,self.parse));self.parse.assert_not_called()
 def test_unrelated_host_cannot_supply_a_release(self):
  self.cache(url='https://persistent.oaistatic.com.example.test/codex-app-prod/appcast-99.0.xml')
  self.assertIsNone(desktop.chatgpt_release(self.home,desktop.BUNDLE,self.parse));self.parse.assert_not_called()
 def test_old_or_corrupt_cache_does_not_claim_an_update(self):
  self.cache(age=8*86400)
  self.assertIsNone(desktop.chatgpt_release(self.home,desktop.BUNDLE,self.parse));self.parse.assert_not_called()
  (self.root/'Cache.db').write_bytes(b'corrupt')
  self.assertIsNone(desktop.chatgpt_release(self.home,desktop.BUNDLE,self.parse))

if __name__=='__main__':unittest.main()
