import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
import swiftbar_config as config
import swiftbar_discovery as discovery

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def test_existing_comment_only_user_file_wins_over_legacy(self):
        state=self.root/'state';state.mkdir();target=state/'config.local.sh';target.write_text('# examples only\n')
        legacy=self.root/'.opencodex-panel/config.local.sh';legacy.parent.mkdir();legacy.write_text('export KOMARI_BASE_URL=https://old.invalid\n')
        config.migrate_config(self.root,state)
        self.assertEqual(target.read_text(),'# examples only\n');self.assertFalse(legacy.exists())
    def test_legacy_migrates_once_and_not_from_checkout(self):
        legacy=self.root/'.opencodex-panel/config.local.sh';legacy.parent.mkdir();legacy.write_text('export KOMARI_BASE_URL=https://monitor.invalid\n')
        config.migrate_config(self.root,self.root/'state')
        target=self.root/'state/config.local.sh'
        self.assertEqual(target.stat().st_mode&0o777,0o600)
        with self.assertRaises(ValueError):config.migrate_config(self.root,self.root/'state',target)
        config.migrate_config(self.root,self.root/'state');self.assertIn('monitor.invalid',target.read_text())
    def test_overrides_preserve_unrelated_settings_and_shell_quote_paths(self):
        marker=self.root/'must-not-exist';filename=str(self.root/('key $(touch '+str(marker)+')'))
        target=config.ensure_file(self.root);target.write_text('export OCX_TIMEZONE=UTC\nexport KOMARI_BASE_URL=https://old.invalid\n')
        config.write_overrides(self.root,{'DEEPSEEK_API_KEY_FILE':filename,'KOMARI_BASE_URL':''})
        out=subprocess.run(['/bin/bash','-c','source "$1"; printf "%s\\n%s\\n%s" "$OCX_TIMEZONE" "$KOMARI_BASE_URL" "$DEEPSEEK_API_KEY_FILE"','test',str(target)],capture_output=True,text=True,check=True)
        self.assertEqual(out.stdout,'UTC\n\n'+filename);self.assertFalse(marker.exists())
        self.assertEqual(target.stat().st_mode&0o777,0o600)
        config.write_overrides(self.root,{'KOMARI_BASE_URL':'https://new.invalid'})
        self.assertEqual(target.read_text().count('export KOMARI_BASE_URL=') ,2) # preserved advanced + one managed override
    def test_placeholder_or_malformed_monitor_is_not_detected(self):
        for url in ('','https://your-komari.example','example.com','file:///tmp/a','https://user:password@host','https://host/?token=secret','https://host:bad'):
            self.assertEqual(config.monitor_url(url),'')
            self.assertNotIn('komari',discovery.detect({},self.root,komari_url=url,which=lambda _:None))
        self.assertEqual(config.monitor_url(' http://localhost:25774/ '),'http://localhost:25774')
    def test_rejects_unknown_or_multiline_settings_without_writing(self):
        for values in ({'PATH':'/tmp'}, {'KOMARI_BASE_URL':'https://a\ncommand'}):
            with self.assertRaises(ValueError):config.write_overrides(self.root,values)
        self.assertFalse((self.root/'config.local.sh').exists())

class PowerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'OCX_CACHE_DIR':self.temp.name,'OCX_STATE_DIR':self.temp.name+'/state','OCX_PLUGIN_PATH':str(ROOT/'opencodex.30s.sh'),'OS_APPEARANCE':'Light'})
        env.start();self.addCleanup(env.stop)
        self.m=types.ModuleType('power_test')
        code=(ROOT/'opencodex.30s.sh').read_text().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        exec(compile(code,'plugin','exec'),self.m.__dict__)
        self.write('power-state',{'battery':False,'checkedAt':self.m.time.time()})
    def write(self,name,value):self.m.write_json_cache(self.m.cache_path(name),dict(schema=1,**value) if "schema" not in value else value)
    def test_closed_visible_battery_and_dead_helper_cadence(self):
        self.assertEqual(self.m.refresh_ttl(30),180)
        self.write('power-state',{'battery':True,'checkedAt':self.m.time.time()})
        self.assertEqual(self.m.refresh_ttl(30),300)
        self.write('panel-state',{'visible':True,'pid':os.getpid()})
        self.assertEqual(self.m.refresh_ttl(30),30)
        self.assertEqual(self.m.refresh_ttl(21600),21600)
        with patch.object(self.m.os,'kill',side_effect=ProcessLookupError):self.assertEqual(self.m.refresh_ttl(30),300)
    def test_unchanged_snapshot_is_not_republished(self):
        self.write('panel-view',{'schema':1,'entries':[]});path=Path(self.m.cache_path('panel-view'));before=path.stat().st_mtime_ns
        self.write('panel-view',{'schema':1,'entries':[]});self.assertEqual(before,path.stat().st_mtime_ns)
    def test_configuration_switch_invalidates_only_resource_without_moving_ipc(self):
        self.m.sync_connection_cache();cache=self.m.CACHE_DIR
        self.write('komari',{'payload':{'servers':['old']}});self.write('minimax',{'payload':{'balance':2}})
        with patch.dict(os.environ,{'KOMARI_BASE_URL':'https://other.invalid'}):self.m.sync_connection_cache()
        self.assertFalse(Path(self.m.cache_path('komari')).exists());self.assertTrue(Path(self.m.cache_path('minimax')).exists());self.assertEqual(cache,self.m.CACHE_DIR)
    def test_cancel_connection_never_writes_or_changes_selection(self):
        for key in ('komari','grok','minimax','deepseek'):
            with patch.object(self.m,'applescript',return_value=types.SimpleNamespace(returncode=1,stdout='')),patch.object(self.m.connections,'write_overrides') as write,patch.object(self.m.preferences,'update') as prefs:
                self.m.configure_connection(key);write.assert_not_called();prefs.assert_not_called()
    def test_cancel_second_grok_prompt_does_not_save_partial_key(self):
        key=Path(self.temp.name)/'key';key.write_text('test-key')
        responses=[types.SimpleNamespace(returncode=0,stdout=str(key)),types.SimpleNamespace(returncode=1,stdout='')]
        with patch.object(self.m,'applescript',side_effect=responses),patch.object(self.m.connections,'write_overrides') as write:
            self.m.configure_connection('grok');write.assert_not_called()
    def test_cached_foreground_does_not_repeat_local_network_calls(self):
        with patch.object(self.m,'ocx_configured',return_value=True),patch.object(self.m,'schedule_background_refresh'),patch.object(self.m,'request',return_value=({'status':'ready'},None)) as request:
            self.m.gather();count=request.call_count;self.m.gather()
        self.assertGreater(count,0);self.assertEqual(request.call_count,count)
    def test_range_collection_never_requests_a_second_host_refresh(self):
        with patch.object(self.m,'cached_fetch',return_value=({},None)),patch.object(self.m.subprocess,'run') as run:
            self.m.range_usage_cached();run.assert_not_called()
    def test_unconfigured_komari_does_not_schedule_network_polling(self):
        self.m.KOMARI_BASE_URL=''
        self.assertNotIn('komari',self.m.external_loaders())

    def test_delayed_response_from_previous_connection_is_not_displayed(self):
        with patch.dict(os.environ,{'KOMARI_BASE_URL':'https://old.invalid'}):
            self.m.cached_fetch('komari',lambda:({'servers':['old']},None),30)
        with patch.dict(os.environ,{'KOMARI_BASE_URL':'https://new.invalid'}):
            self.assertEqual(self.m.read_cache('komari'),{})

    def test_connection_rows_use_explicit_status_labels(self):
        with patch.object(self.m,'detected_modules',return_value=['claude']),patch.object(self.m,'connection_ready',return_value=False),patch.object(self.m,'chatgpt_configured',return_value=False):
            rows=self.m.connection_options()
        for row in rows:
            if row.get('detail'):self.assertIn(row['detail'],('已配置','未配置'))
        by_name={r['label']:r for r in rows}
        self.assertEqual(by_name['Claude Code']['detail'],'已配置')
        self.assertEqual(by_name['Komari 监控']['detail'],'未配置')
        self.assertEqual(by_name['DeepSeek API']['detail'],'未配置')
    def test_deepseek_requires_actual_key_and_official_connection(self):
        self.m.CONFIG_FILE=str(Path(self.temp.name)/'proxy-config.json')
        for provider,expected in [({},False),({'baseUrl':'https://api.deepseek.com','apiKey':'example-key'},True),({'baseUrl':'https://third-party.invalid','apiKey':'example-key'},False)]:
            Path(self.m.CONFIG_FILE).write_text(json.dumps({'providers':{'deepseek':provider}}))
            self.assertEqual(self.m.connection_ready('deepseek'),expected)
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY_FILE':'/missing/explicit/key'}):self.assertFalse(self.m.connection_ready('deepseek'))

    def test_configured_source_shows_selected_directory_and_finder_action(self):
        folder=Path(self.temp.name)/'custom projects';folder.mkdir()
        self.m.preferences.update(self.m.STATE_DIR,'path','claude',str(folder))
        with patch.object(self.m,'detected_modules',return_value=[]):
            row=next(r for r in self.m.connection_options() if r['label']=='Claude Code')
        self.assertEqual(row['detail'],'已配置')
        self.assertTrue(any(c.get('detail')==str(folder.resolve()) for c in row['children']))
        self.assertTrue(any(c.get('action')==['reveal-source','claude'] for c in row['children']))
    def test_workbuddy_locations_show_actual_project_roots_not_home(self):
        root=Path(self.temp.name);expected=[str(root/n/'projects') for n in ('.workbuddy-ai','.workbuddy')]
        for folder in expected:Path(folder).mkdir(parents=True)
        with patch.object(self.m,'source_path',return_value=str(root)):
            self.assertEqual(self.m.source_locations('workbuddy'),expected)
    def test_key_file_path_is_shown_without_credential_contents(self):
        path=Path(self.temp.name)/'provider.key';path.write_text('PRIVATE-TEST-KEY')
        with patch.dict(os.environ,{'DEEPSEEK_API_KEY_FILE':str(path)}),patch.object(self.m,'detected_modules',return_value=[]):
            row=next(r for r in self.m.connection_options() if r['label']=='DeepSeek API')
        text=json.dumps(row)
        self.assertIn(str(path),text);self.assertNotIn('PRIVATE-TEST-KEY',text)
