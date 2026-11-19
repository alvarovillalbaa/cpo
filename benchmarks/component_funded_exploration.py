"""Give incompatible diagnostic hypotheses and matched alternatives full validation."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from typing import NamedTuple
from unittest.mock import patch

from benchmarks import component_dependencies as prior, component_merge as fixture, frontier
from benchmarks.component_refresh import changed_context
from cpo import Row
from cpo._contract import digest
from cpo.certified_pool import select_certified_pool
from cpo.evidence import can_reuse_component_feedback as compatible


SEEDS = tuple(range(60401, 61313, 19))
REFERENCES = ('cpo-dependencies', 'cpo-component', 'gepa-dependencies', 'gepa-dependencies-merge')
RESERVED = 'cpo-reserved'
GUIDED = 'cpo-funded-hint'
MATCHED = 'cpo-funded-alternative'
ARMS = (RESERVED, GUIDED, MATCHED, *REFERENCES)


class Pair(NamedTuple):
    parent: str
    hint: str
    alternative: str


def choose_pair(result, journal, training, validation, seed):
    """Choose two unmeasured, unsupported single edits from a common parent."""
    parents = sorted((event for event in result.events if event['kind'] == 'validated'),
                     key=lambda event: (event['prompt'] != result.prompt, -len(event['passed']), event['prompt']))
    training_evidence = [(json.loads(prompt), observation.feedback['diagnostics'])
                         for (prompt, case), observation in journal.items() if case in training]
    for event in parents:
        parent = json.loads(event['prompt'])
        supported, hints = set(), set()
        for source, diagnostics in training_evidence:
            for diagnosis in diagnostics:
                edit = diagnosis.component, diagnosis.replacement
                if compatible(source, parent, diagnosis.component, dependencies=diagnosis.declared):
                    supported.add(edit)
                elif changed_context(source, parent, diagnosis):
                    hints.add(edit)
        if not hints - supported:
            continue
        eligible = {}
        for family in frontier.FAMILIES:
            for value in ('guarded', 'broad'):
                if parent[family] == value or (family, value) in supported:
                    continue
                candidate = fixture.encode({**parent, family: value})
                if not any((candidate, case) in journal for case in validation):
                    eligible[family, value] = candidate
        guided, alternatives = eligible.keys() & hints, eligible.keys() - hints
        if guided and alternatives:
            def order(edit):
                return digest([seed, event['prompt'], *edit])

            return Pair(event['prompt'], eligible[min(guided, key=order)], eligible[min(alternatives, key=order)])
    return None


def should_promote(incumbent, candidate, validation):
    protected = {row.id for row in validation if row.critical and incumbent[row.id]}
    return all(candidate[case] for case in protected) and sum(candidate.values()) > sum(incumbent.values())


def run_reserved_search(groups, profile, seed, cap):
    training = {row['id']: row for row in groups['train']}
    validation = {row['id']: row for row in groups['validation']}
    rows = [Row(case, row['family'], row['critical']) for case, row in validation.items()]
    search_rows = training | validation
    journal, seen, audit = {}, set(), Counter()
    captured = []
    search = fixture.search

    def observe(program, case):
        if case not in search_rows:
            raise ValueError('Search requested a holdout case')
        key = fixture.encode(program), case
        if key not in journal:
            if len(journal) >= cap - len(rows):
                raise fixture.BudgetReached
            journal[key] = prior.score(program, search_rows[case], profile)
        return journal[key]

    def propose(parent, _slot, _profile):
        return prior.next_edit(parent, journal, training, seen, 'dependencies', audit)

    def capture(*args, **kwargs):
        result = search(*args, **kwargs)
        captured.append(result)
        return result

    initial = dict.fromkeys(frontier.FAMILIES, 'off')
    with patch.object(fixture, 'search', capture), patch.object(fixture, 'propose_edit', propose):
        selected, proposals, _, _ = fixture.run_cpo('cpo-reserved', groups, profile, seed, cap, initial, observe, journal)
    incumbent = fixture.encode(selected)
    pair = choose_pair(captured[0], journal, training, validation, seed)
    prefix = len(journal) + len(proposals)
    initial_validation = {row.id: journal[incumbent, row.id].passed for row in rows}

    def holdout(program):
        return {row['id']: prior.score(program, row, profile).passed for row in groups['holdout']}

    record = {'chosen': incumbent, 'outcomes': holdout(selected), 'calls': prefix, 'stale': audit['stale'],
              'transferred': audit['transferred'], 'mergesAccepted': 0,
              'searchSha256': digest([(prompt, case, item.passed) for (prompt, case), item in journal.items()])}
    arms = dict.fromkeys((RESERVED, GUIDED, MATCHED), record)
    if pair is None:
        return arms, None

    details = {}
    for arm, candidate in ((GUIDED, pair.hint), (MATCHED, pair.alternative)):
        program = json.loads(candidate)
        if len(journal) + len(rows) > cap or any((candidate, row.id) in journal for row in rows):
            raise ValueError('Paired validation must be fresh and fit inside the earmarked budget')
        fresh = {(candidate, row.id): prior.score(program, validation[row.id], profile) for row in rows}
        candidate_validation = {case: outcome.passed for (_, case), outcome in fresh.items()}
        promote = should_promote(initial_validation, candidate_validation, rows)
        certificate_lookups = set()

        def lookup(prompt, row):
            key = prompt, row.id
            if key in fresh:
                certificate_lookups.add(key)
                return fresh[key]
            return journal[key]

        certificate = select_certified_pool([incumbent, candidate], rows, lookup, metric_limit=2 * len(rows))
        winner = candidate if promote else incumbent
        if certificate.prompt != winner:
            raise ValueError('Certified stopping and full validation disagree on promotion')
        candidate_holdout = holdout(program)
        arms[arm] = {**record, 'calls': prefix + 1 + len(fresh), 'chosen': winner,
                     'outcomes': candidate_holdout if promote else record['outcomes'],
                     'searchSha256': digest([record['searchSha256'], candidate, candidate_validation])}
        details[arm] = {'candidate': candidate, 'accepted': promote, 'validation': candidate_validation,
                        'holdout': candidate_holdout, 'fullLookups': len(fresh),
                        'certifiedLookups': len(certificate_lookups)}
    return arms, {'parent': pair.parent, 'incumbent': incumbent, 'incumbentValidation': initial_validation, 'arms': details}


def compare(profile, seed, cap):
    groups = prior.cases(profile, seed)
    with patch.object(prior, 'ARMS', REFERENCES):
        trial = prior.compare(profile, seed, cap)
    arms, pair = run_reserved_search(groups, profile, seed, cap)
    return {**trial, 'arms': {**trial['arms'], **arms}, 'pair': pair}


def summarize(trials):
    with patch.object(prior, 'ARMS', ARMS), patch.object(prior, 'PRIMARY', GUIDED):
        summary = prior.summarize(trials)
    pairs = [trial['pair'] for trial in trials if trial['pair'] is not None]
    diagnostics = {}
    for arm in (GUIDED, MATCHED):
        measurements = [pair['arms'][arm] for pair in pairs]
        diagnostics[arm] = {'promoted': sum(item['accepted'] for item in measurements),
                            'candidateValidationPasses': sum(sum(item['validation'].values()) for item in measurements),
                            'candidateHoldoutPasses': sum(sum(item['holdout'].values()) for item in measurements),
                            'fullLookups': sum(item['fullLookups'] for item in measurements),
                            'certifiedLookups': sum(item['certifiedLookups'] for item in measurements)}
    return {**summary, 'pairCount': len(pairs), 'incumbentPairs': sum(pair['parent'] == pair['incumbent'] for pair in pairs),
            'candidates': diagnostics, 'trials': trials}


def prepare():
    plan = prior.prepare()
    root = Path(__file__).resolve().parents[1]
    for name in ('benchmarks/component_funded_exploration.py', 'benchmarks/component_refresh.py', 'cpo/certified_pool.py'):
        plan['sourceSha256'][name] = sha256((root / name).read_bytes()).hexdigest()
    return {**plan, 'protocol': 'cpo-component-funded-exploration-v1', 'arms': list(ARMS), 'primary': GUIDED,
            'seeds': list(SEEDS), 'reservedValidationPanels': 1, 'allocation': 'one complete validation panel per arm',
            'cohortDigests': {profile: digest([prior.cases(profile, seed) for seed in SEEDS]) for profile in prior.PROFILES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {}
    for cap in plan['caps']:
        results[str(cap)] = {}
        for profile in plan['profiles']:
            trials = [compare(profile, seed, cap) for seed in plan['seeds']]
            results[str(cap)][profile] = summarize(trials)
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
