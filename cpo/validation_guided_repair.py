"""Chain training edits, using validation misses to find subsequent evidence."""

from collections import Counter
from dataclasses import replace

from .expected_cost_proposal_cycle import ExpectedCostProposalCycleResult
from .family_qualification import certify_family_qualification
from .opening_repair_cycle import _first_proposal
from .opening_screen_cycle import run_opening_screen_cycle
from .optimizer import balanced_order
from .routed_repair_cycle import _categorical_features, _fallback_probes, _rank_probes


def run_validation_guided_repair_cycle(
    incumbent, train, validation, holdout, evaluate, propose, *, input_features, opening_pair,
    metric_limit, qualify, diagnostic_prompt=None, screen_rows=8, repeats=1, minimum_gain=1,
    seed=0, field_credit=False, qualification_limit=None, retry_probe_limit=0,
):
    """Stage up to three training-supported edits before one full validation.

    The screened opening is the validated fallback. After an edit, check its
    remaining opening validation misses to route the next training probes.
    Input features affect routing, and only training observations reach the
    proposer. The final edit chain needs a strict validation gain and must
    preserve the opening's critical passes and score in every family.
    Qualification independently compares the nominee with the incumbent.

    A positive retry_probe_limit funds additional, less-exposed training rows
    when a residual miss has no failing routed probe. The cap is shared across
    the later stages, and the full final validation reserve still applies.
    """
    if not callable(input_features):
        raise ValueError('The input feature extractor must be callable')
    if diagnostic_prompt is not None and not callable(diagnostic_prompt):
        raise ValueError('The diagnostic prompt transform must be callable')
    if qualification_limit is not None and (type(qualification_limit) is not int or qualification_limit < 0):
        raise ValueError('Qualification limit must be a nonnegative integer')
    if type(retry_probe_limit) is not int or retry_probe_limit < 0:
        raise ValueError('The retry probe cap must be a nonnegative integer')

    train, validation, holdout = tuple(train), tuple(validation), tuple(holdout)
    ledger, vectors = {}, {}

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

    def vector(row):
        if row.id not in vectors:
            vectors[row.id] = _categorical_features(row, input_features)
        return vectors[row.id]

    def deferred(*_):
        raise RuntimeError('Only the final nominee can enter qualification')

    opening = run_opening_screen_cycle(
        incumbent, train, validation, holdout, observe, opening_pair=opening_pair,
        metric_limit=metric_limit, qualify=deferred, screen_rows=screen_rows, repeats=repeats,
        minimum_gain=minimum_gain, seed=seed, field_credit=field_credit, qualification_limit=0,
    )
    result = opening.search
    anchor = parent = result.prompt
    if anchor == incumbent:
        return opening

    opening_passes = [ledger[anchor, row.id].passed for row in validation]
    event = {'kind': 'staged-repairs', 'stages': [], 'status': 'opening-retained'}
    reflections = 0
    if not all(opening_passes) and len(ledger) + len(validation) < metric_limit:
        training = balanced_order(train, seed)
        ranked = _rank_probes(training, validation, opening_passes, vector)
        opening_misses = [row for row, hit in zip(validation, opening_passes, strict=True) if not hit]
        used, witnesses, proposed = set(), [], {anchor, incumbent}
        retry_remaining = retry_probe_limit
        for step in range(3):
            capacity = metric_limit - len(ledger) - len(validation)
            if capacity <= 0:
                break
            available = [row for row in ranked if row.id not in used]
            if step == 0:
                candidates = available[:min(2, capacity)]
            else:
                checked = event.setdefault('residualChecks', [])
                remaining_miss = None
                for row in opening_misses:
                    if len(ledger) + len(validation) >= metric_limit:
                        break
                    hit = observe(parent, row).passed
                    checked.append((step, row.id, hit))
                    if not hit:
                        remaining_miss = row
                        break
                if remaining_miss is None:
                    break
                capacity = metric_limit - len(ledger) - len(validation)
                candidates = _rank_probes([*witnesses, *available], (remaining_miss,), (False,), vector)
                candidates = candidates[:min(4, capacity)]

            probe_prompt = diagnostic_prompt(parent) if diagnostic_prompt is not None else parent
            if not isinstance(probe_prompt, str) or not probe_prompt.strip():
                raise ValueError('The diagnostic prompt transform must return a nonempty prompt')
            feedback = []
            for row in candidates:
                reply = observe(probe_prompt, row)
                feedback.append((row, reply))
                used.add(row.id)
                if not reply.passed:
                    break
            retry_rows = []
            fallback_limit = 12 if step == 0 else retry_remaining
            if fallback_limit and all(reply.passed for _, reply in feedback):
                capacity = metric_limit - len(ledger) - len(validation)
                for row in _fallback_probes(training, used, vector, min(fallback_limit, capacity)):
                    reply = observe(probe_prompt, row)
                    used.add(row.id)
                    feedback.append((row, reply))
                    if step > 0:
                        retry_rows.append(row.id)
                    if not reply.passed:
                        break
            retry_remaining -= len(retry_rows)
            witnesses = [row for row, reply in feedback if not reply.passed]
            stage = {'rows': [row.id for row, _ in feedback], 'failedRows': [row.id for row in witnesses]}
            if retry_rows:
                stage['retryRows'] = retry_rows
            event['stages'].append(stage)
            if not witnesses:
                break
            repair = _first_proposal(propose(parent, feedback, [], 1))
            reflections += 1
            if not isinstance(repair, str) or not repair.strip() or repair in proposed:
                break
            parent = repair
            proposed.add(parent)

    if parent != anchor:
        gains = Counter()
        critical_loss = False
        for row in validation:
            before, after = ledger[anchor, row.id].passed, observe(parent, row).passed
            gains[row.family] += after - before
            critical_loss |= row.critical and before and not after
        if not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) > 0:
            anchor = parent
            event['status'] = 'accepted'
        else:
            event['status'] = 'rejected'

    search = replace(result, prompt=anchor, evaluations=len(ledger), reflections=reflections,
                     events=[*result.events, event])
    proof = certify_family_qualification(incumbent, anchor, holdout, qualify, repeats=repeats,
                                          minimum_gain=minimum_gain, seed=seed, evaluation_limit=qualification_limit)
    return ExpectedCostProposalCycleResult(search, proof)
