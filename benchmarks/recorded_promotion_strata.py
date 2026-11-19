"""Compare risk-diverse promotion panels with matched critical quotas and case swaps."""

import argparse
from bisect import bisect_right
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
from random import Random
import re
from unittest.mock import patch

from benchmarks import recorded_archive_restart as restart, recorded_promotion_coverage as prior
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
POLICIES = ('two-critical', 'matched-swaps', 'risk-diverse')
BASE = 'two-critical'
DIVERSE = 'risk-diverse'
PRIMARY = f'cpo.{DIVERSE}'
OUTAGE = re.compile(r'Duration minutes=(\d+); Plan=(?:STANDARD|PLUS); Monthly fee whole USD=\d+; Evidence=(MISSING|POSTED)\.')
WAREHOUSE = re.compile(r'On hand=(\d+); Reserved=(\d+); Damaged=(\d+); Inspection=(PASS|FAIL); '
                       r'Tier=(NORMAL|RUSH); Site=(?:NORTH|SOUTH)\.')
TICKET = re.compile(r'Topic=([\w-]+)\. Channel=\w+\. Reference=T-\d+\.')
INPUT_PATTERNS = {'outage': OUTAGE, 'warehouse': WAREHOUSE, 'ticket': TICKET}


def risk_stratum(task, row):
    """Use documented policy inputs. Expected answers and model grades are inaccessible."""
    prefix = f"Record {row['id']}. "
    raw = row['input']
    match = INPUT_PATTERNS[task].fullmatch(raw.removeprefix(prefix))
    if not raw.startswith(prefix) or match is None:
        raise ValueError(f'Case does not match the archived {task} input contract')
    if task == 'outage':
        duration, evidence = match.groups()
        return bisect_right((30, 120), int(duration)), evidence
    if task == 'warehouse':
        on_hand, reserved, damaged, inspection, tier = match.groups()
        return int(on_hand) - int(reserved) - int(damaged) <= 0, inspection, tier
    return match.group(1)


def coverage(panel, critical, strata):
    return len({strata[case] for case in panel if case in critical}), len({strata[case] for case in panel})


def assign_risk_panels(validation, promotion, critical, strata, seed):
    """Preserve both role sizes and critical counts, with a seeded swap-matched control."""
    original = frozenset(promotion)
    available = tuple(promotion) + tuple(validation)
    pool = frozenset(available)
    if len(pool) != len(available) or pool - strata.keys():
        raise ValueError('Panels require disjoint cases with known policy strata')
    quota = len(original & critical)
    options = [frozenset(items) for items in combinations(available, len(promotion))
               if len(set(items) & critical) == quota]

    def rank(panel):
        promotion_critical, promotion_types = coverage(panel, critical, strata)
        validation_critical, validation_types = coverage(pool - panel, critical, strata)
        return promotion_critical, validation_critical, promotion_types, validation_types, -len(panel - original)

    diverse = max(options, key=rank)
    swaps = len(diverse - original)
    control = Random(seed).choice([panel for panel in options if len(panel - original) == swaps])

    def ordered(panel):
        promote = iter(case for case in validation if case in panel)
        validate = iter(case for case in promotion if case not in panel)
        return ([next(validate) if case in panel else case for case in validation],
                [case if case in panel else next(promote) for case in promotion])

    return {DIVERSE: ordered(diverse), 'matched-swaps': ordered(control)}


def load_json(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique_object)


