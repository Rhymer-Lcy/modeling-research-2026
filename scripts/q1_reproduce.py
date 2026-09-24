"""Repeat full generators, preserving separate raw/scientific failure statuses."""
from __future__ import annotations

import json
from pathlib import Path
import platform
import re
import subprocess
import sys

import numpy as np
import scipy
import pandas
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.paths import REPO_ROOT, ATT_A, TABLES, CONFIGS, PROBLEM_F_SOURCE, PROBLEM_F_DERIVED, PROBLEM_F_INTERFACES, require
from src.quality.realdata import file_hash
from src.quality.configuration import load_settings
from src.mixture.data import MIXTURE_FILES, LOSS_FILES
from src.interfaces import IF1DomainQuality, IF2MixtureResponse, Provenance


def input_files():
    result={'A1':require(ATT_A/'slimpajama_quality_signal_sample.jsonl.xz'),
            'A16':require(ATT_A/'domain_mapping_guide.csv'),
            'DOCX':require(PROBLEM_F_SOURCE/'problem_statement.docx')}
    for aid,domain in [('A2','arxiv'),('A3','github')]:
        matches=sorted((ATT_A/'slimpajama_quality_extended').glob(domain+'_*.jsonl.xz'))
        if len(matches)!=1:
            raise ValueError('extension file missing or ambiguous')
        result[aid]=matches[0]
    for aid,name in MIXTURE_FILES.items():
        result[aid]=require(ATT_A/'regmix_tables'/name)
        result['A'+str(int(aid[1:])+1)]=require(ATT_A/'regmix_tables'/LOSS_FILES[aid])
    if len(result)!=17:
        raise ValueError('require all sixteen attachments and official DOCX')
    return result


def run(script):
    print('RUN',script,'interpreter:',sys.executable,flush=True)
    completed=subprocess.run([sys.executable,str(REPO_ROOT/'scripts'/script)],cwd=REPO_ROOT,
                             capture_output=True,text=True,encoding='utf-8')
    print(completed.stdout,end='',flush=True)
    if completed.stderr:
        print(completed.stderr,end='',file=sys.stderr,flush=True)
    return completed.returncode,completed.stdout


def artifacts():
    paths=[p for p in TABLES.glob('q1-*.md') if p.name!='q1-reproduction.md']
    paths+=sorted((PROBLEM_F_DERIVED/'q1').glob('*-standardized.npz'))
    paths+=[PROBLEM_F_DERIVED/'q1'/name for name in ('quality-analysis.json','mixture-analysis.json',
            'mixture-frozen.json','mixture-frozen-validation.json')]
    paths+=sorted(PROBLEM_F_INTERFACES.glob('q1-if*.json'))
    return {p.relative_to(REPO_ROOT).as_posix():file_hash(require(p)) for p in sorted(paths)}


def check_release(kind,code,stdout):
    path=PROBLEM_F_DERIVED/'q1'/(('quality' if kind=='IF1' else 'mixture')+'-analysis.json')
    report=json.loads(require(path).read_text(encoding='utf-8'))
    release=report['release']
    ready=release['status']=='READY FOR REVIEW'
    if code!=(0 if ready else 2) or kind+':' not in stdout:
        raise ValueError(kind+' execution failure inconsistent with scientific report')
    canonical=PROBLEM_F_INTERFACES/('q1-if1-domain-quality.json' if kind=='IF1' else 'q1-if2-mixture-response.json')
    if ready:
        value=json.loads(require(canonical).read_text(encoding='utf-8'))
        value['provenance']=Provenance(**value['provenance'])
        (IF1DomainQuality if kind=='IF1' else IF2MixtureResponse)(**value).validate()
        if kind=='IF2':
            scope=value['validation'].get('scope_release',{})
            acceptance=value['validation'].get('acceptance',{})
            if (value.get('fit_scale')!='1M' or scope.get('scope_release_pass') is not True
                    or scope.get('frozen_model_sha256')!=report['frozen']['model_sha256']
                    or scope.get('limitations',{}).get('absolute_use_outside_1M')!='PROHIBITED'
                    or scope.get('limitations',{}).get('scale_invariance_supported') is not False
                    or scope.get('a8_a9_absolute_transfer_pass') is not False
                    or scope.get('a10_a11_out_of_design_shape_pass') is not False
                    or acceptance.get('release_pass') is not False):
                raise ValueError('IF2 scope receipt does not preserve its 1M-only limits')
        if file_hash(canonical)!=release['sha256']:
            raise ValueError('interface fingerprint mismatch')
    elif canonical.exists():
        raise ValueError('blocked interface has a stale canonical output; stop for review')
    return {'exit_code':code,'status':release['status'],'validate':'PASS' if ready else 'NOT RELEASED'}


