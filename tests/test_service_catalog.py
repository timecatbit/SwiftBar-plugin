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
        code=(ROOT/'lib/swiftbar_plugin.py').read_text()
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
        self.assertEqual(value['visible'],['summary','chatgpt','claude']);self.assertNotIn('chatgptSource',value)
        self.assertEqual(value['paths'],original['paths']);self.assertEqual(value['expandedProviders'],['claude'])
        self.assertEqual(target.read_bytes(),before) # Reading migration never rewrites user files.
        preferences.update(path,'module','kimi-api','true')
        self.assertEqual(set(preferences.read(path)['visible']),{'summary','chatgpt','claude','kimi-api'})
    def test_both_legacy_quotas_merge_once(self):
        path=Path(self.m.STATE_DIR);path.mkdir()
        (path/'preferences.json').write_text(json.dumps({'schema':1,'visible':['codex-quota','chatgpt']}))
        self.assertEqual(preferences.read(path)['visible'],['chatgpt'])
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
    def test_chatgpt_subscription_source_follows_opencodex_selection(self):
        with patch.object(self.m,'ocx_configured',return_value=True):
            preferences.update(self.m.STATE_DIR,'module','opencodex','true')
            self.assertEqual(self.m.chatgpt_source(),'proxy');self.assertIn('opencodex',self.m.external_loaders())
            with patch.object(self.m,'invalidate_caches') as invalidate:
                self.m.refresh_resource('chatgpt');self.m.refresh_resource('chatgpt')
            invalidate.assert_called_once_with(['quota','accounts','active'])
            preferences.update(self.m.STATE_DIR,'module','opencodex','false')
            # Unchecked OpenCodex: local login is used and its management API is no longer polled.
            self.assertEqual(self.m.chatgpt_source(),'client');self.assertNotIn('opencodex',self.m.external_loaders())
        with patch.object(self.m,'ocx_configured',return_value=False):
            preferences.update(self.m.STATE_DIR,'module','opencodex','true')
            self.assertEqual(self.m.chatgpt_source(),'client')
        self.assertFalse(any('set-chatgpt-source' in json.dumps(entry) for entry in self.m.module_options()))
    def dialogs(self,*answers):
        replies=iter(types.SimpleNamespace(returncode=0 if a is not None else 1,stdout=a or '') for a in answers)
        return patch.object(self.m,'applescript',side_effect=lambda script:next(replies,types.SimpleNamespace(returncode=0,stdout='')))
    def test_typed_key_is_stored_privately_and_only_referenced(self):
        with self.dialogs('sk-PRIVATE-TYPED-KEY-123','国际站'),patch.object(self.m,'schedule_background_refresh'):
            self.m.run_action('enter-api-key',['kimi-api'])
        stored=Path(self.m.STATE_DIR)/'keys'/'moonshot_api_key.key'
        self.assertEqual(stored.read_text().strip(),'sk-PRIVATE-TYPED-KEY-123')
        self.assertEqual(stored.stat().st_mode&0o777,0o600);self.assertEqual(stored.parent.stat().st_mode&0o777,0o700)
        config=(Path(self.m.STATE_DIR)/'config.local.sh').read_text()
        self.assertIn(str(stored),config);self.assertNotIn('PRIVATE-TYPED',config);self.assertIn("MOONSHOT_REGION=international",config)
        self.assertTrue(self.m.module_enabled('kimi-api'));self.assertTrue(self.m.connection_ready('kimi-api'))
        self.assertNotIn('PRIVATE-TYPED',json.dumps(self.m.service_connection_entry('kimi-api')))
        with patch.object(self.m,'confirm',return_value=True),patch.object(self.m,'schedule_background_refresh'):
            self.m.run_action('clear-connection',['kimi-api'])
        self.assertFalse(stored.exists());self.assertFalse(self.m.connection_ready('kimi-api'))
    def test_cancelled_or_malformed_typed_key_writes_nothing(self):
        for answers in [(None,),('sk-PRIVATE-TYPED-KEY-123',None),('short key',)]:
            with self.dialogs(*answers),patch.object(self.m,'schedule_background_refresh'):
                self.m.configure_connection('kimi-api',typed=True)
        self.assertFalse((Path(self.m.STATE_DIR)/'keys').exists())
        self.assertFalse((Path(self.m.STATE_DIR)/'config.local.sh').exists());self.assertFalse((Path(self.m.STATE_DIR)/'preferences.json').exists())
    def test_choosing_a_key_file_removes_the_previously_typed_copy_but_never_user_files(self):
        chosen=self.root/'my-openai-key';chosen.write_text('sk-USER-OWNED-FILE')
        with self.dialogs('sk-PRIVATE-TYPED-KEY-123'),patch.object(self.m,'schedule_background_refresh'):
            self.m.configure_connection('chatgpt-api',typed=True)
        typed=Path(self.m.STATE_DIR)/'keys'/'openai_api_key.key';self.assertTrue(typed.exists())
        with self.dialogs(str(chosen)),patch.object(self.m,'schedule_background_refresh'):
            self.m.configure_connection('chatgpt-api')
        self.assertFalse(typed.exists());self.assertEqual(self.m.accounts.credential('OPENAI_API_KEY'),'sk-USER-OWNED-FILE')
        with patch.object(self.m,'confirm',return_value=True),patch.object(self.m,'schedule_background_refresh'):
            self.m.configure_connection('chatgpt-api',clear=True)
        self.assertTrue(chosen.exists())
    def test_key_check_is_explicit_and_forgotten_when_the_key_changes(self):
        preferences.update(self.m.STATE_DIR,'module','claude-api','true')
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'sk-ant-PRIVATE-ONE'}):
            with patch.object(self.m.accounts,'check_key',side_effect=AssertionError('rendering must not test keys')):
                rows=self.m.resource_panel_entries({})
            entry=next(e for e in rows if e['label']=='Claude API')
            test=next(c for c in entry['children'] if c['label']=='测试 Key')
            self.assertEqual(test['action'],['test-api-key','claude-api']);self.assertEqual(test['value'],'尚未测试')
            with patch.object(self.m.accounts,'check_key',return_value={'valid':True,'state':'Key 有效'}) as check:
                self.m.run_action('test-api-key',['claude-api'])
            check.assert_called_once_with('claude-api','sk-ant-PRIVATE-ONE')
            self.assertEqual(self.m.key_check('claude-api')['state'],'Key 有效')
            self.assertNotIn('PRIVATE',(Path(self.m.CACHE_DIR)/'key-checks.json').read_text())
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'sk-ant-PRIVATE-TWO'}):
            self.assertIsNone(self.m.key_check('claude-api'))
        with self.assertRaises(ValueError):self.m.test_api_key('minimax-api')
    def test_kimi_balance_row_shows_currency_and_breakdown(self):
        preferences.update(self.m.STATE_DIR,'module','kimi-api','true')
        with patch.dict(os.environ,{'MOONSHOT_API_KEY':'sk-PRIVATE'}):
            self.assertIn('kimi-api',self.m.external_loaders())
            rows=self.m.resource_panel_entries({'kimi-api':{'balance':49.5,'cash':-0.5,'voucher':50,'currency':'CNY','state':'已同步'}})
        entry=next(e for e in rows if e['label']=='Kimi API')
        self.assertEqual(entry['value'],'¥49.50')
        self.assertEqual([(c['label'],c.get('value')) for c in entry['children'] if c['label'] in ('现金余额','代金券余额')],[('现金余额','¥-0.50'),('代金券余额','¥50.00')])
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
