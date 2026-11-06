"""Prepare pinned, interpreter-specific Claude HTTP wheels before publishing an install."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def prepare(root,python):
    requirements=root/'lib/claude-http-requirements.txt'
    script="import sys,sysconfig,platform; print(sys.implementation.cache_tag+'-'+sysconfig.get_platform()+'-'+platform.machine())"
    tag=subprocess.run([python,'-c',script],capture_output=True,text=True,check=True).stdout.strip()
    if not tag or '/' in tag or '\\' in tag:raise RuntimeError('Invalid Python runtime tag')
    target=root/'build/python'/tag
    fingerprint=hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker=target/'.requirements-sha256'
    def usable(path):
        probe='import sys; sys.path.insert(0,sys.argv[1]); from curl_cffi import requests; requests.Session(impersonate="chrome").close()'
        return subprocess.run([python,'-c',probe,str(path)],capture_output=True,timeout=15).returncode==0
    if marker.is_file() and marker.read_text().strip()==fingerprint and usable(target):return target
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.claude-http-',dir=target.parent) as scratch:
        staging=Path(scratch)/'packages'
        # Public wheels only. No credentials are read or passed to the dependency installer.
        command=[python,'-m','pip','--isolated','install','--disable-pip-version-check',
                 '--only-binary=:all:','--require-hashes','--no-compile','--index-url','https://pypi.org/simple',
                 '--target',str(staging),'-r',str(requirements)]
        environment={k:v for k,v in os.environ.items() if k in ('HOME','PATH','TMPDIR','LANG','LC_ALL')}
        result=subprocess.run(command,capture_output=True,text=True,timeout=180,env=environment)
        if result.returncode or not usable(staging):
            raise RuntimeError('Claude HTTP component installation failed; check Python pip and access to pypi.org. No installed files were changed.')
        (staging/'.requirements-sha256').write_text(fingerprint+'\n')
        if target.exists():shutil.rmtree(target)
        os.replace(staging,target)
    return target
