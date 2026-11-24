"""Require stronger independent proof for a second-case repair."""

from dataclasses import replace

from .paired_qualification import QualificationObservation, certify_paired_qualification
from .qualification_prefix_cycle import run_qualification_prefix_cycle


TWO_GAIN = 'two-gain'
NO_LOSS = 'no-paired-loss'
GUARDS = (TWO_GAIN, NO_LOSS)


def _extend_proof(incumbent, decision, rows, qualify, *, guard, minimum_gain, seed):
    """Extend a promoted proof without rereading any prompt and case."""
    reads = list(decision.observations)
    grades = {(item.prompt, item.row_id, item.repeat): item.passed for item in reads}
    originals = {row.id: row for row in rows}
    challenger = decision.prompt
    if guard == TWO_GAIN:
        minimum_gain = max(minimum_gain, 2)
        if decision.lower_gain >= minimum_gain:
            return decision
    else:
        rows = tuple(replace(row, critical=True) for row in rows)

    def reuse(prompt, row, repeat):
        key = prompt, row.id, repeat
        if key not in grades:
            passed = qualify(prompt, originals[row.id], repeat)
            if type(passed) is not bool:
                raise ValueError('Qualification requires exact boolean outcomes')
            grades[key] = passed
            reads.append(QualificationObservation(prompt, row.id, repeat, passed))
        return grades[key]

    strengthened = certify_paired_qualification(incumbent, challenger, rows, reuse,
                                                minimum_gain=minimum_gain, seed=seed)
    favorable = sum(item.passed == (item.prompt == challenger) for item in reads)
    return replace(strengthened, observations=tuple(reads), lower_gain=favorable - len(rows),
                   upper_gain=favorable + len(rows) - len(reads))


def run_second_case_qualification_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                        metric_limit, qualify, opening_screen, switch_screen, guard,
                                        minimum_gain=1, seed=0):
    """Strengthen only promotions based on a paid repair on the second case.

    Reuse the original qualification prefix and any later grades. Require a
    gain of at least two or preserve every incumbent pass on qualification.
    The strengthened proof shares the original two-sided qualification
    envelope. Original rejects and ordinary opening repairs stay settled.
    """
    if guard not in GUARDS:
        raise ValueError('Use a supported qualification guard')
    validation, rows = tuple(validation), tuple(qualification_rows)
    on_second = False

    def track_switch(base, roster, panel, observe, cap):
        nonlocal on_second
        if len(panel) < 2 or any(row.critical for row in panel):
            return switch_screen(base, roster, panel, observe, cap)
        grades = {}
        second = panel[1]

        def track(prompt, row):
            reply = observe(prompt, row)
            if row == second:
                grades[prompt] = reply.passed
            return reply

        result, counts = switch_screen(base, roster, panel, track, cap)
        on_second = grades.get(base) is False and grades.get(result.finalist) is True
        return result, counts

    screens = (opening_screen,) + (track_switch,) * (len(rows) - 1)
    original = run_qualification_prefix_cycle(incumbent, candidates, validation, rows, evaluate,
                                               metric_limit=metric_limit, qualify=qualify, screens=screens,
                                               minimum_gain=minimum_gain, seed=seed)
    if not original.promoted or not on_second:
        return original
    checked = _extend_proof(incumbent, original.qualification, rows, qualify, guard=guard,
                            minimum_gain=minimum_gain, seed=seed)
    return replace(original, qualification=checked)
