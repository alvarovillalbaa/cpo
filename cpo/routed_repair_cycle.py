"""Route up to two repairs using input features and paid validation outcomes."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import replace

from .expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from .expected_qualification import certify_expected_qualification
from .opening_repair_cycle import _first_proposal
from .opening_screen_cycle import run_opening_screen_cycle
from .optimizer import balanced_order
from .paired_qualification import certify_paired_qualification


def _categorical_features(row, input_features):
    features = input_features(row)
    if not isinstance(features, Mapping) or any(
        not isinstance(name, str) or type(value) not in (str, int, bool)
        for name, value in features.items()
    ):
        raise ValueError('Input features require a mapping from strings to strings, integers, or booleans')
    return tuple((name, type(value), value) for name, value in features.items())


def _rank_probes(training, validation, passed, features):
    failures, successes = Counter(), Counter()
    for row, exact_pass in zip(validation, passed, strict=True):
        (successes if exact_pass else failures).update(features(row))
    pass_count = sum(passed)
    miss_count = len(passed) - pass_count
    weights = {key: max(0, hits * pass_count - successes[key] * miss_count) for key, hits in failures.items()}
    if not any(weights.values()):
        weights = failures
    return sorted(training, key=lambda row: sum(weights.get(key, 0) for key in features(row)), reverse=True)


def run_routed_repair_cycle(incumbent, train, validation, holdout, evaluate, propose, *, input_features,
                            opening_pair, metric_limit, qualify, diagnostic_prompt=None, max_training_probes=2,
                            screen_rows=8, repeats=1, minimum_gain=1, seed=0, field_credit=False,
                            qualification_limit=None):
    """Route training probes using input-only categorical features of each row.

    Each repair funds a full validation panel before evaluating training probes.
    The proposer receives the full parent and training observations only. The
    optional diagnostic transform supplies the prompt evaluated on training.
    The second repair may build on a row-preserving tie, but the nominee must
    improve exact validation passes while preserving critical passes and scores
    by family. Only the final nominee enters independent qualification.
    """
    if not callable(input_features):
        raise ValueError('The input feature extractor must be callable')
    if diagnostic_prompt is not None and not callable(diagnostic_prompt):
        raise ValueError('The diagnostic prompt transform must be callable')
    if type(max_training_probes) is not int or max_training_probes < 0:
        raise ValueError('The training probe cap must be a nonnegative integer')
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')

    train, validation, holdout = tuple(train), tuple(validation), tuple(holdout)
    ledger, feature_cache = {}, {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in ledger:
            if len(ledger) >= metric_limit:
                raise RuntimeError('Search evaluation budget exhausted')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Search observations require an exact boolean outcome')
            if field_credit and (type(reply.matched_fields) is not int
                                 or not 0 <= reply.matched_fields <= row.fields
                                 or reply.passed != (reply.matched_fields == row.fields)):
                raise ValueError('Field observations must match the row capacity and exact-pass decision')
            ledger[key] = reply
        return ledger[key]

    def features(row):
        if row.id not in feature_cache:
            feature_cache[row.id] = _categorical_features(row, input_features)
        return feature_cache[row.id]

    def qualification_deferred(*_):
        raise RuntimeError('Only the final nominee can enter qualification')

    opening = run_opening_screen_cycle(
        incumbent, train, validation, holdout, observe, opening_pair=opening_pair,
        metric_limit=metric_limit, qualify=qualification_deferred, screen_rows=screen_rows,
        repeats=repeats, minimum_gain=minimum_gain, seed=seed, field_credit=field_credit, qualification_limit=0,
    )
    result = opening.search
    accepted = parent = result.prompt
    if accepted == incumbent:
        return opening

    events, used, reflections = list(result.events), set(), 0
    training = balanced_order(train, seed)
    for attempt in range(2):
        passed = [ledger[parent, row.id].passed for row in validation]
        remaining = [row for row in training if row.id not in used]
        funded = min(max_training_probes, len(remaining), metric_limit - len(ledger) - len(validation))
        if all(passed) or funded <= 0:
            break
        probes = _rank_probes(remaining, validation, passed, features)[:funded]
        used.update(row.id for row in probes)
        probe_prompt = diagnostic_prompt(parent) if diagnostic_prompt is not None else parent
        if not isinstance(probe_prompt, str) or not probe_prompt.strip():
            raise ValueError('The diagnostic prompt transform must return a nonempty prompt')
        feedback = [(row, observe(probe_prompt, row)) for row in probes]
        event = {'kind': 'routed-probes', 'probeRows': [row.id for row in probes], 'status': 'no-training-error'}
        events.append(event)
        if all(reply.passed for _, reply in feedback):
            break

        repair = _first_proposal(propose(parent, feedback, [], 1))
        reflections += 1
        if not isinstance(repair, str) or not repair.strip():
            event['status'] = 'no-repair'
            break
        if repair in (incumbent, parent, accepted):
            event['status'] = 'duplicate'
            break
        gains = Counter()
        critical_loss, row_preserving = False, True
        for row in validation:
            old, new = ledger[accepted, row.id], observe(repair, row)
            critical_loss |= row.critical and old.passed and not new.passed
            row_preserving &= old.passed == new.passed and (
                not field_credit or new.matched_fields >= old.matched_fields)
            gains[row.family] += new.passed - old.passed
        if not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) > 0:
            event['status'] = 'accepted'
            accepted = parent = repair
        elif attempt == 0 and row_preserving:
            event['status'] = 'provisional'
            parent = repair
        else:
            event['status'] = 'rejected'
            break

    result = replace(result, prompt=accepted, evaluations=len(ledger), reflections=reflections, events=events)
    options = dict(repeats=repeats, minimum_gain=minimum_gain, seed=seed, evaluation_limit=qualification_limit)
    if qualification_limit is not None and qualification_limit < 2 * repeats * len(holdout):
        decision = certify_paired_qualification(incumbent, accepted, holdout, qualify, **options)
    else:
        counts = tuple((sum(ledger[prompt, row.id].passed for row in validation), len(validation))
                       for prompt in (incumbent, accepted))
        decision = certify_expected_qualification(incumbent, accepted, holdout, qualify,
                                                 validation_counts=counts, **options)
    return ExpectedCostProposalCycleResult(result, decision)
