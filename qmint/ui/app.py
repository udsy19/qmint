"""Assemble the self-contained workbench site (inline CSS/JS, no network, deterministic)."""

from __future__ import annotations

import json
from html import escape

from qmint.core.contracts import EvidenceKind
from qmint.core.serialization import sha256_hex
from qmint.ui import views
from qmint.ui.claims import anchor
from qmint.ui.evidence_badges import all_badges
from qmint.ui.records import LoadedRecord, Skipped
from qmint.ui.svg import spacetime_svg

BANNER = "Research simulator — not money, not a payment system"
FIXTURE_LABEL = "FIXTURE DATA"

_TONES = {  # light, dark: (fg, bg)
    "ok": (("#0b5d1e", "#d7f5de"), ("#9be7ad", "#123d1d")),
    "info": (("#123f7a", "#dde9fb"), ("#a9c8f5", "#15284a")),
    "neutral": (("#333", "#e6e6e6"), ("#ddd", "#333")),
    "warn": (("#6b4300", "#fdebc8"), ("#f6cf86", "#4a3307")),
    "danger": (("#8a1111", "#fbdcdc"), ("#f5a3a3", "#4d1414")),
}

_CSS_BASE = """
:root{color-scheme:light dark;--bg:#fbfaf7;--fg:#1b1b1b;--muted:#5d5d5d;--card:#fff;--line:#d5d2c8;
--accent:#3a4fb8;--danger:#8a1111;--danger-bg:#fbdcdc;--warn:#6b4300;--warn-bg:#fdebc8;--fix:#6b4300;
--fix-bg:repeating-linear-gradient(45deg,#fdebc8 0 12px,#f9dfa8 12px 24px)}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ececea;--muted:#a8a8a3;--card:#1e1e1c;
--line:#3a3a36;--accent:#a8b4f5;--danger:#f5a3a3;--danger-bg:#4d1414;--warn:#f6cf86;--warn-bg:#4a3307;
--fix:#f6cf86;--fix-bg:repeating-linear-gradient(45deg,#4a3307 0 12px,#3d2a06 12px 24px)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent)}code{font:0.9em ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:var(--card);padding:8px;z-index:9}
header.top{border-bottom:1px solid var(--line);padding:12px 16px}
.banner{font-weight:700;margin:0}
.fixture{background:var(--fix-bg);color:var(--fix);border:2px solid currentColor;font-weight:800;
letter-spacing:.06em;text-align:center;padding:10px 16px;margin:0;font-size:1.15rem}
nav ul{list-style:none;margin:8px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:4px 16px}
main{max-width:1080px;margin:0 auto;padding:0 16px 48px}
section{margin-top:32px}h1{font-size:1.5rem;margin:4px 0}h2{border-bottom:1px solid var(--line);padding-bottom:4px}
.intro,.muted{color:var(--muted)}.missing{font-style:italic;color:var(--muted)}
.missing::before{content:"\\2014 "}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
details.proto{border:1px solid var(--line);border-radius:8px;margin:8px 0;padding:8px 12px;background:var(--card)}
details.proto summary{cursor:pointer}.tag{font-size:.8em;color:var(--muted)}
.tbl{overflow-x:auto;margin:8px 0}table{border-collapse:collapse;width:100%;font-size:.92em}
caption{text-align:left;color:var(--muted);padding:4px 0}th,td{border-bottom:1px solid var(--line);
padding:6px 8px;text-align:left;vertical-align:top}.hash{font-size:.75em}
.badge{display:inline-block;border-radius:4px;padding:0 6px;font:700 .72rem/1.6 ui-monospace,monospace;
letter-spacing:.03em;border:1px solid currentColor;white-space:nowrap}
.cited{white-space:normal}.src{font-size:.78em;color:var(--muted)}.unit{color:var(--muted);font-size:.9em}
.alert{border-left:6px solid currentColor;padding:8px 12px;margin:8px 0;border-radius:4px}
.alert.danger{color:var(--danger);background:var(--danger-bg)}.alert.warn{color:var(--warn);background:var(--warn-bg)}
.alert ul{margin:4px 0}.claims li{margin:6px 0}
.caption-big{font-size:1.15rem;font-weight:700}
.chooser{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
select,input{font:inherit;padding:4px 8px;max-width:100%}
.figwrap{overflow-x:auto}svg.fig{width:100%;min-width:320px;height:auto;max-width:720px}
svg .axis{stroke:var(--fg);stroke-width:1}svg .worldline{stroke:var(--line);stroke-width:2}
svg .edge{stroke:var(--fg);stroke-width:1.2;opacity:.7}
svg .cone{stroke:var(--accent);stroke-dasharray:6 4;stroke-width:1.2}
svg .lbl,svg .evl{fill:var(--fg);font:11px ui-monospace,monospace}
svg .mk{stroke:var(--fg);stroke-width:1.2;fill:var(--card)}svg .mk-validation{fill:var(--accent)}
svg .mk-settlement{fill:var(--muted)}svg .mk-irrevocable{fill:var(--fg)}svg .cross{stroke:var(--danger);stroke-width:2.5}
svg .frontier{fill:none;stroke:var(--fg);stroke-width:2}svg .pt-cert{fill:var(--fg)}
svg .pt-excl{fill:none;stroke:var(--muted);stroke-width:1.5;stroke-dasharray:3 2}
footer{color:var(--muted);font-size:.85em;border-top:1px solid var(--line);margin-top:48px;padding:16px}
@media (max-width:600px){body{font-size:15px}th,td{padding:4px}}
@media print{.chooser{display:none}}
"""

