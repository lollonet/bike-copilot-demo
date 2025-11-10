from __future__ import annotations

import gradio as gr

from .search import search
from .types import Brake, Freehub, Rotor, SearchRequest
from .quote import render_quote
from .models import EventLog, SessionLocal, SupplierOffer


def _do_search(query: str, speed: str, freehub: str, brake: str, axle: str, rotor: str, budget: float | None):
    req = SearchRequest(
        query_text=query or None,
        speed=(speed or None),
        freehub=(Freehub(freehub) if freehub else None),
        brake=(Brake(brake) if brake else None),
        axle=(axle or None),
        rotor=(Rotor(rotor) if rotor else None),
        budget_max=budget,
    )
    res = search(req)
    rows = [
        {
            "offer_id": it.id,
            "brand": it.brand,
            "mpn": it.mpn,
            "supplier": it.supplier,
            "price": it.price,
            "stock": it.in_stock,
            "lead": it.lead_time_days,
            "score": round(it.score, 3),
        }
        for it in res.items
    ]
    return rows


def _create_quote(offer_id: int, customer: str, contact: str, validity: int, notes: str):
    with SessionLocal() as db:
        offer = db.get(SupplierOffer, int(offer_id))
        if offer is None:
            return "OFFERTA NON TROVATA", ""
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
        db.add(EventLog(type="quote_created", payload={"offer_id": offer.id, "ui": True, "pdf": bool(pdf_path)}))
        db.commit()
        return html_path, (pdf_path or "")


def build_interface() -> gr.Interface:
    with gr.Blocks() as demo:
        gr.Markdown("# Bike Copilot Demo – Lite UI")
        with gr.Row():
            query = gr.Textbox(label="Testo libero (opzionale)")
        with gr.Row():
            speed = gr.Textbox(label="Velocità (es. 11 o 12)")
            freehub = gr.Dropdown(choices=["", "HG", "XD", "MS"], value="", label="Freehub")
            brake = gr.Dropdown(choices=["", "disc"], value="", label="Freno")
            axle = gr.Textbox(label="Axle (es. 12x148)")
            rotor = gr.Dropdown(choices=["", "CL", "6B"], value="", label="Rotore")
            budget = gr.Number(label="Budget max", value=None)
        search_btn = gr.Button("Cerca")
        results = gr.Dataframe(headers=["offer_id", "brand", "mpn", "supplier", "price", "stock", "lead", "score"], interactive=False)

        with gr.Row():
            offer_id = gr.Number(label="offer_id")
            customer = gr.Textbox(label="Cliente")
            contact = gr.Textbox(label="Contatto")
            validity = gr.Number(label="Validità giorni", value=7)
            notes = gr.Textbox(label="Note")
        quote_btn = gr.Button("Crea preventivo")
        html_out = gr.Textbox(label="HTML path", interactive=False)
        pdf_out = gr.Textbox(label="PDF path (se disponibile)", interactive=False)

        search_btn.click(_do_search, inputs=[query, speed, freehub, brake, axle, rotor, budget], outputs=results)
        quote_btn.click(_create_quote, inputs=[offer_id, customer, contact, validity, notes], outputs=[html_out, pdf_out])
    return demo


def main() -> None:
    iface = build_interface()
    iface.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
