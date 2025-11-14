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

from __future__ import annotations

from typing import Dict, List, Tuple


from .models import DealerPolicy, SessionLocal
from .pn import search_pn_batch
from .types import (
    OptimizeItem,
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
    for line in lines:
        per_dealer[line.dealer] = per_dealer.get(line.dealer, 0.0) + float(
            line.line_total or 0.0
        )
    dealers = list(per_dealer.keys())
    with SessionLocal() as db:
        rows = (
            db.query(
                DealerPolicy.dealer, DealerPolicy.base_cost, DealerPolicy.free_threshold
            )
            .filter(DealerPolicy.dealer.in_(dealers))
            .all()
        )
    policy: Dict[str, Tuple[float | None, float | None]] = {
        str(name): (
            float(cost) if cost is not None else None,
            float(thr) if thr is not None else None,
        )
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
    """Optimize an order given PN items and heuristic params.

    Public semantics are preserved: the same scenarios and cost model apply.
    """
    items = req.items
    params: OptimizeParams = req.params
    batch = search_pn_batch(SearchPNBatchRequest(items=[it.maker_pn for it in items]))
    per_pn: List[List[PNOfferItem]] = [res.offers for res in batch.results]
    qty_list: List[int] = [max(1, int(it.qty)) for it in items]

    lines, notes = _lines_for_scenario(items, per_pn, qty_list, params)
    dealers, costs = _compute_costs(lines, params)
    return OptimizeResponse(lines=lines, dealers=dealers, costs=costs, notes=notes)


def _lines_for_scenario(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    params: OptimizeParams,
) -> Tuple[List[OptimizeLine], List[str]]:
    scenario = (params.scenario or "miglior-prezzo").lower()
    if scenario == "miglior-prezzo":
        return _scenario_miglior_prezzo(items, per_pn, qty_list)
    if scenario == "piu-veloce":
        return _scenario_piu_veloce(items, per_pn, qty_list)
    if scenario == "un-solo-dealer":
        return _scenario_un_solo_dealer(items, per_pn, qty_list, params)
    if scenario == "max-n-dealer":
        return _scenario_max_n_dealer(items, per_pn, qty_list, params)
    # Fallback: behave like 'miglior-prezzo'
    return _scenario_miglior_prezzo(items, per_pn, qty_list)


def _scenario_miglior_prezzo(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
) -> Tuple[List[OptimizeLine], List[str]]:
    lines: List[OptimizeLine] = []
    for offers, q, pn in zip(per_pn, qty_list, [it.maker_pn for it in items]):
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
    return lines, []


def _scenario_piu_veloce(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
) -> Tuple[List[OptimizeLine], List[str]]:
    lines: List[OptimizeLine] = []
    for offers, q, pn in zip(per_pn, qty_list, [it.maker_pn for it in items]):
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
    return lines, []


def _scenario_un_solo_dealer(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    params: OptimizeParams,
) -> Tuple[List[OptimizeLine], List[str]]:
    notes: List[str] = []
    per_pn_dealers: List[set[str]] = [
        set(o.dealer for o in offers) for offers in per_pn
    ]
    common = set.intersection(*per_pn_dealers) if per_pn_dealers else set()
    if not common:
        notes.append("Nessun dealer singolo copre tutti i PN; fallback miglior-prezzo")
        lines, _ = _scenario_miglior_prezzo(items, per_pn, qty_list)
        return lines, notes
    best: Tuple[float, str, List[OptimizeLine]] | None = None
    for d in common:
        cand_lines: List[OptimizeLine] = []
        ok = True
        for offers, q, pn in zip(per_pn, qty_list, [it.maker_pn for it in items]):
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
        subtotal = sum(line.line_total for line in cand_lines)
        ship = _shipping_costs(cand_lines)
        lead_avg = _avg_lead(cand_lines)
        penalties = params.penale_lead * lead_avg
        tot = subtotal + ship + penalties
        if best is None or tot < best[0]:
            best = (tot, d, cand_lines)
    if best:
        _, _, lines = best
        return lines, notes
    # If no consistent candidate, fall back to miglior-prezzo
    lines, _ = _scenario_miglior_prezzo(items, per_pn, qty_list)
    return lines, notes


def _scenario_max_n_dealer(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    params: OptimizeParams,
) -> Tuple[List[OptimizeLine], List[str]]:
    N = int(params.max_dealer or 1)
    base_lines: List[OptimizeLine] = []
    base_idx: List[int] = []
    for idx, (offers, q, pn) in enumerate(
        zip(per_pn, qty_list, [it.maker_pn for it in items])
    ):
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
    if not base_lines:
        return [], []
    lines = _reduce_dealers_greedy(base_lines, base_idx, per_pn, qty_list, N, params)
    return lines, []


def _compute_costs(
    lines: List[OptimizeLine], params: OptimizeParams
) -> Tuple[List[str], OptimizeCost]:
    dealers = sorted(list({line.dealer for line in lines}))
    subtotal = sum(line.line_total for line in lines)
    ship = _shipping_costs(lines)
    lead_avg = _avg_lead(lines)
    penalties = (
        params.penale_dealer * max(0, len(dealers) - 1) + params.penale_lead * lead_avg
    )
    total = subtotal + ship + penalties
    return dealers, OptimizeCost(
        subtotal=subtotal, shipping=ship, penalties=penalties, total=total
    )


def _avg_lead(lines: List[OptimizeLine]) -> float:
    vals = [
        int(line.lead_time_days) for line in lines if line.lead_time_days is not None
    ]
    return (sum(vals) / len(vals)) if vals else 0.0


def _reduce_dealers_greedy(
    lines: List[OptimizeLine],
    line_idx: List[int],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    N: int,
    params: OptimizeParams,
) -> List[OptimizeLine]:
    # Greedy: while dealers > N, pick the dealer whose removal increases total least
    curr = list(lines)
    curr_idx = list(line_idx)

    def dealers_of(ls: List[OptimizeLine]) -> List[str]:
        return sorted(list({line.dealer for line in ls}))

    while len(dealers_of(curr)) > max(1, N):
        dealers = dealers_of(curr)
        # Compute current total including shipping and penalties
        curr_sub = sum(line.line_total for line in curr)
        curr_ship = _shipping_costs(curr)
        curr_lead = _avg_lead(curr)
        curr_pen = (
            params.penale_dealer * max(0, len(dealers) - 1)
            + params.penale_lead * curr_lead
        )
        curr_total = curr_sub + curr_ship + curr_pen

        best_choice: Tuple[float, str, List[OptimizeLine], List[int]] | None = None
        for d in dealers:
            # Reassign lines currently served by d to next best offers from other dealers
            cand: List[OptimizeLine] = []
            cand_idx: List[int] = []
            for pos, line in enumerate(curr):
                if line.dealer != d:
                    cand.append(line)
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
                    maker_pn=line.maker_pn,
                    dealer=nb.dealer,
                    unit_price=nb.price,
                    qty=line.qty,
                    line_total=unit * line.qty,
                    lead_time_days=nb.lead_time_days,
                )
                cand.append(new_line)
                cand_idx.append(idx)
            if not cand:
                continue
            # Compute full candidate total including shipping and penalties
            cand_dealers = dealers_of(cand)
            cand_sub = sum(line.line_total for line in cand)
            cand_ship = _shipping_costs(cand)
            cand_lead = _avg_lead(cand)
            cand_pen = (
                params.penale_dealer * max(0, len(cand_dealers) - 1)
                + params.penale_lead * cand_lead
            )
            cand_total = cand_sub + cand_ship + cand_pen
            delta = cand_total - curr_total
            if best_choice is None or delta < best_choice[0]:
                best_choice = (delta, d, cand, cand_idx)
        if best_choice is None:
            break
        curr = best_choice[2]
        # Apply the PN index list selected for the chosen candidate
        curr_idx = best_choice[3]
    return curr
