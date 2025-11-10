from __future__ import annotations

import os
from typing import Any

import gradio as gr
import httpx

from .search import search
from .types import Brake, Freehub, Rotor, SearchRequest
from .models import EventLog, SessionLocal, SupplierOffer
from .quote import render_quote


API_BASE = os.environ.get("APP_API_BASE", "http://127.0.0.1:8000")
API_USER = os.environ.get("APP_BASIC_USER", "")
API_PASS = os.environ.get("APP_BASIC_PASS", "")


def _do_search(
    query: str,
    speed: str,
    freehub: str,
    brake: str,
    axle: str,
    rotor: str,
    budget: float | None,
):
    req = SearchRequest(
        query_text=(query or None),
        speed=(speed or None),
        freehub=(Freehub(freehub) if freehub else None),
        brake=(Brake(brake) if brake else None),
        axle=(axle or None),
        rotor=(Rotor(rotor) if rotor else None),
        budget_max=budget,
    )
    res = search(req)
    rows = []
    options: list[tuple[str, int]] = []
    mapping: dict[int, dict[str, Any]] = {}
    for it in res.items:
        row = {
            "ID": it.id,
            "Brand": it.brand,
            "MPN": it.mpn,
            "Fornitore": it.supplier,
            "Prezzo": round(it.price, 2),
            "Stock": "Sì" if it.in_stock else "No",
            "Lead (gg)": it.lead_time_days or "-",
            "Score": round(it.score, 3),
        }
        rows.append(row)
        label = f"{it.id} · {it.brand} {it.mpn} · {it.supplier} · €{it.price:.2f}"
        options.append((label, it.id))
        mapping[it.id] = {
            "brand": it.brand,
            "mpn": it.mpn,
            "supplier": it.supplier,
            "price": it.price,
        }
    return rows, options, mapping, f"Trovate {len(rows)} offerte"