def main():
    seed,_=load_settings('quality')
    print('seed:',seed,'interpreter:',sys.executable,flush=True)
    inputs=input_files()
    before={aid:file_hash(path) for aid,path in inputs.items()}
    audit=require(TABLES/'q1-input-audit.md').read_text(encoding='utf-8')
    secured=dict(re.findall(r'^\| (A\d+) \| `[^`]+` \| `([a-f0-9]{64})` \|$',audit,re.M))
    secured['DOCX']=re.search(r'Official DOCX SHA-256: `([a-f0-9]{64})`',audit).group(1)
    if secured!=before:
        raise ValueError('raw inputs differ from secured audit checkpoint')
    config={p.name:file_hash(p) for p in (CONFIGS/'default.yaml',CONFIGS/'q1.yaml')}
    snapshots=[]
    passes=[]
    for iteration in range(2):
        print('FULL REGENERATION PASS',iteration+1,flush=True)
        scalar,_=run('q1_scalarize.py')
        if scalar!=0:
            raise ValueError('scalarization failed')
        raw,stdout=run('q1_audit_inputs.py')
        if raw!=2 or 'raw-input audit: KNOWN INPUT DEFECT' not in stdout:
            raise ValueError('raw audit differs from the documented expected failure')
        q,stdout=run('q1_quality.py')
        if1=check_release('IF1',q,stdout)
        m,stdout=run('q1_mixture.py')
        if2=check_release('IF2',m,stdout)
        if before!={aid:file_hash(path) for aid,path in inputs.items()}:
            raise ValueError('raw input hash changed')
        if config!={p.name:file_hash(p) for p in (CONFIGS/'default.yaml',CONFIGS/'q1.yaml')}:
            raise ValueError('configuration changed')
        passes.append({'scalarization':scalar,'raw_audit':{'exit_code':raw,'status':'KNOWN INPUT DEFECT'},'IF1':if1,'IF2':if2})
        snapshots.append(artifacts())
    if snapshots[0]!=snapshots[1] or passes[0]!=passes[1]:
        raise ValueError('full regeneration is not byte deterministic')
    versions={'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,
              'pandas':pandas.__version__,'pyyaml':yaml.__version__}
    report={'runtime':versions,'passes':passes,'raw_sha256':before,'configuration_sha256':config,
            'artifact_sha256':snapshots[1],'raw_immutability':'PASS','byte_determinism':'PASS',
            'warning':'reproducibility success does not turn scientific validation failure into success'}
    target=PROBLEM_F_DERIVED/'q1'/'reproduction.json'
    target.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n')
    lines=['# Q1 full regeneration verification','','Generated by `python scripts/q1_reproduce.py`; do not edit.','',
           'Two complete passes are byte-identical, including local standardized arrays and available interfaces.',
           'All A1-A16 inputs plus the official DOCX match the secured audit and remain byte-identical.',
           'Runtime: '+json.dumps(versions,sort_keys=True),
           'Scientific and input status (identical in both passes): '+json.dumps(passes[1],sort_keys=True),
           '**Reproducibility PASS does not establish broad scientific acceptance. A released IF2, if present, is limited to its explicit 1M scope receipt.**','',
           '| Regenerated artifact | SHA-256 |','| --- | --- |']
    lines += ['| '+p+' | '+h+' |' for p,h in snapshots[1].items()]
    (TABLES/'q1-reproduction.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print('REPRODUCIBILITY PASS; separate scientific status:',passes[1],flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
