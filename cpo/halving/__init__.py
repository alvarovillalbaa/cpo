"""Certify the exact Successive Halving winner with fewer paid grades."""

__all__ = ['HalvingSearch']


class _LookupLimit(Exception):
    pass


class HalvingSearch:
    """Share paid binary grades and a new-lookup ceiling across selections.

    Pass candidate prompts in tie-break order and validation case IDs in
    evaluation order. The logical limit sets the ordinary Halving schedule.
    Skipped and cached grades leave that schedule unchanged. An unfinished
    selection returns None and stops the search at its physical ceiling.
    """

    def __init__(self, *, metric_limit, paid=()):
        if type(metric_limit) is not int or metric_limit < 0:
            raise ValueError('The new-lookup limit must be a nonnegative integer')
        self._paid = dict(paid)
        if any(type(value) is not bool for value in self._paid.values()):
            raise ValueError('Previously paid grades must be exact booleans')
        self._remaining = metric_limit
        self.evaluations = 0
        self.exhausted = False

    @property
    def observations(self):
        return dict(self._paid)

    def select(self, candidates, validation, evaluate, *, logical_limit=8):
        active, cases = list(candidates), tuple(validation)
        if not active or any(not isinstance(prompt, str) for prompt in active) or len(set(active)) != len(active):
            raise ValueError('Halving requires a distinct, ordered roster of prompts')
        if not cases or len(set(cases)) != len(cases):
            raise ValueError('Halving requires distinct validation cases')
        if type(logical_limit) is not int or logical_limit < 0:
            raise ValueError('The logical schedule limit must be a nonnegative integer')
        if self.exhausted:
            return None

        def read(prompt, case):
            if not self._remaining:
                raise _LookupLimit
            self._remaining -= 1
            self.evaluations += 1
            grade = evaluate(prompt, case)
            if type(grade) is not bool:
                raise ValueError('Halving requires exact boolean grades')
            self._paid[prompt, case] = grade

        rounds = (len(active) - 1).bit_length()
        depth = scheduled = 0
        try:
            for step in range(rounds):
                extra = min((logical_limit - scheduled) // ((rounds - step) * len(active)), len(cases) - depth)
                scheduled += extra * len(active)
                depth += extra
                active = self._round(active, cases[:depth], read)
        except _LookupLimit:
            self.exhausted = True
            return None
        return active[0]

    def _round(self, active, prefix, read):
        keep = (len(active) + 1) // 2
        order = {prompt: index for index, prompt in enumerate(active)}
        while True:
            missing, low, high = {}, {}, {}
            for prompt in active:
                missing[prompt] = [case for case in prefix if (prompt, case) not in self._paid]
                observed = sum(self._paid.get((prompt, case), False) for case in prefix)
                low[prompt] = observed, -order[prompt]
                high[prompt] = observed + len(missing[prompt]), -order[prompt]
            ranked = sorted(active, key=low.__getitem__, reverse=True)
            for index, prompt in enumerate(ranked[:keep]):
                rival = max(ranked[index + 1:], key=high.__getitem__)
                if low[prompt] < high[rival]:
                    undecided = prompt if missing[prompt] else rival
                    read(undecided, missing[undecided][0])
                    break
            else:
                return ranked[:keep]
