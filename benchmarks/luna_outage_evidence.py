"""Audit which archived outage receipts support the comparison with GEPA."""

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
from contextlib import redirect_stdout
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RECORDED_REPORT = '85bdcb19940e4800aa627696c2ad2410e407cec61b51a16c7a20deeae1eadf5a'
V1_SEAL = '8c673bcdc1107c821622a46940c94cf4ec36d9331251d4177f94566b32c181dd'
V5_RECOVERY_SEAL = '3f34a88c0459892689a731ba96ba7545f4509208f1de84be40149e7e7816ccb9'
OUTAGE = re.compile(r'(?:Record [^.]+\. )?Duration minutes=(\d+); Plan=(?:STANDARD|PLUS); '
                    r'Monthly fee whole USD=\d+; Evidence=(MISSING|POSTED)\.')


def category(row):
    match = OUTAGE.fullmatch(row['input'])
    if not match:
        raise ValueError('The outage case differs from the typed policy format')
    duration, evidence = match.groups()
    band = ('under-30', '30-to-119', '120-plus')[bisect_right((30, 120), int(duration))]
    return f'{band}/{evidence.lower()}'


def recorded_losses():
    from benchmarks import recorded_coverage_confirmation as source
    from cpo._contract import digest

    raw = (ROOT / 'docs/recorded-coverage-confirmation-results-v1.json').read_bytes()
    reference = json.loads(raw)
    plan, tasks = source.prepare()
    if sha256(raw).hexdigest() != RECORDED_REPORT or digest(plan) != reference['planSha256']:
        raise ValueError('Recorded replay differs from its published seal')
    task = tasks['outage']
    cases = task[0]
    losses = {arm: Counter() for arm in source.GEPA}
    seen = {arm: set() for arm in source.GEPA}
    compare = source.compare

    def observe(data, held, seed, cap):
        record, validation, qualification = compare(data, held, seed, cap)
        for arm in source.GEPA:
            for case in held:
                if cases[case]['critical'] and record[arm]['outcomes'][case] and not record[source.PRIMARY]['outcomes'][case]:
                    losses[arm][category(cases[case])] += 1
                    seen[arm].add(case)
        return record, validation, qualification

    with patch.object(source, 'compare', observe):
        measured = source.summarize(task, 36, list(combinations(sorted(cases), 3)), plan)
    if measured != reference['results']['outage']['36']:
        raise ValueError('Recorded outage choices and costs did not reproduce')
    return {'planSha256': digest(plan), 'traceSha256': measured['tracesSha256'],
            'criticalLossesByCondition': losses, 'distinctLossCases': {arm: len(rows) for arm, rows in seen.items()},
            'uniqueLossCasesAcrossControls': len(set.union(*seen.values()))}


def luna_v1(root):
    import cpo_typed_study as trial
    from prompt_contract import digest

    plan = trial.prepare()
    directory = root / 'live-cpo-luna-typed-v1'
    if digest(plan) != V1_SEAL:
        raise ValueError('Load the verified v1 optimizer and source plan')
    result, blobs, _ = trial.replay_development(plan, directory)
    if result['delivery'] != 'live':
        raise ValueError('The evidence requires the completed provider archive')
    docs, _ = trial.study.inputs()
    cases = {row['id']: row for row in docs['outage']['datasets']['holdout']}
    outcomes = defaultdict(dict)
    for row in json.loads(blobs['qualification/qualification.json']):
        if row['task'] == 'outage':
            key = row['case'], row['repeat']
            if row['arm'] in outcomes[key] or row['critical'] != cases[key[0]]['critical']:
                raise ValueError('Duplicate or misclassified qualification evidence')
            outcomes[key][row['arm']] = row['classification'] == 'pass'
    expected = {(case, repeat) for case in cases for repeat in range(plan['qualificationReplicates'])}
    if outcomes.keys() != expected or any(set(row) != {*plan['arms'], trial.study.CONTROL}
                                          for row in outcomes.values()):
        raise ValueError('The outage qualification did not cover the sealed paired sample schedule')
    grouped = defaultdict(Counter)
    for (case, _), replies in outcomes.items():
        item = grouped[category(cases[case])]
        item.update(matchedRepeats=1, criticalRepeats=int(cases[case]['critical']))
        item.update({f'passes/{arm}': int(passed) for arm, passed in replies.items()})
    return {'planSha256': V1_SEAL, 'developmentQualified': result['qualified'],
            'studyProviderRequests': result['providerRequests'], 'model': plan['targetModel'],
            'searchWireSha256': sha256(blobs['search-wire.jsonl']).hexdigest(),
            'qualificationWireSha256': sha256(blobs['qualification/wire.jsonl']).hexdigest(),
            'outageHoldout': grouped}


def luna_v5(root):
    import cpo_typed_grounded_opening as trial
    import cpo_typed_grounded_opening_recovery as recovery
    from prompt_contract import digest

    retained = recovery.prepare(root / 'live-cpo-luna-typed-grounded-opening-v5')
    if digest(retained.plan) != V5_RECOVERY_SEAL:
        raise ValueError('The retained v5 archive does not match the pending recovery seal')
    groups, _, demos = trial.inputs(retained.plan)
    inputs = {row['input']: (task, split) for task, cohorts in groups.items()
              for split, cohort in cohorts.items() for row in cohort}
    evaluations = Counter()
    for request, _ in retained.calls:
        if request['role'] == 'evaluation':
            task, split = inputs[json.loads(request['request'])['input']]
            if split not in ('train', 'validation'):
                raise ValueError('Prefix reached a later split')
            evaluations[task] += 1
    outage = groups['outage']
    planned = {split: Counter(category(row) for row in rows if row['critical']) for split, rows in outage.items()}
    training = {row['id']: row for row in outage['train']}
    planned['demonstrations'] = Counter(category(training[row['id']]) for row in demos['outage']
                                        if training[row['id']]['critical'])
    return {'sourcePlanSha256': retained.plan['previousPlanSha256'], 'recoveryPlanSha256': V5_RECOVERY_SEAL,
            'sourceWireSha256': sha256(retained.wire).hexdigest(), 'model': retained.plan['targetModel'],
            'physicalRepliesVerified': len(retained.calls), 'outageEvaluationReplies': evaluations['outage'],
            'qualificationReplies': sum(request['role'] == 'qualification' for request, _ in retained.calls),
            'plannedCriticalCasesByCondition': planned,
            'independentPanelSha256': retained.plan['independentPanelSha256'],
            'recoveryClaimPresent': recovery.claim_path(retained).exists()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('recorded', 'luna-v1', 'luna-v5'))
    parser.add_argument('--study-root', type=Path)
    args = parser.parse_args()
    with redirect_stdout(sys.stderr):
        if args.phase == 'recorded':
            report = recorded_losses()
        else:
            if args.study_root is None:
                parser.error('Luna phases require --study-root')
            report = (luna_v1 if args.phase == 'luna-v1' else luna_v5)(args.study_root)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
