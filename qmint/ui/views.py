"""Workbench views. Each function returns an HTML ``<section>`` string.

All numbers go through :func:`qmint.ui.claims.render` (cited, with evidence badge and source
link). Badges come only from ``EvidenceKind`` / ``CertificateStatus`` enums.
"""

from __future__ import annotations

from html import escape

from qmint.core.contracts import (
    PROTOCOL_GAMES,
    AttackResult,
    BenchmarkRecord,
    CalibrationRecord,
    CertificateStatus,
    EvidenceKind,
    EvidenceManifest,
    GameId,
    Interval,
    ProtocolSpec,
    SecurityCertificate,
    SpacetimeNetwork,
    TransactionTrace,
)
from qmint.ui.claims import NO_BOUND, Cited, ClaimPanel, anchor, badge_html, bound, render
from qmint.ui.evidence_badges import evidence_badge, status_badge
from qmint.ui.records import LoadedRecord, Skipped
from qmint.ui.svg import pareto_svg, spacetime_svg

# Registered statements, transcribed from the frozen contract (qmint/core/contracts.py GameId).
# The UI does not re-verify these against primary sources; that is lane A/D's job.
GAME_STATEMENTS: dict[GameId, tuple[str, str]] = {
    GameId.W1: ("Wiesner simple 1->2 counterfeiting, exact verifier (MVW 2012)", "(3/4)^n"),
    GameId.W1_CV: ("MVW 2012 classical-verification variant (a distinct game)", "(3/4 + sqrt(2)/8)^n"),
    GameId.W2: ("Noisy/threshold Wiesner", "no published closed form assumed"),
    GameId.S1: ("Ideal two-site S-token (Kent et al. 2022)", "(1/2 + 1/(2 sqrt 2))^N"),
    GameId.S2: ("Realistic noisy/lossy S-token (Kent et al. 2022, finite-size)", "not transcribed in the UI"),
    GameId.D1: ("Quantum-digital payment cryptogram (Schiansky et al. 2023)", "not transcribed in the UI"),
    GameId.A1: ("Anonymity / issuer tracking (Gavinsky et al. 2025)", "not transcribed in the UI"),
    GameId.C1: ("Classical double-spend systems game", "not a quantum theorem"),
}

AXES = ("epsilon_unf", "epsilon_cor", "epsilon_rob", "epsilon_priv")


def ebadge(kind: EvidenceKind) -> str:
    b = evidence_badge(kind)
    return badge_html(b.label, b.css, b.title)


def sbadge(status: CertificateStatus) -> str:
    b = status_badge(status)
    return badge_html(b.label, b.css, b.title)


def _section(sid: str, title: str, body: str, intro: str = "") -> str:
    p = f'<p class="intro">{intro}</p>' if intro else ""
    return (f'<section id="{sid}" aria-labelledby="{sid}-h"><h2 id="{sid}-h">{escape(title)}</h2>'
            f"{p}{body}</section>")


def _table(caption: str, head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f'<th scope="col">{escape(h)}</th>' for h in head)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="tbl"><table><caption>{escape(caption)}</caption><thead><tr>{th}</tr></thead>'
            f"<tbody>{trs}</tbody></table></div>")


def _interval(iv: Interval | None, rid: str, ev: EvidenceKind, missing: str = "not reported") -> str:
    if iv is None:
        return f'<span class="missing">{escape(missing)}</span>'
    lo = render(Cited(iv.lo, rid, ev, iv.unit.value), with_badge=False)
    hi = render(Cited(iv.hi, rid, ev, iv.unit.value), with_badge=False)
    pt = "" if iv.point is None else f" point {render(Cited(iv.point, rid, ev, iv.unit.value), with_badge=False)}"
    return f"[{lo}, {hi}]{pt}"


def _warn_failed(failed: list[str], what: str) -> str:
    if not failed:
        return ""
    items = "".join(f"<li><code>{escape(a)}</code></li>" for a in failed)
    return (f'<div class="alert danger" role="alert"><strong>WARNING: failed assumptions</strong> '
            f"for {escape(what)}. No security claim applies.<ul>{items}</ul></div>")


# --------------------------------------------------------------------------- views


