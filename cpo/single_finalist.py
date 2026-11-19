"""Screen a fixed prompt pool and certify a single finalist."""

from dataclasses import dataclass

from .challenger import certify_challenger
from .optimizer import Observation


@dataclass(frozen=True)
class FinalistResult:
    prompt: str
    finalist: str | None
    evaluations: int


def select_single_finalist(incumbent, candidates, validation, evaluate, *, metric_limit, screen='ordered'):
    """Use shared probes to nominate one challenger within a fresh-call cap.

    The gain-based modes screen on a row the incumbent failed. The first-gain
    mode stops screening at the first pass. Other modes can break ties with
    a second shared probe when the cap can still fund the finalist suffix.
    The finalist needs an exact gain and must preserve critical passes.
    """
    candidates, rows = tuple(candidates), tuple(validation)
    if incumbent in candidates or len(candidates) != len(set(candidates)):
        raise ValueError('The pool needs distinct challengers besides the incumbent')
    if not rows or len({row.id for row in rows}) != len(rows):
        raise ValueError('The validation panel needs distinct, nonempty rows')
    if type(metric_limit) is not int or metric_limit < len(rows):
        raise ValueError('The evaluation cap must fund the incumbent')
    if screen not in ('ordered', 'gain-first', 'first-gain'):
        raise ValueError('Unknown finalist screening policy')

    paid = 0

    def observe(prompt, row):
        nonlocal paid
        passed = evaluate(prompt, row).passed
        if type(passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        paid += 1
        return passed

    if not candidates:
        return FinalistResult(incumbent, None, paid)
    baseline = {row.id: observe(incumbent, row) for row in rows}
    if all(baseline.values()):
        return FinalistResult(incumbent, None, paid)

    probes = rows if screen == 'ordered' else sorted(rows, key=lambda row: baseline[row.id])
    first = probes[0]
    if screen == 'first-gain':
        available = metric_limit - paid - (len(rows) - 1)
        finalist = next((prompt for prompt in candidates[:max(0, available)] if observe(prompt, first)), None)
        if finalist is None:
            return FinalistResult(incumbent, None, paid)
        evidence = {finalist: {first.id: True}}
    else:
        if paid + len(candidates) + len(rows) - 1 > metric_limit:
            return FinalistResult(incumbent, None, paid)
        evidence = {prompt: {first.id: observe(prompt, first)} for prompt in candidates}
        best = max(item[first.id] for item in evidence.values())
        finalists = [prompt for prompt in candidates if evidence[prompt][first.id] == best]
        if len(finalists) > 1 and len(rows) > 1 and paid + len(finalists) + len(rows) - 2 <= metric_limit:
            second = probes[1]
            for prompt in finalists:
                evidence[prompt][second.id] = observe(prompt, second)
            finalists.sort(key=lambda prompt: evidence[prompt][second.id], reverse=True)
        finalist = finalists[0]
    order = sorted(rows, key=lambda row: baseline[row.id])
    result = certify_challenger(order, baseline, lambda row: Observation(observe(finalist, row), {}),
                                metric_limit=metric_limit - paid, observed=evidence[finalist])
    selected = finalist if result.status == 'promote' else incumbent
    return FinalistResult(selected, finalist, paid)
