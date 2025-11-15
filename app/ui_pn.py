from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import gradio as gr
import httpx

API_BASE = os.environ.get("APP_API_BASE", "http://localhost:8000").rstrip("/")
_auth_credentials: tuple[str, str] | None = None
_basic_user = os.environ.get("APP_BASIC_USER")
_basic_pass = os.environ.get("APP_BASIC_PASS")
if _basic_user and _basic_pass:
    _auth_credentials = (_basic_user, _basic_pass)


def _api_get(path: str) -> Dict[str, Any]:
    with httpx.Client(timeout=15.0) as client:
        auth = _auth_credentials if _auth_credentials else httpx.USE_CLIENT_DEFAULT
        r = client.get(f"{API_BASE}{path}", auth=auth)
        r.raise_for_status()
        return r.json()


def _api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        auth = _auth_credentials if _auth_credentials else httpx.USE_CLIENT_DEFAULT
        r = client.post(f"{API_BASE}{path}", json=payload, auth=auth)
        r.raise_for_status()
        return r.json()


def _parse_pn_lines(text: str) -> List[str]:
    # Split by newline/space/comma; one PN per entry
    raw = [t.strip() for t in text.replace(",", "\n").splitlines()]
    return [t for t in raw if t]


def load_dealers() -> List[str]:
    try:
        data = _api_get("/dealers")
        return sorted([d["name"] for d in data.get("dealers", []) if d.get("name")])
    except Exception:
        return []


def _cart_to_rows(cart: List[Dict[str, Any]] | None) -> List[List[Any]]:
    rows: List[List[Any]] = []
    for row in cart or []:
        rows.append(
            [
                row.get("PN") or "",
                row.get("Descrizione") or "",
                row.get("Dealer") or "",
                row.get("Prezzo") or 0.0,
                row.get("Qty") or 1,
                row.get("Lead"),
                row.get("OfferID"),
                bool(row.get("LockedDealer", False)),
            ]
        )
    return rows


def _rows_to_cart(rows: List[List[Any]] | None) -> List[Dict[str, Any]]:
    cart: List[Dict[str, Any]] = []
    if not rows:
        return cart
    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        pn = str(row[0] or "").strip()
        if not pn:
            continue
        descr = str(row[1] or "").strip()
        dealer = str(row[2] or "").strip()
        try:
            price = float(row[3]) if row[3] not in ("", None) else 0.0
        except (TypeError, ValueError):
            price = 0.0
        try:
            qty_val = int(row[4]) if row[4] not in ("", None) else 1
        except (TypeError, ValueError):
            qty_val = 1
        lead = row[5]
        offer_raw = row[6]
        try:
            offer_id = int(offer_raw) if offer_raw not in ("", None) else None
        except (TypeError, ValueError):
            offer_id = None
        lock_val = bool(row[7]) if len(row) > 7 else False
        cart.append(
            {
                "PN": pn,
                "Descrizione": descr or pn,
                "Dealer": dealer,
                "Prezzo": price,
                "Qty": qty_val,
                "Lead": lead,
                "OfferID": offer_id,
                "LockedDealer": lock_val,
            }
        )
    return cart


def do_search(
    pn_text: str, dealers: List[str], in_stock_only: bool
) -> Tuple[List[List[Any]], Dict[str, Any]]:
    items = _parse_pn_lines(pn_text)
    if not items:
        return [], {"results": []}
    payload: Dict[str, Any] = {"items": items}
    if dealers:
        payload["dealers"] = dealers
    if in_stock_only:
        payload["in_stock_only"] = True
    data = _api_post("/search_pn_batch", payload)
    # Flatten offers to a simple table per PN for preview
    rows: List[List[Any]] = []
    for res in data.get("results", []):
        pn = res.get("maker_pn")
        offers = res.get("offers", [])
        for o in offers:
            rows.append(
                [
                    pn,
                    o.get("name"),
                    o.get("dealer"),
                    o.get("price"),
                    "✓" if o.get("in_stock") else "✗",
                    o.get("lead_time_days"),
                    o.get("offer_id"),
                ]
            )
    return rows, data


