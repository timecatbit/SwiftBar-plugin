import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
import swiftbar_catalog as catalog
import swiftbar_preferences as preferences
import swiftbar_discovery as discovery

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        env=patch.dict(os.environ,{'OCX_STATE_DIR':str(self.root/'state'),'OCX_CACHE_DIR':str(self.root),'OCX_PLUGIN_PATH':str(ROOT/'opencodex.30s.sh')})
        env.start();self.addCleanup(env.stop)
        self.m=types.ModuleType('catalog_test')
        code=(ROOT/'opencodex.30s.sh').read_text().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        exec(compile(code,'plugin','exec'),self.m.__dict__)
    def test_catalog_exact_order_and_independent_service_ids(self):
        self.assertEqual([s.brand for s in catalog.SERVICES if s.category=='订阅'],['ChatGPT','Claude','MiniMax','Gemini','Grok','Kimi'])
        self.assertEqual([s.brand for s in catalog.SERVICES if s.category=='API'],['ChatGPT','Claude','DeepSeek','MiniMax','Gemini','Grok','Kimi'])
        self.assertEqual(len(catalog.BY_KEY),13)
        self.assertNotIn('codex-quota',preferences.KNOWN)
        self.assertEqual(next(label for k,label,g in preferences.MODULES if k=='codex'),'ChatGPT 本机用量')
    def test_upgrade_retains_proxy_source_and_other_preferences(self):
        path=Path(self.m.STATE_DIR);path.mkdir()
        original={'schema':1,'visible':['summary','codex-quota','claude'],'appearance':'solid','expandedProviders':['claude'],'paths':{'claude':'/chosen/records'}}
        target=path/'preferences.json';target.write_text(json.dumps(original));before=target.read_bytes()
        value=preferences.read(path)
        self.assertEqual(value['visible'],['summary','chatgpt','claude']);self.assertEqual(value['chatgptSource'],'proxy')
        self.assertEqual(value['paths'],original['paths']);self.assertEqual(value['expandedProviders'],['claude'])
        self.assertEqual(target.read_bytes(),before) # Reading migration never rewrites user files.
        preferences.update(path,'module','kimi-api','true')
        self.assertEqual(preferences.read(path)['chatgptSource'],'proxy')
        self.assertEqual(self.m.chatgpt_source(),'proxy')
    def test_both_legacy_quotas_merge_once_and_keep_auto_choice(self):
        path=Path(self.m.STATE_DIR);path.mkdir()
        (path/'preferences.json').write_text(json.dumps({'schema':1,'visible':['codex-quota','chatgpt']}))
        value=preferences.read(path)
        self.assertEqual(value['visible'],['chatgpt']);self.assertEqual(value['chatgptSource'],'auto')
    def test_subscription_and_api_configuration_are_not_interchangeable(self):
        with patch.dict(os.environ,{'MINIMAX_API_KEY':'subscription-test','ANTHROPIC_API_KEY':'api-test','GEMINI_API_KEY':'api-test'}):
            self.assertTrue(self.m.connection_ready('minimax'))
            self.assertFalse(self.m.connection_ready('minimax-api'))
            self.assertFalse(self.m.connection_ready('claude-subscription'))
            self.assertFalse(self.m.connection_ready('gemini-subscription'))
            found=discovery.detect({},self.root,which=lambda _:None)
        self.assertIn('claude-api',found);self.assertIn('gemini-api',found)
        self.assertNotIn('claude-subscription',found);self.assertNotIn('gemini-subscription',found)
        self.assertNotIn('minimax-api',found)
    def test_manual_membership_mark_survives_restart_and_is_not_an_inference(self):
        self.m.run_action('set-subscription',['kimi-subscription','true'])
        self.assertTrue(self.m.connection_ready('kimi-subscription'))
        self.assertNotIn('kimi-subscription',preferences.read(self.m.STATE_DIR)['visible'])
        found=discovery.detect({},self.root,which=lambda _:None,configured_subscriptions=preferences.read(self.m.STATE_DIR)['configuredSubscriptions'])
        self.assertIn('kimi-subscription',found)
        text=json.dumps(self.m.service_connection_entry('kimi-subscription'),ensure_ascii=False)
        self.assertIn('preferences.json',text);self.assertIn('不验证套餐状态',text)
        self.m.run_action('set-subscription',['kimi-subscription','false'])
        self.assertFalse(self.m.connection_ready('kimi-subscription'))
    def test_portal_modules_do_not_request_or_fabricate_balance(self):
        for s in catalog.SERVICES:preferences.update(self.m.STATE_DIR,'module',s.key,'true')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'PRIVATE-KEY','ANTHROPIC_API_KEY':'PRIVATE-KEY','MINIMAX_PLATFORM_API_KEY':'PRIVATE-KEY','GEMINI_API_KEY':'PRIVATE-KEY','MOONSHOT_API_KEY':'PRIVATE-KEY'}),patch.object(self.m.accounts,'get_json') as network:
            rows=self.m.resource_panel_entries({})
            for key in catalog.PORTAL_APIS:
                entry=next(e for e in rows if e['label']==catalog.BY_KEY[key].label)
                self.assertEqual(entry['value'],'官网查看');self.assertNotIn('onOpenAction',entry)
                self.assertNotIn(key,self.m.external_loaders())
                self.assertNotIn('PRIVATE-KEY',json.dumps(self.m.service_connection_entry(key)))
            network.assert_not_called()
        self.assertEqual([e['label'] for e in rows if e.get('section')],['订阅用量','API 余额','其他'])
    def test_key_file_reference_is_private_and_shown_without_contents(self):
        key=self.root/'provider-key';key.write_text('SECRET-NEVER-DISPLAY')
        with patch.dict(os.environ,{'MOONSHOT_API_KEY_FILE':str(key)}):
            row=self.m.service_connection_entry('kimi-api')
            self.assertEqual(row['value'],'已配置');text=json.dumps(row)
            self.assertIn(str(key),text);self.assertNotIn('SECRET-NEVER-DISPLAY',text)
    def test_chatgpt_source_selector_does_not_enable_hidden_module(self):
        preferences.update(self.m.STATE_DIR,'module','chatgpt','false')
        with patch.object(self.m,'schedule_background_refresh'):
            self.m.run_action('set-chatgpt-source',['proxy'])
        self.assertEqual(self.m.chatgpt_source(),'proxy');self.assertFalse(self.m.module_enabled('chatgpt'))
        with patch.object(self.m,'invalidate_caches') as invalidate:
            preferences.update(self.m.STATE_DIR,'module','chatgpt','true')
            self.m.refresh_resource('chatgpt');self.m.refresh_resource('chatgpt')
        invalidate.assert_called_once_with(['quota','accounts','active'])
    def test_cancel_portal_key_configuration_leaves_preferences_untouched(self):
        for key in catalog.PORTAL_APIS:
            with patch.object(self.m,'applescript',return_value=types.SimpleNamespace(returncode=1,stdout='')),patch.object(self.m.connections,'write_overrides') as write:
                self.m.configure_connection(key);write.assert_not_called()
        self.assertFalse((Path(self.m.STATE_DIR)/'preferences.json').exists())
    def test_many_proxy_accounts_have_compact_home_badge_and_complete_details(self):
        data={'accounts':{'accounts':[{'id':str(i),'logLabel':'account-'+str(i)} for i in range(5)]}}
        with patch.object(self.m,'chatgpt_source',return_value='proxy'):
            rows=self.m.panel_entries(self.m.chatgpt_lines(data))
        self.assertEqual(rows[0]['value'],'5 个账户')
        for i in range(5):self.assertTrue(any('account-'+str(i) in e['label'] for e in rows[0]['children']))
