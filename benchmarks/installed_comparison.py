"""Verify packaged CPO by replaying sealed comparisons from an installed wheel."""

import argparse
from hashlib import sha256
from importlib import import_module
from importlib.metadata import distribution, version
import json
from pathlib import Path
import sys
import sysconfig


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = (
    ('opening_budget', 'opening-budget'),
    ('development_qualification', 'development-qualification'),
    ('qualification_precheck_replay', 'qualification-precheck-replay'),
)
PACKAGE_MODULES = ('cpo', 'cpo.optimizer', 'cpo.opening', 'cpo.development_qualification', 'cpo.qualification_precheck')


def local_import(name):
    module = import_module(name)
    installed = Path(module.__file__).resolve()
    site = Path(sysconfig.get_path('purelib')).resolve()
    if not installed.is_relative_to(site):
        raise ValueError(f'{name} must be imported from the installed environment')
    return installed.relative_to(site)


def verify():
    if sys.prefix == sys.base_prefix or not sys.flags.isolated:
        raise ValueError('Run the verifier with python -I from a dedicated virtual environment')
    required = {local_import(name) for name in PACKAGE_MODULES}
    modules = {Path(file) for file in distribution('cpo').files or ()
               if file.parts[0] == 'cpo' and file.suffix == '.py'}
    if not required <= modules:
        raise ValueError('The installed distribution does not record the required APIs')
    sources = {}
    site = Path(sysconfig.get_path('purelib')).resolve()
    for relative in sorted(modules):
        payload = (site / relative).read_bytes()
        if payload != (ROOT / relative).read_bytes():
            raise ValueError(f'{relative} differs from the comparison source')
        sources[relative.as_posix()] = sha256(payload).hexdigest()
    local_import('gepa')
    sys.path.append(str(ROOT))
    receipts = {}
    for name, report in FIXTURES:
        runner = import_module(f'benchmarks.{name}')
        raw = (ROOT / 'docs' / f'{report}-results-v1.json').read_bytes()
        expected = json.loads(raw)
        if version('gepa') != expected['plan']['gepaVersion']:
            raise ValueError('Use the GEPA version recorded in the comparison')
        if name == 'qualification_precheck_replay':
            plan, *sources_for_replay = runner.prepare()
            result = runner.replay(plan, *sources_for_replay)
        else:
            plan = runner.plan()
            result = runner.replay(plan)
        if (json.dumps(result, sort_keys=True, indent=2) + '\n').encode() != raw:
            raise ValueError(f'{name} did not reproduce its published comparison')
        receipts[report] = {'planSha256': result['planSha256'], 'reportSha256': sha256(raw).hexdigest()}
    return {'python': '.'.join(map(str, sys.version_info[:3])), 'cpo': version('cpo'), 'gepa': version('gepa'),
            'packageFileSha256': sources, 'verifiedComparisons': receipts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Verification requires a fresh output path')
    evidence = verify()
    with args.out.open('x') as stream:
        json.dump(evidence, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
