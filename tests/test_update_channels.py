import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
import swiftbar_update_channels as channels


class ChannelTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def binary(self,path):
  p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.touch();return p
 def test_homebrew_executable_symlink_uses_cask_release_not_npm(self):
  p=self.binary('Caskroom/codex/0.166.0/bin/codex')
  metadata=self.root/'Caskroom/codex/.metadata';metadata.mkdir()
  (metadata/'INSTALL_RECEIPT.json').write_text(json.dumps({'source':{'tap':'homebrew/cask'}}))
  link=self.root/'bin/codex';link.parent.mkdir();link.symlink_to(p)
  result=channels.codex_channel(link)
  self.assertEqual(result['channel'],'Homebrew Cask')
  self.assertEqual(result['releaseURL'],'https://formulae.brew.sh/api/cask/codex.json')
  self.assertEqual(channels.latest_version(result,b'{"version":"0.166.0"}'),'0.166.0')
 def test_npm_install_uses_npm_release(self):
  p=self.binary('node_modules/@openai/codex/bin/codex.js')
  (p.parent.parent/'package.json').write_text('{"name":"@openai/codex"}')
  self.assertEqual(channels.codex_channel(p)['channelId'],'npm')
 def test_custom_or_unknown_install_does_not_make_a_false_update_claim(self):
  self.assertNotIn('releaseURL',channels.codex_channel(self.binary('bin/codex')))
  self.assertNotIn('releaseURL',channels.codex_channel(self.binary('Caskroom/codex/9.0/bin/codex')))

if __name__=='__main__':unittest.main()
