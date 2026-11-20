"""Require narrow-search finalists to show a gain beyond their first screen."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import case_difficulty_allocation as inputs
from benchmarks import funded_finalist_retry as parent
from cpo._contract import digest
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
SOURCE_REPORT = 'ef1e7228fb7a75573b4b184c55361ac5dffcf86121168a187efd8f91cb61fc85'
POLICIES = ('second-repair', 'independent-gain')
CONTROLS = parent.parent.METHODS
METHODS = (*CONTROLS, *POLICIES)


def confirm(incumbent, challenger, rows, observe, evidence, *, net_gain):
    """Resolve the complement's exact predicate with just the missing replies it needs."""
    def observed(prompt, row):
        item = evidence.get((prompt, row.id))
        return item.passed if item is not None else None

    while True:
        pairs = [(row, observed(incumbent, row), observed(challenger, row)) for row in rows]
        if net_gain:
            lower = sum((new is True) - (old is not False) for _, old, new in pairs)
            upper = sum((new is not False) - (old is True) for _, old, new in pairs)
            if lower > 0 or upper <= 0:
                return lower > 0
        else:
            possible = [(row, old, new) for row, old, new in pairs if old is not True and new is not False]
            if not possible or any(old is False and new is True for _, old, new in possible):
                return bool(possible)
            pairs = possible
        row, old, _ = min((pair for pair in pairs if pair[1] is None or pair[2] is None),
                          key=lambda pair: pair[1] is None and pair[2] is None)
        observe(incumbent if old is None else challenger, row)


def select(incumbent, candidates, rows, evaluate, *, metric_limit, net_gain, audit):
    rows = tuple(rows)
    evidence = {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in evidence:
            if len(evidence) >= metric_limit:
                raise ValueError('The complementary check exceeded full validation funding')
            evidence[key] = evaluate(prompt, row)
            if type(evidence[key].passed) is not bool:
                raise ValueError('Validation requires exact boolean outcomes')
        return evidence[key]

    reference = select_with_lazy_incumbent(incumbent, candidates, rows, observe, metric_limit=metric_limit)
    if reference.prompt == incumbent:
        return reference
    challenger = reference.prompt
    witness = next(case for prompt, case in evidence if prompt == challenger)
    if evidence[incumbent, witness].passed or not evidence[challenger, witness].passed:
        raise ValueError('The original shortlist must enter through a paired repair')
    before = len(evidence)
    rest = tuple(row for row in rows if row.id != witness)
    passed = confirm(incumbent, challenger, rest, observe, evidence, net_gain=net_gain)
    audit.update(nomineesChecked=1, nomineesVetoed=int(not passed), complementaryLookups=len(evidence) - before)
    return FinalistResult(challenger if passed else incumbent, reference.finalist, len(evidence))


def episode(matrix, held, seed, plan, start, label):
    if label in CONTROLS:
        return parent.parent.run(matrix, held, seed, plan, start, label, ordered=False)
    audit = Counter()

    def narrow(incumbent, candidates, rows, evaluate, *, metric_limit):
        return select(incumbent, candidates, rows, evaluate, metric_limit=metric_limit,
                      net_gain=label == 'independent-gain', audit=audit)

    with patch.object(parent.route.ties.split, 'select_with_lazy_incumbent', narrow):
        counts, trace = parent.route.run(matrix, held, seed, plan, start, 'strict')
    counts.update(audit)
    return counts, trace


def prepare():
    frozen, panels = parent.prepare()
    previous = inputs.checked_file('docs/funded-finalist-retry-results-v1.json', SOURCE_REPORT)
    if previous['designSha256'] != digest(frozen):
        raise ValueError('The preceding narrow-search replay no longer reproduces its design')
    for name, (_, _, references) in panels.items():
        for panel, points in references.items():
            for mode in CONTROLS:
                parent.route.ties.frontier.expect_reference(previous['results'][name]['panels'][panel][mode],
                                                             points[mode]['original'])
    paths = ('benchmarks/independent_witness_validation.py', 'benchmarks/funded_finalist_retry.py',
             'benchmarks/routed_witness_split.py', 'cpo/lazy_incumbent.py', 'cpo/challenger.py')
    design = {'protocol': 'cpo-independent-witness-validation-v1', 'sourceDesignSha256': digest(frozen),
              'sourceReportSha256': SOURCE_REPORT, 'methods': METHODS, 'primary': POLICIES[1],
              'scope': ('Veto a narrow-search nominee unless it shows either another repair or a strict '
                        'net gain on existing validation rows excluding its first probe. Complete only '
                        'needed evidence under the existing cap. Leave qualification and archive preflight fixed.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return design, panels


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, panels = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, plan, _ in panels.values()):
        cli.error('Use pinned GEPA 0.1.4')
    with patch.multiple(parent, METHODS=METHODS, POLICIES=POLICIES, episode=episode):
        results = {name: parent.measure(*item) for name, item in panels.items()}
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
