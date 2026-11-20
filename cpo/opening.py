"""Collect shared opening proposals under an explicit output reservation."""

from dataclasses import dataclass
import json
from typing import Literal

from ._contract import unique_object


@dataclass(frozen=True)
class OpeningReply:
    status: Literal['completed', 'output_limit']
    text: str


@dataclass(frozen=True)
class OpeningAttempt:
    role: str
    max_output_tokens: int
    status: str
    accepted: tuple[str, ...]


@dataclass(frozen=True)
class OpeningResult:
    rewrite: str | None
    repair: str | None
    attempts: tuple[OpeningAttempt, ...]

    @property
    def prompts(self):
        return tuple(prompt for prompt in (self.rewrite, self.repair) if prompt is not None)


def collect_opening(initial, request, *, mode, pair_tokens, single_tokens, output_budget, max_instruction_bytes):
    """Read a pair, two separate replies, or missing slots after an initial pair.

    The callback accepts a role and its output cap. An explicit output-limit
    reply contributes no proposals. Callback failures propagate without another
    request. Each accepted instruction must fit its serialized JSON byte limit.
    """
    if mode not in ('pair', 'split', 'fill-missing'):
        raise ValueError('Unknown opening mode')
    if any(type(value) is not int or value < 1
           for value in (pair_tokens, single_tokens, output_budget, max_instruction_bytes)):
        raise ValueError('Opening budgets and byte bounds must be positive integers')
    slots = ('rewrite', 'repair')
    roles = ('pair',) if mode == 'pair' else slots if mode == 'split' else ('pair', *slots)
    caps = {'pair': pair_tokens, 'rewrite': single_tokens, 'repair': single_tokens}
    found, attempts = {}, []
    remaining = output_budget
    for role in roles:
        cap = caps[role]
        if role in found or cap > remaining:
            continue
        reply = request(role, cap)
        if (not isinstance(reply, OpeningReply) or reply.status not in ('completed', 'output_limit')
                or not isinstance(reply.text, str)):
            raise ValueError('Opening requests need a completed or explicit output-limit reply')
        remaining -= cap
        accepted = []
        if reply.status == 'completed':
            try:
                payload = json.loads(reply.text, object_pairs_hook=unique_object)
            except ValueError:
                payload = None
            keys = slots if role == 'pair' else ('instruction',)
            if isinstance(payload, dict) and set(payload).issubset(keys):
                for key in keys:
                    prompt = payload.get(key)
                    if not isinstance(prompt, str):
                        continue
                    prompt = prompt.strip()
                    if (not prompt or prompt == initial or prompt in found.values()
                            or len(json.dumps(prompt).encode('ascii')) > max_instruction_bytes):
                        continue
                    # JSON can parse a lone surrogate that cannot be sent as text.
                    try:
                        prompt.encode('utf-8')
                    except UnicodeError:
                        continue
                    slot = key if role == 'pair' else role
                    found[slot] = prompt
                    accepted.append(slot)
        attempts.append(OpeningAttempt(role, cap, reply.status, tuple(accepted)))
    return OpeningResult(found.get('rewrite'), found.get('repair'), tuple(attempts))
