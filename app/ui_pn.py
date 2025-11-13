from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import gradio as gr
import httpx

API_BASE = os.environ.get("APP_API_BASE", "http://localhost:8000").rstrip("/")
AUTH = None
if os.environ.get("APP_BASIC_USER") and os.environ.get("APP_BASIC_PASS"):
    AUTH = (os.environ.get("APP_BASIC_USER", ""), os.environ.get("APP_BASIC_PASS", ""))


def _api_get(path: str) -> Dict[str, Any]:
    with httpx.Client(timeout=15.0) as client:
        r = client.get(f"{API_BASE}{path}", auth=AUTH)
        r.raise_for_status()
        return r.json()


def _api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        r = client.post(f"{API_BASE}{path}", json=payload, auth=AUTH)
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


def do_search(
    pn_text: str, dealers: List[str], in_stock_only: bool
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
    rows: List[Dict[str, Any]] = []
    for res in data.get("results", []):
        pn = res.get("maker_pn")
        offers = res.get("offers", [])
        for o in offers:
            rows.append(
                {
                    "PN": pn,
                    "Dealer": o.get("dealer"),
                    "Prezzo": o.get("price"),
                    "Stock": "✓" if o.get("in_stock") else "✗",
                    "Lead": o.get("lead_time_days"),
                    "OfferID": o.get("offer_id"),
                }
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
                "Dealer": o.get("dealer"),
                "Prezzo": float(o.get("price") or 0.0),
                "Qty": 1,
                "Lead": o.get("lead_time_days"),
                "OfferID": o.get("offer_id"),
            }
        )
    return cart


def to_quote_items(cart: List[Dict[str, Any]]) -> List[Dict[str, int]]:
    items: List[Dict[str, int]] = []
    for r in cart:
        try:
            items.append(
                {"offer_id": int(r.get("OfferID")), "qty": int(r.get("Qty", 1))}
            )
        except Exception:
            continue
    return items


def ui() -> None:
    dealers = load_dealers()
    with gr.Blocks(title="PN-first — Preventivo") as demo:
        gr.Markdown("## Preventivo PN‑first")
        with gr.Row():
            pn_text = gr.Textbox(lines=6, label="PN (uno per riga)")
            with gr.Column(scale=0.6):
                dealer_ms = gr.CheckboxGroup(choices=dealers, label="Dealer")
                in_stock = gr.Checkbox(label="Solo in stock", value=True)
                search_btn = gr.Button("Cerca", variant="primary")
                add_btn = gr.Button("Aggiungi migliori al carrello")
        results = gr.Dataframe(
            headers=["PN", "Dealer", "Prezzo", "Stock", "Lead", "OfferID"],
            interactive=False,
            wrap=True,
        )
        batch_state = gr.State({})
        cart_state = gr.State([])  # list of rows
        gr.Markdown("### Carrello")
        cart_df = gr.Dataframe(
            headers=["PN", "Dealer", "Prezzo", "Qty", "Lead", "OfferID"],
            interactive=True,
        )
        with gr.Row():
            quote_btn = gr.Button("Crea preventivo")
            quote_out = gr.JSON(label="Esito preventivo")
        with gr.Row():
            opt_btn = gr.Button("Ottimizza (anteprima)")
            opt_json = gr.JSON(label="Piano ottimizzato")

        def _on_search(text: str, dlrs: List[str], stock: bool):
            rows, data = do_search(text, dlrs, stock)
            return rows, data

        def _on_add(batch: Dict[str, Any], cart: List[Dict[str, Any]]):
            new_cart = add_best_to_cart(batch, cart or [])
            return new_cart

        def _on_quote(cart: List[Dict[str, Any]]):
            items = to_quote_items(cart or [])
            if not items:
                return {"error": "carrello vuoto"}
            try:
                data = _api_post(
                    "/quote",
                    {
                        "items": items,
                        "customer_name": "Cliente",
                        "customer_contact": "",
                        "validity_days": 7,
                    },
                )
                return data
            except Exception as e:
                return {"error": str(e)}

        def _on_optimize(cart: List[Dict[str, Any]]):
            # Use PN+qty from cart; ignore locked dealers (v1)
            if not cart:
                return {"error": "carrello vuoto"}
            items: List[Dict[str, Any]] = []
            for r in cart:
                pn = str(r.get("PN") or "").strip()
                q = int(r.get("Qty", 1) or 1)
                if pn and q > 0:
                    items.append({"maker_pn": pn, "qty": q})
            try:
                data = _api_post(
                    "/optimize",
                    {"items": items, "params": {"scenario": "miglior-prezzo"}},
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
        ).then(lambda c: c, cart_state, cart_df)
        quote_btn.click(_on_quote, inputs=[cart_state], outputs=[quote_out])
        opt_btn.click(_on_optimize, inputs=[cart_state], outputs=[opt_json])

    demo.launch(server_name="0.0.0.0", server_port=7861)


if __name__ == "__main__":
    ui()
