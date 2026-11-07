import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'lib'))
import swiftbar_qoder as qoder


def logged(at,usage,prefix='[INFO] [main] [Auth] [AccountUsage] 用量响应摘要 '):
    stamp=time.strftime('%Y-%m-%dT%H:%M:%S.000Z',time.gmtime(at))
    return '[%s] %s%s\n'%(stamp,prefix,json.dumps({'operation':'account.getQuotaUsage','email':'private@example.com','qoderUsage':usage}))


class QoderSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name);self.now=time.time()
        self.logs=self.home/'Library/Application Support/com.qoder.app.stable/logs'
        self.usage={'userType':'personal_standard','expiresAt':int((self.now+86400*20)*1000),'isQuotaExceeded':False,
                    'userQuota':{'total':2000,'used':1500,'remaining':500,'unit':'credits'},
                    'addOnQuota':{'total':1500,'used':300,'unit':'credits'}}
    def write(self,session,text,age=0):
        path=self.logs/session/'main.log';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        os.utime(path,(self.now-age,self.now-age));return path
    def test_newest_summary_keeps_only_credit_fields(self):
        older=dict(self.usage,userQuota={'total':2000,'used':100,'remaining':1900})
        self.write('s1','noise\n'+logged(self.now-3600,older)+'more noise\n',age=3600)
        self.write('s2',logged(self.now-120,self.usage)+'[x] unrelated {"qoderUsage": broken\n')
        value=qoder.snapshot(self.home,now=self.now)
        self.assertEqual(value['plan'],{'used':1500.0,'total':2000.0,'remaining':500.0})
        self.assertEqual(value['addOn'],{'used':300.0,'total':1500.0,'remaining':1200.0})
        self.assertAlmostEqual(value['resetsAt'],self.now+86400*20,delta=1)
        self.assertNotIn('private',json.dumps(value))
    def test_old_far_future_and_malformed_summaries(self):
        self.write('s1',logged(self.now-8*86400,self.usage))
        self.assertIsNone(qoder.snapshot(self.home,now=self.now))
        self.write('s2',logged(self.now,dict(self.usage,expiresAt=253402214400000,addOnQuota=None)))
        value=qoder.snapshot(self.home,now=self.now)
        self.assertIsNone(value['resetsAt']);self.assertIsNone(value['addOn'])
        for bad in ({'userQuota':{'total':'2000','used':1}},{'userQuota':{'total':-1,'used':1}},{'userQuota':{'total':True,'used':1}}):
            self.assertIsNone(qoder.summary(logged(self.now,bad).strip()))
        self.assertIsNone(qoder.summary(json.dumps({'qoderUsage':self.usage})))  # No log time, no snapshot.


class QoderPanelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        env=patch.dict(os.environ,{'OCX_STATE_DIR':str(self.root/'state'),'OCX_CACHE_DIR':str(self.root),'OCX_PLUGIN_PATH':str(ROOT/'token-monitor.30s.sh')})
        env.start();self.addCleanup(env.stop)
        self.m=types.ModuleType('qoder_test')
        exec(compile((ROOT/'lib/swiftbar_plugin.py').read_text(),'plugin','exec'),self.m.__dict__)
        app=patch.object(self.m,'installed_app_path',return_value=None);app.start();self.addCleanup(app.stop)
        self.now=time.time()
    def rows(self,payload):
        head=self.m.panel_entries(self.m.qoder_subscription_lines({'qoder_subscription':payload}))[0]
        return [head]+head['children']
    def test_fresh_snapshot_is_coloured_and_old_one_is_labelled(self):
        payload={'observedAt':self.now-60,'plan':{'used':1500,'total':2000,'remaining':500},'addOn':{'used':300,'total':1500,'remaining':1200},'resetsAt':self.now+86400}
        head,source,plan,extra,updated,*rest=self.rows(payload)
        self.assertEqual(head['value'],'已用 75%');self.assertEqual(head['usageLevel'],'warning')
        self.assertTrue(plan['detail'].startswith('1,500 / 2,000 · 剩余 500'));self.assertIn('重置于',plan['detail'])
        self.assertEqual(extra['value'],'已用 20%');self.assertEqual(updated['label'],'更新时间')
        old=self.rows(dict(payload,observedAt=self.now-7200))
        self.assertTrue(old[0]['value'].startswith('已用 75% · 截至 '));self.assertNotIn('usageLevel',old[0])
        self.assertIn('Credits 用量',old[4]['detail'])
    def test_no_snapshot_says_what_is_known(self):
        with patch.object(self.m,'connection_ready',return_value=False):
            self.assertEqual(self.rows({'empty':True})[0]['value'],'未发现 Qoder App')
        with patch.object(self.m,'connection_ready',return_value=True):
            rows=self.rows({'empty':True})
        self.assertEqual(rows[0]['value'],'暂无本机记录');self.assertIn('Credits 用量',rows[2]['label'])
        self.assertEqual(self.rows({'observedAt':self.now,'plan':{'used':0,'total':0,'remaining':0},'exceeded':True})[0]['value'],'额度已用完')


class QoderApiTests(unittest.TestCase):
    def test_shared_add_on_credits_sum_active_pages_only(self):
        import swiftbar_accounts as accounts
        pages={None:{'resourcePackages':[{'status':'active','remainingValue':1200.5},{'status':'expired','remainingValue':900}],'nextToken':'p2'},
               'p2':{'resourcePackages':[{'status':'ACTIVE','remainingValue':300}]}}
        seen=[]
        def fetch(url):
            seen.append(url);token=url.split('nextToken=')[1] if 'nextToken=' in url else None
            return pages[token]
        value=accounts.qoder_packages(fetch,'org/1')
        self.assertEqual(value,{'balance':1500.5,'currency':'Credits','packages':2,'state':'已同步'})
        self.assertTrue(seen[0].startswith('https://api.qoder.com/v1/organizations/org%2F1/resource-packages?status=active'))
        for bad in ({'resourcePackages':None},{'resourcePackages':[{'status':'active','remainingValue':'x'}]},{'resourcePackages':[{'status':'active','remainingValue':-1}]}):
            self.assertEqual(accounts.qoder_packages(lambda url:bad,'o')['state'],'余额格式待检查')
        with patch.dict(os.environ,{},clear=True):
            self.assertIn('组织 ID',accounts.account('qoder-api',key='k')['state'])
    def test_balance_reads_in_credits_with_the_shared_pool_explained(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        env=patch.dict(os.environ,{'OCX_STATE_DIR':str(root/'state'),'OCX_CACHE_DIR':str(root),'OCX_PLUGIN_PATH':str(ROOT/'token-monitor.30s.sh'),'QODER_API_KEY':'secret-key','QODER_ORG_ID':'org1'})
        env.start();self.addCleanup(env.stop)
        m=types.ModuleType('qoder_api_test');exec(compile((ROOT/'lib/swiftbar_plugin.py').read_text(),'plugin','exec'),m.__dict__)
        self.assertTrue(m.default_ready('qoder-api'))
        data={'qoder-api':{'balance':1500.5,'currency':'Credits','packages':2,'state':'已同步','_fetchedAt':time.time()}}
        head=m.panel_entries(m.api_lines('qoder-api',data))[0]
        self.assertEqual(head['value'],'余额 1,500 Credits')
        rows={r['label']:r for r in head['children'][0]['children']}
        self.assertEqual(rows['组织共享加购 Credits']['value'],'2 个有效资源包');self.assertEqual(rows['组织 ID']['value'],'org1')
        self.assertNotIn('secret-key',json.dumps(head,ensure_ascii=False))


if __name__=='__main__':
    unittest.main()
