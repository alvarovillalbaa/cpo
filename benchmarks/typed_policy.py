"""Generate fresh, labeled policy cohorts for a grounded prompt comparison."""

from itertools import product
from random import Random


TASKS = ("ticket", "warehouse", "outage")
SPLITS = {"train": 16, "validation": 12, "holdout": 18, "confirmation": 8}
QUEUES = {
    "refund-question": "Q-M74",
    "invoice-copy": "Q-L91",
    "delivery-date": "Q-X36",
    "return-label": "Q-J58",
    "packaging": "Q-V27",
    "translation": "Q-F43",
}
WAREHOUSE_CORE = (
    ("positive", "PASS", "NORMAL", "NORTH"), ("positive", "PASS", "RUSH", "SOUTH"),
    ("positive", "FAIL", "NORMAL", "SOUTH"), ("positive", "FAIL", "RUSH", "NORTH"),
    ("zero", "PASS", "NORMAL", "SOUTH"), ("zero", "PASS", "RUSH", "NORTH"),
    ("depleted", "PASS", "NORMAL", "NORTH"), ("depleted", "FAIL", "RUSH", "SOUTH"),
)
WAREHOUSE = (*WAREHOUSE_CORE, *(regime for regime in product(
    ("depleted", "zero", "positive"), ("PASS", "FAIL"), ("NORMAL", "RUSH"), ("NORTH", "SOUTH")
) if regime not in WAREHOUSE_CORE))
OUTAGE = (
    (29, "STANDARD", False, "POSTED"), (30, "STANDARD", False, "POSTED"),
    (29, "PLUS", False, "POSTED"), (30, "PLUS", False, "POSTED"),
    (119, "STANDARD", False, "POSTED"), (120, "STANDARD", False, "POSTED"),
    (119, "PLUS", False, "POSTED"), (120, "PLUS", False, "POSTED"),
    (37, "STANDARD", True, "POSTED"), (41, "PLUS", True, "POSTED"),
    (122, "PLUS", True, "POSTED"), (123, "STANDARD", True, "POSTED"),
    (26, "STANDARD", False, "MISSING"), (36, "PLUS", False, "MISSING"),
    (121, "STANDARD", True, "MISSING"), (121, "PLUS", False, "MISSING"),
)


def ticket(index, rng):
    topics = (*QUEUES, "general-inquiry", "unlisted-topic")
    topic = topics[index % len(topics)]
    channel = rng.choice(("chat", "email", "web"))
    return f"Topic={topic}. Channel={channel}. Reference=CPO-{index}.", {
        "queue": QUEUES.get(topic, "GENERAL"),
    }, topic in ("refund-question", "return-label", "unlisted-topic")


def warehouse(index, rng, regime):
    stock, inspection, tier, site = regime
    count = 35 + 3 * index
    remainder = {"depleted": -rng.randint(1, 6), "zero": 0, "positive": rng.randint(1, 12)}[stock]
    damaged = rng.randint(1, 8)
    reserved = count - damaged - remainder
    available = max(0, remainder)
    rush = tier == "RUSH"
    action = "HOLD" if inspection == "FAIL" or not available else ("REVIEW" if rush else "RELEASE")
    facts = (f"On hand={count}; Reserved={reserved}; Damaged={damaged}; "
             f"Inspection={inspection}; Tier={tier}; Site={site}.")
    return facts, {"available": available, "action": action,
                   "owner": {"NORTH": "CREW-N", "SOUTH": "CREW-S"}[site],
                   "windowHours": 4 if rush else 8}, inspection == "FAIL" or stock == "zero"


def outage(index, rng, regime):
    duration, plan, capped, evidence = regime
    # Keep the selected cap above zero and distinct across repeated boundary cases.
    uncapped = duration // (3 if plan == "PLUS" else 5) if duration >= 30 else 0
    fee = (20 + 10 * (index % 3) + rng.randrange(10) if capped
           else 500 + 13 * index + rng.randrange(10))
    credit = min(uncapped, fee // 10)
    missing, long = evidence == "MISSING", duration >= 120
    facts = f"Duration minutes={duration}; Plan={plan}; Monthly fee whole USD={fee}; Evidence={evidence}."
    return facts, {"credit": credit, "review": missing or long,
                   "reason": "NEEDS_DOC" if missing else ("LONG" if long else "NORMAL")}, missing or long


def cohorts(seed=41491):
    """Return repeatable task cohorts with disjoint facts and boundary coverage."""
    rng = Random(seed)
    output = {}
    for task in TASKS:
        groups, seen, index = {}, set(), 0
        for split, count in SPLITS.items():
            rows = []
            for offset in range(count):
                if task == "ticket":
                    facts, expected, critical = ticket(index, rng)
                elif task == "warehouse":
                    regime = WAREHOUSE[offset % len(WAREHOUSE)]
                    facts, expected, critical = warehouse(index, rng, regime)
                else:
                    for _ in range(30):
                        index_in_panel = ((0, 1, 4, 5, 8, 9, 12, 14)[offset] if split == "confirmation"
                                          else (offset * 5) % len(OUTAGE))
                        regime = OUTAGE[index_in_panel]
                        facts, expected, critical = outage(index, rng, regime)
                        if facts not in seen:
                            break
                        index += 1
                if facts in seen:
                    raise ValueError("Policy facts must be disjoint across cohorts")
                seen.add(facts)
                row_id = f"grounded-{task}-{split}-{offset + 1:02}"
                rows.append({"id": row_id, "input": facts, "expected": expected, "critical": critical})
                index += 1
            groups[split] = rows
        output[task] = groups
    return output
