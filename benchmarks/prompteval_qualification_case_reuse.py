"""Reuse wholly unobserved qualification cases across a matched four-cycle replay."""

import argparse
from collections import Counter, deque
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import prompteval_continuous as continuous, prompteval_transfer as transfer
from benchmarks.gepa_disjoint_cases import CaseRows
from cpo import Observation, ProposalBatch, ProposalPair, Row, search as cpo_search
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = ROOT / 'benchmarks/data/prompteval-episode-budget-v1.json'
EXTERNAL_SHA = '91a4f77273dc7ef934f766ea8652a4a16daa1c8c7cc24adeab91e66a890f7297'
PHASES = ('development', 'retrospective-transfer', 'episode-budget-subjects')
POLICIES = ('retire-assigned', 'recycle-unread')
METHODS = (continuous.CPO[0], *continuous.GEPA)
CAPS = (88, 136)


def prepare():
    phases = {name: continuous.prepare(name) for name in PHASES[:2]}
    raw = EXTERNAL.read_bytes()
    if sha256(raw).hexdigest() != EXTERNAL_SHA:
        raise ValueError('The recorded episode budget corpus changed')
    data = json.loads(raw)
    sizes = {panel['subject']: len(panel['correctness'][0]) for panel in data['panels']}
    base = phases['retrospective-transfer'][0]
    external = transfer.plan(data, sizes, EXTERNAL_SHA)
    phases[PHASES[-1]] = ({**base, **{key: external[key] for key in ('corpusSha256', 'holdoutCaseIDs',
                                                                  'sourceDataset', 'observedRepoRevision')}}, data)
    phases = {name: ({**plan, 'maximumExtensionRows': 4, 'qualificationPolicy': 'extend-ties'}, data)
              for name, (plan, data) in phases.items()}
    files = ('benchmarks/prompteval_qualification_case_reuse.py', 'benchmarks/gepa_disjoint_cases.py',
             'cpo/paired_qualification.py')
    plan = {'protocol': 'prompteval-qualification-case-reuse-v1', 'gepaVersion': '0.1.4',
            'searchLookupCeilingsPerCycle': list(CAPS), 'validationCasesReusedAcrossCycles': base['validationRows'],
            'matchedInputPlans': {name: digest(plan) for name, (plan, _) in phases.items()},
            'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
            'methods': list(METHODS), 'policies': list(POLICIES),
            'nativeCaseIdentity': 'Original case IDs, disjoint across training and validation',
            'reuseRule': 'Return unopened qualification cases in original order after the exact decision. '
                         'Each individual observed grade retires its whole case.'}
    return plan, phases


def paired_order(incumbent, challenger, cases, seed):
    rng = Random(seed)
    for case in cases:
        prompts = [incumbent, challenger]
        rng.shuffle(prompts)
        for prompt in prompts:
            yield prompt, case


def bounded_decision(incumbent, challenger, current, reserve, observe, *, threshold, seed):
    def certify(cases):
        rows = [Row(str(case), 'task') for case in cases]
        return certify_paired_qualification(incumbent, challenger, rows, lambda p, row, _: observe(p, int(row.id)),
                                            minimum_gain=threshold, seed=seed)

    base = certify(current)
    low, high = base.lower_gain, base.upper_gain
    if incumbent == challenger or not reserve or base.status == 'promoted' or not low <= 0 <= high:
        return base.prompt, False
    bound_count = len(base.observations)
    for prompt, case in list(paired_order(incumbent, challenger, current, seed))[bound_count:]:
        if observe(prompt, case) == (prompt == challenger):
            low += 1
        else:
            high -= 1
        if not low <= 0 <= high:
            return incumbent, False
    return certify((*current, *reserve)).prompt, True


