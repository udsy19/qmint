"""Inline, dependency-free SVG figures (deterministic text output)."""

from __future__ import annotations

import math
from html import escape

from qmint.core.contracts import SpacetimeNetwork, TransactionTrace

C_M_PER_NS = 0.299792458  # speed of light in vacuum, m/ns (exact by SI definition)

# Event-kind groups: distinct shape AND text label (never color alone).
_GROUP = {
    "local_validation_start": ("validation", "circle"),
    "verification_result_available_local": ("validation", "circle"),
    "issuer_aware_of_spend": ("settlement", "square"),
    "bank_settlement_final": ("settlement", "square"),
    "merchant_funds_irrevocable": ("irrevocable", "diamond"),
    "reject": ("reject", "cross"),
}


def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _marker(shape: str, x: float, y: float, cls: str) -> str:
    r = 6.0
    if shape == "square":
        return f'<rect class="{cls}" x="{_f(x - r)}" y="{_f(y - r)}" width="{_f(2 * r)}" height="{_f(2 * r)}"/>'
    if shape == "diamond":
        pts = f"{_f(x)},{_f(y - r - 2)} {_f(x + r + 2)},{_f(y)} {_f(x)},{_f(y + r + 2)} {_f(x - r - 2)},{_f(y)}"
        return f'<polygon class="{cls}" points="{pts}"/>'
    if shape == "cross":
        return (f'<path class="{cls} cross" d="M{_f(x - r)},{_f(y - r)}L{_f(x + r)},{_f(y + r)}'
                f'M{_f(x - r)},{_f(y + r)}L{_f(x + r)},{_f(y - r)}"/>')
    return f'<circle class="{cls}" cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}"/>'


def spacetime_svg(trace: TransactionTrace, network: SpacetimeNetwork | None, source_id: str) -> str:
    """Space (sites, horizontal) vs time (ns, upward) diagram with causal edges and light cones.

    Light-cone lines are drawn from every ``branch_choice``/``commitment`` event using the site
    coordinates of the matching network (vacuum c). Without a network no cones are drawn.
    """
    site_order: list[str] = []
    pos_m: dict[str, float] = {}
    if network is not None:
        for s in sorted(network.sites, key=lambda s: (s.x_m, s.y_m, s.site_id)):
            site_order.append(s.site_id)
            pos_m[s.site_id] = s.x_m
    for e in trace.events:
        if e.site_id not in site_order:
            site_order.append(e.site_id)

    sites_xyz = {s.site_id: (s.x_m, s.y_m, s.z_m) for s in network.sites} if network else {}

    def dist_m(a: str, b: str) -> float | None:
        if a in sites_xyz and b in sites_xyz:
            return math.dist(sites_xyz[a], sites_xyz[b])
        return None

    cones: list[tuple[str, float, str, float]] = []  # (from_site, t0, to_site, t_arrival)
    for e in trace.events:
        if e.kind in ("branch_choice", "commitment"):
            for s in site_order:
                d = dist_m(e.site_id, s)
                if s != e.site_id and d is not None:
                    cones.append((e.site_id, e.time_ns, s, e.time_ns + d / C_M_PER_NS))

    times = [e.time_ns for e in trace.events] + [c[3] for c in cones]
    t0, t1 = min(times), max(times)
    span = (t1 - t0) or 1.0
    W, H, ml, mr, mt, mb = 640, 420, 70, 30, 30, 50
    pw, ph = W - ml - mr, H - mt - mb
    n = len(site_order)
    xs = {s: ml + (pw * (i + 0.5) / n) for i, s in enumerate(site_order)}

    def y(t: float) -> float:
        return mt + ph - (t - t0) / span * ph

    title = f"Spacetime diagram for trace {trace.trace_id}"
    desc = (f"{len(trace.events)} events at {n} sites; time axis in ns from {_f(t0)} to {_f(t1)}. "
            f"Source record {source_id}. Latency evidence: {trace.latency_evidence.value}.")
    out = [
        f'<svg class="fig" viewBox="0 0 {W} {H}" role="img" aria-labelledby="st-t-{escape(trace.trace_id)} '
        f'st-d-{escape(trace.trace_id)}" xmlns="http://www.w3.org/2000/svg">',
        f'<title id="st-t-{escape(trace.trace_id)}">{escape(title)}</title>',
        f'<desc id="st-d-{escape(trace.trace_id)}">{escape(desc)}</desc>',
        f'<line class="axis" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}"/>',
        f'<text class="lbl" x="12" y="{mt + 4}">t (ns)</text>',
        f'<text class="lbl" x="12" y="{_f(y(t1))}" dy="14">{escape(_f(t1))}</text>',
        f'<text class="lbl" x="12" y="{_f(y(t0))}">{escape(_f(t0))}</text>',
    ]
    for s in site_order:
        x = xs[s]
        out.append(f'<line class="worldline" x1="{_f(x)}" y1="{mt}" x2="{_f(x)}" y2="{mt + ph}"/>')
        label = s if s not in pos_m else f"{s} (x={_f(pos_m[s])} m)"
        out.append(f'<text class="lbl" text-anchor="middle" x="{_f(x)}" y="{H - 18}">{escape(label)}</text>')
    for src, ta, dst, tb in cones:
        out.append(f'<line class="cone" x1="{_f(xs[src])}" y1="{_f(y(ta))}" x2="{_f(xs[dst])}" y2="{_f(y(tb))}">'
                   f'<title>light cone {escape(src)} to {escape(dst)}: earliest arrival {escape(_f(tb))} ns</title>'
                   f'</line>')
    by_id = {e.event_id: e for e in trace.events}
    for e in trace.events:
        for p in e.causal_parent_ids:
            pe = by_id[p]
            out.append(f'<line class="edge" x1="{_f(xs[pe.site_id])}" y1="{_f(y(pe.time_ns))}" '
                       f'x2="{_f(xs[e.site_id])}" y2="{_f(y(e.time_ns))}"/>')
    for e in trace.events:
        group, shape = _GROUP.get(e.kind, ("other", "circle"))
        x, yy = xs[e.site_id], y(e.time_ns)
        out.append(f'<g class="ev ev-{group}"><title>{escape(e.event_id)}: {escape(e.kind)} at site '
                   f'{escape(e.site_id)}, t={escape(_f(e.time_ns))} ns (src: {escape(source_id)})</title>')
        out.append(_marker(shape, x, yy, f"mk mk-{group}"))
        out.append(f'<text class="evl" x="{_f(x + 10)}" y="{_f(yy + 4)}">{escape(e.kind)}</text></g>')
    out.append("</svg>")
    return "".join(out)


