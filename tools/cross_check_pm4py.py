"""Doi chieu kham pha Declare cua core voi pm4py (moi truong rieng ngoai kho).

Chay trong venv pm4py rieng (``~/workspace/pm4py-venv``), KHONG trong venv
cua worktree va KHONG them pm4py vao phu thuoc cua core (spec, dong 146 va
225): pm4py la AGPL-3.0, chi dung lam bo doi chieu ngoai kho. Khong mo ma
nguon pm4py; chi goi API cong khai cua no nhu mot hop den.

Cach chay (tu goc worktree):

    ~/workspace/pm4py-venv/bin/python -m tools.cross_check_pm4py

Doi chieu tren cung log gia nhu 4.3/4.4: lat nho 4.3 (8 trace) va log sinh
tu generator (30 trace, seed 20261003). Hai nguong support=0.5,
confidence=0.5. Thoat 0 khi ca hai log deu trung khop, 1 khi lech.

Luu y ve dinh nghia support/confidence (khac nhau giua hai ben):
- Miner cua core: support = so case thoa man / tong so case; confidence =
  so case thoa man / so case da kich hoat.
- pm4py tra ve so dem: ``support`` = so case da kich hoat, ``confidence``
  = so case thoa man (da kich hoat va thoa man). Nen support cua core =
  confidence_pm4py / N, va confidence cua core = confidence_pm4py /
  support_pm4py. Script chuyen doi roi loc lai theo nguong cua core (goi
  pm4py voi min_support_ratio=0.0 de tranh lech nghia support, chi loc
  truoc theo confidence — dinh nghia nay hai ben giong nhau), sau do so
  tap luat (mau, hai hoat dong, support, confidence) — phai trung khop.
"""

from __future__ import annotations

import sys

# pm4py/pandas chi co trong venv doi chieu rieng, khong co trong venv
# worktree (noi chay mypy). Ma loi mypy doi theo moi truong (pandas co the
# la import-not-found neu vang mat, hoac import-untyped neu co san nhung
# khong co stub) nen dung ignore tran de dung o ca hai truong hop.
import pandas as pd  # type: ignore
import pm4py  # type: ignore
from tests.synthetic_log import generate_log

from praxon_core.declare.index import Trace
from praxon_core.declare.miner import Rule, discover

SUPPORT = 0.5
CONFIDENCE = 0.5
N_GENERATED_TRACES = 30
SEED = 20261003


def _lat_nho_43() -> list[Trace]:
    """Lat nho 4.3: 8 trace, giong tests/test_declare_filter.py."""
    return [
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "c")),
        Trace(events=("a", "b", "d")),
        Trace(events=("a", "c", "e")),
    ]


def discover_with_pm4py(
    traces: list[Trace], *, support: float, confidence: float
) -> frozenset[Rule]:
    """Chay pm4py discover_declare, chuyen ve Rule cua core, loc theo nguong."""
    rows: list[dict[str, object]] = []
    for i, trace in enumerate(traces):
        for j, activity in enumerate(trace.events):
            rows.append(
                {
                    "case:concept:name": f"case_{i}",
                    "concept:name": activity,
                    "time:timestamp": pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=j),
                }
            )
    frame = pd.DataFrame(rows)
    frame = pm4py.format_dataframe(
        frame,
        case_id="case:concept:name",
        activity_key="concept:name",
        timestamp_key="time:timestamp",
    )
    model = pm4py.discover_declare(
        frame,
        allowed_templates={"response", "precedence"},
        min_support_ratio=0.0,
        min_confidence_ratio=confidence,
    )
    total = len(traces)
    rules: set[Rule] = set()
    for template, by_pair in model.items():
        for pair, counts in by_pair.items():
            activated = int(counts["support"])
            satisfied = int(counts["confidence"])
            if activated == 0:
                continue
            rule_support = satisfied / total
            rule_confidence = satisfied / activated
            if rule_support >= support and rule_confidence >= confidence:
                first, second = pair
                rules.add(
                    Rule(
                        template=str(template),
                        first=str(first),
                        second=str(second),
                        support=rule_support,
                        confidence=rule_confidence,
                    )
                )
    return frozenset(rules)


def _check(name: str, traces: list[Trace], *, support: float, confidence: float) -> bool:
    """Doi chieu mot log: miner cua core va pm4py phai cho cung tap luat."""
    mine = discover(traces, support=support, confidence=confidence)
    theirs = discover_with_pm4py(traces, support=support, confidence=confidence)
    match = mine == theirs
    print(f"{name}: core={len(mine)} luat, pm4py={len(theirs)} luat, trung khop={match}")
    if not match:
        only_mine = sorted(rule.canonical_key for rule in mine - theirs)
        only_theirs = sorted(rule.canonical_key for rule in theirs - mine)
        print(f"  chi co o core: {only_mine[:5]}")
        print(f"  chi co o pm4py: {only_theirs[:5]}")
    return match


def main() -> int:
    """Chay doi chieu; 0 neu trung khop tren ca hai log, 1 neu lech."""
    ok_small = _check(
        "lat nho 4.3 (8 trace)",
        _lat_nho_43(),
        support=SUPPORT,
        confidence=CONFIDENCE,
    )
    generated = generate_log(n_traces=N_GENERATED_TRACES, seed=SEED)
    ok_generated = _check(
        f"log sinh ({N_GENERATED_TRACES} trace, seed {SEED})",
        generated,
        support=SUPPORT,
        confidence=CONFIDENCE,
    )
    if ok_small and ok_generated:
        print("TRUNG KHOP: miner cua core cho cung tap luat nhu pm4py.")
        return 0
    print("KHONG TRUNG KHOP: xem chi tiet o tren.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
