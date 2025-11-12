from __future__ import annotations

"""Order optimizer (v1 heuristic).

Scenarios:
- 'miglior-prezzo': per PN choose cheapest offer (in-stock first, then price), sum shipping per dealer.
- 'un-solo-dealer': pick a single dealer that can fulfil all PNs at minimal cost; if none, fall back to 'miglior-prezzo'.
- 'max-n-dealer': greedy reduction from 'miglior-prezzo' to at most N dealers.
- 'piu-veloce': per PN choose lowest lead (tie-break by price), then sum shipping.

Penalties:
- dealer penalty per extra dealer beyond 1
- lead penalty per average days

Note: Simple heuristics suitable for demo; can be upgraded to ILP later.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from sqlalchemy import select, func

from .models import DealerPolicy, SessionLocal
from .pn import search_pn_batch, normalize_pn
from .types import (
    OptimizeRequest,
    OptimizeResponse,
    OptimizeLine,
    OptimizeCost,
    OptimizeParams,
    PNOfferItem,
    SearchPNBatchRequest,
)


def _shipping_costs(lines: List[OptimizeLine]) -> float:
    """Compute shipping as sum of per-dealer costs using each dealer's line subtotal.

    Free-shipping thresholds are evaluated against the subtotal of the lines
    assigned to that specific dealer, not the whole order subtotal.
    """
    if not lines:
        return 0.0
    # Subtotal per dealer
    per_dealer: Dict[str, float] = {}
    for l in lines:
        per_dealer[l.dealer] = per_dealer.get(l.dealer, 0.0) + float(l.line_total or 0.0)
    dealers = list(per_dealer.keys())
    with SessionLocal() as db:
        rows = (
            db.query(DealerPolicy.dealer, DealerPolicy.base_cost, DealerPolicy.free_threshold)
            .filter(DealerPolicy.dealer.in_(dealers))
            .all()
        )
    policy: Dict[str, Tuple[float | None, float | None]] = {
        str(name): (float(cost) if cost is not None else None, float(thr) if thr is not None else None)
        for (name, cost, thr) in rows
    }
    total = 0.0
    for d, dealer_subtotal in per_dealer.items():
        base, thr = policy.get(d, (6.9, 49.0))  # fallback defaults when policy missing
        if thr is not None and dealer_subtotal >= thr:
            continue
        total += float(base or 0.0)
    return total


def _pick_cheapest(offers: List[PNOfferItem]) -> PNOfferItem | None:
    if not offers:
        return None
    # in-stock first, then price, then lead
    def key(o: PNOfferItem) -> Tuple[int, float, int]:
        instock = 0 if o.in_stock else 1
        price = o.price if o.price is not None else float("inf")
        lead = o.lead_time_days if o.lead_time_days is not None else 9999
        return (instock, price, lead)

    return sorted(offers, key=key)[0]


def _pick_fastest(offers: List[PNOfferItem]) -> PNOfferItem | None:
    if not offers:
        return None
    def key(o: PNOfferItem) -> Tuple[int, float]:
        lead = o.lead_time_days if o.lead_time_days is not None else 9999
        price = o.price if o.price is not None else float("inf")
        return (lead, price)
    return sorted(offers, key=key)[0]


def optimize(req: OptimizeRequest) -> OptimizeResponse:
    items = req.items
    params: OptimizeParams = req.params
    # Resolve offers per PN via batch search (preserve multiplicity)
    batch = search_pn_batch(
        SearchPNBatchRequest(items=[it.maker_pn for it in items])
    )
    # Build candidate lists
    per_pn: List[List[PNOfferItem]] = [res.offers for res in batch.results]
    qty_list: List[int] = [max(1, int(it.qty)) for it in items]

    lines: List[OptimizeLine] = []
    notes: List[str] = []

    scenario = (params.scenario or "miglior-prezzo").lower()

    if scenario == "miglior-prezzo":
        for (offers, q, pn) in zip(per_pn, qty_list, [it.maker_pn for it in items]):
            o = _pick_cheapest(offers)
            if not o:
                continue
            unit = float(o.price or 0.0)
            lines.append(
                OptimizeLine(
                    maker_pn=pn,
                    dealer=o.dealer,
                    unit_price=o.price,
                    qty=q,
                    line_total=unit * q,
                    lead_time_days=o.lead_time_days,
                )
            )
    elif scenario == "piu-veloce":
        for (offers, q, pn) in zip(per_pn, qty_list, [it.maker_pn for it in items]):
            o = _pick_fastest(offers)
            if not o:
                continue
            unit = float(o.price or 0.0)
            lines.append(
                OptimizeLine(
                    maker_pn=pn,
                    dealer=o.dealer,
                    unit_price=o.price,
                    qty=q,
                    line_total=unit * q,
                    lead_time_days=o.lead_time_days,
                )
            )
    elif scenario == "un-solo-dealer":
        # Find dealers that can serve all PNs
        # Gather set of dealers per PN
        per_pn_dealers: List[set[str]] = [set(o.dealer for o in offers) for offers in per_pn]
        common = set.intersection(*per_pn_dealers) if per_pn_dealers else set()
        if not common:
            notes.append("Nessun dealer singolo copre tutti i PN; fallback miglior-prezzo")
            params = OptimizeParams(scenario="miglior-prezzo", penale_dealer=params.penale_dealer, penale_lead=params.penale_lead)
            return optimize(OptimizeRequest(items=req.items, params=params))
        # For each candidate dealer, compute cost choosing its offers
        best: Tuple[float, str, List[OptimizeLine]] | None = None
        for d in common:
            cand_lines: List[OptimizeLine] = []
            ok = True
            for (offers, q, pn) in zip(per_pn, qty_list, [it.maker_pn for it in items]):
                # choose offer for dealer d
                cand = [o for o in offers if o.dealer == d]
                sel = _pick_cheapest(cand)
                if not sel:
                    ok = False
                    break
                unit = float(sel.price or 0.0)
                cand_lines.append(
                    OptimizeLine(
                        maker_pn=pn,
                        dealer=sel.dealer,
                        unit_price=sel.price,
                        qty=q,
                        line_total=unit * q,
                        lead_time_days=sel.lead_time_days,
                    )
                )
            if not ok:
                continue
            subtotal = sum(l.line_total for l in cand_lines)
            ship = _shipping_costs(cand_lines)
            lead_avg = _avg_lead(cand_lines)
            penalties = params.penale_lead * lead_avg
            tot = subtotal + ship + penalties
            if best is None or tot < best[0]:
                best = (tot, d, cand_lines)
        if best:
            _, _, lines = best
    elif scenario == "max-n-dealer":
        N = int(params.max_dealer or 1)
        # Start from best price per PN
        base_lines: List[OptimizeLine] = []
        base_idx: List[int] = []
        for idx, (offers, q, pn) in enumerate(zip(per_pn, qty_list, [it.maker_pn for it in items])):
            o = _pick_cheapest(offers)
            if not o:
                continue
            unit = float(o.price or 0.0)
            base_lines.append(
                OptimizeLine(
                    maker_pn=pn,
                    dealer=o.dealer,
                    unit_price=o.price,
                    qty=q,
                    line_total=unit * q,
                    lead_time_days=o.lead_time_days,
                )
            )
            base_idx.append(idx)
        lines = _reduce_dealers_greedy(base_lines, base_idx, per_pn, qty_list, N)
    else:
        # default fallback
        return optimize(OptimizeRequest(items=req.items, params=OptimizeParams(scenario="miglior-prezzo", penale_dealer=params.penale_dealer, penale_lead=params.penale_lead)))

    dealers = sorted(list({l.dealer for l in lines}))
    subtotal = sum(l.line_total for l in lines)
    ship = _shipping_costs(lines)
    lead_avg = _avg_lead(lines)
    penalties = params.penale_dealer * max(0, len(dealers) - 1) + params.penale_lead * lead_avg
    total = subtotal + ship + penalties
    return OptimizeResponse(
        lines=lines,
        dealers=dealers,
        costs=OptimizeCost(subtotal=subtotal, shipping=ship, penalties=penalties, total=total),
        notes=notes,
    )


def _avg_lead(lines: List[OptimizeLine]) -> float:
    vals = [int(l.lead_time_days) for l in lines if l.lead_time_days is not None]
    return (sum(vals) / len(vals)) if vals else 0.0


def _reduce_dealers_greedy(
    lines: List[OptimizeLine], line_idx: List[int], per_pn: List[List[PNOfferItem]], qty_list: List[int], N: int
) -> List[OptimizeLine]:
    # Greedy: while dealers > N, pick the dealer whose removal increases total least
    curr = list(lines)
    curr_idx = list(line_idx)
    def dealers_of(ls: List[OptimizeLine]) -> List[str]:
        return sorted(list({l.dealer for l in ls}))

    while len(dealers_of(curr)) > max(1, N):
        dealers = dealers_of(curr)
        worst_choice: Tuple[float, str, List[OptimizeLine]] | None = None
        for d in dealers:
            # Reassign lines currently served by d to next best offers from other dealers
            cand: List[OptimizeLine] = []
            cand_idx: List[int] = []
            cost_increase = 0.0
            for pos, l in enumerate(curr):
                if l.dealer != d:
                    cand.append(l)
                    cand_idx.append(curr_idx[pos])
                    continue
                # choose next best from other dealers for PN idx
                idx = curr_idx[pos]
                offers = per_pn[idx]
                alt = [o for o in offers if o.dealer != d]
                nb = _pick_cheapest(alt)
                if not nb:
                    cand = []
                    break
                unit = float(nb.price or 0.0)
                new_line = OptimizeLine(
                    maker_pn=l.maker_pn,
                    dealer=nb.dealer,
                    unit_price=nb.price,
                    qty=l.qty,
                    line_total=unit * l.qty,
                    lead_time_days=nb.lead_time_days,
                )
                cand.append(new_line)
                cand_idx.append(idx)
                cost_increase += (new_line.line_total - l.line_total)
            if not cand:
                continue
            if worst_choice is None or cost_increase < worst_choice[0]:
                worst_choice = (cost_increase, d, cand)
        if worst_choice is None:
            break
        curr = worst_choice[2]
        # Recompute curr_idx consistent with curr by rebuilding from cand_idx above
        # Since worst_choice was built in this loop, reuse cand_idx from the last iteration
        curr_idx = cand_idx
    return curr
