"""Causality checks for C4 traces (lane G, master plan T6).

Conventions
-----------
* Coordinates are taken from ``Site.x_m/y_m/z_m`` in the site's declared ``frame``; two
  sites must declare the same frame to be compared (no silent frame mixing).
* The light-cone delay between two sites is the straight-line (chord) distance / c. This
  is the physical lower bound for *any* signal; it is not a network latency estimate.
* Event times in traces are coordinate times (ns). Clock uncertainty is handled
  explicitly by the ``*_with_uncertainty`` predicates, which return ``AMBIGUOUS`` instead
  of guessing when the error bars overlap.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from qmint.core.contracts import Site, SpacetimeNetwork, TraceEvent, TransactionTrace

C_M_PER_S = 299_792_458.0  # exact (SI definition)
C_M_PER_NS = C_M_PER_S * 1e-9

#: Floating-point slack (ns) for comparisons; far below any modelled delay.
TIME_TOL_NS = 1e-6


class CausalityViolation(AssertionError):
    """A trace or network asserts something physically impossible under the declared model."""


def site_distance_m(a: Site, b: Site) -> float:
    if a.frame != b.frame:
        raise ValueError(f"sites {a.site_id} and {b.site_id} declare different frames ({a.frame} vs {b.frame})")
    return math.dist((a.x_m, a.y_m, a.z_m), (b.x_m, b.y_m, b.z_m))


def lightcone_delay_ns(a: Site, b: Site) -> float:
    """Minimum time for any signal to travel between two sites (vacuum light speed)."""
    return site_distance_m(a, b) / C_M_PER_NS


# --------------------------------------------------------------------------- #
# Network-level checks
# --------------------------------------------------------------------------- #


def network_violations(net: SpacetimeNetwork, tol_ns: float = TIME_TOL_NS) -> list[str]:
    """Links whose declared lower bound is *below* the light cone claim superluminal signalling."""
    sites = {s.site_id: s for s in net.sites}
    out: list[str] = []
    for lk in net.links:
        lc = lightcone_delay_ns(sites[lk.src], sites[lk.dst])
        if lk.propagation_lower_bound_ns + tol_ns < lc:
            out.append(
                f"link {lk.src}->{lk.dst}: declared lower bound {lk.propagation_lower_bound_ns} ns "
                f"< light-cone {lc:.3f} ns"
            )
    return out


def link_lower_bound_ns(net: SpacetimeNetwork, src_site: str, dst_site: str) -> float:
    """Effective lower bound: max(declared link bound, light cone). Same site -> 0."""
    if src_site == dst_site:
        return 0.0
    sites = {s.site_id: s for s in net.sites}
    lc = lightcone_delay_ns(sites[src_site], sites[dst_site])
    declared = [lk.propagation_lower_bound_ns for lk in net.links if lk.src == src_site and lk.dst == dst_site]
    return max([lc, *declared])


# --------------------------------------------------------------------------- #
# Trace-level checks
# --------------------------------------------------------------------------- #


def _events(trace: TransactionTrace | Iterable[TraceEvent]) -> list[TraceEvent]:
    return list(trace.events) if isinstance(trace, TransactionTrace) else list(trace)


def retrocausal_violations(trace: TransactionTrace | Iterable[TraceEvent]) -> list[str]:
    """Parents after children, or a message received before it was sent."""
    evs = _events(trace)
    by_id = {e.event_id: e for e in evs}
    out: list[str] = []
    for e in evs:
        for p in e.causal_parent_ids:
            if p in by_id and by_id[p].time_ns > e.time_ns + TIME_TOL_NS:
                out.append(f"retrocausal edge {p}->{e.event_id}")
    sends = {e.message_id: e for e in evs if e.kind == "message_send" and e.message_id}
    for e in evs:
        if e.kind == "message_receive" and e.message_id in sends:
            if e.time_ns + TIME_TOL_NS < sends[e.message_id].time_ns:
                out.append(f"message {e.message_id} received before it was sent")
    return out


def propagation_violations(
    trace: TransactionTrace | Iterable[TraceEvent], net: SpacetimeNetwork, tol_ns: float = TIME_TOL_NS
) -> list[str]:
    """No information faster than the bound, along *every* causal path (not just direct edges).

    For each event ``e`` and each causal ancestor ``a`` at a different site we require
    ``t(e) - t(a) >= bound(site(a), site(e))`` where ``bound`` is the light cone. Direct
    message edges are additionally checked against the declared link lower bound.
    """
    evs = _events(trace)
    by_id = {e.event_id: e for e in evs}
    sites = {s.site_id: s for s in net.sites}
    out: list[str] = []

    sends = {e.message_id: e for e in evs if e.kind == "message_send" and e.message_id}
    for e in evs:
        if e.kind == "message_receive" and e.message_id in sends:
            s = sends[e.message_id]
            bound = link_lower_bound_ns(net, s.site_id, e.site_id)
            if e.time_ns - s.time_ns + tol_ns < bound:
                out.append(
                    f"message {e.message_id} {s.site_id}->{e.site_id} took {e.time_ns - s.time_ns:.3f} ns "
                    f"< bound {bound:.3f} ns"
                )

    # Transitive closure over the DAG (events sorted by time so ancestors come first).
    ancestors: dict[str, set[str]] = {}
    for e in sorted(evs, key=lambda x: x.time_ns):
        acc: set[str] = set()
        for p in e.causal_parent_ids:
            if p in by_id:
                acc.add(p)
                acc |= ancestors.get(p, set())
        ancestors[e.event_id] = acc
        for a_id in acc:
            a = by_id[a_id]
            if a.site_id == e.site_id:
                continue
            lc = lightcone_delay_ns(sites[a.site_id], sites[e.site_id])
            if e.time_ns - a.time_ns + tol_ns < lc:
                out.append(
                    f"information from {a_id}@{a.site_id} reached {e.event_id}@{e.site_id} in "
                    f"{e.time_ns - a.time_ns:.3f} ns < light-cone {lc:.3f} ns"
                )
    return out


def assert_causal(trace: TransactionTrace | Iterable[TraceEvent], net: SpacetimeNetwork) -> None:
    problems = retrocausal_violations(trace) + propagation_violations(trace, net) + network_violations(net)
    if problems:
        raise CausalityViolation("; ".join(problems[:10]))


# --------------------------------------------------------------------------- #
# Separation and ordering predicates
# --------------------------------------------------------------------------- #


class Separation(str, Enum):
    SPACELIKE = "spacelike"  # no signal could connect them, for every admissible clock error
    TIMELIKE_OR_LIGHTLIKE = "timelike_or_lightlike"  # connectable for every admissible clock error
    AMBIGUOUS = "ambiguous"  # depends on clock errors within the declared bounds


def separation(
    t1_ns: float,
    site1: Site,
    t2_ns: float,
    site2: Site,
    clock_err1_ns: float = 0.0,
    clock_err2_ns: float = 0.0,
) -> Separation:
    """Classify two events given timestamps with absolute clock-error bounds.

    With exact clocks: spacelike iff ``|t1 - t2| < d/c``. With errors, the true difference
    lies in ``[|dt| - e1 - e2, |dt| + e1 + e2]`` (clipped at 0) and we only answer when the
    whole interval is on one side of ``d/c``.
    """
    if clock_err1_ns < 0 or clock_err2_ns < 0:
        raise ValueError("clock error bounds must be >= 0")
    lc = lightcone_delay_ns(site1, site2)
    dt = abs(t1_ns - t2_ns)
    err = clock_err1_ns + clock_err2_ns
    if dt + err < lc:
        return Separation.SPACELIKE
    if max(dt - err, 0.0) >= lc:
        return Separation.TIMELIKE_OR_LIGHTLIKE
    return Separation.AMBIGUOUS


def is_spacelike(e1: TraceEvent, e2: TraceEvent, net: SpacetimeNetwork, use_clock_bounds: bool = True) -> bool:
    """True only if the two events are *certainly* spacelike separated."""
    sites = {s.site_id: s for s in net.sites}
    s1, s2 = sites[e1.site_id], sites[e2.site_id]
    err1 = s1.clock_error_bound_ns if use_clock_bounds else 0.0
    err2 = s2.clock_error_bound_ns if use_clock_bounds else 0.0
    return separation(e1.time_ns, s1, e2.time_ns, s2, err1, err2) is Separation.SPACELIKE


class Order(str, Enum):
    BEFORE = "before"
    AFTER = "after"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class Stamp:
    """A local timestamp with an absolute error bound relative to coordinate time."""

    local_ns: float
    error_bound_ns: float


def order_with_uncertainty(a: Stamp, b: Stamp) -> Order:
    """Order two timestamps only if their uncertainty intervals do not overlap."""
    if a.local_ns + a.error_bound_ns < b.local_ns - b.error_bound_ns:
        return Order.BEFORE
    if b.local_ns + b.error_bound_ns < a.local_ns - a.error_bound_ns:
        return Order.AFTER
    return Order.UNDETERMINED


# --------------------------------------------------------------------------- #
# Coordination analysis
# --------------------------------------------------------------------------- #


def ancestors_of(event_id: str, events: Iterable[TraceEvent]) -> set[str]:
    by_id = {e.event_id: e for e in events}
    seen: set[str] = set()
    stack = list(by_id[event_id].causal_parent_ids)
    while stack:
        p = stack.pop()
        if p in seen or p not in by_id:
            continue
        seen.add(p)
        stack.extend(by_id[p].causal_parent_ids)
    return seen


def synchronous_cross_site_round_trips(
    events: Iterable[TraceEvent], decision_event_id: str, trigger_event_id: str
) -> list[str]:
    """Cross-site messages *sent after and because of* ``trigger`` that ``decision`` waited for.

    This is the operational meaning of "validation required a synchronous cross-site
    query": some causal ancestor of the decision is a message_receive whose matching send
    happened at another site and itself descends from the trigger (e.g. the presentation).
    Messages sent before the trigger (pre-distribution, a one-way commitment forwarded in
    advance) are not round trips triggered by this presentation.
    """
    evs = list(events)
    by_id = {e.event_id: e for e in evs}
    anc = ancestors_of(decision_event_id, evs)
    sends = {e.message_id: e for e in evs if e.kind == "message_send" and e.message_id}
    out = []
    for a_id in anc:
        a = by_id[a_id]
        if a.kind != "message_receive" or a.message_id not in sends:
            continue
        s = sends[a.message_id]
        if s.site_id == a.site_id:
            continue
        if s.event_id == trigger_event_id or trigger_event_id in ancestors_of(s.event_id, evs):
            out.append(a.message_id or "")
    return sorted(out)