def qualify(incumbent, challenger, current, bank, touched, measure, *, plan, seed, recycle):
    """Settle one matched trial and make its unopened cases eligible for later trials."""
    if plan['qualificationPolicy'] != 'extend-ties':
        raise ValueError('Case reuse requires the sealed tie extension policy')
    reserve = bank[:plan['maximumExtensionRows']]
    available = set(current + reserve)
    if len(available) != len(current) + len(reserve) or available & touched:
        raise ValueError('Qualification allocation contains an observed or duplicate case')
    observed = {}

    def evaluate(prompt, case):
        key = prompt, case
        if prompt not in (incumbent, challenger) or case not in available:
            raise ValueError('Qualification request left its sealed cases')
        if key not in observed:
            observed[key] = measure(prompt, case)
            if type(observed[key]) is not bool:
                raise ValueError('Qualification requires an exact boolean grade')
        return observed[key]

    selected, extended = bounded_decision(incumbent, challenger, current, reserve, evaluate,
                                         threshold=plan['minimumQualificationGain'], seed=seed)
    used = {case for _, case in observed}

    touched.update(used)
    returned_base = len(set(current) - used) if recycle and challenger != incumbent else 0
    returned_extension = len(set(reserve) - used) if recycle and extended else 0
    if recycle:
        bank[:] = [case for case in (*bank, *current) if case not in used]
    elif challenger == incumbent:
        bank.extend(current)
    elif extended:
        del bank[:len(reserve)]
    evidence = tuple((prompt, case, passed) for (prompt, case), passed in observed.items())
    return selected, evidence, {'qualificationLookups': len(observed), 'reserveAllocations': int(extended),
                                'borrowedCasesRead': len(used.intersection(reserve)), 'returnedBaseCases': returned_base,
                                'returnedExtensionCases': returned_extension, 'promotions': int(selected != incumbent),
                                'evidenceSha256': digest(evidence)}


def schedule(case_count, template_count, holdout, seed, plan):
    initial, layouts = continuous.schedule(case_count, template_count, holdout, seed, plan)
    anchors = layouts[0]['validation']
    excluded = set(holdout).union(anchors, *(layout['qualify'] for layout in layouts))
    for layout in layouts[1:]:
        train = [case for case in layout['train'] if case not in excluded]
        unused = sorted(set(range(case_count)) - excluded - set(train))
        Random(layout['seed']).shuffle(unused)
        count = plan['trainRows']
        layout['train'] = train + unused[:count - len(train)]
        layout['validation'] = anchors
        if len(layout['train']) != count:
            raise ValueError('The episode cannot support the full shared-validation schedule')
    return initial, layouts


def search(method, incumbent, layout, observe, plan):
    train, validation, alternatives, seed = (layout[name] for name in ('train', 'validation', 'alternatives', 'seed'))
    if method in continuous.GEPA:
        return transfer.optimize_gepa(incumbent, alternatives, train, validation, observe,
                                      batched=method == 'gepa-batched', seed=seed)
    rows, valid = ([Row(str(case), 'task') for case in values] for values in (train, validation))
    later = deque(alternatives[2:])

    def propose(_parent, _feedback, _history, width):
        proposals = tuple(later.popleft() for _ in range(min(width, len(later))))
        return ProposalBatch(proposals, exhausted=not later)

    def evaluate(prompt, row):
        passed = observe(prompt, int(row.id))
        return Observation(passed, {'correct': passed})

    return cpo_search(incumbent, rows, valid, evaluate, propose, metric_limit=plan['evaluationLookupLimit'],
                      rounds=len(alternatives) // 2, train_per_round=plan['probeSize'], seed=seed, adaptive=True,
                      opening_pair=ProposalPair(*alternatives[:2])).prompt


def audit_decision(incumbent, challenger, current, reserve, measure, *, threshold, seed):
    if incumbent == challenger:
        return incumbent, (), False
    rng = Random(seed)

    def full(cases):
        outcomes = []
        for case in cases:
            prompts = [incumbent, challenger]
            rng.shuffle(prompts)
            outcomes.extend((prompt, case, measure(prompt, case)) for prompt in prompts)
        return outcomes

    outcomes = full(current)
    gain = sum(passed if prompt == challenger else -passed for prompt, _, passed in outcomes)
    extended = bool(reserve) and gain == 0
    if extended:
        extra = full(reserve)
        gain += sum(passed if prompt == challenger else -passed for prompt, _, passed in extra)
        outcomes.extend(extra)
    return challenger if gain >= threshold else incumbent, tuple(outcomes), extended