def _create_quote(
    offer_id: int, customer: str, contact: str, validity: int, notes: str
):
    payload = {
        "offer_id": int(offer_id),
        "customer_name": customer,
        "customer_contact": contact,
        "validity_days": int(validity),
        "notes": notes or None,
    }
    try:
        auth = (API_USER, API_PASS) if API_USER and API_PASS else None
        r = httpx.post(f"{API_BASE}/quote", json=payload, auth=auth, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return (
                data.get("html_path", ""),
                data.get("pdf_path") or "",
                data.get("file_url") or "",
            )
    except Exception:
        pass

    with SessionLocal() as db:
        offer = db.get(SupplierOffer, int(offer_id))
        if offer is None:
            return "OFFERTA NON TROVATA", "", ""
        product = offer.product
        context = {
            "customer_name": customer,
            "customer_contact": contact,
            "validity_days": validity,
            "notes": notes,
            "item": {
                "brand": product.brand,
                "mpn": product.mpn,
                "name": product.name,
                "supplier": offer.supplier,
                "price": offer.price,
                "in_stock": offer.in_stock,
                "lead_time_days": offer.lead_time_days,
            },
        }
        html_path, pdf_path = render_quote(context)
        db.add(
            EventLog(
                type="quote_created",
                payload={"offer_id": offer.id, "ui": True, "pdf": bool(pdf_path)},
            )
        )
        db.commit()
        return html_path, (pdf_path or ""), ""


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="Bike Copilot Demo") as demo:
        gr.Markdown("""
        ## Bike Copilot — Ricerca e Preventivo
        Cerca un componente, confronta le offerte e genera un preventivo in 1 click.
        """)

        results_state = gr.State({})

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Ricerca")
                query = gr.Textbox(
                    label="Ricerca (testo libero)",
                    placeholder="Es. cassetta 11v HG 11-32, catena CN-HG601",
                    info="Parole chiave libere: marca, MPN, specifiche.",
                )
                with gr.Accordion("Filtri tecnici", open=False):
                    speed = gr.Dropdown(
                        choices=["", "11", "12"],
                        value="",
                        label="Velocità",
                        info="Numero di velocità (lascia vuoto per qualsiasi).",
                    )
                    freehub = gr.Dropdown(
                        choices=["", "HG", "XD", "MS"],
                        value="",
                        label="Corpetto",
                        info="Tipo di freehub/corpetto (HG, XD, MicroSpline).",
                    )
                    brake = gr.Dropdown(
                        choices=["", "disc"],
                        value="",
                        label="Freno",
                        info="Tipologia freno (disc per disco).",
                    )
                    axle = gr.Textbox(
                        label="Asse (Axle)",
                        placeholder="Es. 12x148",
                        info="Formato perno posteriore (es. 12x148, 12x142).",
                    )
                    rotor = gr.Dropdown(
                        choices=["", "CL", "6B"],
                        value="",
                        label="Rotore",
                        info="Standard disco: CL (CenterLock) o 6B (6 fori).",
                    )
                    budget = gr.Number(
                        label="Budget massimo (€)",
                        value=None,
                        info="Filtra offerte con prezzo ≤ budget.",
                    )
                with gr.Row():
                    search_btn = gr.Button("Cerca", variant="primary")
                    clear_btn = gr.Button("Pulisci")
                status = gr.Markdown(visible=True)
            with gr.Column(scale=2):
                gr.Markdown("### Risultati")
                results = gr.Dataframe(
                    headers=[
                        "ID",
                        "Brand",
                        "MPN",
                        "Fornitore",
                        "Prezzo",
                        "Stock",
                        "Lead (gg)",
                        "Score",
                    ],
                    interactive=False,
                    wrap=True,
                )
                offer_select = gr.Dropdown(
                    label="Seleziona offerta", choices=[], interactive=True
                )
                preview = gr.Markdown("Seleziona un'offerta per i dettagli")
                gr.Markdown("### Preventivo")
                with gr.Row():
                    customer = gr.Textbox(
                        label="Cliente",
                        placeholder="Nome cognome o ragione sociale",
                        info="Intestatario del preventivo",
                    )
                    contact = gr.Textbox(
                        label="Contatto",
                        placeholder="email o telefono",
                        info="Recapito del cliente",
                    )
                    validity = gr.Number(
                        label="Validità (giorni)",
                        value=7,
                        info="Durata validità del preventivo",
                    )
                notes = gr.Textbox(
                    label="Note", placeholder="Note aggiuntive (opzionale)"
                )
                quote_btn = gr.Button("Crea preventivo")
                html_out = gr.Textbox(label="Percorso HTML", interactive=False)
                pdf_out = gr.Textbox(
                    label="Percorso PDF (se disponibile)", interactive=False
                )
                file_url = gr.Textbox(
                    label="URL file (se API attiva)", interactive=False
                )

        def _on_search(query, speed, freehub, brake, axle, rotor, budget):
            rows, options, mapping, msg = _do_search(
                query, speed, freehub, brake, axle, rotor, budget
            )
            return (
                rows,
                gr.update(
                    choices=[opt[0] for opt in options],
                    value=(options[0][1] if options else None),
                ),
                {k: v for k, v in mapping.items()},
                msg,
            )

        search_btn.click(
            _on_search,
            inputs=[query, speed, freehub, brake, axle, rotor, budget],
            outputs=[results, offer_select, results_state, status],
        )

        def _on_clear():
            return (
                "",
                "",
                "",
                "",
                "",
                "",
                None,
                [],
                gr.update(choices=[], value=None),
                {},
                "",
            )

        clear_btn.click(
            _on_clear,
            inputs=[],
            outputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                results,
                offer_select,
                results_state,
                status,
            ],
        )

        def _on_select(offer_label: str | None, mapping: dict[int, dict[str, Any]]):
            if not offer_label:
                return "Seleziona un'offerta per i dettagli"
            # Extract offer_id from label prefix
            try:
                offer_id = int(str(offer_label).split(" · ")[0])
            except Exception:
                return "Seleziona un'offerta per i dettagli"
            info = mapping.get(int(offer_id)) or {}
            return f"**Offerta {offer_id}** — {info.get('brand', '')} {info.get('mpn', '')} — {info.get('supplier', '')} — €{info.get('price', '')}"

        offer_select.change(
            _on_select, inputs=[offer_select, results_state], outputs=preview
        )

        def _on_quote(
            offer_label: str | None,
            customer: str,
            contact: str,
            validity: int,
            notes: str,
        ):
            if not offer_label:
                return "Seleziona un'offerta", "", ""
            try:
                offer_id = int(str(offer_label).split(" · ")[0])
            except Exception:
                return "Seleziona un'offerta", "", ""
            return _create_quote(offer_id, customer, contact, validity, notes)

        quote_btn.click(
            _on_quote,
            inputs=[offer_select, customer, contact, validity, notes],
            outputs=[html_out, pdf_out, file_url],
        )

    return demo


def main() -> None:
    iface = build_interface()
    iface.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
