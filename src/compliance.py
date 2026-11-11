"""Deterministic checks for explicitly confirmed fresh-perishable cargo only.
Rules are read from the bundled SOP, not a substitute for dispatcher approval.
"""
import math
from src.retrieval import ROOT

SOURCE = 'Cold_Chain_Incident_SOP_v2.md'


def evaluate(temperature_c, cargo_type, risk_classification=None, delay_probability=None,
             port_congestion=None, eta_delay_hours=None):
    values = [temperature_c, delay_probability, port_congestion, eta_delay_hours]
    if any(v is not None and (isinstance(v, bool) or not math.isfinite(v)) for v in values):
        raise ValueError('Measurements must be finite numbers.')
    if delay_probability is not None and not 0 <= delay_probability <= 1:
        raise ValueError('Delay probability must be between zero and one.')
    if eta_delay_hours is not None and eta_delay_hours < 0:
        raise ValueError('ETA delay cannot be negative.')
    if port_congestion is not None and not 0 <= port_congestion <= 10:
        raise ValueError('Port congestion must be between zero and ten.')
    # This deterministic rule pack is version-bound. Fail closed after a policy edit.
    import hashlib
    digest = hashlib.sha256((ROOT / 'data/policy' / SOURCE).read_bytes()).hexdigest()
    if digest != POLICY_SHA256:
        return {'status': 'policy_review_required', 'reason': 'SOP changed; review and update the deterministic rules before use.'}
    if cargo_type != 'fresh_perishables':
        return {'status': 'unknown', 'reason': 'Confirm fresh-perishable cargo before applying its temperature limits.'}
    findings = []
    actions = []
    if temperature_c > 4:
        findings.append('Critical breach: fresh-perishable temperature exceeds 4 C.')
        actions.append('Dispatcher should contact the driver to restart the auxiliary cooling unit.')
        if eta_delay_hours is None:
            actions.append('Verify ETA delay before deciding whether the cold-storage diversion rule applies.')
        elif eta_delay_hours > 1:
            actions.append('Dispatcher should arrange diversion to the nearest emergency cold-storage facility.')
    elif temperature_c < 0:
        findings.append('Below the fresh-perishable 0–4 C range; the SOP critical-breach definition only specifies above 4 C.')
        actions.append('Request supervisor review; no freezing-specific mitigation is supplied by this SOP.')
    else:
        findings.append('Temperature is within the fresh-perishable 0–4 C range for this observation only.')
    if risk_classification and risk_classification.casefold().strip() == 'high risk' and delay_probability is not None and delay_probability > .65:
        findings.append('Tier 2 escalation threshold met.')
        actions.append('Dispatcher should escalate to the Tier 2 Logistics Manager.')
    if port_congestion is not None and port_congestion > 7:
        findings.append('Port congestion diversion threshold met; verify Long Beach / LA scope.')
        actions.append('For Long Beach / LA port operations, dispatcher should divert to Inland Empire Overflow Depot for cross-docking.')
    return {'status': 'evaluated', 'findings': findings, 'recommendations': actions,
            'citations': [f'{SOURCE} — 1. Temperature Control & Spoilage Prevention (Cold-Chain)',
                          f'{SOURCE} — 2. Route Congestion & Diversion Tactics',
                          f'{SOURCE} — 3. Risk Classification Triggers'],
            'warning': 'Advisory only. Confirm shipment identity, cargo type, timestamp and missing measurements. No actions have been executed.'}

POLICY_SHA256 = 'a920645b4af242a8de35430a3bf93e1d64eacd6346d2a46916ae874799afd9b0'
