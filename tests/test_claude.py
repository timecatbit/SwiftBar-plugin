from pathlib import Path
import os,json,types,tempfile,unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
SOURCE=Path(__file__).resolve().parents[1]/'opencodex.30s.sh'
CODE=SOURCE.read_text().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
class ClaudeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'projects';self.root.mkdir()
  env=patch.dict(os.environ,{'KOMARI_BASE_URL':'https://komari.example.test','OCX_PLUGIN_PATH':str(SOURCE.resolve()),'OCX_CACHE_DIR':self.temp.name});env.start();self.addCleanup(env.stop)
  self.m=types.ModuleType('test');exec(compile(CODE,str(SOURCE),'exec'),self.m.__dict__)
  self.now=datetime(2026,11,4,12,tzinfo=ZoneInfo('Asia/Taipei'));self.db=str(Path(self.temp.name)/'usage.db')
 def row(self,id='m1',timestamp='2026-11-04T01:00:00Z',output=20,model='claude-opus-5-5'):
  return {'type':'assistant','timestamp':timestamp,'sessionId':'session','requestId':'req-'+id,'message':{'id':id,'model':model,'usage':{'input_tokens':100,'output_tokens':output,'cache_read_input_tokens':1000,'cache_creation_input_tokens':200,'cache_creation':{'ephemeral_1h_input_tokens':200,'ephemeral_5m_input_tokens':0}}}}
 def write(self,name,rows):
  (self.root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
 def stats(self):return self.m.claude_usage_live(self.root,self.db,self.now)[0]
 def test_copied_transcripts_and_stream_chunks_are_not_double_counted(self):
  self.write('a.jsonl',[self.row(output=0),self.row(output=20),self.row(output=20)])
  self.write('b.jsonl',[self.row(output=20)])
  s=self.stats()['summary'];self.assertEqual(s['requests'],1);self.assertEqual(s['totalTokens'],1320);self.assertEqual(s['outputTokens'],20)
 def test_append_only_and_incomplete_lines(self):
  self.write('a.jsonl',[self.row()]);self.stats()
  p=self.root/'a.jsonl'
  with p.open('a') as f:f.write(json.dumps(self.row('m2')))
  self.assertEqual(self.stats()['summary']['requests'],1)
  with p.open('a') as f:f.write('\n')
  self.assertEqual(self.stats()['summary']['requests'],2)
  self.assertEqual(self.stats()['summary']['requests'],2)
 def test_taipei_midnight_uses_local_day(self):
  self.write('a.jsonl',[self.row('yesterday','2026-11-03T15:59:59Z'),self.row('today','2026-11-03T16:00:00Z')])
  self.assertEqual(self.stats()['summary']['requests'],1)
 def test_unknown_model_has_unpriced_count(self):
  self.write('a.jsonl',[self.row(model='claude-unknown')]);s=self.stats()['summary']
  self.assertEqual(s['unpricedRequests'],1);self.assertEqual(s['totalTokens'],1320)
 def test_official_55_cache_and_fast_pricing(self):
  self.assertAlmostEqual(self.m.claude_price('claude-opus-5-5',(1000000,1000000,1000000,1000000,1000000)),37.2)
  self.assertAlmostEqual(self.m.claude_price('claude-opus-5-5',(1000000,0,0,0,0),'fast','us'),8.8)
  self.assertAlmostEqual(self.m.claude_price('claude-haiku-5-5',(100001,0,0,0,0)),.0500005)
 def test_non_assistant_and_synthetic_are_ignored(self):
  row=self.row();row['type']='user';self.write('a.jsonl',[row,self.row('s',model='<synthetic>')]);self.assertEqual(self.stats()['summary']['requests'],0)
 def test_third_party_model_is_tracked_without_invented_price(self):
  self.write('third.jsonl',[self.row(model='deepseek-flash')]);summary=self.stats()['summary']
  self.assertEqual(summary['totalTokens'],1320);self.assertEqual(summary['unpricedRequests'],1)
 def test_changing_source_directory_does_not_reuse_old_usage(self):
  self.write('one.jsonl',[self.row()])
  first=self.m.claude_usage_live(self.root,now=self.now)[0]
  other=Path(self.temp.name)/'other';other.mkdir()
  second=self.m.claude_usage_live(other,now=self.now)[0]
  self.assertEqual(first['summary']['requests'],1);self.assertEqual(second['summary']['requests'],0)
if __name__=='__main__':unittest.main(verbosity=2)
