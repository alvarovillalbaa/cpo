"""Bound paid requests by the samples the paired-opening trial can share."""

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from benchmarks import grounded_staged_paired_opening_comparison as parent
from benchmarks import grounded_staged_policy_comparison as comparison
from cpo._contract import digest


PARENT_SEAL = '3d6dfcaee13796276e6bca057cbe1bf9d087cc388d0ab3bde77ac05b483017f3'
PROTOCOL = 'portable-grounded-staged-paired-opening-budget-v1'
ARM, ARMS = parent.ARM, parent.ARMS
ARCHIVE_FILES, PricedReply, grade = parent.ARCHIVE_FILES, parent.PricedReply, parent.grade
DYNAMIC = ('cpo', 'gepa-sequential', 'gepa-batched')
FIXED = frozenset(ARMS) - frozenset(DYNAMIC)
MAX_PROMPTS = 3 + len(DYNAMIC)
SOURCE = 'benchmarks/grounded_staged_paired_opening_budget.py'
BASELINE = comparison.grounded.BASELINE


def development_limits(groups, plan):
    repeats, cap = plan['repeats'], plan['searchCap']
    return {'reflection': plan['physicalLimitsByRole']['reflection'],
            'evaluation': sum(len(DYNAMIC) * cap + 3 * len(splits['validation']) for splits in groups.values()),
            'admission': sum(MAX_PROMPTS * len(splits['admission']) * repeats for splits in groups.values()),
            'qualification': sum(MAX_PROMPTS * len(splits['holdout']) * repeats for splits in groups.values())}


def prepare(development=None, **_):
    _, base, _ = parent.prepare()
    if digest(base) != PARENT_SEAL:
        raise ValueError('Use the exact paired-opening portable baseline')
    with patch.object(parent, 'replay', replay):
        groups, plan, prior = parent.prepare(development)
    plan = {**plan, 'protocol': PROTOCOL if prior is None else PROTOCOL + '-confirmation',
            'budgetParentPlanSha256': PARENT_SEAL, 'sourceSha256': {**plan['sourceSha256'],
                SOURCE: sha256(Path(__file__).read_bytes()).hexdigest()},
            'physicalSampleBound': {'dynamicEvaluationArms': list(DYNAMIC), 'maxFixedValidationPrompts': 3,
                                    'maxDevelopmentPromptsPerTask': MAX_PROMPTS}}
    if prior is None:
        limits = development_limits(groups, plan)
        plan['developmentRequestCeiling'] = sum(limits.values())
    else:
        counts = {task: len(set(prompts.values())) for task, prompts in prior['selected'].items()}
        if counts.keys() != groups.keys() or any(count > MAX_PROMPTS for count in counts.values()):
            raise ValueError('The bound development selected too many distinct prompts')
        count = sum(counts[task] * len(splits['confirmation']) * plan['repeats'] for task, splits in groups.items())
        limits = {'qualification': count}
        plan['confirmationPromptCountsByTask'] = counts
        plan['confirmationRequestCeiling'] = count
    if any(limit > plan['physicalLimitsByRole'][role] for role, limit in limits.items()):
        raise ValueError('The shared-sample proof exceeded the original envelope')
    return groups, {**plan, 'physicalLimitsByRole': limits}, prior


class Journal(parent.Journal):
    def __init__(self, wire, frozen, respond):
        super().__init__(wire, frozen, respond)
        groups = comparison.staged.cohorts()
        self.repeats = frozen['repeats']
        self.confirmation = frozen.get('confirmationPromptCountsByTask')
        scoring = 'holdout' if self.confirmation is None else 'confirmation'
        self.inputs = {task: {role: {row['input'] for split in parts for row in splits[split]}
                              for role, parts in (('evaluation', ('train', 'validation')),
                                                  ('fixed', ('validation',)), ('admission', ('admission',)),
                                                  ('qualification', (scoring,)))} for task, splits in groups.items()}
        self.schemas = {task: digest(comparison.staged.schema(splits)) for task, splits in groups.items()}
        self.openers = {}
        self.nominees = defaultdict(dict)
        self.scoring_prompts = defaultdict(set)

    def send(self, arm, request):
        task, role = request['task'], request['role']
        if task not in self.inputs or role not in self.physical_limits:
            raise ValueError('Request left its sealed task or stage')
        if role == 'reflection':
            if arm not in (*DYNAMIC, *FIXED, 'shared'):
                raise ValueError('Unknown reflection arm')
            reply = super().send(arm, request)
            if arm == 'shared':
                pair = comparison.grounded.proposals(reply, BASELINE, ('rewrite', 'repair'))
                if len(pair) != 2:
                    raise ValueError('The budget proof requires two distinct shared openers')
                self.openers[task] = frozenset((BASELINE, *pair))
            return reply

        prompt = request['instruction']
        fields = {'task', 'role', 'instruction', 'input', 'jsonSchema'}
        if role != 'evaluation':
            fields.add('repeat')
            value = request.get('repeat')
            if type(value) is not int or not 0 <= value < self.repeats:
                raise ValueError('Request left its sealed repetition range')
        if (request.keys() != fields or digest(request['jsonSchema']) != self.schemas[task] or not isinstance(prompt, str)
                or request['input'] not in self.inputs[task][role]):
            raise ValueError('Request left its sealed case or canonical sample identity')

        if role == 'qualification':
            if arm != 'paired':
                raise ValueError('Scoring must group identical prompts before dispatch')
            if self.confirmation is None:
                if prompt not in self.openers[task] and prompt not in self.nominees[task].values():
                    raise ValueError('Development scoring used a prompt outside the sealed pool')
            else:
                known = self.scoring_prompts[task]
                if prompt not in known and len(known) >= self.confirmation[task]:
                    raise ValueError('Confirmation exceeded the bound prompt count')
                known.add(prompt)
        elif arm in FIXED:
            if (prompt not in self.openers[task] or
                    role == 'evaluation' and request['input'] not in self.inputs[task]['fixed']):
                raise ValueError('A fixed opener left the shared validation or prompt pool')
        elif arm in DYNAMIC:
            if role == 'admission' and prompt != BASELINE:
                if self.nominees[task].setdefault(arm, prompt) != prompt:
                    raise ValueError('A dynamic arm submitted more than one nominee')
        else:
            raise ValueError('Unknown search or admission arm')
        return super().send(arm, request)


def run(seal, directory, respond, *, delivery, development=None, **_):
    with (patch.multiple(comparison, prepare=prepare, grade=grade, Journal=Journal),
          patch.object(comparison.staged, 'choose', parent.choose)):
        return parent._run(seal, directory, respond, delivery=delivery, development=development)


def replay(directory, fresh, *, development=None):
    with patch.object(comparison, 'run', run):
        return parent._replay(directory, fresh, development=development)