def add_best_to_cart(
    batch: Dict[str, Any], cart: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    # For each PN pick the first offer (already sorted by the backend) and add to cart
    for res in batch.get("results", []):
        pn = res.get("maker_pn")
        offers = res.get("offers", [])
        if not offers:
            continue
        o = offers[0]
        cart.append(
            {
                "PN": pn,
                "Descrizione": o.get("name"),
                "Dealer": o.get("dealer"),
                "Prezzo": float(o.get("price") or 0.0),
                "Qty": 1,
                "Lead": o.get("lead_time_days"),
                "OfferID": o.get("offer_id"),
                "LockedDealer": False,
            }
        )
    return cart


def to_quote_items(cart: List[Dict[str, Any]]) -> List[Dict[str, int]]:
    items: List[Dict[str, int]] = []
    for r in cart:
        offer_raw = r.get("OfferID")
        if offer_raw is None:
            continue
        try:
            offer_id = int(offer_raw)
        except (TypeError, ValueError):
            continue
        qty_raw = r.get("Qty", 1)
        try:
            qty = int(qty_raw if qty_raw is not None else 1)
        except (TypeError, ValueError):
            qty = 1
        items.append({"offer_id": offer_id, "qty": qty})
    return items


def ui() -> None:
    dealers = load_dealers()
    with gr.Blocks(title="PN-first — Preventivo") as demo:
        gr.Markdown("## Preventivo PN‑first")
        scenario_options = [
            ("Miglior prezzo (multi-dealer)", "miglior-prezzo"),
            ("Un solo dealer", "un-solo-dealer"),
            ("Al massimo N dealer", "max-n-dealer"),
            ("Più veloce", "piu-veloce"),
        ]
        scenario_value_map = {label: value for label, value in scenario_options}

        with gr.Row():
            pn_text = gr.Textbox(lines=6, label="PN (uno per riga)")
            with gr.Column(scale=1):
                dealer_ms = gr.CheckboxGroup(choices=dealers, label="Dealer")
                in_stock = gr.Checkbox(label="Solo in stock", value=True)
                search_btn = gr.Button("Cerca", variant="primary")
                add_btn = gr.Button("Aggiungi migliori al carrello")
        notes_box = gr.Textbox(
            label="Descrizione preventivo (facoltativa)",
            placeholder="Note per il cliente / condizioni particolari",
            lines=2,
        )
        with gr.Row():
            scenario_dd = gr.Radio(
                choices=[label for label, _ in scenario_options],
                value=scenario_options[0][0],
                label="Scenario ottimizzazione",
            )
            max_dealer_slider = gr.Slider(
                minimum=1,
                maximum=5,
                value=2,
                step=1,
                label="Dealer max (solo scenario 'Al massimo N dealer')",
            )
        with gr.Row():
            penale_dealer_input = gr.Number(
                value=3.5, label="Penale per dealer aggiuntivo (€)"
            )
            penale_lead_input = gr.Number(
                value=0.5, label="Penale per giorno di lead time (€)"
            )
        results = gr.Dataframe(
            headers=[
                "PN",
                "Descrizione",
                "Dealer",
                "Prezzo",
                "Stock",
                "Lead",
                "OfferID",
            ],
            interactive=False,
            wrap=True,
        )
        batch_state = gr.State({})
        cart_state = gr.State([])  # list of rows
        opt_state = gr.State({})
        gr.Markdown("### Carrello")
        cart_df = gr.Dataframe(
            headers=[
                "PN",
                "Descrizione",
                "Dealer",
                "Prezzo",
                "Qty",
                "Lead",
                "OfferID",
                "Blocca dealer",
            ],
            datatype=[
                "str",
                "str",
                "str",
                "number",
                "number",
                "str",
                "number",
                "bool",
            ],
            interactive=True,
            type="array",
        )
        gr.Markdown(
            "_Imposta **Blocca dealer** a `True` per mantenere il fornitore corrente durante l'ottimizzazione._"
        )
        with gr.Row():
            quote_btn = gr.Button("Crea preventivo")
            quote_out = gr.Markdown(
                "_Premi **Crea preventivo** per generare l'offerta con i link._"
            )
        with gr.Row():
            opt_btn = gr.Button("Ottimizza (anteprima)")
            apply_btn = gr.Button("Applica piano al carrello")
        opt_json = gr.Markdown(
            "_Premi **Ottimizza** per vedere la proposta multi-dealer._"
        )

        def _on_search(text: str, dlrs: List[str], stock: bool):
            rows, data = do_search(text, dlrs, stock)
            return rows, data

        def _on_add(batch: Dict[str, Any], cart: List[Dict[str, Any]]):
            new_cart = add_best_to_cart(batch, cart or [])
            return new_cart

        def _on_quote(cart: List[Dict[str, Any]], notes: str):
            items = to_quote_items(cart or [])
            if not items:
                return {"error": "carrello vuoto"}
            try:
                payload = {
                    "items": items,
                    "customer_name": "Cliente",
                    "customer_contact": "",
                    "validity_days": 7,
                }
                note_txt = (notes or "").strip()
                if note_txt:
                    payload["notes"] = note_txt
                data = _api_post(
                    "/quote",
                    payload,
                )
                return data
            except Exception as e:
                return {"error": str(e)}

        def _on_optimize(
            cart: List[Dict[str, Any]],
            scenario_label: str,
            max_dealer: float,
            penale_dealer: float,
            penale_lead: float,
        ):
            if not cart:
                return {"error": "carrello vuoto"}
            items: List[Dict[str, Any]] = []
            for r in cart:
                pn = str(r.get("PN") or "").strip()
                q = int(r.get("Qty", 1) or 1)
                if pn and q > 0:
                    locked = bool(r.get("LockedDealer"))
                    dealer_lock = str(r.get("Dealer") or "").strip() if locked else ""
                    payload_item: Dict[str, Any] = {"maker_pn": pn, "qty": q}
                    if locked and dealer_lock:
                        payload_item["locked_dealer"] = dealer_lock
                    items.append(payload_item)
            try:
                scenario_code = scenario_value_map.get(scenario_label, "miglior-prezzo")
                data = _api_post(
                    "/optimize",
                    {
                        "items": items,
                        "params": {
                            "scenario": scenario_code,
                            "max_dealer": int(max_dealer),
                            "penale_dealer": float(penale_dealer),
                            "penale_lead": float(penale_lead),
                        },
                    },
                )
                return data
            except Exception as e:
                return {"error": str(e)}

        search_btn.click(
            _on_search,
            inputs=[pn_text, dealer_ms, in_stock],
            outputs=[results, batch_state],
        )
        add_btn.click(
            _on_add, inputs=[batch_state, cart_state], outputs=[cart_state]
        ).then(_cart_to_rows, cart_state, cart_df)

        def _render_quote(cart: List[Dict[str, Any]], notes: str) -> str:
            payload = _on_quote(cart, notes)
            if "error" in payload:
                return f"**Errore:** {payload['error']}"
            html_path = payload.get("html_path") or "(n/d)"
            pdf_path = payload.get("pdf_path")
            file_url = payload.get("file_url")
            rows = [
                "### Esito preventivo",
                f"- HTML: `{html_path}`",
                f"- PDF: `{pdf_path or 'non generato'}`",
            ]
            if file_url:
                rows.append(f"- Link: [{file_url}]({file_url})")
            note_txt = (notes or "").strip()
            if note_txt:
                rows.append(f"- Note: {note_txt}")
            return "\n".join(rows)

        def _render_opt_payload(payload: Dict[str, Any], scenario_label: str) -> str:
            rows = [f"### Piano ottimizzato ({scenario_label})"]
            notes = payload.get("notes") or []
            if notes:
                rows.append("\n".join(f"- {n}" for n in notes))
            offer_lines = payload.get("lines") or []
            if offer_lines:
                rows.append(
                    "| PN | Descrizione | Dealer | Qty | Prezzo | Lead | Totale |"
                )
                rows.append("| --- | --- | --- | --- | --- | --- | --- |")
                for line in offer_lines:
                    rows.append(
                        "| {pn} | {name} | {dealer} | {qty} | {price:.2f} | {lead} | {total:.2f} |".format(
                            pn=line.get("maker_pn", ""),
                            name=line.get("name") or "",
                            dealer=line.get("dealer", ""),
                            qty=line.get("qty") or 0,
                            price=float(line.get("unit_price") or 0.0),
                            lead=line.get("lead_time_days") or "-",
                            total=float(line.get("line_total") or 0.0),
                        )
                    )
            costs = payload.get("costs") or {}
            if costs:
                rows.append(
                    "\n**Costi** — Subtotale: {sub:.2f} € · Spedizione: {ship:.2f} € · Penalità: {pen:.2f} € · Totale: {tot:.2f} €".format(
                        sub=float(costs.get("subtotal") or 0.0),
                        ship=float(costs.get("shipping") or 0.0),
                        pen=float(costs.get("penalties") or 0.0),
                        tot=float(costs.get("total") or 0.0),
                    )
                )
            dealers = payload.get("dealers") or []
            if dealers:
                rows.append("**Dealer coinvolti:** " + ", ".join(dealers))
            return "\n".join(rows)

        def _format_optimize(
            cart: List[Dict[str, Any]],
            scenario_label: str,
            max_dealer: float,
            penale_dealer: float,
            penale_lead: float,
        ) -> Tuple[str, Dict[str, Any]]:
            payload = _on_optimize(
                cart, scenario_label, max_dealer, penale_dealer, penale_lead
            )
            if "error" in payload:
                return f"**Errore:** {payload['error']}", {}
            scenario_code = scenario_value_map.get(scenario_label, "miglior-prezzo")
            label = scenario_label or scenario_code
            md = _render_opt_payload(payload, label)
            return md, payload

        def _apply_plan(plan: Dict[str, Any], cart: List[Dict[str, Any]]):
            if not isinstance(plan, dict) or not plan.get("lines"):
                return cart or []
            new_cart: List[Dict[str, Any]] = []
            for line in plan.get("lines", []):
                offer_id = line.get("offer_id")
                if offer_id is None:
                    continue
                new_cart.append(
                    {
                        "PN": line.get("maker_pn"),
                        "Descrizione": line.get("name") or line.get("maker_pn"),
                        "Dealer": line.get("dealer"),
                        "Prezzo": float(line.get("unit_price") or 0.0),
                        "Qty": int(line.get("qty") or 1),
                        "Lead": line.get("lead_time_days"),
                        "OfferID": offer_id,
                        "LockedDealer": False,
                    }
                )
            return new_cart

        quote_btn.click(
            _render_quote, inputs=[cart_state, notes_box], outputs=[quote_out]
        )
        opt_btn.click(
            _format_optimize,
            inputs=[
                cart_state,
                scenario_dd,
                max_dealer_slider,
                penale_dealer_input,
                penale_lead_input,
            ],
            outputs=[opt_json, opt_state],
        )
        apply_btn.click(
            _apply_plan, inputs=[opt_state, cart_state], outputs=[cart_state]
        ).then(_cart_to_rows, cart_state, cart_df)

        def _sync_cart(
            table: List[List[Any]],
        ) -> Tuple[List[Dict[str, Any]], List[List[Any]]]:
            new_cart = _rows_to_cart(table)
            return new_cart, _cart_to_rows(new_cart)

        cart_df.change(_sync_cart, inputs=[cart_df], outputs=[cart_state, cart_df])

    demo.launch(server_name="0.0.0.0", server_port=7861)


if __name__ == "__main__":
    ui()
