"""Test one extra certificate when a first-gain screen keeps its incumbent."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_single_finalist as prior
from benchmarks.prompteval_validation_transfer import CPO, paired
from cpo._contract import digest, unique_object
from cpo.challenger import certify_challenger
from cpo.single_finalist import FinalistResult, select_single_finalist


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = 'd74cbfe37948db493599fd0c3c0ba419253972356b9bd76018d29572aeda780a'
POLICIES = {'same-miss': (False, None), 'next-miss': (True, None), 'next-miss-at-most-eight': (True, 8)}


def retry_finalist(incumbent, candidates, validation, evaluate, *, metric_limit, policy, audit):
    """Reuse first-attempt evidence and try at most one additional certificate."""
    journal = {}

    def observe(prompt, row):
        evidence = journal.setdefault(prompt, {})
        if row.id not in evidence:
            evidence[row.id] = evaluate(prompt, row)
        return evidence[row.id]

    candidates, rows = tuple(candidates), tuple(validation)
    first = select_single_finalist(incumbent, candidates, rows, observe,
                                   metric_limit=metric_limit, screen='first-gain')
    if first.prompt != incumbent:
        audit['firstCertified'] += 1
        return first
    if not candidates:
        return first
    baseline = {case: reply.passed for case, reply in journal[incumbent].items()}
    failures = [row for row in rows if not baseline[row.id]]
    if not failures:
        audit['perfectIncumbent'] += 1
        return first
    audit['firstRejected' if first.finalist is not None else 'firstNoNominee'] += 1
    rotate, allowance = POLICIES[policy]
    witness = failures[1] if rotate and len(failures) > 1 else failures[0]
    order = sorted(rows, key=lambda row: baseline[row.id])
    remaining = metric_limit - first.evaluations
    if allowance is not None:
        remaining = min(remaining, allowance)
    retry_budget = remaining
    selected, finalist = first.prompt, first.finalist
    for prompt in candidates:
        if prompt == first.finalist:
            continue
        evidence = journal.get(prompt, {})
        if witness.id not in evidence:
            if remaining == 0:
                break
            observe(prompt, witness)
            remaining -= 1
        if not journal[prompt][witness.id].passed:
            continue
        exact = certify_challenger(order, baseline, lambda row: observe(prompt, row), metric_limit=remaining,
                                   observed={case: reply.passed for case, reply in journal[prompt].items()})
        remaining -= exact.evaluations
        audit['retryCertificate.' + exact.status] += 1
        if exact.status == 'promote':
            selected = finalist = prompt
        break
    audit['additionalLookups'] += retry_budget - remaining
    return FinalistResult(selected, finalist, first.evaluations + retry_budget - remaining)


def prepare():
    parent, original, source, _ = prior.prepare()
    raw = (ROOT / 'docs/prompteval-single-finalist-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The archived single-finalist result differs')
    receipt = json.loads(raw, object_pairs_hook=unique_object)
    if digest(parent) != receipt['planSha256']:
        raise ValueError('The single-finalist seal differs')
    plan = {
        'protocol': 'cpo-prompteval-finalist-retry-v1', 'parentPlanSha256': digest(parent),
        'parentReportSha256': SOURCE_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'gepaVersion': original['gepaVersion'], 'rowsAndCap': parent['rowsAndCap'],
        'policies': {k: {'nextMiss': rotate, 'extraLookupCap': cap} for k, (rotate, cap) in POLICIES.items()},
        'gate': parent['gate'],
        'scope': 'Retry after no exact certificate, with unchanged archived panels and qualification',
    }
    return plan, original, source, receipt['panels']


def replay(plan, original, source, published):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        seeds = original['seeds']
        references = [prior.screened_episode(matrix, held, seed, original, 'first-gain') for seed in seeds]
        traces = {method: [episode[method] for episode in references] for method in prior.METHODS}
        if (digest(traces[CPO]) != published[name]['candidates']['first-gain']['traceSha256'] or
                any(prior.totals(traces[method]) != published[name]['baseline'][method]
                    for method in prior.METHODS[1:])):
            raise ValueError('The archived first-gain trace or GEPA totals differ')
        candidates = {}
        for policy in POLICIES:
            audit = Counter()

            def select(incumbent, candidates, validation, evaluate, *, metric_limit, screen):
                if screen != 'first-gain':
                    raise ValueError('Unexpected base screen')
                return retry_finalist(incumbent, candidates, validation, evaluate, metric_limit=metric_limit,
                                       policy=policy, audit=audit)

            with patch.object(prior, 'select_single_finalist', select):
                episodes = [prior.screened_episode(matrix, held, seed, original, 'first-gain') for seed in seeds]
            if any([episode[method] for episode in episodes] != traces[method] for method in prior.METHODS[1:]):
                raise ValueError('A retry changed a matched GEPA trace')
            retry = [episode[CPO] for episode in episodes]
            candidates[policy] = {'totals': prior.totals(retry), 'traceSha256': digest(retry),
                                  'audit': dict(audit),
                                  'comparisons': {method: paired(retry, trace) for method, trace in traces.items()}}
        panels[name] = {'baseline': {method: prior.totals(trace) for method, trace in traces.items()},
                        'candidates': candidates}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels,
            'panelsClearingBothGates': {policy: [name for name, panel in panels.items() if all(
                panel['candidates'][policy]['comparisons'][method]['qualified'] for method in prior.METHODS[1:])]
                                       for policy in POLICIES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, source, published = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, original, source, published)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
