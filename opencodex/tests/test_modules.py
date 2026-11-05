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
import swiftbar_preferences as preferences

class ModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'OCX_CACHE_DIR':self.temp.name,'OCX_STATE_DIR':self.temp.name+'/settings','OCX_PLUGIN_PATH':str(ROOT/'opencodex.30s.sh'),'OS_APPEARANCE':'Light'})
        env.start();self.addCleanup(env.stop)
        self.m=types.ModuleType('module_test')
        code=(ROOT/'opencodex.30s.sh').read_text().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        exec(compile(code,'plugin','exec'),self.m.__dict__)
    def toggle(self,key,value):
        return preferences.update(self.m.STATE_DIR,'module',key,'true' if value else 'false')
    def test_preferences_persist_privately_and_keep_unrelated_settings(self):
        self.toggle('komari',False)
        preferences.update(self.m.STATE_DIR,'appearance','solid')
        self.assertNotIn('komari',preferences.read(self.m.STATE_DIR)['visible'])
        self.assertEqual(preferences.read(self.m.STATE_DIR)['appearance'],'solid')
        self.assertEqual((Path(self.m.STATE_DIR)/'preferences.json').stat().st_mode & 0o777,0o600)
        preferences.update(self.m.STATE_DIR,'reset')
        self.assertIn('komari',preferences.read(self.m.STATE_DIR)['visible'])
    def test_unknown_or_malformed_preference_is_not_an_action(self):
        with self.assertRaises(ValueError):self.toggle('arbitrary-command',True)
        Path(self.m.STATE_DIR).mkdir(exist_ok=True)
        (Path(self.m.STATE_DIR)/'preferences.json').write_text('{broken')
        self.assertEqual(preferences.read(self.m.STATE_DIR)['visible'],preferences.DEFAULT_VISIBLE)
    def test_hide_resource_and_management_branches(self):
        for key in ('opencodex','codex-quota','deepseek','komari','updates'):self.toggle(key,False)
        lines='\n'.join(self.m.management_lines({}))
        for text in ('OpenCodex 管理','DeepSeek 余额','Codex 可用','Komari 监控','应用更新'):self.assertNotIn(text,lines)
        self.assertIn('刷新数据',lines);self.assertIn('SwiftBar 管理',lines)
    def test_usage_selection_changes_chart_and_cache_scope(self):
        old=self.m.range_cache_name()
        self.toggle('opencodex',False);self.toggle('codex',True)
        dashboard=self.m.dashboard_payload({'range_usage':{'range':'today','codex':{'summary':{'totalTokens':120,'requests':1}},'opencodex':{'summary':{'totalTokens':999,'requests':1}}}})
        self.assertEqual([p['id'] for p in dashboard['providers']],['claude','codex'])
        self.assertEqual(sum(p['tokens'] for p in dashboard['providers']),120)
        self.assertNotEqual(old,self.m.range_cache_name())
    def test_disabled_harness_is_not_read(self):
        for key in preferences.USAGE:self.toggle(key,False)
        with patch.object(self.m,'ocx_range_usage') as oc,patch.object(self.m,'claude_usage_live') as cc,patch.object(self.m.subprocess,'run'):
            value,error=self.m.range_usage_cached()
        oc.assert_not_called();cc.assert_not_called();self.assertIsNone(error)
        self.assertNotIn('opencodex',value)
    def test_new_sources_work_without_opencodex(self):
        for key in preferences.USAGE:self.toggle(key,key=='codex')
        with patch.object(self.m,'ocx_configured',return_value=False),patch.object(self.m.sources,'jsonl_usage',return_value={'summary':{'totalTokens':42,'requests':1}}) as local,patch.object(self.m.subprocess,'run'),patch.object(self.m,'request') as remote:
            bundle,error=self.m.range_usage_cached()
        self.assertEqual(bundle['codex']['summary']['totalTokens'],42)
        local.assert_called_once();remote.assert_not_called()
    def test_menu_has_checkmarks_and_restore_even_if_all_hidden(self):
        for key in preferences.KNOWN:self.toggle(key,False)
        choices=self.m.module_options()
        self.assertTrue(any(c.get('action')==['reset-modules'] for group in choices for c in [group]+group.get('children',[])))
        self.assertIn('主页模块','\n'.join(self.m.module_menu_lines()))
        self.assertFalse(any(c.get('checked') for c in choices if (c.get('action') or [''])[0]=='set-module'))
        self.assertEqual(self.m.dashboard_payload({})['providers'],[])
    def test_module_actions_use_existing_whitelist_and_receipt(self):
        self.m.write_json_cache(self.m.cache_path('panel-view'),{'schema':1,'entries':[],'moduleOptions':self.m.module_options()})
        self.m.write_json_cache(self.m.cache_path('panel-action'),{'schema':1,'id':'modules','action':['set-module','komari','false'],'createdAt':self.m.time.time()})
        with patch.object(self.m,'schedule_background_refresh'):self.m.consume_panel_action()
        self.assertFalse(self.m.module_enabled('komari'))
        self.assertEqual(self.m.read_cache('panel-action-receipt')['status'],'done')
    def test_standalone_deepseek_never_needs_proxy(self):
        direct={'reports':[{'provider':'deepseek'}]}
        with patch.object(self.m,'ocx_configured',return_value=False),patch.object(self.m,'deepseek_balance_direct',return_value=direct),patch.object(self.m,'request') as remote:
            value,error=self.m.provider_quotas_cached()
        self.assertEqual(value['reports'],direct['reports']);self.assertIsNone(error);remote.assert_not_called()

    def test_native_right_menu_only_has_module_management(self):
        app=Path(self.temp.name)/'Panel.app';app.mkdir()
        with patch.object(self.m,'PANEL_APP',str(app)):
            result=self.m.render({'healthz':{'version':'test'}})
        self.assertIn('主页模块…',result)
        self.assertIn('自动检测',result);self.assertIn('detect-modules',result)
        for label in ('DeepSeek 余额','OpenCodex 管理','Komari 监控','刷新数据'):self.assertNotIn(label,result)
    def test_native_manager_request_switches_existing_helper_mode(self):
        app=Path(self.temp.name)/'Panel.app';app.mkdir()
        with patch.object(self.m,'PANEL_APP',str(app)),patch.object(self.m.subprocess,'run'):
            self.m.run_action('panel-modules',[])
            self.assertEqual(self.m.read_cache('panel-open')['mode'],'modules')
            self.m.run_action('panel',[])
            self.assertEqual(self.m.read_cache('panel-open')['mode'],'home')
    def test_quick_second_toggle_is_whitelisted_but_unknown_module_is_not(self):
        snapshot={'schema':1,'entries':[],'moduleOptions':self.m.module_options()}
        self.m.write_json_cache(self.m.cache_path('panel-view'),snapshot)
        self.m.write_json_cache(self.m.cache_path('panel-action'),{'schema':1,'id':'quick','action':['set-module','komari','true'],'createdAt':self.m.time.time()})
        with patch.object(self.m,'schedule_background_refresh'):self.m.consume_panel_action()
        self.assertEqual(self.m.read_cache('panel-action-receipt')['status'],'done')
    def test_codex_details_do_not_double_summary_proxy(self):
        self.toggle('codex',True)
        bundle={'range':'today','opencodex':{'summary':{'totalTokens':100,'requests':1}},'codex':{'summary':{'totalTokens':100,'requests':1}}}
        providers=self.m.dashboard_payload({'range_usage':bundle})['providers']
        included=[p for p in providers if p['summaryIncluded']]
        self.assertEqual(sum(p['tokens'] for p in included),100)
        self.assertFalse(next(p for p in providers if p['id']=='codex')['summaryIncluded'])
    def test_explicit_deepseek_key_overrides_proxy_account(self):
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY_FILE':'/path/selected-by-user'}),patch.object(self.m,'ocx_configured',return_value=True),patch.object(self.m,'deepseek_balance_direct',return_value={'reports':[]}) as direct,patch.object(self.m,'request') as proxy:
            self.m.provider_quotas_cached()
        direct.assert_called_once();proxy.assert_not_called()
    def test_optional_account_resources_are_on_homepage(self):
        for key in ('grok','minimax'):self.toggle(key,True)
        lines='\n'.join(self.m.resource_lines({'grok':{'balance':12.3},'minimax':{'windows':[{'name':'text','remaining':65}]}}))
        self.assertIn('Grok API 余额',lines);self.assertIn('$12.30',lines);self.assertIn('65% 可用',lines)
        self.assertIn('grok',self.m.external_loaders());self.assertIn('minimax',self.m.external_loaders())
    def test_resource_open_forces_one_target_and_debounces(self):
        self.toggle('grok',True)
        loader=unittest.mock.Mock()
        with patch.object(self.m,'external_loaders',return_value={'grok':loader,'minimax':unittest.mock.Mock()}),patch.object(self.m,'invalidate_caches') as invalidate:
            self.m.refresh_resource('grok');self.m.refresh_resource('grok')
        loader.assert_called_once();invalidate.assert_called_once_with(['grok'])
        with self.assertRaises(ValueError):self.m.refresh_resource('minimax')
    def test_flyout_checks_use_visible_action_whitelist(self):
        self.toggle('grok',True)
        entries=self.m.resource_panel_entries({})
        grok=next(e for e in entries if e['label']=='Grok API 余额')
        self.assertEqual(grok['onOpenAction'],['refresh-source','grok'])
        self.m.write_json_cache(self.m.cache_path('panel-view'),{'schema':1,'entries':entries})
        self.m.write_json_cache(self.m.cache_path('panel-action'),{'id':'on-open','action':['refresh-source','grok'],'createdAt':self.m.time.time()})
        with patch.object(self.m,'refresh_resource') as refresh:self.m.consume_panel_action()
        refresh.assert_called_once_with('grok');self.assertEqual(self.m.read_cache('panel-action-receipt')['status'],'done')
    def test_enable_account_invalidates_recent_unconfigured_cache(self):
        with patch.object(self.m,'invalidate_caches') as invalidate,patch.object(self.m,'schedule_background_refresh') as schedule:
            self.m.run_action('set-module',['grok','true'])
        invalidate.assert_called_once_with(['grok']);schedule.assert_called_once()
    def test_background_completion_republishes_without_waiting_for_interval(self):
        name=self.m.range_cache_name()
        self.m.write_json_cache(self.m.cache_path(name),{'schema':1,'payload':{'range':'today'},'fetchedAt':self.m.time.time()})
        loader=unittest.mock.Mock()
        with patch.object(self.m,'external_loaders',return_value={'grok':loader}),patch.object(self.m,'ocx_configured',return_value=False),patch.object(self.m,'notify_app_updates'),patch.object(self.m,'refresh_swiftbar') as refresh:
            self.m.background_refresh()
        loader.assert_called_once();refresh.assert_called_once()
