"""Replay exact paired qualification stopping on the frozen PromptEval transfer."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import prompteval_archive_cycles as archive
from benchmarks import prompteval_continuous as continuous
from benchmarks import prompteval_validation_size as selection, prompteval_validation_transfer as transfer
from cpo import Row
from cpo._contract import digest, unique_object
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '64041b252305c0666b9e7afd70c7965ab74e2df1d3f8fd3670beb3915929097b'
METHODS = tuple(f'{arm}.runner-up' for arm in archive.METHODS)


def qualification_cost(step, layout):
    full = step['qualificationLookups']
    incumbent, challenger, nominee = (step[key] for key in ('incumbent', 'challenger', 'archiveNominee'))
    if step['archivePromoted'] or challenger == incumbent:
        return full, full
    replies = {(prompt, case): passed for prompt, case, passed in step['qualification']}
    if len(replies) != full:
        raise ValueError('Qualification trace has inconsistent paid outcomes')
    prepaid = {key for key in replies if nominee is not None and key[0] in (incumbent, nominee)}
    rows = [Row(str(case), 'task') for case in layout['qualify']]
    decision = certify_paired_qualification(incumbent, challenger, rows,
                                            lambda prompt, row, _: replies[prompt, int(row.id)], seed=layout['seed'])
    if decision.status == 'undecided' or decision.prompt != step['selected']:
        raise ValueError('The stopping decision differs from the full qualification')
    used = {(obs.prompt, int(obs.row_id)) for obs in decision.observations}
    individual = len(prepaid | used)
    if len(decision.observations) % 2:
        last = decision.observations[-1]
        other = incumbent if last.prompt == challenger else challenger
        used.add((other, int(last.row_id)))
    complete_pairs = len(prepaid | used)
    if not individual <= complete_pairs <= full:
        raise ValueError('Stopping must use only paid cases from the full replay')
    return individual, complete_pairs


def prepare():
    parent, original, data = transfer.prepare()
    raw = (ROOT / 'docs/prompteval-validation-transfer-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Published transfer report differs from the verified source')
    prior = json.loads(raw, object_pairs_hook=unique_object)
    if digest(parent) != prior['planSha256']:
        raise ValueError('Transfer plan differs from the verified source')
    plan = {'protocol': 'cpo-prompteval-qualification-bounds-v1', 'parentPlanSha256': digest(parent),
            'parentReportSha256': SOURCE_SHA256, 'gepaVersion': original['gepaVersion'],
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'qualificationSha256': sha256((ROOT / 'cpo/paired_qualification.py').read_bytes()).hexdigest(),
            'methods': list(METHODS), 'validationCases': transfer.DESIGNS['candidate'][0],
            'searchCap': transfer.DESIGNS['candidate'][1],
            'scope': 'Keep archive preflight and search fixed. Stop only the ordinary post-search qualification.'}
    return plan, original, data, prior['panels']


def replay(plan, original, data, prior):
    panels = {}
    for panel in data['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        key = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        totals = {method: Counter(holdoutPasses=0, searchLookups=0, fullQualification=0,
                                  completePairQualification=0, individualReplyQualification=0, decisions=0,
                                  stoppedBetweenReplies=0) for method in METHODS}
        for seed in original['seeds']:
            _, layouts = continuous.schedule(len(matrix[0]), len(matrix), held, seed, original)
            episodes = selection.episode(matrix, held, seed, original, plan['validationCases'], plan['searchCap'])
            for method, summary in totals.items():
                result = episodes[method]
                summary['holdoutPasses'] += result['holdoutPasses']
                for step, layout in zip(result['steps'], layouts, strict=True):
                    one, paired = qualification_cost(step, layout)
                    summary.update(searchLookups=step['searchLookups'], fullQualification=step['qualificationLookups'],
                                   completePairQualification=paired, individualReplyQualification=one,
                                   decisions=int(step['challenger'] != step['incumbent'] and not step['archivePromoted']),
                                   stoppedBetweenReplies=int(one < paired))
        for method, total in totals.items():
            original_total = prior[key]['totals']['candidate'][method]
            if (total['holdoutPasses'] != original_total['holdoutPasses'] or
                    total['searchLookups'] + total['fullQualification'] != original_total['paidLookups']):
                raise ValueError('The full transfer trajectory differs from the published totals')
        panels[key] = totals
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, data, prior = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, original, data, prior)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