def protocols_view(recs: list[LoadedRecord], certs: list[LoadedRecord]) -> str:
    specs = {r.model.protocol_id: r for r in recs}  # type: ignore[attr-defined]
    options = "".join(f'<option value="{escape(p)}">{escape(p)}</option>' for p in sorted(PROTOCOL_GAMES))
    chooser = (
        '<form class="chooser" onsubmit="return false"><label for="proto-pick">Protocol family</label> '
        f'<select id="proto-pick" data-filter="proto"><option value="">all</option>{options}</select>'
        '<p class="muted">Each protocol may be scored only under its registered games. '
        "Theorems are never transferred across games.</p></form>"
    )
    cards = []
    for pid in sorted(PROTOCOL_GAMES):
        spec = specs.get(pid)
        games = sorted(PROTOCOL_GAMES[pid], key=lambda g: g.value)
        gcards = []
        for g in games:
            name, form = GAME_STATEMENTS[g]
            gcerts = [c for c in certs if c.model.protocol_id == pid and c.model.game_id == g]  # type: ignore[attr-defined]
            if gcerts:
                rows = []
                for c in gcerts:
                    m: SecurityCertificate = c.model  # type: ignore[assignment]
                    rows.append(f"<li>{sbadge(m.proof_check_status)} epsilon_unf: "
                                f"{render(bound(m.upper_bounds.epsilon_unf, c.record_id, m.evidence_kind))}</li>")
                applied = "<ul>" + "".join(rows) + "</ul>"
            else:
                applied = f'<p><span class="missing">{NO_BOUND}</span>: no certificate record loaded.</p>'
            gcards.append(
                f'<article class="card theorem"><h4>Game <code>{g.value}</code></h4>'
                f"<p>{escape(name)}</p><p>Registered statement: <code>{escape(form)}</code> "
                '<span class="muted">(from frozen contract C7; not re-verified by the UI)</span></p>'
                f"<p>Loaded bounds for this protocol and game only:</p>{applied}</article>"
            )
        if spec is not None:
            ps: ProtocolSpec = spec.model  # type: ignore[assignment]
            meta = (f'<p>Spec <a class="src" href="#{anchor(spec.record_id)}">src: {escape(spec.record_id)}</a>; '
                    f"paper <code>{escape(ps.source_paper_id)}</code>; theorem id "
                    f"<code>{escape(ps.theorem_id or 'none')}</code>; issuer trust "
                    f"<code>{escape(ps.issuer_trust)}</code>; quantum memory required: "
                    f"{'yes' if ps.quantum_memory_required else 'no'}.</p>")
        else:
            meta = '<p class="muted">No ProtocolSpec record loaded for this protocol.</p>'
        kind = "classical" if pid.startswith("classical_") else "quantum"
        cards.append(f'<details class="proto" data-proto="{escape(pid)}"><summary><code>{escape(pid)}</code> '
                     f'<span class="tag">{kind}</span></summary>{meta}<div class="grid">{"".join(gcards)}</div>'
                     "</details>")
    return _section("protocols", "Protocol and security game", chooser + "".join(cards))


def attacks_view(recs: list[LoadedRecord]) -> str:
    if not recs:
        return _section("attacks", "Attack results", '<p class="muted">No AttackResult records loaded.</p>')
    blocks = []
    for r in recs:
        a: AttackResult = r.model  # type: ignore[assignment]
        rid, ev = r.record_id, a.evidence_kind
        mc = ""
        if a.trials > 0:
            mc = (f"<p>Trials {render(Cited(a.trials, rid, ev, 'count'), with_badge=False)}, successes "
                  f"{render(Cited(a.successes, rid, ev, 'count'), with_badge=False)}; success-rate CI "
                  f"{_interval(a.success_rate_ci, rid, ev)} ({escape(a.ci_method or 'method not stated')}). "
                  "<strong>A sampled success rate is a lower bound on worst-case attack success.</strong></p>")
        sdp = ""
        if a.sdp_primal is not None or a.sdp_dual is not None:
            rows = [
                ["primal (attack value)", render(Cited(a.sdp_primal, rid, ev), with_badge=False)],
                ["dual (upper bound if feasible)", render(Cited(a.sdp_dual, rid, ev), with_badge=False)],
                ["dual feasibility residual", render(Cited(a.dual_feasibility_residual, rid, ev), with_badge=False)],
                ["primal feasibility residual",
                 render(Cited(a.primal_feasibility_residual, rid, ev), with_badge=False)],
                ["solver", f"<code>{escape(a.solver or 'not stated')}</code>"],
            ]
            note = ("Numerical solver output: not a proof without rigorous residual accounting."
                    if ev == EvidenceKind.NUMERICAL_SDP else "")
            sdp = _table(f"SDP primal/dual for {rid}", ["quantity", "value"], rows) + (
                f'<p class="muted">{note}</p>' if note else "")
        oom = ""
        if a.proof_applicability == "OUT_OF_MODEL":
            oom = ('<div class="alert danger" role="alert"><strong>OUT OF MODEL:</strong> this attack '
                   "uses capabilities outside the proof's assumptions; it says nothing about the theorem.</div>")
        blocks.append(
            f'<article class="card" id="att-{anchor(rid)}"><h3><code>{escape(rid)}</code> {ebadge(ev)}</h3>'
            f"<p>Game <code>{a.game_id.value}</code>, method <code>{escape(a.attack_method)}</code>, n = "
            f"{render(Cited(a.token_n, rid, ev, 'qubits'), with_badge=False)}, backend "
            f"<code>{escape(a.backend_kind)}</code>, applicability <code>{a.proof_applicability}</code>.</p>"
            f"{oom}{mc}{sdp}<p>Theorem upper bound: "
            f"{render(bound(a.theorem_upper_bound, rid, EvidenceKind.PUBLISHED_THEOREM if a.theorem_upper_bound is not None else EvidenceKind.UNCERTIFIED))}"
            "</p></article>"
        )
    return _section("attacks", "Attack results", "".join(blocks),
                    "Monte Carlo estimates and SDP values are shown with their evidence kind; neither is "
                    "promoted to a theorem.")


