"""Run an opening screen with one funded repair before qualification."""

from collections import Counter
from dataclasses import replace

from .expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from .expected_qualification import certify_expected_qualification
from .opening_screen_cycle import run_opening_screen_cycle
from .optimizer import ProposalBatch, ProposalPair, balanced_order
from .paired_qualification import certify_paired_qualification


def _first_proposal(proposals):
    if isinstance(proposals, ProposalPair):
        return proposals.rewrite
    if isinstance(proposals, ProposalBatch):
        proposals = proposals.prompts
    if isinstance(proposals, str) or proposals is None:
        return proposals
    return next(iter(proposals), None)


def run_opening_repair_cycle(incumbent, train, validation, holdout, evaluate, propose, *, opening_pair,
                             metric_limit, qualify, diagnostic_prompt=None, max_training_probes=2,
                             screen_rows=8, repeats=1, minimum_gain=1, seed=0, field_credit=False,
                             qualification_limit=None):
    """Use up to one repair to address validation misses in the opening nominee.

    diagnostic_prompt optionally maps the full nominee to the variant evaluated
    on training. propose receives the full nominee and those training replies.
    A chosen repair must improve the full validation score, preserve critical
    passes and preserve scores by family. Only the final nominee qualifies.
    """
    if diagnostic_prompt is not None and not callable(diagnostic_prompt):
        raise ValueError('The diagnostic prompt transform must be callable')
    if type(max_training_probes) is not int or max_training_probes < 0:
        raise ValueError('The training probe cap must be a nonnegative integer')
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')

    train, validation, holdout = tuple(train), tuple(validation), tuple(holdout)
    ledger = {}

    def observe(prompt, row):
        key = (prompt, row.id)
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

    def qualification_deferred(*_):
        raise RuntimeError('Only the final nominee can enter qualification')

    opening = run_opening_screen_cycle(
        incumbent, train, validation, holdout, observe, opening_pair=opening_pair,
        metric_limit=metric_limit, qualify=qualification_deferred, screen_rows=screen_rows,
        repeats=repeats, minimum_gain=minimum_gain, seed=seed, field_credit=field_credit, qualification_limit=0,
    )
    result = opening.search
    parent = result.prompt
    if parent == incumbent:
        return opening

    nominee, reflections, status = parent, 0, 'validation-complete'
    probes = []
    if any(not ledger[parent, row.id].passed for row in validation):
        funded = min(max_training_probes, metric_limit - len(ledger) - len(validation))
        status = 'unfunded'
        if funded > 0:
            probe_prompt = diagnostic_prompt(parent) if diagnostic_prompt is not None else parent
            if not isinstance(probe_prompt, str) or not probe_prompt.strip():
                raise ValueError('The diagnostic prompt transform must return a nonempty prompt')
            feedback = [(row, observe(probe_prompt, row)) for row in balanced_order(train, seed)[:funded]]
            probes = [{'row_id': row.id, 'passed': reply.passed} for row, reply in feedback]
            status = 'no-training-error'
            if any(not reply.passed for _, reply in feedback):
                repair = _first_proposal(propose(parent, feedback, [], 1))
                reflections = 1
                status = 'no-repair'
                if isinstance(repair, str) and repair.strip() and repair not in (incumbent, parent):
                    gains = Counter()
                    critical_loss = False
                    for row in validation:
                        old = ledger[parent, row.id].passed
                        new = observe(repair, row).passed
                        critical_loss |= row.critical and old and not new
                        gains[row.family] += new - old
                    accepted = not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) > 0
                    status = 'accepted' if accepted else 'rejected'
                    nominee = repair if accepted else parent

    event = {'kind': 'targeted-repair', 'prompt': nominee, 'status': status,
             'addedLookups': len(ledger) - result.evaluations, 'probes': probes}
    result = replace(result, prompt=nominee, evaluations=len(ledger), reflections=reflections,
                     events=[*result.events, event])
    options = dict(repeats=repeats, minimum_gain=minimum_gain, seed=seed, evaluation_limit=qualification_limit)
    if qualification_limit is not None and qualification_limit < 2 * repeats * len(holdout):
        decision = certify_paired_qualification(incumbent, nominee, holdout, qualify, **options)
    else:
        counts = tuple((sum(ledger[prompt, row.id].passed for row in validation), len(validation))
                       for prompt in (incumbent, nominee))
        decision = certify_expected_qualification(incumbent, nominee, holdout, qualify,
                                                 validation_counts=counts, **options)
    return ExpectedCostProposalCycleResult(result, decision)
