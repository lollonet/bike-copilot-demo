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


from .logging_utils import log_event
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


def _shipping_costs(lines: List[OptimizeLine], db=None) -> float:
    """Compute shipping as sum of per-dealer costs using each dealer's line subtotal.

    Free-shipping thresholds are evaluated against the subtotal of the lines
    assigned to that specific dealer, not the whole order subtotal.
    """
    if not lines:
        return 0.0
    per_dealer = _dealer_subtotals(lines)
    policy = _load_shipping_policy(list(per_dealer.keys()), db=db)
    total = 0.0
    for dealer, dealer_subtotal in per_dealer.items():
        total += _shipping_for_dealer(dealer, dealer_subtotal, policy)
    return total


def _dealer_subtotals(lines: List[OptimizeLine]) -> Dict[str, float]:
    per_dealer: Dict[str, float] = {}
    for line in lines:
        per_dealer[line.dealer] = per_dealer.get(line.dealer, 0.0) + float(
            line.line_total or 0.0
        )
    return per_dealer


def _load_shipping_policy(
    dealers: List[str], db=None
) -> Dict[str, Tuple[float | None, float | None]]:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    if db is None:
        with SessionLocal() as scoped_db:
            return _load_shipping_policy(dealers, scoped_db)

    assert isinstance(db, Session)
    rows = db.execute(
        select(
            DealerPolicy.dealer, DealerPolicy.base_cost, DealerPolicy.free_threshold
        ).where(DealerPolicy.dealer.in_(dealers))
    ).all()
    policy: Dict[str, Tuple[float | None, float | None]] = {}
    for name, cost, thr in rows:
        policy[str(name)] = (
            float(cost) if cost is not None else None,
            float(thr) if thr is not None else None,
        )
    return policy


def _shipping_for_dealer(
    dealer: str,
    dealer_subtotal: float,
    policy: Dict[str, Tuple[float | None, float | None]],
) -> float:
    base, thr = policy.get(dealer, (6.9, 49.0))
    if thr is not None and dealer_subtotal >= thr:
        return 0.0
    return float(base or 0.0)


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


def optimize(req: OptimizeRequest, db=None) -> OptimizeResponse:
    """Optimize an order given PN items and heuristic params.

    Public semantics are preserved: the same scenarios and cost model apply.
    """
    items = req.items
    params: OptimizeParams = req.params
    batch = search_pn_batch(
        SearchPNBatchRequest(items=[it.maker_pn for it in items]), db=db
    )
    per_pn: List[List[PNOfferItem]] = [res.offers for res in batch.results]
    qty_list: List[int] = [max(1, int(it.qty)) for it in items]

    locked_offers, lock_notes = _apply_locked_dealers(per_pn, items)
    lines, scenario_notes = _lines_for_scenario(items, locked_offers, qty_list, params)
    dealers, costs = _compute_costs(lines, params, db=db)
    notes = lock_notes + scenario_notes
    log_event(
        "INFO",
        op="optimize",
        kind="service",
        message="order optimization completed",
        trace_id=None,
        extra={
            "scenario": params.scenario or "miglior-prezzo",
            "items": len(items),
            "dealers": len(dealers),
        },
    )
    return OptimizeResponse(lines=lines, dealers=dealers, costs=costs, notes=notes)


def _lines_for_scenario(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    params: OptimizeParams,
) -> Tuple[List[OptimizeLine], List[str]]:
    scenario = (params.scenario or "miglior-prezzo").lower()
    if scenario == "miglior-prezzo":
        return _lines_scenario_miglior_prezzo(items, per_pn, qty_list)
    if scenario == "piu-veloce":
        return _lines_scenario_piu_veloce(items, per_pn, qty_list)
    if scenario == "un-solo-dealer":
        return _scenario_un_solo_dealer(items, per_pn, qty_list, params)
    if scenario == "max-n-dealer":
        return _lines_scenario_max_n(items, per_pn, qty_list, params)
    lines, extra = _scenario_miglior_prezzo(items, per_pn, qty_list)
    notes = [f"Scenario '{scenario}' non supportato: fallback su miglior-prezzo."]
    notes.extend(extra)
    return lines, notes


def _lines_scenario_miglior_prezzo(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
) -> Tuple[List[OptimizeLine], List[str]]:
    lines, extra = _scenario_miglior_prezzo(items, per_pn, qty_list)
    notes = [
        "Scenario miglior-prezzo: selezionati i prezzi minimi per ciascun PN indipendentemente dal dealer."
    ]
    notes.extend(extra)
    return lines, notes