def run_arm(matrix, holdout, initial, layouts, plan, method, policy):
    journal = {}
    incumbent, bank, touched, trace = initial, [], set(), []
    reserved = [case for layout in layouts for case in layout['qualify']]
    excluded = set(reserved).union(holdout)
    if len(excluded) != len(reserved) + len(holdout):
        raise ValueError('Qualification and holdout must use disjoint cases')
    totals = Counter()
    for layout in layouts:
        train, validation, current = (layout[key] for key in ('train', 'validation', 'qualify'))
        allowed = set(train + validation)
        if len(allowed) != len(train) + len(validation) or allowed & excluded:
            raise ValueError('Search crossed the reserved qualification or holdout cases')
        def score(prompt, case):
            return matrix[int(prompt)][case] == '1'

        logical = {}
        feasible_prompts = {incumbent, *layout['alternatives']}

        def observe(prompt, case):
            if case not in allowed or prompt not in feasible_prompts:
                raise ValueError('Search left its sealed candidates or case split')
            key = prompt, case
            if key not in logical:
                if len(logical) >= plan['evaluationLookupLimit']:
                    raise ValueError('An arm exceeded the shared logical search ceiling')
                if key not in journal:
                    journal[key] = score(prompt, case)
                logical[key] = journal[key]
            return logical[key]

        before = len(journal)
        challenger = search(method, incumbent, layout, observe, plan)
        reserve = bank[:plan['maximumExtensionRows']]
        selected, evidence, receipt = qualify(incumbent, challenger, current, bank, touched, score, plan=plan,
                                              seed=layout['seed'], recycle=policy == 'recycle-unread')
        expected, full, extended = audit_decision(incumbent, challenger, current, reserve, score,
                                                   threshold=plan['minimumQualificationGain'], seed=layout['seed'])
        if selected != expected or receipt['reserveAllocations'] != int(extended) or evidence != full[:len(evidence)]:
            raise ValueError('The exact certificate changed the full decision on the allocated cases')
        incumbent = selected
        if len(bank) != len(set(bank)) or set(bank) & touched:
            raise ValueError('The qualification bank contains a duplicate or observed case')
        receipt.update(searchLookups=len(logical), reusedSearchLookups=len(logical) - (len(journal) - before))
        totals.update({name: value for name, value in receipt.items() if type(value) is int})
        trace.append((digest(list(logical.items())), challenger, incumbent, receipt, tuple(bank)))
    if (totals['searchLookups'] - totals['reusedSearchLookups'] != len(journal)
            or totals['qualificationLookups'] > 2 * len(touched) or not touched <= set(reserved)):
        raise ValueError('The measured episode exceeded its search or qualification budget')
    totals['paidLookups'] = len(journal) + totals['qualificationLookups']
    totals['holdoutPasses'] = sum(matrix[int(incumbent)][case] == '1' for case in holdout)
    return incumbent, totals, digest(trace)


def measure_panel(matrix, holdout, plan):
    totals = {(method, policy): Counter() for policy in POLICIES for method in METHODS}
    changed = Counter()
    trace = []
    for seed in plan['seeds']:
        initial, layouts = schedule(len(matrix[0]), len(matrix), holdout, seed, plan)
        for method in METHODS:
            old, new = (run_arm(matrix, holdout, initial, layouts, plan, method, policy) for policy in POLICIES)
            for policy, result in zip(POLICIES, (old, new), strict=True):
                totals[method, policy].update(result[1])
            changed[method] += old[0] != new[0]
            trace.append((seed, method, old[0], new[0], old[2], new[2]))
    return {'totals': {policy: {method: totals[method, policy] for method in METHODS} for policy in POLICIES},
            'episodesWithChangedFinalPrompt': changed, 'traceSha256': digest(trace)}


def measure(phases, cap):
    results = {}
    for name, (plan, data) in phases.items():
        plan = {**plan, 'evaluationLookupLimit': cap}
        panels = {}
        for panel in data['panels']:
            subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
            key = f'{subject}/{model}'
            panels[key] = measure_panel(matrix, plan['holdoutCaseIDs'][subject], plan)
        initial_reads = len(panels) * len(plan['seeds']) * plan['cycles'] * plan['validationRows']
        if sum(panel['totals'][POLICIES[0]]['gepa-batched']['searchLookups'] for panel in panels.values()) <= initial_reads:
            raise ValueError('The matched budget must support native batched proposal evaluations')
        results[name] = panels
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, phases = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != '0.1.4':
        parser.error('Use the current seal, pinned GEPA 0.1.4, and a fresh receipt path')
    module = import_module('gepa.optimize_anything')
    native = module.optimize_anything

    def split_safe(*args, dataset, valset, **settings):
        train, validation = [CaseRows({**row, 'id': row['case']} for row in rows) for rows in (dataset, valset)]
        if train.by_id.keys() & validation.by_id.keys():
            raise ValueError('Native GEPA received overlapping case identities')
        return native(*args, dataset=train, valset=validation, **settings)

    results = {}
    with patch.object(module, 'optimize_anything', split_safe):
        for cap in CAPS:
            with patch.object(transfer, 'LOOKUP_LIMIT', cap):
                results[cap] = measure(phases, cap)
    result = {'plan': plan, 'planSha256': seal, 'caps': results, 'newProviderRequests': 0}
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
