"""Prove that the first rewrite wins the adaptive opening before scoring every row."""


def certify_opening_dominance(incumbent, rewrite, rows, observe, *, field_credit):
    """Return the evidence for a strictly dominant rewrite, if it can be established.

    The caller supplies a memoized evaluator and reserves capacity for the whole
    opening pair before attempting the proof. The returned pass list is partial
    unless the proof also establishes a perfect rewrite.
    """
    anchor = [(row, observe(incumbent, row)) for row in rows]
    misses = [(row, old) for row, old in anchor if not old.passed]
    if not misses:
        return None

    passed = []
    for row, old in anchor:
        if old.passed:
            if not observe(rewrite, row).passed:
                return None
            passed.append(row.id)

    field_gain = 0
    unmatched_incumbent_fields = sum(old.matched_fields for _, old in misses) if field_credit else 0
    for row, old in misses:
        new = observe(rewrite, row)
        if new.passed:
            passed.append(row.id)
            if len(passed) == len(rows):
                return {'kind': 'certified-opening-rewrite', 'prompt': rewrite, 'incumbentMiss': row.id,
                        'passed': sorted(passed)}
            return {'kind': 'certified-opening-dominance', 'prompt': rewrite, 'incumbentMiss': row.id,
                    'knownPassed': sorted(passed)}
        if field_credit:
            field_gain += new.matched_fields - old.matched_fields
            unmatched_incumbent_fields -= old.matched_fields
            if field_gain > unmatched_incumbent_fields:
                return {'kind': 'certified-opening-dominance', 'prompt': rewrite, 'knownPassed': sorted(passed),
                        'matchedFieldGainLowerBound': field_gain - unmatched_incumbent_fields}
    return None
