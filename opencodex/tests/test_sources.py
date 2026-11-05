import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import timezone

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import swiftbar_sources as sources

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'sessions';self.root.mkdir();self.cache=Path(self.temp.name)/'cache'
    def read(self,source='codex',exclude=False,start=0,end=9999999999):
        return sources.jsonl_usage(source,self.root,self.cache,start,end,timezone.utc,exclude)
    def write(self,path,rows):
        path.parent.mkdir(exist_ok=True,parents=True)
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    def codex(self,total=150,last=150,when=1730800000):
        def usage(n):return {'total_tokens':n,'input_tokens':n-10,'cached_input_tokens':40,'output_tokens':10,'reasoning_output_tokens':5}
        return {'type':'event_msg','timestamp':when,'payload':{'type':'token_count','info':{'total_token_usage':usage(total),'last_token_usage':usage(last)}}}
    def test_cumulative_repeats_copied_files_and_reasoning_are_not_double_counted(self):
        rows=[{'type':'session_meta','payload':{'id':'session','model_provider':'openai'}},{'type':'turn_context','payload':{'model':'model'}} ,self.codex(1000,150),self.codex(1000,150),self.codex(1150,150)]
        self.write(self.root/'one.jsonl',rows);self.write(self.root/'copy.jsonl',rows)
        result=self.read()
        self.assertEqual(result['summary']['totalTokens'],300)
        self.assertEqual(result['summary']['requests'],2)
        self.assertEqual(result['summary']['unpricedRequests'],2)
        for path in self.cache.glob('*.sqlite3'):
            self.assertNotIn(b'base_instructions',path.read_bytes())
    def test_partial_tail_is_retried_after_append(self):
        path=self.root/'one.jsonl';self.write(path,[self.codex()])
        partial=json.dumps(self.codex(300,150,1730803600))
        with path.open('a') as out:out.write(partial[:30])
        self.assertEqual(self.read()['summary']['requests'],1)
        with path.open('a') as out:out.write(partial[30:]+'\n')
        self.assertEqual(self.read()['summary']['requests'],2)
        self.assertEqual(self.read()['summary']['requests'],2)
    def test_missing_source_is_unavailable_not_zero(self):
        result=sources.jsonl_usage('codex',self.root/'missing',self.cache,0,9999999999,timezone.utc)
        self.assertIn('error',result);self.assertNotIn('summary',result)
    def test_proxy_records_can_be_excluded_from_combined_summary(self):
        self.write(self.root/'one.jsonl',[{'type':'session_meta','payload':{'id':'proxy','model_provider':'opencodex'}},self.codex()])
        result=self.read(exclude=True)
        self.assertEqual(result['summary']['totalTokens'],0);self.assertEqual(result['excludedProxyRequests'],1)
        self.assertEqual(self.read(exclude=False)['summary']['totalTokens'],150)
    def dsh(self,seq=2,inputs=80,kind='assistant/message'):
        return {'type':kind,'seq':seq,'time':1730800000000,'data':{'turn':1,'step':1,'message':{'model':'deepseek-flash','provider':'deepseek'},'usage':{'inputTokens':inputs,'outputTokens':10,'cacheReadTokens':20},'stream':[]}}
    def test_harness_uses_latest_generation_and_latest_settlement(self):
        header={'type':'session','id':'same','version':3,'isSeeded':False}
        self.write(self.root/'session.v2.jsonl',[dict(header,version=2),self.dsh(inputs=999)])
        self.write(self.root/'session.v3.jsonl',[header,self.dsh(),self.dsh(3,90)])
        result=self.read('deepseek-harness')
        self.assertEqual(result['summary']['totalTokens'],120);self.assertEqual(result['summary']['requests'],1)
    def test_harness_inherited_seed_and_failed_attempt_stream(self):
        failed=self.dsh(6,kind='assistant/attempt');failed['data'].pop('usage');failed['data']['stream']=[{'type':'chunk','time':1730800000000,'chunk':{'type':'usage','usage':{'inputTokens':25,'outputTokens':5}}}]
        rows=[{'type':'session','id':'fork','version':4,'isSeeded':True},self.dsh(),{'type':'session/end-seed','data':{'inherited':True}},self.dsh(),{'type':'llm/retry-started','data':{'turn':1,'step':1}},failed]
        self.write(self.root/'session.v4.jsonl',rows)
        result=self.read('deepseek-harness')
        self.assertEqual(result['summary']['totalTokens'],140);self.assertEqual(result['summary']['requests'],2)
    def test_unknown_harness_format_is_not_reported_as_empty(self):
        self.write(self.root/'session.v99.jsonl',[{'type':'session','id':'new','version':99},self.dsh()])
        self.assertIn('error',self.read('deepseek-harness'))
    @unittest.skipUnless(shutil.which('zstd'),'zstd not installed')
    def test_compressed_harness(self):
        raw=json.dumps({'type':'session','id':'compressed','version':3,'isSeeded':False})+'\n'+json.dumps(self.dsh())+'\n'
        packed=subprocess.run(['zstd','-q','-c'],input=raw.encode(),capture_output=True,check=True).stdout
        (self.root/'session.v3.jsonl.zstd').write_bytes(packed)
        self.assertEqual(self.read('deepseek-harness')['summary']['totalTokens'],110)
    def test_opencode_cost_and_tokens_use_read_only_database(self):
        path=self.root/'opencode.db';conn=sqlite3.connect(path)
        conn.execute('CREATE TABLE message(id TEXT,session_id TEXT,time_created INTEGER,data TEXT)')
        row={'role':'assistant','modelID':'m','providerID':'deepseek','tokens':{'input':100,'output':30,'reasoning':10,'cache':{'read':20,'write':5}},'cost':0.25}
        conn.execute('INSERT INTO message VALUES (?,?,?,?)',('m','s',1730800000000,json.dumps(row)));conn.commit();conn.close()
        before=path.read_bytes()
        result=sources.opencode_usage(self.root,0,9999999999,timezone.utc)
        self.assertEqual(result['summary']['totalTokens'],155);self.assertEqual(result['summary']['estimatedCostUsd'],0.25)
        self.assertEqual(before,path.read_bytes())
    def test_range_boundaries_are_exact(self):
        self.write(self.root/'one.jsonl',[self.codex(150,150,100),self.codex(300,150,200)])
        self.assertEqual(self.read(start=101,end=200)['summary']['totalTokens'],150)

    def test_chatgpt_uses_read_only_official_methods_and_caches_no_identity(self):
        server=Path(self.temp.name)/'codex-test'
        server.write_text('#!'+sys.executable+'\n'+"""import json,sys
for line in sys.stdin:
 request=json.loads(line)
 if 'id' not in request:continue
 method=request['method']
 if method=='initialize':result={'userAgent':'test'}
 elif method=='account/read':result={'account':{'type':'chatgpt','email':'private@example.test','planType':'plus'}}
 elif method=='account/rateLimits/read':result={'rateLimits':{'primary':{'usedPercent':30,'windowDurationMins':300,'resetsAt':9999999999}}}
 else:raise RuntimeError('Unexpected method')
 print(json.dumps({'id':request['id'],'result':result}),flush=True)
""")
        server.chmod(0o755)
        result=sources.chatgpt_account(str(server))
        self.assertEqual(result['windows'][0]['remaining'],70)
        self.assertNotIn('private@example.test',json.dumps(result))

if __name__=='__main__':unittest.main()