# Progressive enhancement only: the page is complete without JS.
_JS = """
(function(){var s=document.getElementById('proto-pick');if(s){s.addEventListener('change',function(){
var v=s.value;document.querySelectorAll('details.proto').forEach(function(d){
var on=!v||d.getAttribute('data-proto')===v;d.hidden=!on;if(v&&on)d.open=true;});});}
var f=document.getElementById('ledger-filter');if(f){f.addEventListener('input',function(){
var q=f.value.toLowerCase();document.querySelectorAll('#ledger tbody tr').forEach(function(tr){
tr.hidden=q&&tr.textContent.toLowerCase().indexOf(q)<0;});});}})();
"""


def _badge_css() -> str:
    light, dark = [], []
    for b in sorted(all_badges(), key=lambda b: b.css):
        (lf, lb), (df, db) = _TONES[b.tone]
        # Origin is encoded in the border style too: measured = double, simulated = dashed.
        border = {"measured": "3px double", "simulated": "1px dashed"}.get(b.origin, "1px solid")
        light.append(f".b-{b.css}{{color:{lf};background:{lb};border:{border} currentColor}}")
        dark.append(f".b-{b.css}{{color:{df};background:{db}}}")
    return "\n".join(light) + "\n@media (prefers-color-scheme:dark){" + "".join(dark) + "}\n"


def is_fixture(recs: list[LoadedRecord], real_data: bool) -> bool:
    """Fail-safe: the site is FIXTURE DATA unless explicitly built as real data with no synthetic record."""
    return not real_data or any(r.evidence == EvidenceKind.SYNTHETIC for r in recs)


def render_site(recs: list[LoadedRecord], skipped: list[Skipped], *, real_data: bool = False) -> dict[str, str]:
    """Return {relative path: file text}. Pure and deterministic for a given input."""
    by = {k: [r for r in recs if r.kind == k] for k in
          ("protocol", "attack", "calibration", "trace", "network", "certificate", "benchmark", "manifest")}
    networks = {r.record_id: r for r in by["network"]}
    fixture = is_fixture(recs, real_data)

    cert_html, pareto = views.certificates_view(by["certificate"], by["benchmark"])
    sections = [
        views._section("claims", "Claim panel", views.claim_panel(recs).render(),
                       "Only numbers that cite a loaded record can appear here."),
        views.protocols_view(by["protocol"], by["certificate"]),
        views.attacks_view(by["attack"]),
        views.calibration_view(by["calibration"]),
        views.spacetime_view(by["trace"], networks),
        cert_html,
        views.ledger_view(recs, by["manifest"], skipped),
        views.hardware_view(by["attack"], by["benchmark"]),
    ]
    nav = [("claims", "Claims"), ("protocols", "Protocols & games"), ("attacks", "Attacks"),
           ("photon", "Photon data"), ("spacetime", "Spacetime"), ("certificates", "Certificates"),
           ("ledger", "Evidence ledger"), ("hardware", "Hardware")]
    fix_html = (f'<p class="fixture" role="status">{FIXTURE_LABEL} — synthetic records for interface testing; '
                "no number on this page is a research result.</p>" if fixture else "")
    title = f"QMint evidence workbench{' (' + FIXTURE_LABEL + ')' if fixture else ''}"
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f"<title>{escape(title)}</title><style>{_CSS_BASE}{_badge_css()}</style></head><body>"
        '<a class="skip" href="#main">Skip to content</a>'
        f'{fix_html}<header class="top"><p class="banner" role="note">{escape(BANNER)}</p>'
        f"<h1>{escape(title)}</h1>"
        '<nav aria-label="Sections"><ul>'
        + "".join(f'<li><a href="#{sid}">{escape(lbl)}</a></li>' for sid, lbl in nav)
        + '</ul></nav></header><main id="main">'
        + "".join(sections)
        + "</main><footer><p>"
        + escape(BANNER)
        + ". Every badge is derived from the record's EvidenceKind or CertificateStatus. Monte Carlo values"
        " are lower bounds on worst-case attack success. Download the "
        '<a href="site_manifest.json" download>site manifest</a>.</p>'
        + (f"<p><strong>{FIXTURE_LABEL}</strong></p>" if fixture else "")
        + f"</footer><script>{_JS}</script></body></html>\n"
    )
    files: dict[str, str] = {"index.html": html}
    for r in by["trace"]:
        net = networks.get(r.model.network_id)  # type: ignore[attr-defined]
        files[f"figures/spacetime-{anchor(r.record_id)}.svg"] = spacetime_svg(
            r.model, net.model if net else None, r.record_id  # type: ignore[arg-type]
        ) + "\n"
    if pareto:
        files["figures/pareto.svg"] = pareto + "\n"
    manifest = {
        "fixture_data": fixture,
        "banner": BANNER,
        "records": [{"record_id": r.record_id, "kind": r.kind, "evidence_kind": r.evidence.value,
                     "source_path": r.source_path, "sha256": r.sha256} for r in recs],
        "skipped": [{"source_path": s.source_path, "reason": s.reason} for s in skipped],
        "files": {p: sha256_hex(t) for p, t in sorted(files.items())},
    }
    files["site_manifest.json"] = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    return files