def _lines_scenario_piu_veloce(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
) -> Tuple[List[OptimizeLine], List[str]]:
    lines, extra = _scenario_piu_veloce(items, per_pn, qty_list)
    notes = [
        "Scenario più veloce: priorità ai lead time minori (il prezzo interviene solo a parità)."
    ]
    notes.extend(extra)
    return lines, notes


def _lines_scenario_max_n(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    params: OptimizeParams,
) -> Tuple[List[OptimizeLine], List[str]]:
    lines, extra = _scenario_max_n_dealer(items, per_pn, qty_list, params)
    notes = [f"Scenario max-n-dealer (limite={int(params.max_dealer or 1)})."]
    notes.extend(extra)
    return lines, notes


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
                offer_id=o.offer_id,
                maker_pn=pn,
                name=o.name,
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
                offer_id=o.offer_id,
                maker_pn=pn,
                name=o.name,
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
    common = _common_dealers(per_pn)
    if not common:
        notes.append("Nessun dealer singolo copre tutti i PN; fallback miglior-prezzo")
        lines, _ = _scenario_miglior_prezzo(items, per_pn, qty_list)
        return lines, notes
    best: Tuple[float, str, List[OptimizeLine]] | None = None
    for dealer in common:
        candidate = _single_dealer_candidate(dealer, items, per_pn, qty_list, params)
        if candidate is None:
            continue
        if best is None or candidate[0] < best[0]:
            best = candidate
    if best:
        _, best_dealer, lines = best
        notes.append(f"Scenario un-solo-dealer: {best_dealer} copre tutte le righe.")
        return lines, notes
    # If no consistent candidate, fall back to miglior-prezzo
    lines, _ = _scenario_miglior_prezzo(items, per_pn, qty_list)
    return lines, notes


def _common_dealers(per_pn: List[List[PNOfferItem]]) -> set[str]:
    per_pn_dealers: List[set[str]] = [
        set(o.dealer for o in offers) for offers in per_pn
    ]
    return set.intersection(*per_pn_dealers) if per_pn_dealers else set()


def _single_dealer_candidate(
    dealer: str,
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    params: OptimizeParams,
) -> Tuple[float, str, List[OptimizeLine]] | None:
    cand_lines: List[OptimizeLine] = []
    for offers, q, pn in zip(per_pn, qty_list, [it.maker_pn for it in items]):
        cand = [o for o in offers if o.dealer == dealer]
        sel = _pick_cheapest(cand)
        if not sel:
            return None
        unit = float(sel.price or 0.0)
        cand_lines.append(
            OptimizeLine(
                offer_id=sel.offer_id,
                maker_pn=pn,
                name=sel.name,
                dealer=sel.dealer,
                unit_price=sel.price,
                qty=q,
                line_total=unit * q,
                lead_time_days=sel.lead_time_days,
            )
        )
    total = _single_dealer_total(cand_lines, params)
    return total, dealer, cand_lines


def _single_dealer_total(
    lines: List[OptimizeLine],
    params: OptimizeParams,
) -> float:
    subtotal = sum(line.line_total for line in lines)
    ship = _shipping_costs(lines)
    lead_avg = _avg_lead(lines)
    penalties = params.penale_lead * lead_avg
    return subtotal + ship + penalties


def _scenario_max_n_dealer(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    params: OptimizeParams,
) -> Tuple[List[OptimizeLine], List[str]]:
    N = int(params.max_dealer or 1)
    base_lines, base_idx = _initial_max_n_lines(items, per_pn, qty_list)
    if not base_lines:
        return [], ["Nessuna riga ottimizzabile per questo scenario."]
    lines = _reduce_dealers_greedy(base_lines, base_idx, per_pn, qty_list, N, params)
    used = sorted({line.dealer for line in lines})
    note = f"Scenario max-n-dealer: ridotto a {len(used)} dealer" + (
        f" ({', '.join(used)})" if used else ""
    )
    return lines, [note]


def _initial_max_n_lines(
    items: List[OptimizeItem],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
) -> Tuple[List[OptimizeLine], List[int]]:
    base_lines: List[OptimizeLine] = []
    base_idx: List[int] = []
    for idx, (offers, q, pn) in enumerate(
        zip(per_pn, qty_list, [it.maker_pn for it in items])
    ):
        chosen = _pick_cheapest(offers)
        if not chosen:
            continue
        unit = float(chosen.price or 0.0)
        base_lines.append(
            OptimizeLine(
                offer_id=chosen.offer_id,
                maker_pn=pn,
                name=chosen.name,
                dealer=chosen.dealer,
                unit_price=chosen.price,
                qty=q,
                line_total=unit * q,
                lead_time_days=chosen.lead_time_days,
            )
        )
        base_idx.append(idx)
    return base_lines, base_idx