def calibration_view(recs: list[LoadedRecord]) -> str:
    has_photon = any(r.evidence == EvidenceKind.PHOTON_EXPERIMENT for r in recs)
    head = ("" if has_photon else '<div class="alert warn" role="note"><strong>No photon-experiment dataset '
            "loaded.</strong> Every calibration below is non-experimental.</div>")
    cards = []
    for r in recs:
        c: CalibrationRecord = r.model  # type: ignore[assignment]
        rid, ev = r.record_id, c.data_origin
        sha = (f"<code>{escape(c.dataset_sha256)}</code>" if c.dataset_sha256
               else '<span class="missing">no dataset hash (not experimental data)</span>')
        rows = []
        for name in ("detection_efficiency", "qber", "loss", "multiphoton", "basis_bias", "clock_drift"):
            rows.append([escape(name), _interval(getattr(c, f"{name}_interval"), rid, ev)])
        cards.append(
            f'<article class="card"><h3><code>{escape(rid)}</code> {ebadge(ev)}</h3>'
            f"<p>Device <code>{escape(c.device_id)}</code>, experiment family "
            f"<code>{escape(c.experiment_family)}</code>, events "
            f"{render(Cited(c.n_events, rid, ev, 'count'), with_badge=False)}, confidence level "
            f"{render(Cited(c.confidence_level, rid, ev), with_badge=False)} via "
            f"<code>{escape(c.interval_method)}</code>.</p><p>Dataset SHA-256: {sha}</p>"
            + _table(f"Calibration intervals for {rid}", ["parameter", "interval"], rows)
            + "<p>Independence assumptions: " + ", ".join(f"<code>{escape(a)}</code>"
                                                         for a in c.independence_assumptions) + "</p></article>"
        )
    body = head + ("".join(cards) or '<p class="muted">No CalibrationRecord loaded.</p>')
    return _section("photon", "Photon-data provenance", body)


def spacetime_view(traces: list[LoadedRecord], networks: dict[str, LoadedRecord]) -> str:
    if not traces:
        return _section("spacetime", "Spacetime diagram", '<p class="muted">No TransactionTrace loaded.</p>')
    figs = []
    for r in traces:
        t: TransactionTrace = r.model  # type: ignore[assignment]
        net_rec = networks.get(t.network_id)
        net: SpacetimeNetwork | None = net_rec.model if net_rec else None  # type: ignore[assignment]
        svg = spacetime_svg(t, net, r.record_id)
        lat_rows = [[escape(k), render(Cited(v, r.record_id, t.latency_evidence, "ns"))]
                    for k, v in sorted(t.latency_breakdown_ns.items())]
        net_note = (f'network <a class="src" href="#{anchor(net_rec.record_id)}">src: {escape(net_rec.record_id)}</a>'
                    if net_rec else '<span class="missing">network not loaded: no light cones drawn</span>')
        ds = ('<div class="alert danger" role="alert"><strong>Double spend accepted</strong> in this trace.</div>'
              if t.double_spend_accepted else "")
        figs.append(
            f'<figure class="card"><figcaption><code>{escape(r.record_id)}</code> {ebadge(t.latency_evidence)} '
            f"protocol <code>{escape(t.protocol_id)}</code>; {net_note}; irrevocability rule "
            f"<code>{escape(t.irrevocability_rule)}</code>. Legend: circle = local validation, square = "
            "settlement, diamond = irrevocable, cross = reject; dashed = vacuum light cone.</figcaption>"
            f'{ds}<div class="figwrap">{svg}</div>'
            f'<p><a download="spacetime-{escape(anchor(r.record_id))}.svg" '
            f'href="figures/spacetime-{escape(anchor(r.record_id))}.svg">Download SVG</a></p>'
            + (_table(f"Latency breakdown for {r.record_id}", ["segment", "latency"], lat_rows) if lat_rows else "")
            + "</figure>"
        )
    return _section("spacetime", "Spacetime diagram", "".join(figs))


