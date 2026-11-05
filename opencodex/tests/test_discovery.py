import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import swiftbar_discovery as discovery
import swiftbar_preferences as preferences

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.home=Path(self.temp.name)
        env=patch.dict(os.environ,{},clear=True);env.start();self.addCleanup(env.stop)
    def put(self,name,body='not a conversation parser input'):
        p=self.home/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body);return p
    def detect(self,paths=None,**kw):return discovery.detect(paths or {},self.home,which=lambda _:None,**kw)
    def test_empty_folders_do_not_enable_unavailable_sources(self):
        for folder in ('.claude/projects','.codex/sessions','.gemini/tmp','.workbuddy-ai/projects'):(self.home/folder).mkdir(parents=True)
        self.assertEqual(self.detect(),['summary','updates'])
    def test_existing_harness_records_are_detected_without_parsing(self):
        self.put('.claude/projects/p/one.jsonl');self.put('.codex/sessions/day/one.jsonl')
        self.put('.workbuddy-ai/projects/p/one.jsonl');self.put('.gemini/tmp/p/chats/session-one.jsonl')
        self.put('.local/share/opencode/opencode.db')
        dsh=self.put('dsh/one/session.v4.jsonl.zstd')
        found=self.detect({'deepseek-harness':str(dsh.parent.parent)})
        for key in ('claude','codex','workbuddy','gemini','opencode','deepseek-harness'):self.assertIn(key,found)
        self.assertNotIn('grok',found)
    def test_configured_api_requirements_and_no_secret_persistence(self):
        key=self.put('key','PRIVATE-CREDENTIAL')
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY_FILE':str(key),'MINIMAX_API_KEY':'PRIVATE-MINIMAX','XAI_MANAGEMENT_API_KEY':'PRIVATE-XAI'}):
            found=self.detect();self.assertIn('deepseek',found);self.assertIn('minimax',found);self.assertNotIn('grok',found)
            with patch.dict(os.environ,{'XAI_TEAM_ID':'private-team'}):found=self.detect()
        self.assertIn('grok',found);discovery.initialize(self.home/'state',found)
        self.assertNotIn('PRIVATE', (self.home/'state/preferences.json').read_text())
    def test_proxy_and_komari_are_optional_and_third_party_key_not_reused(self):
        self.put('.opencodex/config.json',json.dumps({'providers':{'deepseek':{'baseUrl':'https://proxy.example','apiKey':'PRIVATE'}}}))
        found=self.detect(configured_proxy=True,komari_url='https://monitor.example')
        self.assertIn('opencodex',found);self.assertIn('codex-quota',found);self.assertIn('komari',found);self.assertNotIn('deepseek',found)
        self.put('.opencodex/config.json',json.dumps({'providers':{'deepseek':{'baseUrl':'https://api.deepseek.com','apiKey':'PRIVATE'}}}))
        self.assertIn('deepseek',self.detect())
    def test_chatgpt_login_is_not_inferred_from_inference_api_key(self):
        auth=self.put('.codex/auth.json',json.dumps({'auth_mode':'apikey','OPENAI_API_KEY':'PRIVATE'}))
        self.assertNotIn('chatgpt',discovery.detect({},self.home,which=lambda _:'/test/codex'))
        auth.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'PRIVATE'}}))
        self.assertIn('chatgpt',discovery.detect({},self.home,which=lambda _:'/test/codex'))
    def test_upgrade_preserves_explicitly_hidden_modules_and_appearance(self):
        state=self.home/'state';original={'schema':1,'visible':['summary'],'appearance':'solid','paths':{'claude':'/chosen/path'}}
        preferences.write(state,original);before=(state/'preferences.json').read_bytes()
        self.assertFalse(discovery.initialize(state,['summary','claude']))
        self.assertEqual((state/'preferences.json').read_bytes(),before)
        discovery.replace_selection(state,['claude'])
        after=preferences.read(state);self.assertEqual(after['visible'],['claude']);self.assertEqual(after['appearance'],'solid');self.assertEqual(after['paths'],original['paths'])
    def test_first_install_preferences_are_private_and_only_detected(self):
        state=self.home/'state';self.assertTrue(discovery.initialize(state,['summary','workbuddy','updates']))
        self.assertEqual(preferences.read(state)['visible'],['summary','workbuddy','updates'])
        self.assertEqual((state/'preferences.json').stat().st_mode&0o777,0o600)
    def test_installed_client_can_be_selected_before_first_session(self):
        app=self.home/'Applications/WorkBuddy.app';app.mkdir(parents=True)
        found=discovery.detect({},self.home,which=lambda name:'/test/gemini' if name=='gemini' else None,app_roots=[app.parent])
        self.assertIn('gemini',found);self.assertIn('workbuddy',found)
        self.assertNotIn('claude',found);self.assertNotIn('chatgpt',found)
