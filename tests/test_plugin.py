import json
import os
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch, Mock

SOURCE = Path(__file__).resolve().parents[1]/'opencodex.30s.sh'
CODE = SOURCE.read_text().split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'KOMARI_BASE_URL':'https://komari.example.test','OS_APPEARANCE':'Dark', 'OCX_CACHE_DIR':self.temp.name,
                                          'OCX_PLUGIN_PATH':str(SOURCE.resolve()), 'OCX_BASE_URL':'http://127.0.0.1:10100'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.m = types.ModuleType('plugin_test')
        exec(compile(CODE, str(SOURCE), 'exec'), self.m.__dict__)

    def record(self, name, payload, age=0):
        self.m.write_json_cache(self.m.cache_path(name), {
            'schema':1, 'payload':payload, 'fetchedAt':time.time()-age,
            'day':self.m.datetime.now().strftime('%Y-%m-%d')})

    def test_cache_hit_avoids_network(self):
        self.record('usage_today', {'summary':{'requests':12}})
        loader=Mock(side_effect=AssertionError('network used'))
        value,error=self.m.cached_fetch('usage_today',loader,60)
        self.assertEqual(value['summary']['requests'],12)
        self.assertIsNone(error)
        loader.assert_not_called()

    def test_error_keeps_last_good_usage_and_backs_off(self):
        self.record('usage_today', {'summary':{'requests':12}}, age=100)
        loader=Mock(return_value=({'error':'read_failed','summary':{'requests':0}},None))
        value,error=self.m.cached_fetch('usage_today',loader,60)
        self.assertEqual(value['summary']['requests'],12)
        self.assertTrue(value['_stale'])
        self.assertIsNotNone(error)
        self.m.cached_fetch('usage_today',loader,60)
        self.assertEqual(loader.call_count,1)

    def test_corrupt_cache_recovers(self):
        os.makedirs(self.m.CACHE_DIR)
        Path(self.m.cache_path('badge')).write_text('not json')
        value,error=self.m.cached_fetch('badge',lambda:({'latestVersion':'3.0'},None),100)
        self.assertEqual(value['latestVersion'],'3.0')

    def test_wrong_cache_shape_recovers(self):
        self.m.write_json_cache(self.m.cache_path('badge'),[])
        self.assertEqual(self.m.read_cache('badge'),{})

    def test_midnight_does_not_show_yesterday_as_today(self):
        self.record('usage_today', {'summary':{'requests':99}})
        r=self.m.read_cache('usage_today'); r['day']='2000-01-01'
        self.m.write_json_cache(self.m.cache_path('usage_today'),r)
        self.assertEqual(self.m.read_cache('usage_today'),{})

    def test_explicit_refresh_preserves_timestamp_and_invalidates(self):
        self.record('badge',{'latestVersion':'3.0'})
        before=self.m.read_cache('badge')['fetchedAt']
        self.m.invalidate_caches(['badge'])
        r=self.m.read_cache('badge')
        self.assertEqual(r['fetchedAt'],before)
        self.assertTrue(self.m.cache_due(r,1800))
        self.assertTrue(self.m.cache_result(r,1800)[0]['_stale'])

    def test_empty_provider_reports_cached(self):
        loader=Mock(return_value=({'reports':[]},None))
        self.m.cached_fetch('provider_quotas',loader,300)
        self.m.cached_fetch('provider_quotas',loader,300)
        self.assertEqual(loader.call_count,1)

    def test_positive_balance_skips_direct_request(self):
        report={'provider':'deepseek','quota':{'customWindows':[{'label':'¥2.00'}]}}
        with patch.object(self.m,'request',return_value=({'reports':[report]},None)), \
             patch.object(self.m,'deepseek_balance_direct') as direct:
            self.m.provider_quotas_cached()
            direct.assert_not_called()

    def test_negative_direct_balance_replaces_zero(self):
        def report(value):
            return {'reports':[{'provider':'deepseek','quota':{'customWindows':[{'label':value}]}}]}
        with patch.object(self.m,'request',return_value=(report('$0.00'),None)), \
             patch.object(self.m,'deepseek_balance_direct',return_value=report('$-0.12')):
            result,error=self.m.provider_quotas_cached()
        self.assertEqual(self.m.deepseek_balance({'provider_quotas':result})[1],-0.12)

    def deepseek_entry(self, payload, error=None):
        with patch.object(self.m,'module_enabled',side_effect=lambda key:key=='deepseek'), \
             patch.object(self.m,'connection_ready',return_value=True), \
             patch.object(self.m,'deepseek_logo_image',return_value=None):
            return self.m.panel_entries(self.m.resource_lines({'provider_quotas':payload,'provider_quotas_error':error}))[0]

    def test_deepseek_refresh_keeps_home_balance_stable_and_reports_status_in_flyout(self):
        payload={'reports':[{'provider':'deepseek','quota':{'customWindows':[{'label':'¥2.00'}]}}]}
        self.record('provider_quotas',payload)
        ttl=self.m.EXTERNAL_TTLS['provider_quotas']
        before=self.deepseek_entry(*self.m.cache_result(self.m.read_cache('provider_quotas'),ttl))
        self.m.invalidate_caches(['provider_quotas'])
        during=self.deepseek_entry(*self.m.cache_result(self.m.read_cache('provider_quotas'),ttl))
        self.assertEqual(before['value'],during['value']);self.assertEqual(during['value'],'¥2.00')
        state=next(row for row in during['children'] if row['label']=='余额更新')
        self.assertEqual(state['value'],'正在刷新')
        after=self.deepseek_entry(*self.m.cached_fetch('provider_quotas',lambda:(payload,None),ttl))
        self.assertEqual(after['value'],'¥2.00')
        self.assertEqual(next(row for row in after['children'] if row['label']=='余额更新')['value'],'刚刚更新')

    def test_deepseek_initial_loading_and_refresh_failure_remain_distinct(self):
        ttl=self.m.EXTERNAL_TTLS['provider_quotas']
        pending=self.deepseek_entry(*self.m.cache_result({},ttl))
        self.assertEqual(pending['value'],'正在读取')
        self.assertNotIn('失败',str(pending))
        self.record('provider_quotas',{'reports':[{'provider':'deepseek','quota':{'customWindows':[{'label':'¥2.00'}]}}]},age=3600)
        failed=self.deepseek_entry(*self.m.cached_fetch('provider_quotas',lambda:(None,(0,'timeout',None)),ttl))
        self.assertEqual(failed['value'],'¥2.00')
        state=next(row for row in failed['children'] if row['label']=='余额更新')
        self.assertEqual(state['value'],'刷新失败');self.assertIn('保留最近余额',state['detail'])
        self.assertNotIn('timeout',str(failed))

    def test_atomic_cache_is_private_and_complete(self):
        self.record('badge',{'latestVersion':'3.0'})
        p=Path(self.m.cache_path('badge'))
        self.assertEqual(p.stat().st_mode & 0o777,0o600)
        self.assertEqual(json.loads(p.read_text())['payload']['latestVersion'],'3.0')
        self.assertEqual(list(p.parent.glob('.cache-*')),[])

    def test_komari_live_render_and_expiry(self):
        payload={'_fetchedAt':time.time(),'statusAvailable':True,'servers':[
            {'uuid':'a','name':'online','online':True,'expired_at':'2027-06-01T00:00:00Z','cpu':12,'ram':50,'ram_total':100},
            {'uuid':'b','name':'offline','online':False,'expired_at':'2226-01-01T00:00:00Z'}]}
        lines='\n'.join(self.m.komari_lines({'komari':payload}))
        self.assertIn('1/2 在线',lines)
        self.assertIn('2027-06-01',lines)
        self.assertIn('长期',lines)
        self.assertIn('CPU 12%',lines)
        self.assertIn('/instance/a',lines)

    def test_stale_komari_not_all_offline(self):
        payload={'_stale':True,'statusAvailable':True,'servers':[{'uuid':'a','name':'A','online':True}]}
        lines='\n'.join(self.m.komari_lines({'komari':payload}))
        self.assertIn('状态待更新',lines)
        self.assertNotIn('0 在线',lines)
        self.assertIn('--? ',lines)

    def test_komari_failed_status_does_not_invent_offline(self):
        def request(path,body=None):
            if path=='/api/nodes': return {'data':[{'uuid':'a','name':'A'}]},None
            return None,(0,'timeout',None)
        with patch.object(self.m,'komari_public_json',side_effect=request):
            result=self.m.komari_snapshot_live()
        self.assertFalse(result['statusAvailable'])
        self.assertIsNone(result['servers'][0]['online'])

    def test_health_failure_precedes_update_badge(self):
        data={'healthz':{'version':'1.0'},'ready':{'status':'failed'},
              'badge':{'updateAvailable':True,'latestVersion':'2.0'}}
        self.assertIn('启动失败',self.m.title(data))
        data['healthz']=None
        self.assertIn('未连接',self.m.title(data))

    def test_usage_failure_never_rendered_as_zero(self):
        text=self.m.render({'healthz':{'version':'1.0'},'ready':{'status':'ready'},
                           'usage_today':{'error':'read_failed','summary':{'requests':0}}})
        self.assertIn('今日用量 · 暂不可用',text)
        self.assertNotIn('今日估算',text)

    def test_gather_does_not_call_remote_services(self):
        def request(path,**kwargs):
            if path=='/healthz': return {'version':'1.0'},None
            if path=='/readyz': return {'status':'ready'},None
            return {},None
        with patch.object(self.m,'request',side_effect=request), \
             patch.object(self.m,'schedule_background_refresh'), \
             patch.object(self.m,'komari_snapshot_live',side_effect=AssertionError('foreground remote')), \
             patch.object(self.m,'deepseek_balance_direct',side_effect=AssertionError('foreground remote')):
            self.assertTrue(self.m.gather()['healthz'])

    def test_callback_paths_with_spaces_are_quoted(self):
        self.m.PLUGIN='/tmp/test path/opencodex.30s.sh'
        out=self.m.item('刷新',**self.m.act('refresh'))
        self.assertIn('bash=/bin/bash',out)
        self.assertIn('param1="/tmp/test path/opencodex.30s.sh"',out)
        self.assertIn('param2=--action',out)
        self.assertIn('param3=refresh',out)
        self.assertNotIn('\n',out)

    def test_background_lock_prevents_duplicate_queries(self):
        os.makedirs(self.m.CACHE_DIR)
        with open(Path(self.m.CACHE_DIR)/'refresh.lock','a') as lock:
            self.m.fcntl.flock(lock,self.m.fcntl.LOCK_EX | self.m.fcntl.LOCK_NB)
            with patch.object(self.m,'komari_snapshot') as remote:
                self.assertEqual(self.m.background_refresh(),0)
                remote.assert_not_called()

    def test_due_but_recent_komari_keeps_online_visible(self):
        data={'komari':{'_fetchedAt':time.time()-35,'_stale':True,'statusAvailable':True,
                        'servers':[{'uuid':'a','name':'server-a','online':True}]}}
        lines=self.m.komari_lines(data)
        self.assertEqual(lines[0].split(' | ')[0],'Komari 监控 · 1/1 在线')
        self.assertIn('1/1 在线',lines[0])
        self.assertFalse(any(line.startswith('--Komari ·') for line in lines))
        self.assertTrue(any(line.startswith('--●') and '在线' in line for line in lines))

    def test_old_snapshot_does_not_claim_current_online(self):
        data={'komari':{'_fetchedAt':time.time()-91,'statusAvailable':True,
                        'servers':[{'uuid':'a','name':'server-a','online':True}]}}
        text='\n'.join(self.m.komari_lines(data))
        self.assertIn('状态待更新',text)
        self.assertNotIn('--●',text)

    def test_unknown_status_is_explicit(self):
        data={'komari':{'_fetchedAt':time.time(),'statusAvailable':True,
                        'servers':[{'uuid':'a','name':'server-a','online':None}]}}
        text='\n'.join(self.m.komari_lines(data))
        self.assertIn('1 未知',text)
        self.assertNotIn('全部在线',text)

    def test_no_old_monitor_endpoint(self):
        self.assertNotIn('nezha',CODE.lower())
        self.assertNotIn('哪吒',CODE)


    def test_new_menu_symbols_use_normalized_template_images(self):
        for symbol in ('arrow.down.circle','chart.bar.xaxis','menubar.rectangle','stop.circle'):
            row=self.m.item('Menu item',sfimage=symbol)
            self.assertIn('templateimage=',row)
            self.assertNotIn('sfimage=',row)

    def test_symbol_fallback_and_menu_bar_have_separate_sizes(self):
        row=self.m.item('Future symbol',sfimage='sun.max')
        self.assertIn('sfsize=13',row)
        title=self.m.item('',sfimage='sparkles',sfsize=18)
        self.assertIn('sfsize=18',title)

if __name__=='__main__':
    unittest.main(verbosity=2)