def certificates_view(certs: list[LoadedRecord], benches: list[LoadedRecord]) -> tuple[str, str | None]:
    """Returns (section html, pareto svg or None)."""
    blocks = []
    for r in certs:
        m: SecurityCertificate = r.model  # type: ignore[assignment]
        rid = r.record_id
        rows = []
        for ax in AXES:
            tgt = getattr(m.targets, ax)
            ub = getattr(m.upper_bounds, ax)
            lg = m.log10_upper_bounds.get(ax)
            if tgt is None and ub is None and lg is None:
                continue
            lg_html = render(Cited(lg, rid, m.evidence_kind), with_badge=False) if lg is not None else "&mdash;"
            rows.append([f"<code>{ax}</code>", render(bound(ub, rid, m.evidence_kind)), lg_html,
                         render(Cited(tgt, rid, EvidenceKind.UNCERTIFIED, "probability", missing="no target"),
                                with_badge=False)])  # a target is a request, not evidence
        st = m.proof_check_status
        blocks.append(
            f'<article class="card cert cert-{st.value.lower()}"><h3><code>{escape(rid)}</code> {sbadge(st)} '
            f"{ebadge(m.evidence_kind)}</h3>"
            f"{_warn_failed(m.failed_assumptions, rid)}"
            f"<p>Protocol <code>{escape(m.protocol_id)}</code>, game <code>{m.game_id.value}</code>, model "
            f"<code>{escape(m.security_model_id)}</code>, claim level <code>{m.claim_level.value}</code>.</p>"
            f"<p>Reason: {escape(m.reason)}. Proof reference: "
            f"{escape(m.proof_reference) if m.proof_reference else '<span class=missing>none</span>'}; "
            f"independent checker: {escape(m.checker_id) if m.checker_id else '<span class=missing>none</span>'}.</p>"
            + (_table(f"Bounds vs targets for {rid}", ["axis", "upper bound", "log10 bound", "target"], rows)
               if rows else "")
            + "</article>"
        )
    certified = {r.record_id for r in certs if r.model.proof_check_status == CertificateStatus.CERTIFIED}  # type: ignore[attr-defined]
    pts: list[tuple[float, float, bool, str]] = []
    dropped: list[str] = []
    for r in benches:
        b: BenchmarkRecord = r.model  # type: ignore[assignment]
        eps = b.security_target.epsilon_unf
        if eps is None or eps <= 0 or b.photons_prepared is None:
            dropped.append(r.record_id)
            continue
        ok = str(b.configuration.get("certificate_ref", "")) in certified
        pts.append((eps, float(b.photons_prepared), ok, r.record_id))
    svg = pareto_svg(pts, "Resource vs target epsilon (certified points only on the frontier)") if pts else None
    n_cert = sum(p[2] for p in pts)
    if svg:
        pnote = ("" if n_cert else '<div class="alert warn" role="note"><strong>No certified points.</strong> '
                 "The frontier is empty; hollow points are excluded because no CERTIFIED certificate backs them."
                 "</div>")
        pareto = (f'<figure class="card"><figcaption>Pareto view. Filled = backed by a CERTIFIED certificate; '
                  f"hollow = excluded.</figcaption>{pnote}<div class=\"figwrap\">{svg}</div>"
                  '<p><a download="pareto.svg" href="figures/pareto.svg">Download SVG</a></p></figure>')
    else:
        pareto = '<p class="muted">No benchmark points with a positive epsilon_unf target and photon count.</p>'
    if dropped:
        pareto += ('<p class="muted">Not plotted (no epsilon_unf target or photon count; log axis has no zero): '
                   + ", ".join(f'<a class="src" href="#{anchor(d)}">{escape(d)}</a>' for d in dropped) + "</p>")
    body = ("".join(blocks) or '<p class="muted">No SecurityCertificate loaded.</p>') + pareto
    return _section("certificates", "Certificates and Pareto view", body,
                    "Green appears only for CERTIFIED. A missing bound reads &ldquo;no applicable bound&rdquo;."), svg


