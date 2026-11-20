"""Compare both staged certificates against exact final-draft validation alone."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded_fixture, grounded_staged as staged, grounded_staged_fixture
from cpo._contract import digest


def mixed_fixture(request):
    if request['task'] == 'ticket':
        return grounded_fixture.respond(request)
    return grounded_staged_fixture.respond(request)


def run_pair(directory, respond, *, certify_opening):
    development, confirmation = directory / 'development', directory / 'confirmation'
    directory.mkdir()
    flags = {'certify_final_draft': True, 'certify_opening': certify_opening}
    _, plan, _ = staged.prepare(**flags)
    dev = staged.run(digest(plan), development, respond, delivery='fixture', **flags)
    _, bound, _ = staged.prepare(development, **flags)
    panel = staged.run(digest(bound), confirmation, respond, development=development, delivery='fixture', **flags)
    if staged.replay(development, directory / 'development-replay') != dev or staged.replay(
            confirmation, directory / 'confirmation-replay', development=development) != panel:
        raise ValueError('Fixture archive did not reproduce through its public replay path')

    def describe(result, archive):
        names = ('planSha256', 'logicalCallsByRole', 'physicalCallsByRole', 'searchCallsByArm', 'outcome')
        return {**{name: result[name] for name in names}, 'selectedSha256': digest(result['selected']),
                'admissionSha256': digest(result['admissionDecisions']), 'heldOutSha256': digest(result['holdout']),
                'archiveSha256': {name: sha256((archive / name).read_bytes()).hexdigest() for name in staged.ARCHIVE_FILES}}

    return {'development': describe(dev, development), 'confirmation': describe(panel, confirmation)}


def measure():
    report = {}
    with TemporaryDirectory(prefix='cpo-combined-staged-') as scratch:
        for name, fixture in (('all-rewrites-faulted', grounded_staged_fixture.respond),
                              ('perfect-ticket-rewrite', mixed_fixture)):
            root = Path(scratch) / name
            root.mkdir()
            single = run_pair(root / 'final-draft', fixture, certify_opening=False)
            combined = run_pair(root / 'combined', fixture, certify_opening=True)
            for phase, baseline in single.items():
                observed = combined[phase]
                if any(observed[key] != baseline[key] for key in ('selectedSha256', 'admissionSha256', 'heldOutSha256')):
                    raise ValueError('The combined certificate changed a prompt or matched result')
                if any(observed['searchCallsByArm'][arm] != baseline['searchCallsByArm'][arm] for arm in staged.ARMS[1:]):
                    raise ValueError('A native GEPA control used a different search allowance')
            if combined['development']['searchCallsByArm']['cpo'] > single['development']['searchCallsByArm']['cpo']:
                raise ValueError('The opening certificate added search calls')
            report[name] = {'finalDraftOnly': single, 'combined': combined}
    return {'schema': 'portable-grounded-staged-combined-rehearsal-v1',
            'fixtureAnalysisSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'profiles': report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out is not None and args.out.exists():
        parser.error('Use a fresh report path')
    text = json.dumps(measure(), indent=2, sort_keys=True) + '\n'
    if args.out is None:
        print(text, end='')
    else:
        with args.out.open('x') as output:
            output.write(text)


if __name__ == '__main__':
    main()