def _compute_costs(
    lines: List[OptimizeLine], params: OptimizeParams, db=None
) -> Tuple[List[str], OptimizeCost]:
    dealers = sorted(list({line.dealer for line in lines}))
    subtotal = sum(line.line_total for line in lines)
    ship = _shipping_costs(lines, db=db)
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

    while len(_dealers_of(curr)) > max(1, N):
        curr_total = _total_with_penalties(curr, params)
        best = _best_dealer_reassignment(
            curr,
            curr_idx,
            per_pn,
            qty_list,
            params,
            curr_total,
        )
        if best is None:
            break
        curr, curr_idx = best
    return curr


def _dealers_of(lines: List[OptimizeLine]) -> List[str]:
    return sorted(list({line.dealer for line in lines}))


def _total_with_penalties(
    lines: List[OptimizeLine],
    params: OptimizeParams,
) -> float:
    dealers = _dealers_of(lines)
    subtotal = sum(line.line_total for line in lines)
    ship = _shipping_costs(lines)
    lead_avg = _avg_lead(lines)
    penalties = (
        params.penale_dealer * max(0, len(dealers) - 1) + params.penale_lead * lead_avg
    )
    return subtotal + ship + penalties


def _best_dealer_reassignment(
    curr: List[OptimizeLine],
    curr_idx: List[int],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
    params: OptimizeParams,
    curr_total: float,
) -> Tuple[List[OptimizeLine], List[int]] | None:
    dealers = _dealers_of(curr)
    best_choice: Tuple[float, List[OptimizeLine], List[int]] | None = None
    for dealer in dealers:
        candidate = _candidate_after_removing_dealer(
            dealer, curr, curr_idx, per_pn, qty_list
        )
        if candidate is None:
            continue
        cand_lines, cand_idx = candidate
        cand_total = _total_with_penalties(cand_lines, params)
        delta = cand_total - curr_total
        if best_choice is None or delta < best_choice[0]:
            best_choice = (delta, cand_lines, cand_idx)
    if best_choice is None:
        return None
    return best_choice[1], best_choice[2]


def _candidate_after_removing_dealer(
    dealer: str,
    curr: List[OptimizeLine],
    curr_idx: List[int],
    per_pn: List[List[PNOfferItem]],
    qty_list: List[int],
) -> Tuple[List[OptimizeLine], List[int]] | None:
    cand: List[OptimizeLine] = []
    cand_idx: List[int] = []
    for pos, line in enumerate(curr):
        if line.dealer != dealer:
            cand.append(line)
            cand_idx.append(curr_idx[pos])
            continue
        replacement = _replacement_line_for_dealer(
            dealer=dealer,
            line=line,
            line_pos=pos,
            curr_idx=curr_idx,
            per_pn=per_pn,
        )
        if replacement is None:
            return None
        new_line, idx = replacement
        cand.append(new_line)
        cand_idx.append(idx)
    return cand, cand_idx


def _replacement_line_for_dealer(
    dealer: str,
    line: OptimizeLine,
    line_pos: int,
    curr_idx: List[int],
    per_pn: List[List[PNOfferItem]],
) -> Tuple[OptimizeLine, int] | None:
    idx = curr_idx[line_pos]
    offers = per_pn[idx]
    alt = [o for o in offers if o.dealer != dealer]
    nb = _pick_cheapest(alt)
    if not nb:
        return None
    unit = float(nb.price or 0.0)
    new_line = OptimizeLine(
        offer_id=nb.offer_id,
        maker_pn=line.maker_pn,
        name=nb.name or line.name,
        dealer=nb.dealer,
        unit_price=nb.price,
        qty=line.qty,
        line_total=unit * line.qty,
        lead_time_days=nb.lead_time_days,
    )
    return new_line, idx


def _apply_locked_dealers(
    per_pn: List[List[PNOfferItem]], items: List[OptimizeItem]
) -> Tuple[List[List[PNOfferItem]], List[str]]:
    """Filter offers per PN according to locked dealer settings."""
    filtered: List[List[PNOfferItem]] = []
    notes: List[str] = []
    for offers, item in zip(per_pn, items):
        dealer = (item.locked_dealer or "").strip()
        if not dealer:
            filtered.append(offers)
            continue
        locked = [o for o in offers if o.dealer == dealer]
        if not locked:
            filtered.append([])
            notes.append(
                f"PN {item.maker_pn}: dealer '{dealer}' non disponibile, riga esclusa."
            )
            continue
        filtered.append(locked)
        notes.append(f"PN {item.maker_pn} bloccato su {dealer}.")

    # Preserve per_pn length if batch returned more entries than items
    if len(per_pn) > len(items):
        filtered.extend(per_pn[len(items) :])
    return filtered, notes