def ledger_view(all_recs: list[LoadedRecord], manifests: list[LoadedRecord], skipped: list[Skipped]) -> str:
    rows = [[f'<span id="{anchor(r.record_id)}"><code>{escape(r.record_id)}</code></span>', escape(r.kind),
             ebadge(r.evidence), f"<code>{escape(r.source_path)}</code>",
             f'<code class="hash">{r.sha256}</code>'] for r in all_recs]
    body = (
        '<form class="chooser" onsubmit="return false"><label for="ledger-filter">Filter</label> '
        '<input id="ledger-filter" type="search" data-filter="ledger" placeholder="id, kind or badge"></form>'
        + _table("Every loaded record (canonical SHA-256 of the validated record)",
                 ["record id", "kind", "evidence", "file", "sha256"], rows)
    )
    for r in manifests:
        m: EvidenceManifest = r.model  # type: ignore[assignment]
        erows = [[f"<code>{escape(e.path_or_uri)}</code>", e.role, e.original_or_derived,
                  f'<code class="hash">{e.sha256}</code>'] for e in m.entries]
        body += (f'<h3>Manifest <code>{escape(r.record_id)}</code> {ebadge(m.evidence_kind)}</h3>'
                 f"<p>Command <code>{escape(m.command)}</code>, git <code>{escape(m.git_sha)}</code>.</p>"
                 + _table(f"Entries of {r.record_id}", ["path", "role", "origin", "sha256"], erows))
    if skipped:
        srows = [[f"<code>{escape(s.source_path)}</code>", escape(s.reason)] for s in skipped]
        body += _table("Rejected inputs (failed frozen-contract validation)", ["file", "reason"], srows)
    return _section("ledger", "Evidence ledger", body)


def hardware_view(attacks: list[LoadedRecord], benches: list[LoadedRecord]) -> str:
    hw_kinds = (EvidenceKind.QPU, EvidenceKind.SIMULATOR_IDEAL, EvidenceKind.SIMULATOR_NOISY)
    rows = [[f'<a class="src" href="#{anchor(r.record_id)}">{escape(r.record_id)}</a>', escape(r.kind),
             ebadge(r.evidence)] for r in [*attacks, *benches] if r.evidence in hw_kinds]
    qpu = [r for r in [*attacks, *benches] if r.evidence == EvidenceKind.QPU]
    status = ("" if qpu else '<div class="alert warn" role="note"><strong>QPU jobs: not run.</strong> '
              "No QPU record is loaded, so the job count is unknown and is not reported as zero.</div>")
    body = (status + '<p class="caption-big">Quantum-circuit primitive demonstration, not proof of a physically '
            "deployable quantum-cash system.</p>"
            + (_table("Circuit / hardware records", ["record", "kind", "evidence"], rows) if rows
               else '<p class="muted">No simulator or QPU records loaded.</p>'))
    return _section("hardware", "Hardware provenance", body)


def claim_panel(all_recs: list[LoadedRecord]) -> ClaimPanel:
    """Headline claims, built only from cited record values."""
    panel = ClaimPanel(frozenset(r.record_id for r in all_recs))
    for r in all_recs:
        if r.kind == "certificate":
            m: SecurityCertificate = r.model  # type: ignore[assignment]
            panel.add(f"Certificate `{r.record_id}` (game `{m.game_id.value}`) status "
                      f"{status_badge(m.proof_check_status).label}; epsilon_unf upper bound {{0}}.",
                      [bound(m.upper_bounds.epsilon_unf, r.record_id, m.evidence_kind)])
        elif r.kind == "attack":
            a: AttackResult = r.model  # type: ignore[assignment]
            if a.success_rate_ci is not None:
                panel.add(f"Attack `{r.record_id}` (game `{a.game_id.value}`): sampled success rate in "
                          "[{0}, {1}] - a lower bound on worst-case attack success.",
                          [Cited(a.success_rate_ci.lo, r.record_id, a.evidence_kind),
                           Cited(a.success_rate_ci.hi, r.record_id, a.evidence_kind)])
            if a.sdp_primal is not None and a.sdp_dual is not None:
                panel.add(f"SDP `{r.record_id}`: primal {{0}}, dual {{1}}.",
                          [Cited(a.sdp_primal, r.record_id, a.evidence_kind),
                           Cited(a.sdp_dual, r.record_id, a.evidence_kind)])
    return panel
