"""Test stratified validation probes against the original PromptEval controls."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import grounded, pool, prompteval_transfer as transfer
from cpo import Observation, Row, select_pool
from cpo._contract import digest


CONFIRMATION_SUBJECTS = ('high_school_statistics', 'high_school_european_history')
CONFIRMATION_DATA = transfer.DATA.with_name('prompteval-confirmation-v1.json')
WEIGHTED = 'cpo-weighted-witnesses'
DIAGNOSTIC = ('cpo-tie-probes', 'cpo-shared-validation', 'cpo-paired-witnesses', WEIGHTED)


def tie_shortlist(candidates, train, observe):
    scores = {prompt: sum(observe(prompt, row) for row in train[:2]) for prompt in candidates}
    incumbent = candidates[0]
    leaders = [prompt for prompt in candidates if scores[prompt] == max(scores.values())]
    used = len(candidates) * 2
    for row in train[2:6]:
        active = list(dict.fromkeys([incumbent, *leaders]))
        if len(leaders) < 2 or used + len(active) > 48:
            break
        for prompt in active:
            scores[prompt] += observe(prompt, row)
        used += len(active)
        highest = max(scores[prompt] for prompt in leaders)
        leaders = [prompt for prompt in leaders if scores[prompt] == highest]
    candidate = leaders[0]
    return [incumbent, candidate] if scores[candidate] > scores[incumbent] else [incumbent]


def witness_rows(incumbent, validation, observe):
    passes, failures = [], []
    for row in validation:
        (passes if observe(incumbent, row) else failures).append(row)
    return passes, failures


def weighted_shortlist(candidates, passes, failures, observe):
    incumbent = candidates[0]
    if not failures:
        return [incumbent]
    strata = [rows for rows in (passes, failures) if rows]
    estimates = {prompt: sum(len(rows) * observe(prompt, rows[0]) for rows in strata) for prompt in candidates}
    candidate = max(candidates, key=estimates.__getitem__)
    return [incumbent] if candidate == incumbent else [incumbent, candidate]


def evaluate_strategy(name, matrix, trial, holdout):
    candidates, train, validation = (trial[key] for key in ('candidates', 'train', 'validation'))
    allowed = set(train + validation if name == 'cpo-tie-probes' else validation)
    if allowed.intersection(holdout):
        raise ValueError('Probe rows must remain disjoint from qualification')
    observed = {}

    def observe(prompt, row):
        if row not in allowed or prompt not in candidates:
            raise ValueError('A witness search accessed outside the sealed pools')
        key = prompt, row
        if key not in observed:
            if len(observed) >= transfer.LOOKUP_LIMIT:
                raise ValueError('A witness search exceeded its lookup cap')
            observed[key] = matrix[int(prompt)][row] == '1'
        return observed[key]

    options = {}
    order, shortlist = validation, candidates
    if name == 'cpo-tie-probes':
        shortlist = tie_shortlist(candidates, train, observe)
        options['metric_limit'] = transfer.LOOKUP_LIMIT - len(observed)
    else:
        if name != 'cpo-shared-validation':
            passes, failures = witness_rows(candidates[0], validation, observe)
            order = list(dict.fromkeys(failures[:1] + passes[:1] + validation))
        if name == WEIGHTED:
            shortlist = weighted_shortlist(candidates, passes, failures, observe)
        else:
            options.update(screen_rows=2, max_challenges=1)
        options['metric_limit'] = transfer.LOOKUP_LIMIT
    result = select_pool(shortlist, [Row(str(row), 'task') for row in order],
                         lambda prompt, row: Observation(observe(prompt, int(row.id)), {}), **options)
    return {'candidate': result.prompt, 'evaluations': len(observed),
            'searchSha256': digest([(prompt, row, passed) for (prompt, row), passed in observed.items()]),
            'holdoutPasses': sum(matrix[int(result.prompt)][row] == '1' for row in holdout)}


def read_source(phase):
    path, subjects = ((transfer.DATA, transfer.SUBJECTS) if phase == 'exploratory' else
                      (CONFIRMATION_DATA, CONFIRMATION_SUBJECTS))
    raw = path.read_bytes()
    data = grounded.load_json(raw)
    expected = [(subject, model) for subject in subjects for model in transfer.MODELS]
    if data['schema'] != 'prompteval-transfer-v1' or [
            (panel['subject'], panel['model']) for panel in data['panels']] != expected:
        raise ValueError('The matrix subjects or model splits do not match the frozen evaluation')
    sizes = {}
    for panel in data['panels']:
        vectors = panel['correctness']
        if len(vectors) != 100 or not all(isinstance(row, str) for row in vectors):
            raise ValueError('Expected every recorded prompt template')
        size = len(vectors[0])
        if size - size * 30 // 100 < transfer.TRAIN_ROWS + transfer.VALIDATION_ROWS or any(
                len(row) != size or set(row) - {'0', '1'} for row in vectors):
            raise ValueError('Expected a complete rectangular binary matrix')
        if sizes.setdefault(panel['subject'], size) != size:
            raise ValueError('The model panels must share subject cases')
    return data, sizes, sha256(raw).hexdigest()


def plan(phase, source, sizes, fingerprint):
    common = transfer.plan(source, sizes, fingerprint)
    name = 'benchmarks/' + Path(__file__).name
    methods = DIAGNOSTIC if phase == 'exploratory' else (WEIGHTED,)
    return {**common, 'protocol': 'prompteval-validation-witnesses-v1', 'phase': phase,
            'subjects': list(sizes), 'arms': [*transfer.ARMS, *methods], 'challengers': list(methods),
            'minibatchProbeLimit': 6, 'minibatchLookupLimit': 48,
            'sourceSha256': {**common['sourceSha256'], name: sha256(Path(__file__).read_bytes()).hexdigest()}}


def execute(frozen, source):
    if version('gepa') != frozen['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        excluded = frozen['holdoutCaseIDs'][subject]
        trials = []
        for seed in frozen['seeds']:
            trial = transfer.compare(matrix, excluded, seed)
            for arm in frozen['challengers']:
                trial['arms'][arm] = evaluate_strategy(arm, matrix, trial, excluded)
            trials.append(trial)
        controls = ('cpo-minibatch', 'gepa-sequential', 'gepa-batched', 'uniform', 'successive-halving')
        totals, _ = pool.summarize(trials, WEIGHTED, controls)
        comparisons = {arm: pool.summarize(trials, arm, controls)[1] for arm in frozen['challengers']}
        panels[f'{subject}/{model}'] = {'totals': totals, 'comparisons': comparisons, 'trials': trials}
    return {'plan': frozen, 'planSha256': digest(frozen), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('exploratory', 'confirmation'), required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    source, sizes, fingerprint = read_source(args.phase)
    frozen = plan(args.phase, source, sizes, fingerprint)
    seal = digest(frozen)
    if args.execute is None and args.out is None:
        print(json.dumps({**frozen, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    result = execute(frozen, source)
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')
    print(json.dumps({panel: values['comparisons'] for panel, values in result['panels'].items()}, sort_keys=True))


if __name__ == '__main__':
    main()
