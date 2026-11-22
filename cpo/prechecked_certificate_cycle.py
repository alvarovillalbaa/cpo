"""Screen a fixed pool after a qualification precheck and certify one nominee."""

from dataclasses import replace

from .challenger import certify_challenger
from .expected_qualification import _advance, _bounds, _minimum_expected_reads, _pass_rate, _settled
from .fixed_pool_cycle import FixedPoolCycleResult
from .paired_qualification import QualificationDecision, QualificationObservation, certify_paired_qualification
from .single_finalist import FinalistResult


def _screen(incumbent, candidates, rows, evaluate, metric_limit):
    paid = 0

    def observe(prompt, row):
        nonlocal paid
        reply = evaluate(prompt, row)
        if type(reply.passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        paid += 1
        return reply

    base = {row.id: observe(incumbent, row).passed for row in rows}
    witness = next((row for row in rows if not base[row.id]), None)
    if witness is not None:
        # Keep enough fresh reads to finish one panel after its screening probe.
        slots = max(0, metric_limit - len(rows) - (len(rows) - 1))
        probes = {prompt: observe(prompt, witness).passed for prompt in candidates[:slots]}
        order = sorted(rows, key=lambda row: base[row.id])
        for prompt in sorted(probes, key=probes.__getitem__, reverse=True):
            decision = certify_challenger(order, base, lambda row: observe(prompt, row),
                                         metric_limit=metric_limit - paid,
                                         observed={witness.id: probes[prompt]})
            if decision.status == 'promote':
                counts = ((sum(base.values()), len(base)),
                          (sum(decision.observations.values()), len(decision.observations)))
                return FinalistResult(prompt, prompt, paid), counts
    return FinalistResult(incumbent, None, paid), None


def _finish(incumbent, nominee, rows, read, history, counts, minimum_gain, seed):
    size = len(rows)
    if size > 8 or len({row.family for row in rows}) > 1 or any(row.critical for row in rows):
        prefix = {reply.row_id: reply.passed for reply in history}

        def reuse(prompt, row, repeat):
            if prompt == incumbent and row.id in prefix:
                return prefix[row.id]
            return read(prompt, row, repeat)

        decision = certify_paired_qualification(incumbent, nominee, rows, reuse, seed=seed, minimum_gain=minimum_gain)
        favorable = sum(reply.passed == (reply.prompt == nominee) for reply in history)
        return replace(decision, observations=tuple(history), lower_gain=favorable - size,
                       upper_gain=favorable + size - len(history))

    prompts = incumbent, nominee
    rates = (4 - _pass_rate(*counts[0]), _pass_rate(*counts[1]))
    sizes = (size,)
    state = ((len(history), 0, sum(not reply.passed for reply in history)),)
    while True:
        low, high = _bounds(sizes, state)
        status = _settled(low, high, minimum_gain)
        if status is not None:
            winner = nominee if status == 'promoted' else incumbent
            return QualificationDecision(status, winner, tuple(history), low[0], high[0])
        _, (_, side) = _minimum_expected_reads(sizes, rates, minimum_gain, state)
        passed = read(prompts[side], rows[state[0][side]], 0)
        state = _advance(state, 0, side, passed == bool(side))


def run_prechecked_certificate_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                     metric_limit, qualify, minimum_gain=1, seed=0):
    """Nominate from a shared first-miss screen and qualify an exact gain.

    The incumbent precheck stops at the first qualification miss. Search
    receives only validation replies, and a nominee spends at most a complete
    paired qualification panel, including the precheck. Up to eight
    noncritical qualification rows in one family use expected-cost ordering.
    Other panels use the seeded certificate and reuse the incumbent prefix.
    Both callbacks return one exact grade per prompt and case.
    """
    candidates, validation, rows = tuple(candidates), tuple(validation), tuple(qualification_rows)
    ids = {row.id for row in (*validation, *rows)}
    if not validation or not rows or len(ids) != len(validation) + len(rows):
        raise ValueError('Validation and qualification must be nonempty, distinct and disjoint')
    if incumbent in candidates or len(set(candidates)) != len(candidates):
        raise ValueError('The pool needs distinct challengers besides the incumbent')
    if type(metric_limit) is not int or metric_limit < len(validation):
        raise ValueError('The evaluation cap must fund the incumbent validation panel')
    if type(minimum_gain) is not int or minimum_gain < 1:
        raise ValueError('The qualification gain must be a positive integer')

    retained = FinalistResult(incumbent, None, 0)
    if not candidates:
        return FixedPoolCycleResult(retained, QualificationDecision('rejected', incumbent, (), 0, 0))
    if minimum_gain > len(rows):
        decision = QualificationDecision('rejected', incumbent, (), -len(rows), len(rows))
        return FixedPoolCycleResult(retained, decision)
    history = []

    def read(prompt, row, repeat):
        passed = qualify(prompt, row, repeat)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        history.append(QualificationObservation(prompt, row.id, repeat, passed))
        return passed

    for row in rows:
        if not read(incumbent, row, 0):
            break
    else:
        return FixedPoolCycleResult(retained, QualificationDecision('rejected', incumbent, tuple(history),
                                                                     -len(rows), 0))

    selection, counts = _screen(incumbent, candidates, validation, evaluate, metric_limit)
    if selection.prompt == incumbent:
        decision = QualificationDecision('rejected', incumbent, tuple(history), 0, 0)
    else:
        decision = _finish(incumbent, selection.prompt, rows, read, history, counts, minimum_gain, seed)
    return FixedPoolCycleResult(selection, decision)
