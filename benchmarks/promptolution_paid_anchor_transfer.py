"""Transfer the fixed eight-lookup paid anchor fallback to GSM8K and SST-5."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import promptolution_witness_fallback as prior, witness_paid_anchor_bounds as anchors
from benchmarks import witness_fallback_caps as limits, witness_paid_anchor_proof_fit as source
from cpo import Row
from cpo._contract import digest
from cpo.halving import HalvingSearch
from cpo.paired_qualification import certify_paired_qualification


episode = prior.episode
CANDIDATE = 'witness-then-paid-anchors/8'
MATCHED = 'witness-then-cached-halving/8'
CAP = 8
REFERENCES = {
    'docs/promptolution-witness-fallback-results-v1.json': '5fde4bdad8e2710a70bad119b2d7791387e2880b7399e4b8b5285f033ba3f68f',
    'docs/witness-fallback-caps-results-v1.json': '49732022e1f778ca5bdf28dee1fd51f48fe9457d5b49131328527d249c27ba5c',
    'docs/witness-paid-anchor-proof-fit-results-v1.json': 'e4f29dda761eaaaa9c0bc579e1cbce77c40f288d3e3c47764a82460c4b0ef12e',
}


def prepare():
    previous = prior.prepare()
    source_plan, *_ = source.prepare()
    references = []
    for name, fingerprint in REFERENCES.items():
        raw = (episode.ROOT / name).read_bytes()
        if sha256(raw).hexdigest() != fingerprint:
            raise ValueError('Use the sealed fallback and fixed-cap results')
        references.append(json.loads(raw))
    historical, matched, origin = references
    if historical['planSha256'] != digest(previous) or origin['planSha256'] != digest(source_plan):
        raise ValueError('The transfer inputs or original fixed-cap selection changed')
    sources = {Path(module.__file__).relative_to(episode.ROOT).as_posix(): sha256(Path(module.__file__).read_bytes()).hexdigest()
               for module in (anchors, limits)}
    sources[Path(__file__).relative_to(episode.ROOT).as_posix()] = sha256(Path(__file__).read_bytes()).hexdigest()
    plan = {**previous, 'protocol': 'promptolution-paid-anchor-transfer-v1', 'candidate': CANDIDATE,
            'parentPlanSha256': digest(previous), 'parentReportSha256': next(iter(REFERENCES.values())),
            'referenceSha256': REFERENCES, 'fixedCapSourcePlanSha256': digest(source_plan),
            'sourceSha256': {**previous['sourceSha256'], **sources}, 'matchedHalving': MATCHED,
            'anchorWidth': source_plan['anchors'], 'newValidationLookupCap': CAP,
            'scope': 'Transfer the fixed eight-new-lookup four-anchor fallback with all proved-gain proofs '
                     'to both recorded tasks, without fitting. Preserve the prior witness, candidate roster, '
                     'validation and holdout cases, cycle order, and one independently paired admission.',
            'decisionRule': 'Require a positive paired lower endpoint against the strongest affordable control '
                            'and against matched-cap Halving, with no greater lookup cost than matched-cap '
                            'Halving, separately on both tasks and pooled.'}
    return plan, historical, matched


def halving_nomination(start, layouts, paid, evaluate, activity):
    trial = HalvingSearch(metric_limit=CAP, paid=paid)
    nominee = None
    for layout in layouts:
        activity['halvingCycles'] += 1
        winner = trial.select((start, *layout['alternatives']), layout['validation'], evaluate)
        if winner is None:
            break
        if winner != start:
            nominee = winner
            break
    activity['cappedEpisodes'] += int(trial.exhausted)
    return anchors.RANKING.Nomination(nominee, len(trial.observations), trial.observations)


def extend(witness, matrix, layouts, seed, method, held):
    _, initial, first = witness
    if initial['admissions']:
        return witness

    start = episode.START
    activity = Counter(fallbacks=1)
    paid = dict(first['search'])
    ordered = [{'alternatives': candidates, 'validation': cases, 'seed': seed + cycle}
               for cycle, (candidates, cases, _, _) in enumerate(layouts)]
    validation = {case for _, cases, _, _ in layouts for case in cases}
    protected = held | {case for _, _, train, proof in layouts for case in (*train, *proof)}
    if validation & protected or first['admission']:
        raise ValueError('Fallback search must preserve the independent cases and unused proof')

    def evaluate(prompt, case):
        if case not in validation:
            raise ValueError('Fallback left the validation panel')
        return matrix[prompt][case] == '1'

    if method == CANDIDATE:
        choice = anchors.fallback(start, ordered, paid, evaluate, CAP, activity, allow_proved_gain=True)
    else:
        choice = halving_nomination(start, ordered, paid, evaluate, activity)
    purchased = choice.paid_search - len(paid)
    if not 0 <= purchased <= CAP or any(choice.grades[key] != grade for key, grade in paid.items()):
        raise ValueError('Fallback search must preserve paid grades and fit the shared cap')

    admissions, final, status = {}, start, 'no-nominee'
    if choice.original is not None:
        cycle = next(i for i, layout in enumerate(layouts) if choice.original in layout[0])
        proof_cases = layouts[cycle][3]

        def grade(prompt, row, _repeat):
            case = int(row.id)
            if prompt not in (start, choice.original) or case not in proof_cases:
                raise ValueError('Proof left its enrolled prompts or cases')
            admissions[prompt, case] = matrix[prompt][case] == '1'
            return admissions[prompt, case]

        proof = certify_paired_qualification(start, choice.original, tuple(Row(str(case), 'task') for case in proof_cases),
                                             grade, seed=seed + cycle)
        final, status = proof.prompt, proof.status

    counts = {**initial, **activity, 'searchLookups': choice.paid_search, 'fallbackSearchLookups': purchased,
              'admissionLookups': len(admissions), 'paidLookups': choice.paid_search + len(admissions),
              'admissions': int(bool(admissions)), 'promotions': int(final != start),
              'occupiedCycles': initial['occupiedCycles'] + activity['races'] + activity['halvingCycles']}
    return final, counts, {'selected': final, 'witnessDecisions': first['decisions'], 'fallbackDecision': status,
                           'nominee': choice.original, 'search': list(choice.grades.items()),
                           'admission': list(admissions.items())}


def matched_comparison(plan, panels):
    difference = [[new - old for new, old in zip(vectors[CANDIDATE], vectors[MATCHED], strict=True)]
                  for _, vectors in panels]
    paid_delta = sum(totals[CANDIDATE]['paidLookups'] - totals[MATCHED]['paidLookups'] for totals, _ in panels)
    rng = Random(plan['resampleSeed'])
    draws = [sum(sum(rng.choices(task, k=len(task))) for task in difference) for _ in range(plan['draws'])]
    paired = episode.ranges(draws, len(panels) * episode.HOLDOUT * len(episode.SEEDS))
    return {'control': MATCHED, 'passDelta': sum(map(sum, difference)), 'paidLookupDelta': paid_delta, **paired,
            'qualifies': paid_delta <= 0 and paired['interval95PercentagePoints'][0] > 0}


def execute(plan, archive, historical, matched):
    play, compare = episode.play, episode.compare
    knobs = {'CONTROLS': plan['controlSettings'], 'GEPA': (*episode.GEPA, *prior.sensitivity.SMALL),
             'HALVING': (*episode.HALVING, *prior.EXTRA_HALVING),
             'ARMS': (*episode.ARMS, *prior.sensitivity.SMALL, *prior.EXTRA_HALVING,
                      prior.CANDIDATE, MATCHED, CANDIDATE)}

    def run(matrix, layouts, seed, method, held):
        if method not in (prior.CANDIDATE, MATCHED, CANDIDATE):
            return play(matrix, layouts, seed, method, held)
        first = play(matrix, layouts, seed, episode.CPO, held)
        if method == prior.CANDIDATE:
            selected, counts, trace = prior.combine(first, lambda: play(matrix, layouts, seed, prior.HALVING, held))
            counts['fallbacks'] = int(not first[1]['admissions'])
            counts['reusedSearchLookups'] = trace.get('reusedSearchLookups', 0)
            return selected, counts, trace
        return extend(first, matrix, layouts, seed, method, held)

    def compared(current, panels, controls):
        all_controls = episode.RETAIN in controls
        extra = (episode.CPO, prior.CANDIDATE, MATCHED) if all_controls else ()
        with patch.object(episode, 'CPO', CANDIDATE):
            result = compare(current, panels, (*controls, *extra))
        if all_controls:
            result['matchedCapHalving'] = matched_comparison(current, panels)
        return result

    with patch.multiple(episode, **knobs, play=run, compare=compared):
        report = episode.execute(plan, archive)
    for task, expected in historical['tasks'].items():
        panel = report['tasks'][task]
        if panel['heldCaseSha256'] != expected['heldCaseSha256'] or any(
                panel['arms'][method] != metrics for method, metrics in expected['arms'].items()):
            raise ValueError('A published control trace, charge, or holdout split changed')
        exact = matched['fallbackDeltas'][task][f'{limits.CERTIFIED}/{CAP}']
        new, baseline = (panel['arms'][method] for method in (MATCHED, episode.CPO))
        if (new['holdoutPasses'] - baseline['holdoutPasses'], new['paidLookups'] - baseline['paidLookups'],
                new.get('cappedEpisodes', 0), new['fallbacks']) != (
                exact['addedPasses'], exact['addedLookups'], exact['cappedEpisodes'], exact['eligibleEpisodes']):
            raise ValueError('Matched-cap Halving does not reproduce the established control')
    comparisons = [report['pooledComparisons'], *(row['comparisons'] for row in report['tasks'].values())]
    report['qualified'] = report['qualified'] and all(
        scope['allControlsAndRetain']['matchedCapHalving']['qualifies'] for scope in comparisons)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, historical, matched = prepare()
    seal = digest(plan)
    if args.corpus is None and args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.corpus is None or args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the pinned archive, current seal, and a fresh report path')
    report = execute(plan, episode.load_corpus(args.corpus.read_bytes()), historical, matched)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
