"""Use the established round order on cold four-prompt Halving boards."""

from . import HalvingSearch
from .lookahead import LookaheadHalving


class CachedLookaheadHalving(LookaheadHalving):
    """Use lookahead when it has paid evidence, with a cheaper cold path."""

    def select(self, candidates, validation, evaluate, *, logical_limit=8):
        prompts, cases = tuple(candidates), tuple(validation)
        if (type(logical_limit) is int and logical_limit == 8 and len(prompts) >= 4 and len(cases) >= 3
                and not self.exhausted and all(isinstance(prompt, str) for prompt in prompts)):
            width, rounds = len(prompts), (len(prompts) - 1).bit_length()
            while rounds * width > logical_limit:
                width = (width + 1) // 2
                rounds -= 1
            if width == 4:
                keys = tuple((prompt, case) for prompt in prompts[:width] for case in cases[:3])
                if not any(key in self._paid for key in keys):
                    return HalvingSearch.select(self, prompts, cases, evaluate, logical_limit=logical_limit)
        return super().select(prompts, cases, evaluate, logical_limit=logical_limit)