def prepare(replay_path):
    base_plan, data, run_gepa, cohorts = prior.prepare()
    public = load_json(ROOT / 'docs/recorded-promotion-coverage-results-v1.json')
    raw = replay_path.read_bytes()
    artifact = json.loads(raw, object_pairs_hook=unique_object)
    if (sha256(raw).hexdigest() != public['detailsSha256'] or digest(base_plan) != public['planSha256'] or
            artifact['plan'] != base_plan):
        raise ValueError('Original promotion replay and source plan must match')
    strata = {task: {case: risk_stratum(task, row) for case, row in dataset[0][1].items()}
              for task, dataset in data.items()}
    plan = {'protocol': 'cpo-recorded-promotion-strata-v1', 'primary': PRIMARY, 'policies': list(POLICIES),
            'basePlanSha256': public['planSha256'], 'baseReplaySha256': public['detailsSha256'],
            'gepaVersion': base_plan['gepaVersion'], 'riskStrataSha256': digest(strata),
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'tieOrder': 'Retain existing cases and order where possible, then use the seeded input order',
            'control': 'Identical panel sizes, critical quotas, and number of swaps as the diverse allocation',
            'strataRules': {'outage': 'Duration bands below 30, 30–119, and 120 or more, crossed with evidence status',
                            'ticket': 'Topic', 'warehouse': 'Nonpositive available stock, inspection, and tier'}}
    return plan, base_plan, artifact['results'], data, run_gepa, cohorts, strata


def replay_task(data, strata, previous, holdouts, plan, run_gepa):
    rows = data[0][1]
    critical = {case for case, row in rows.items() if row['critical']}
    baseline_assign = prior.assign_panels
    trials = []
    for index, (holdout, archived) in enumerate(zip(holdouts, previous['trials'], strict=True)):
        seed = plan['seedStart'] + index * plan['seedStride']
        layouts = {}

        def allocate(validation, promotion, metadata, policy):
            if not layouts:
                baseline = baseline_assign(validation, promotion, metadata, 2)
                layouts[BASE] = baseline
                layouts.update(assign_risk_panels(*baseline, critical, strata, seed))
            return layouts[policy]

        with patch.object(prior, 'POLICIES', dict(zip(POLICIES, POLICIES, strict=True))), patch.object(
                prior, 'assign_panels', allocate):
            trial = prior.compare(data, holdout, seed, plan, run_gepa)
        reference = {arm: record for arm, record in trial['arms'].items() if arm.endswith(f'.{BASE}')}
        if any(info != archived['arms'][arm] for arm, info in reference.items()) or list(holdout) != archived['holdout']:
            raise ValueError('The matched baseline did not reproduce the published promotion decisions')
        for name, (validation, promotion) in layouts.items():
            stats = trial['allocations'][name]
            stats['criticalValidationStrata'], stats['validationStrata'] = coverage(validation, critical, strata)
            stats['criticalPromotionStrata'], stats['promotionStrata'] = coverage(promotion, critical, strata)
            stats['swapsFromBaseline'] = len(set(promotion) - set(layouts[BASE][1]))
        trials.append(trial)
    with patch.object(restart, 'PRIMARY', PRIMARY):
        result = restart.summarize(trials)
    result.pop('trials')
    result['allocations'] = {
        policy: dict(sum_allocations(trial['allocations'][policy] for trial in trials)) for policy in POLICIES}
    result['distinctProviderHoldoutPairs'] = {}
    for arm in ('cpo.two-critical', 'gepa-sequential.risk-diverse', 'gepa-batched.risk-diverse'):
        observed = [(trial['arms'][PRIMARY], trial['arms'][arm]) for trial in trials]
        pairs = {(a['chosen'], b['chosen']): (a['originalHoldout'], b['originalHoldout']) for a, b in observed
                 if a['chosen'] != b['chosen']}
        verified = [(a, b) for a, b in pairs.values() if a and a.keys() == b.keys()]
        result['distinctProviderHoldoutPairs'][arm] = {'differentPromptPairs': len(pairs), 'matchedPairs': len(verified),
                                                       'knownPassDelta': sum(sum(a.values()) - sum(b.values())
                                                                             for a, b in verified)}
    return result


def sum_allocations(items):
    result = Counter()
    for item in items:
        result.update(item)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, base_plan, previous, data, run_gepa, cohorts, strata = prepare(args.replay)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {task: replay_task(dataset, strata[task], previous[task], cohorts[task], base_plan, run_gepa)
               for task, dataset in sorted(data.items())}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
