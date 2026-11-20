"""Verify the public critical-coverage selector on the sealed provider replay."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
REPLAY_REPORT = '85bdcb19940e4800aa627696c2ad2410e407cec61b51a16c7a20deeae1eadf5a'


def verify(study: Path, *, allow_interpreter_drift=False):
    from cpo import Observation, Row
    from cpo import covered_pool

    for directory in (ROOT, study.resolve(strict=True)):
        sys.path.append(str(directory))
    from benchmarks import installed_comparison, recorded_coverage_confirmation as source
    from cpo._contract import digest

    if not sys.flags.isolated or sys.prefix == sys.base_prefix:
        raise ValueError('Installed verification requires an isolated virtual environment')
    site = Path(covered_pool.__file__).resolve().parents[1]
    for name in ('cpo.covered_pool', 'cpo.coverage_confirmation'):
        module = installed_comparison.local_import(name)
        if (ROOT / module).read_bytes() != (site / module).read_bytes():
            raise ValueError(f'Installed {name} differs from its source')
    installed_comparison.local_import('gepa')

    report = (ROOT / 'docs/recorded-coverage-confirmation-results-v1.json').read_bytes()
    settings, data = source.prepare()
    expected = json.loads(report)
    if (sha256(report).hexdigest() != REPLAY_REPORT or digest(settings) != expected['planSha256']
            or version('gepa') != settings['gepaVersion']):
        raise ValueError('Replay source plan, report or control version differs')
    other_races = source.race
    decisions = 0

    def replaced(initial, roster, validation, strata, evaluate, spent, *, cap, method):
        nonlocal decisions
        if method != source.PRIMARY:
            return other_races(initial, roster, validation, strata, evaluate, spent, cap=cap, method=method)
        attempted = set()
        rows = tuple(Row(key, 'task', key in strata) for key in validation)

        def read(prompt, row):
            attempted.add(prompt)
            passed, fields = evaluate(prompt, row.id)
            return Observation(passed, {}, fields)

        result = covered_pool.select_covered_pool((initial, *roster), rows, read,
                                                 metric_limit=cap, critical_strata=strata)
        if result.evaluations != spent():
            raise ValueError('Selector lookup count differs from the archive lookup journal')
        decisions += 1
        return result.prompt, len(attempted - {initial})

    with patch.object(source, 'race', replaced):
        result = source.run(settings, data)
    published_match = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode() == report
    if not published_match:
        original = source.run(settings, data)
        if result != original:
            raise ValueError('Public selector differs from the original loop on this interpreter')
        if not allow_interpreter_drift:
            raise ValueError('The original loop differs from the report on this interpreter')
    differences = [f'{task}/{cap}' for task, caps in result['results'].items() for cap, arm in caps.items()
                   if arm != expected['results'][task][cap]]
    return {'candidateDecisions': decisions, 'gepaVersion': version('gepa'), 'cpoVersion': version('cpo'),
            'python': '.'.join(map(str, sys.version_info[:3])), 'publishedReportMatched': published_match,
            'differencesFromPublished': differences,
            'selectorSha256': sha256(Path(covered_pool.__file__).read_bytes()).hexdigest(),
            'planSha256': expected['planSha256'], 'reportSha256': REPLAY_REPORT}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study-root', type=Path, required=True)
    parser.add_argument('--allow-interpreter-drift', action='store_true',
                        help='Also accept an exact match to the original loop on the same interpreter')
    args = parser.parse_args()
    print(json.dumps(verify(args.study_root, allow_interpreter_drift=args.allow_interpreter_drift),
                     indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
