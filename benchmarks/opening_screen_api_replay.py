"""Verify that the public opening screen reproduces its sealed archive results."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import proposal_opening_transfer as source
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.prompteval_continuous import schedule
from cpo import Observation, ProposalPair, Row, opening_screen_cycle
from cpo._contract import digest


REFERENCE = '7797a7bfcbe6e0a08be46c9b6db7dc652e154ccf2b72dbc02f956ffafe351c4c'


def prepare():
    parent, plan, panels, _ = source.prepare()
    frozen = checked_file('docs/proposal-opening-transfer-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The transfer benchmark changed')
    design = {'protocol': 'cpo-opening-screen-api-replay-v1', 'referenceReportSha256': REFERENCE,
              'searchCap': parent['searchCap'], 'screenWidth': parent['screenWidth'],
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'packageSourceSha256': sha256(Path(opening_screen_cycle.__file__).read_bytes()).hexdigest()}
    return design, plan, panels, frozen['results']['panels']


def replay_panel(matrix, held, plan, design):
    width = design['screenWidth']
    total, paths = Counter(), []
    for seed in plan['seeds']:
        incumbent, layouts = schedule(len(matrix[0]), len(matrix), held, seed, plan)
        steps = []
        for layout in layouts:
            training, validation, holdout = ([Row(str(case), 'task') for case in layout[cohort]]
                                             for cohort in ('train', 'validation', 'qualify'))
            search_paid, qualification_paid = {}, {}
            validation_ids = {row.id for row in validation}
            qualification_ids = {row.id for row in holdout}

            def evaluate(prompt, row):
                key = prompt, int(row.id)
                if row.id not in validation_ids or key in search_paid:
                    raise ValueError('Search dispatched outside validation or repeated an evaluation')
                passed = matrix[int(prompt)][key[1]] == '1'
                search_paid[key] = passed
                return Observation(passed, {'correct': passed})

            def qualify(prompt, row, repeat):
                key = prompt, row.id, repeat
                if row.id not in qualification_ids or key in qualification_paid:
                    raise ValueError('Qualification dispatched outside its panel or repeated an evaluation')
                passed = matrix[int(prompt)][int(row.id)] == '1'
                qualification_paid[key] = passed
                return passed

            result = opening_screen_cycle.run_opening_screen_cycle(
                incumbent, training, validation, holdout, evaluate, qualify=qualify,
                opening_pair=ProposalPair(*layout['alternatives'][:2]), metric_limit=design['searchCap'],
                screen_rows=width, seed=layout['seed'], minimum_gain=plan['minimumQualificationGain'])
            replies = () if result.qualification is None else result.qualification.observations
            recorded = [(item.prompt, item.row_id, item.repeat, item.passed) for item in replies]
            if (result.search.evaluations != len(search_paid)
                    or recorded != [(*key, passed) for key, passed in qualification_paid.items()]):
                raise ValueError('The public result disagrees with actual callback dispatch')

            events = result.search.events
            completed = events[-1]['kind'] == 'full-validation'
            extra = 2 * (len(validation) - width) if completed else 0
            if completed:
                total.update(screenNominees=1, completionLookups=extra,
                             fullPanelRejections=int(not events[-1]['accepted']))
            total.update(searchLookups=len(search_paid), expected=len(recorded), screenLookups=len(search_paid) - extra,
                         promotions=int(result.promoted), reflections=result.search.reflections,
                         screenCandidates=len(events) - 1 - int(completed),
                         prefixPerfect=int(len(events[0]['passed']) == width))
            search_hash = digest([(prompt, case, value) for (prompt, case), value in search_paid.items()])
            steps.append((incumbent, result.search.prompt, result.prompt, search_hash, recorded))
            incumbent = result.prompt
        paths.append(steps)
        total['holdoutPasses'] += sum(matrix[int(incumbent)][case] == '1' for case in held)
    return {**total, 'paidLookups': total['searchLookups'] + total['expected'], 'traceSha256': digest(paths)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, plan, panels, previous = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    matched = {}
    for panel in panels:
        subject, model = panel['subject'], panel['model']
        name = f'{subject}/{model}'
        point = replay_panel(panel['correctness'], plan['holdoutCaseIDs'][subject], plan, design)
        if point != previous[name][source.PRIMARY]:
            raise ValueError(f'The package changed the published searches, cost, or decisions on {name}')
        matched[name] = point['traceSha256']
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'matchedPanelTraces': matched,
                   'cycles': len(matched) * len(plan['seeds']) * plan['cycles']}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