def pareto_svg(points: list[tuple[float, float, bool, str]], title: str) -> str:
    """Scatter on log10(epsilon) vs resource. ``points`` = (epsilon>0, resource, certified, record_id).

    Certified points are filled and joined into the non-dominated frontier; uncertified points are
    hollow and labelled "excluded". Callers must already have dropped epsilon <= 0 (no log zeros).
    """
    W, H, ml, mr, mt, mb = 640, 360, 80, 30, 30, 50
    pw, ph = W - ml - mr, H - mt - mb
    lx = [math.log10(p[0]) for p in points]
    ry = [p[1] for p in points]
    x0, x1 = min(lx), max(lx)
    y0, y1 = min(ry), max(ry)
    xs, ys = (x1 - x0) or 1.0, (y1 - y0) or 1.0

    def X(v: float) -> float:
        return ml + (math.log10(v) - x0) / xs * pw

    def Y(v: float) -> float:
        return mt + ph - (v - y0) / ys * ph

    out = [
        f'<svg class="fig" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}" '
        'xmlns="http://www.w3.org/2000/svg">',
        f'<title>{escape(title)}</title>',
        f'<line class="axis" x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}"/>',
        f'<line class="axis" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}"/>',
        f'<text class="lbl" x="{ml + pw / 2}" y="{H - 10}" text-anchor="middle">'
        'log10 target epsilon_unf (smaller = stronger)</text>',
        f'<text class="lbl" x="14" y="{mt - 10}">photons prepared</text>',
        f'<text class="lbl" x="{ml}" y="{mt + ph + 18}" text-anchor="middle">{_f(x0)}</text>',
        f'<text class="lbl" x="{ml + pw}" y="{mt + ph + 18}" text-anchor="middle">{_f(x1)}</text>',
        f'<text class="lbl" x="{ml - 6}" y="{mt + ph}" text-anchor="end">{_f(y0)}</text>',
        f'<text class="lbl" x="{ml - 6}" y="{mt + 10}" text-anchor="end">{_f(y1)}</text>',
    ]
    frontier: list[tuple[float, float, bool, str]] = []
    best = math.inf
    for p in sorted((p for p in points if p[2]), key=lambda p: (p[0], p[1])):  # strongest epsilon first
        if p[1] < best:
            frontier.append(p)
            best = p[1]
    if len(frontier) > 1:
        pts = " ".join(f"{_f(X(p[0]))},{_f(Y(p[1]))}" for p in frontier)
        out.append(f'<polyline class="frontier" points="{pts}"/>')
    for eps, res, ok, rid in points:
        cls = "pt-cert" if ok else "pt-excl"
        state = "certified" if ok else "excluded: no CERTIFIED certificate"
        out.append(f'<g><title>{escape(rid)}: epsilon={eps:.3e}, photons={_f(res)} ({state})</title>'
                   f'<circle class="{cls}" cx="{_f(X(eps))}" cy="{_f(Y(res))}" r="6"/></g>')
    out.append("</svg>")
    return "".join(out)
