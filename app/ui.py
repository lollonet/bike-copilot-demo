from __future__ import annotations

import os
from typing import Any

import gradio as gr
import httpx

from .logging_utils import log_exception
from .search import search
from .types import Brake, Freehub, Rotor, SearchRequest
from sqlalchemy.orm import Session
from typing import Any, cast

from sqlalchemy.orm import Session

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
    category: str | None,
    suppliers_sel: list[str] | None,
    in_stock_only: bool | None,
):
    req = _search_request_from_inputs(
        query,
        speed,
        freehub,
        brake,
        axle,
        rotor,
        budget,
        category,
        suppliers_sel,
        in_stock_only,
    )
    res = search(req)
    return _search_rows_from_response(res)


def _search_request_from_inputs(
    query: str,
    speed: str,
    freehub: str,
    brake: str,
    axle: str,
    rotor: str,
    budget: float | None,
    category: str | None,
    suppliers_sel: list[str] | None,
    in_stock_only: bool | None,
) -> SearchRequest:
    return SearchRequest(
        query_text=(query or None),
        speed=(speed or None),
        freehub=(Freehub(freehub) if freehub else None),
        brake=(Brake(brake) if brake else None),
        axle=(axle or None),
        rotor=(Rotor(rotor) if rotor else None),
        budget_max=budget,
        category=(category or None),
        suppliers=(suppliers_sel or []),
        in_stock_only=bool(in_stock_only),
    )


def _search_rows_from_response(
    res,
) -> tuple[list[list[object]], list[tuple[str, int]], dict[int, dict[str, Any]], str]:
    rows, table_rows, options, mapping = _build_search_collections(res)
    msg = f"Trovate {len(rows)} offerte"
    return table_rows, options, mapping, msg


def _build_search_collections(
    res,
) -> tuple[
    list[dict[str, object]],
    list[list[object]],
    list[tuple[str, int]],
    dict[int, dict[str, Any]],
]:
    rows: list[dict[str, object]] = []
    table_rows: list[list[object]] = []
    options: list[tuple[str, int]] = []
    mapping: dict[int, dict[str, Any]] = {}
    for it in res.items:
        row, table_row, option, mapping_entry = _search_row_parts(it)
        rows.append(row)
        table_rows.append(table_row)
        options.append(option)
        mapping[mapping_entry[0]] = mapping_entry[1]
    return rows, table_rows, options, mapping


def _search_row_parts(
    it,
) -> tuple[
    dict[str, object],
    list[object],
    tuple[str, int],
    tuple[int, dict[str, Any]],
]:
    row: dict[str, object] = {
        "ID": it.id,
        "Brand": it.brand,
        "MPN": it.mpn,
        "Fornitore": it.supplier,
        "Prezzo": round(it.price, 2),
        "Stock": "Sì" if it.in_stock else "No",
        "Lead (gg)": it.lead_time_days or "-",
        "Score": round(it.score, 3),
    }
    table_row: list[object] = [
        it.id,
        it.brand,
        it.mpn,
        it.supplier,
        round(it.price, 2),
        "Sì" if it.in_stock else "No",
        it.lead_time_days or "-",
        round(it.score, 3),
    ]
    label = f"{it.id} · {it.brand} {it.mpn} · {it.supplier} · €{it.price:.2f}"
    option = (label, it.id)
    mapping_entry = (
        it.id,
        {
            "brand": it.brand,
            "mpn": it.mpn,
            "supplier": it.supplier,
            "price": it.price,
        },
    )
    return row, table_row, option, mapping_entry


def _create_quote(
    offer_id: int, customer: str, contact: str, validity: int, notes: str
):
    payload = _quote_payload(offer_id, customer, contact, validity, notes)
    via_api = _try_create_quote_via_api(payload)
    if via_api is not None:
        return via_api
    return _create_local_quote(offer_id, customer, contact, validity, notes)


def _quote_payload(
    offer_id: int, customer: str, contact: str, validity: int, notes: str
) -> dict[str, object]:
    return {
        "offer_id": int(offer_id),
        "customer_name": customer,
        "customer_contact": contact,
        "validity_days": int(validity),
        "notes": notes or None,
    }


def _try_create_quote_via_api(
    payload: dict[str, object],
) -> tuple[str, str, str] | None:
    try:
        auth = (API_USER, API_PASS) if API_USER and API_PASS else None
        r = httpx.post(f"{API_BASE}/quote", json=payload, auth=auth, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        return (
            data.get("html_path", ""),
            data.get("pdf_path") or "",
            data.get("file_url") or "",
        )
    except Exception as exc:
        log_exception("ui", "quote-api", "failed to create quote via api", exc)
        return None


def _create_local_quote(
    offer_id: int, customer: str, contact: str, validity: int, notes: str
) -> tuple[str, str, str]:
    with SessionLocal() as db:
        offer = db.get(SupplierOffer, int(offer_id))
        if offer is None:
            return "OFFERTA NON TROVATA", "", ""
        context = _single_line_quote_context(offer, customer, contact, validity, notes)
        html_path, pdf_path = render_quote(context)
        _log_ui_quote_created(db, offer.id, pdf_path)
        return html_path, (pdf_path or ""), ""


def _single_line_quote_context(
    offer: SupplierOffer,
    customer: str,
    contact: str,
    validity: int,
    notes: str,
) -> dict[str, object]:
    product = offer.product
    return {
        "customer_name": customer,
        "customer_contact": contact,
        "validity_days": validity,
        "notes": notes,
        "items": [
            {
                "brand": product.brand,
                "mpn": product.mpn,
                "name": product.name,
                "supplier": offer.supplier,
                "price": offer.price,
                "qty": 1,
                "in_stock": offer.in_stock,
                "lead_time_days": offer.lead_time_days,
            }
        ],
    }


def _log_ui_quote_created(
    db: Session,
    offer_id: int,
    pdf_path: str | None,
) -> None:
    db.add(
        EventLog(
            type="quote_created",
            payload={"offer_id": offer_id, "ui": True, "pdf": bool(pdf_path)},
        )
    )
    db.commit()


def build_interface() -> gr.Blocks:
    css = """
    #filters-row { gap: 8px; }
    @media (max-width: 980px){
      #filters-row { flex-wrap: wrap; }
      #results-col { flex: 1 1 100% !important; }
    }
    """
    with gr.Blocks(title="Bike Copilot Demo", css=css) as demo:
        gr.Markdown("""
        ## Bike Copilot — Ricerca e Preventivo
        Cerca un componente, confronta le offerte e genera un preventivo in 1 click.
        """)

        results_state = gr.State({})
        cart_state = gr.State({})

        # Search bar full-width at the top
        gr.Markdown("### Ricerca")
        with gr.Row():
            query = gr.Textbox(
                label="Ricerca (testo libero)",
                placeholder="Es. cassetta 11v HG 11-32, catena CN-HG601",
                info="Parole chiave libere: marca, MPN, specifiche.",
                scale=3,
            )
            search_btn = gr.Button("Cerca", variant="primary")
            clear_btn = gr.Button("Pulisci")

        # Primary filters under the search: Category, Suppliers, Stock, Budget
        with gr.Row(elem_id="filters-row"):
            category = gr.Dropdown(label="Categoria", choices=[""], value="", scale=1)
            suppliers = gr.CheckboxGroup(label="Fornitori", choices=[], scale=2)
            in_stock = gr.Checkbox(label="Solo in stock", value=False)
            budget = gr.Number(
                label="Budget massimo (€)",
                value=None,
                info="0 = nessun limite; filtra offerte con prezzo ≤ budget.",
            )
            budget_slider = gr.Slider(
                label="Budget (slider)",
                minimum=0,
                maximum=1000,
                step=1,
                value=0,
                info="Usa lo slider per impostare rapidamente il budget (0 = nessun limite).",
            )

        with gr.Row():
            active_filters = gr.CheckboxGroup(
                label="Filtri attivi (seleziona e rimuovi)",
                choices=[],
                value=[],
                interactive=True,
            )
            remove_filters_btn = gr.Button("Rimuovi filtri selezionati", variant="secondary")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Pannello filtri")
                # Technical state (handled by the post-search facet tree)
                speed = gr.State("")
                freehub = gr.State("")
                brake = gr.State("")
                axle = gr.State("")
                rotor = gr.State("")
                # Facet tree (populated after first search)
                with gr.Accordion("Albero filtri (post-ricerca)", open=False):
                    facet_speed = gr.Radio(
                        label="Velocità", choices=[], interactive=True
                    )
                    facet_freehub = gr.Radio(
                        label="Corpetto", choices=[], interactive=True
                    )
                    facet_brake = gr.Radio(label="Freno", choices=[], interactive=True)
                    facet_rotor = gr.Radio(label="Rotore", choices=[], interactive=True)
                    facet_axle = gr.Radio(
                        label="Asse (Axle)", choices=[], interactive=True
                    )
                with gr.Row():
                    # Buttons already defined above; visual reminder only
                    pass
                status = gr.Markdown(visible=True)
            with gr.Column(scale=3, elem_id="results-col"):
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
                with gr.Row():
                    qty_input = gr.Number(label="Qtà", value=1, precision=0)
                    add_btn = gr.Button("Aggiungi al carrello")
                preview = gr.Markdown("Seleziona un'offerta per i dettagli")
                gr.Markdown("### Carrello")
                cart_table = gr.Dataframe(
                    headers=[
                        "ID",
                        "Brand",
                        "MPN",
                        "Fornitore",
                        "Prezzo",
                        "Qtà",
                        "Totale",
                    ],
                    interactive=False,
                )
                cart_select = gr.Dropdown(
                    label="Seleziona riga carrello", choices=[], interactive=True
                )
                with gr.Row():
                    minus_btn = gr.Button("− Qtà")
                    plus_btn = gr.Button("+ Qtà")
                    remove_btn = gr.Button("Rimuovi selezionato")
                    clear_cart_btn = gr.Button("Svuota carrello")
                totals_md = gr.Markdown(visible=True)
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

        def _active_filters_list(
            category,
            suppliers_sel,
            in_stock_only,
            speed,
            freehub,
            brake,
            axle,
            rotor,
            budget,
        ) -> list[str]:
            filters: list[str] = []
            if category:
                filters.append(f"category:{category}")
            if suppliers_sel:
                filters.append(f"suppliers:{','.join(sorted(suppliers_sel))}")
            if in_stock_only:
                filters.append("in_stock:true")
            if speed:
                filters.append(f"speed:{speed}")
            if freehub:
                filters.append(f"freehub:{freehub}")
            if brake:
                filters.append(f"brake:{brake}")
            if axle:
                filters.append(f"axle:{axle}")
            if rotor:
                filters.append(f"rotor:{rotor}")
            if budget is not None:
                try:
                    bval = float(budget)
                except Exception:
                    bval = 0.0
                if bval > 0:
                    filters.append(f"budget:<= {bval:.0f}")
            return filters

        def _on_search(
            query,
            speed,
            freehub,
            brake,
            axle,
            rotor,
            budget,
            category,
            suppliers_sel,
            in_stock_only,
        ):
            rows, options, mapping, msg = _do_search(
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers_sel,
                in_stock_only,
            )
            labels = [opt[0] for opt in options]
            default_label = labels[0] if labels else None
            # Fetch facets from API to refresh filter options/info
            try:
                auth = (API_USER, API_PASS) if API_USER and API_PASS else None
                payload = {
                    "query_text": query or None,
                    "speed": speed or None,
                    "freehub": (freehub or None),
                    "brake": (brake or None),
                    "axle": axle or None,
                    "rotor": (rotor or None),
                    "budget_max": (
                        float(budget)
                        if (budget is not None and float(budget) > 0)
                        else None
                    ),
                    "category": category or None,
                    "suppliers": suppliers_sel or [],
                    "in_stock_only": bool(in_stock_only),
                }
                r = httpx.post(
                    f"{API_BASE}/facets", json=payload, auth=auth, timeout=10
                )
                if r.status_code == 200:
                    f = r.json()
                    # Build info strings
                    speed_info = ", ".join(
                        [f"{k} ({v})" for k, v in sorted(f.get("speed", {}).items())]
                    )
                    freehub_info = ", ".join(
                        [f"{k} ({v})" for k, v in sorted(f.get("freehub", {}).items())]
                    )
                    brake_info = ", ".join(
                        [f"{k} ({v})" for k, v in sorted(f.get("brake", {}).items())]
                    )
                    axle_info = ", ".join(
                        [f"{k} ({v})" for k, v in sorted(f.get("axle", {}).items())]
                    )
                    rotor_info = ", ".join(
                        [f"{k} ({v})" for k, v in sorted(f.get("rotor", {}).items())]
                    )
                    # Choices are only keys with count>0 to avoid dead filters
                    speed_choices = sorted(list(f.get("speed", {}).keys()))
                    freehub_choices = sorted(list(f.get("freehub", {}).keys()))
                    brake_choices = sorted(list(f.get("brake", {}).keys()))
                    # Axle choices remain free-text for now (tooltip only)
                    rotor_choices = sorted(list(f.get("rotor", {}).keys()))

                    # Coverage gating based on product totals
                    totals = f.get("totals", {})
                    prod_total = int(totals.get("products", 0) or 0) or 1

                    def _coverage(counts: dict[str, int]) -> float:
                        return sum(int(v) for v in (counts or {}).values()) / float(
                            prod_total
                        )

                    # Reset value to "" if current selection disappears
                    speed_val = speed if speed in speed_choices else ""
                    freehub_val = freehub if freehub in freehub_choices else ""
                    brake_val = brake if brake in brake_choices else ""
                    rotor_val = rotor if rotor in rotor_choices else ""
                    category_choices = sorted(list(f.get("category", {}).keys()))
                    category_val = category if category in category_choices else ""

                    thr = 0.15

                    def _annotate(info: str | None, cov: float) -> str | None:
                        if not info:
                            return None
                        return (
                            f"{info} — poche specifiche nei risultati"
                            if cov < thr
                            else info
                        )

                    cov_speed = _coverage(f.get("speed", {}))
                    cov_freehub = _coverage(f.get("freehub", {}))
                    cov_brake = _coverage(f.get("brake", {}))
                    cov_rotor = _coverage(f.get("rotor", {}))
                    _ = gr.update(
                        choices=[""] + speed_choices,
                        value=speed_val,
                        info=_annotate((speed_info or None), cov_speed),
                        interactive=(cov_speed >= thr),
                    )
                    _ = gr.update(
                        choices=[""] + freehub_choices,
                        value=freehub_val,
                        info=_annotate((freehub_info or None), cov_freehub),
                        interactive=(cov_freehub >= thr),
                    )
                    _ = gr.update(
                        choices=[""] + brake_choices,
                        value=brake_val,
                        info=_annotate((brake_info or None), cov_brake),
                        interactive=(cov_brake >= thr),
                    )
                    _ = gr.update(info=(axle_info or None))
                    _ = gr.update(
                        choices=[""] + rotor_choices,
                        value=rotor_val,
                        info=_annotate((rotor_info or None), cov_rotor),
                        interactive=(cov_rotor >= thr),
                    )
                    suppliers_upd = gr.update(
                        choices=sorted(list(f.get("supplier", {}).keys()))
                    )
                    category_upd = gr.update(
                        choices=[""] + category_choices,
                        value=category_val,
                        interactive=bool(category_choices),
                        info=(
                            None
                            if category_choices
                            else "Nessuna categoria nei risultati"
                        ),
                    )
                    price = f.get("price", {})
                    price_info = None
                    if (
                        price
                        and price.get("max") is not None
                        and price.get("min") is not None
                    ):
                        price_info = f"Prezzo min/max: €{float(price['min']):.2f} – €{float(price['max']):.2f}"
                    # Update number info and slider bounds; keep 0 as 'no limit'
                    max_val = float(price.get("max") or 0.0)
                    # If budget is None or 0, keep slider at 0; else clamp in [min,max]
                    if budget is None or float(budget) <= 0:
                        slider_val = 0
                    else:
                        slider_val = max(min(int(float(budget)), int(max_val)), 0)
                    budget_upd = gr.update(info=price_info)
                    budget_slider_upd = gr.update(
                        minimum=0,
                        maximum=max(100, int(max_val) or 100),
                        value=slider_val,
                    )
                    # Facet tree radios (choices + enablement)
                    cov_speed = _coverage(f.get("speed", {}))
                    cov_freehub = _coverage(f.get("freehub", {}))
                    cov_brake = _coverage(f.get("brake", {}))
                    cov_rotor = _coverage(f.get("rotor", {}))
                    facet_speed_upd = gr.update(
                        choices=speed_choices,
                        value=None,
                        interactive=(cov_speed >= thr),
                        info=_annotate(speed_info or None, cov_speed),
                    )
                    facet_freehub_upd = gr.update(
                        choices=freehub_choices,
                        value=None,
                        interactive=(cov_freehub >= thr),
                        info=_annotate(freehub_info or None, cov_freehub),
                    )
                    facet_brake_upd = gr.update(
                        choices=brake_choices,
                        value=None,
                        interactive=(cov_brake >= thr),
                        info=_annotate(brake_info or None, cov_brake),
                    )
                    facet_rotor_upd = gr.update(
                        choices=rotor_choices,
                        value=None,
                        interactive=(cov_rotor >= thr),
                        info=_annotate(rotor_info or None, cov_rotor),
                    )
                    facet_axle_upd = gr.update(
                        choices=sorted(list(f.get("axle", {}).keys())),
                        value=None,
                        info=axle_info or None,
                    )
                else:
                    suppliers_upd = gr.update()
                    category_upd = gr.update()
                    budget_upd = gr.update()
                    budget_slider_upd = gr.update()
                    facet_speed_upd = gr.update()
                    facet_freehub_upd = gr.update()
                    facet_brake_upd = gr.update()
                    facet_rotor_upd = gr.update()
                    facet_axle_upd = gr.update()
            except Exception as exc:
                log_exception("ui", "facets", "failed to build facets", exc)
                suppliers_upd = gr.update()
                category_upd = gr.update()
                budget_upd = gr.update()
                budget_slider_upd = gr.update()
                facet_speed_upd = gr.update()
                facet_freehub_upd = gr.update()
                facet_brake_upd = gr.update()
                facet_rotor_upd = gr.update()
                facet_axle_upd = gr.update()

            af = _active_filters_list(
                category,
                suppliers_sel,
                in_stock_only,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
            )
            active_filters_upd = gr.update(choices=af, value=af)

            return (
                rows,
                gr.update(choices=labels, value=default_label),
                {k: v for k, v in mapping.items()},
                msg,
                suppliers_upd,
                category_upd,
                budget_upd,
                budget_slider_upd,
                facet_speed_upd,
                facet_freehub_upd,
                facet_brake_upd,
                facet_rotor_upd,
                facet_axle_upd,
                active_filters_upd,
            )

        search_btn.click(
            _on_search,
            inputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers,
                in_stock,
            ],
            outputs=[
                results,
                offer_select,
                results_state,
                status,
                suppliers,
                category,
                budget,
                budget_slider,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )

        for ctrl in [
            budget,
            budget_slider,
            category,
            suppliers,
            in_stock,
        ]:
            cast(Any, ctrl).change(  # type: ignore[attr-defined]
                _on_search,
                inputs=[
                    query,
                    speed,
                    freehub,
                    brake,
                    axle,
                    rotor,
                    budget,
                    category,
                    suppliers,
                    in_stock,
                ],
                outputs=[
                    results,
                    offer_select,
                    results_state,
                    status,
                    suppliers,
                    category,
                    budget,
                    budget_slider,
                    facet_speed,
                    facet_freehub,
                    facet_brake,
                    facet_rotor,
                    facet_axle,
                    active_filters,
                ],
            )

        # Textbox does not trigger live change-search; use Enter or the button
        query.submit(
            _on_search,
            inputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers,
                in_stock,
            ],
            outputs=[
                results,
                offer_select,
                results_state,
                status,
                suppliers,
                category,
                budget,
                budget_slider,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )

        def _on_clear():
            return (
                "",  # query
                gr.update(value=""),  # speed
                gr.update(value=""),  # freehub
                gr.update(value=""),  # brake
                gr.update(value=""),  # axle
                gr.update(value=""),  # rotor
                gr.update(value=None),  # budget number
                gr.update(value=0),  # budget slider
                [],  # results
                gr.update(choices=[], value=None),  # offer_select
                {},  # results_state
                "",  # status
                gr.update(choices=[], value=None),  # facet_speed
                gr.update(choices=[], value=None),  # facet_freehub
                gr.update(choices=[], value=None),  # facet_brake
                gr.update(choices=[], value=None),  # facet_rotor
                gr.update(choices=[], value=None),  # facet_axle
                gr.update(choices=[], value=[]),  # active_filters
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
                budget_slider,
                results,
                offer_select,
                results_state,
                status,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )

        def _remove_filters(
            selected: list[str] | None,
            category_val,
            suppliers_val,
            in_stock_val,
            speed_val,
            freehub_val,
            brake_val,
            axle_val,
            rotor_val,
            budget_val,
            budget_slider_val,
        ):
            selected_set = set(selected or [])

            def _has(prefix: str) -> bool:
                return any(s.startswith(prefix + ":") for s in selected_set)

            category_new = "" if _has("category") else category_val
            suppliers_new = [] if _has("suppliers") else suppliers_val
            in_stock_new = False if _has("in_stock") else in_stock_val
            speed_new = "" if _has("speed") else speed_val
            freehub_new = "" if _has("freehub") else freehub_val
            brake_new = "" if _has("brake") else brake_val
            axle_new = "" if _has("axle") else axle_val
            rotor_new = "" if _has("rotor") else rotor_val
            budget_new = None if _has("budget") else budget_val
            budget_slider_new = 0 if _has("budget") else budget_slider_val

            return (
                category_new,
                suppliers_new,
                in_stock_new,
                speed_new,
                freehub_new,
                brake_new,
                axle_new,
                rotor_new,
                budget_new,
                budget_slider_new,
                gr.update(choices=[], value=[]),
            )

        remove_filters_btn.click(
            _remove_filters,
            inputs=[
                active_filters,
                category,
                suppliers,
                in_stock,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                budget_slider,
            ],
            outputs=[
                category,
                suppliers,
                in_stock,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                budget_slider,
                active_filters,
            ],
        ).then(
            _on_search,
            inputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers,
                in_stock,
            ],
            outputs=[
                results,
                offer_select,
                results_state,
                status,
                suppliers,
                category,
                budget,
                budget_slider,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )

        # Facet tree interactions: pick → set corresponding control, then the .change handler triggers search
        # Apply facet picks to internal state and re-run search
        facet_speed.change(
            lambda v: (v or ""), inputs=[facet_speed], outputs=[speed]
        ).then(
            _on_search,
            inputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers,
                in_stock,
            ],
            outputs=[
                results,
                offer_select,
                results_state,
                status,
                suppliers,
                category,
                budget,
                budget_slider,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )
        facet_freehub.change(
            lambda v: (v or ""), inputs=[facet_freehub], outputs=[freehub]
        ).then(
            _on_search,
            inputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers,
                in_stock,
            ],
            outputs=[
                results,
                offer_select,
                results_state,
                status,
                suppliers,
                category,
                budget,
                budget_slider,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )
        facet_brake.change(
            lambda v: (v or ""), inputs=[facet_brake], outputs=[brake]
        ).then(
            _on_search,
            inputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers,
                in_stock,
            ],
            outputs=[
                results,
                offer_select,
                results_state,
                status,
                suppliers,
                category,
                budget,
                budget_slider,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )
        facet_rotor.change(
            lambda v: (v or ""), inputs=[facet_rotor], outputs=[rotor]
        ).then(
            _on_search,
            inputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers,
                in_stock,
            ],
            outputs=[
                results,
                offer_select,
                results_state,
                status,
                suppliers,
                category,
                budget,
                budget_slider,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )
        facet_axle.change(
            lambda v: (v or ""), inputs=[facet_axle], outputs=[axle]
        ).then(
            _on_search,
            inputs=[
                query,
                speed,
                freehub,
                brake,
                axle,
                rotor,
                budget,
                category,
                suppliers,
                in_stock,
            ],
            outputs=[
                results,
                offer_select,
                results_state,
                status,
                suppliers,
                category,
                budget,
                budget_slider,
                facet_speed,
                facet_freehub,
                facet_brake,
                facet_rotor,
                facet_axle,
                active_filters,
            ],
        )

        # Keep slider and number in sync (0 means no budget)
        def _sync_budget_from_slider(val: float | int | None):
            try:
                v = float(val or 0)
            except Exception as exc:
                log_exception("ui", "budget", "invalid slider value", exc, extra={"val": val})
                v = 0.0
            if v <= 0:
                return gr.update(value=None)
            return gr.update(value=v)

        def _sync_slider_from_budget(val: float | None):
            try:
                v = float(val) if val is not None else 0.0
            except Exception as exc:
                log_exception("ui", "budget", "invalid budget value", exc, extra={"val": val})
                v = 0.0
            return gr.update(value=(0 if v <= 0 else v))

        budget_slider.change(
            _sync_budget_from_slider, inputs=[budget_slider], outputs=[budget]
        )
        budget.change(
            _sync_slider_from_budget, inputs=[budget], outputs=[budget_slider]
        )

        def _on_select(offer_label: str | None, mapping: dict[int, dict[str, Any]]):
            if not offer_label:
                return "Seleziona un'offerta per i dettagli"
            # Extract offer_id from label prefix
            try:
                offer_id = int(str(offer_label).split(" · ")[0])
            except Exception as exc:
                log_exception("ui", "select-offer", "failed to parse offer label", exc, extra={"label": offer_label})
                return "Seleziona un'offerta per i dettagli"
            info = mapping.get(int(offer_id)) or {}
            return f"**Offerta {offer_id}** — {info.get('brand', '')} {info.get('mpn', '')} — {info.get('supplier', '')} — €{info.get('price', '')}"

        cast(Any, offer_select).change(  # type: ignore[attr-defined]
            _on_select, inputs=[offer_select, results_state], outputs=preview
        )

        def _cart_rows(cart: dict[int, dict[str, Any]]):
            rows = []
            labels = []
            for oid, info in cart.items():
                qty = int(info.get("qty", 1))
                total = float(info.get("price", 0.0)) * qty
                rows.append(
                    [
                        oid,
                        info.get("brand", ""),
                        info.get("mpn", ""),
                        info.get("supplier", ""),
                        round(float(info.get("price", 0.0)), 2),
                        qty,
                        round(total, 2),
                    ]
                )
                labels.append(f"{oid} · {info.get('brand', '')} {info.get('mpn', '')}")
            return rows, labels

        def _cart_totals(cart: dict[int, dict[str, Any]]):
            subtotal = 0.0
            for info in cart.values():
                qty = int(info.get("qty", 1))
                price = float(info.get("price", 0.0))
                subtotal += price * qty
            vat_rate = float(os.environ.get("APP_VAT", "0") or 0)
            vat = subtotal * vat_rate
            total = subtotal + vat
            return subtotal, vat_rate, vat, total

        def _totals_md(cart: dict[int, dict[str, Any]]):
            subtotal, vat_rate, vat, total = _cart_totals(cart)
            return f"**Subtotale:** €{subtotal:.2f} &nbsp;&nbsp; **IVA ({vat_rate * 100:.0f}%):** €{vat:.2f} &nbsp;&nbsp; **Totale:** €{total:.2f}"

        def _on_add(
            offer_label: str | None,
            qty: float | int,
            mapping: dict[int, dict[str, Any]],
            cart: dict[int, dict[str, Any]],
        ):
            if not offer_label:
                return gr.update(), cart, gr.update()
            try:
                offer_id = int(str(offer_label).split(" · ")[0])
            except Exception as exc:
                log_exception("ui", "cart-add", "failed to parse offer label", exc, extra={"label": offer_label})
                return gr.update(), cart, gr.update()
            info = mapping.get(offer_id)
            if not info:
                return gr.update(), cart, gr.update()
            prev = cart.get(offer_id, {**info, "qty": 0})
            prev_qty = int(prev.get("qty", 0))
            prev.update({"qty": prev_qty + max(1, int(qty))})
            cart[offer_id] = prev
            rows, labels = _cart_rows(cart)
            return (
                rows,
                cart,
                gr.update(choices=labels, value=(labels[-1] if labels else None)),
                _totals_md(cart),
            )

        add_btn.click(
            _on_add,
            inputs=[offer_select, qty_input, results_state, cart_state],
            outputs=[cart_table, cart_state, cart_select, totals_md],
        )

        def _on_remove(cart_label: str | None, cart: dict[int, dict[str, Any]]):
            if not cart_label:
                return gr.update(), cart, gr.update(), _totals_md(cart)
            try:
                offer_id = int(str(cart_label).split(" · ")[0])
            except Exception as exc:
                log_exception("ui", "cart-remove", "failed to parse cart label", exc, extra={"label": cart_label})
                return gr.update(), cart, gr.update(), _totals_md(cart)
            if offer_id in cart:
                cart.pop(offer_id)
            rows, labels = _cart_rows(cart)
            return rows, cart, gr.update(choices=labels, value=None), _totals_md(cart)

        remove_btn.click(
            _on_remove,
            inputs=[cart_select, cart_state],
            outputs=[cart_table, cart_state, cart_select, totals_md],
        )

        def _on_clear_cart():
            return [], {}, gr.update(choices=[], value=None), ""

        clear_cart_btn.click(
            _on_clear_cart,
            inputs=[],
            outputs=[cart_table, cart_state, cart_select, totals_md],
        )

        def _on_adjust(
            sign: str, cart_label: str | None, cart: dict[int, dict[str, Any]]
        ):
            if not cart_label:
                return gr.update(), cart, gr.update(), _totals_md(cart)
            try:
                offer_id = int(str(cart_label).split(" · ")[0])
            except Exception as exc:
                log_exception("ui", "cart-adjust", "failed to parse cart label", exc, extra={"label": cart_label})
                return gr.update(), cart, gr.update(), _totals_md(cart)
            if offer_id not in cart:
                return gr.update(), cart, gr.update(), _totals_md(cart)
            cur = cart[offer_id]
            qty = int(cur.get("qty", 1))
            if sign == "+":
                qty += 1
            else:
                qty = max(1, qty - 1)
            cur["qty"] = qty
            cart[offer_id] = cur
            rows, labels = _cart_rows(cart)
            return (
                rows,
                cart,
                gr.update(choices=labels, value=cart_label),
                _totals_md(cart),
            )

        plus_btn.click(
            _on_adjust,
            inputs=[gr.State("+"), cart_select, cart_state],
            outputs=[cart_table, cart_state, cart_select, totals_md],
        )
        minus_btn.click(
            _on_adjust,
            inputs=[gr.State("-"), cart_select, cart_state],
            outputs=[cart_table, cart_state, cart_select, totals_md],
        )

        def _render_local_cart(
            items: list[dict[str, int]],
            customer: str,
            contact: str,
            validity: int,
            notes: str,
        ):
            from .models import SupplierOffer

            rows: list[dict[str, Any]] = []
            with SessionLocal() as db:
                for entry in items:
                    oid = int(entry.get("offer_id", 0))
                    qty = int(entry.get("qty", 1))
                    offer = db.get(SupplierOffer, oid)
                    if not offer:
                        continue
                    p = offer.product
                    rows.append(
                        {
                            "brand": p.brand,
                            "mpn": p.mpn,
                            "name": p.name,
                            "supplier": offer.supplier,
                            "price": offer.price,
                            "qty": qty,
                            "in_stock": offer.in_stock,
                            "lead_time_days": offer.lead_time_days,
                        }
                    )
            if not rows:
                return "Nessun elemento nel carrello", "", ""
            ctx = {
                "customer_name": customer,
                "customer_contact": contact,
                "validity_days": validity,
                "notes": notes,
                "items": rows,
            }
            html_path, pdf_path = render_quote(ctx)
            return html_path, (pdf_path or ""), ""

        def _on_quote(
            offer_label: str | None,
            customer: str,
            contact: str,
            validity: int,
            notes: str,
            cart: dict[int, dict[str, Any]],
        ):
            # Prefer cart items if present; otherwise fallback to selected offer
            items: list[dict[str, Any]] = []
            if cart:
                for oid, info in cart.items():
                    items.append({"offer_id": int(oid), "qty": int(info.get("qty", 1))})
            else:
                if not offer_label:
                    return "Seleziona un'offerta", "", ""
                try:
                    offer_id = int(str(offer_label).split(" · ")[0])
                except Exception as exc:
                    log_exception("ui", "quote", "failed to parse offer label", exc, extra={"label": offer_label})
                    return "Seleziona un'offerta", "", ""
                items = [{"offer_id": offer_id, "qty": 1}]
            # Call API
            try:
                auth = (API_USER, API_PASS) if API_USER and API_PASS else None
                payload = {
                    "items": items,
                    "customer_name": customer,
                    "customer_contact": contact,
                    "validity_days": int(validity),
                    "notes": notes or None,
                }
                r = httpx.post(f"{API_BASE}/quote", json=payload, auth=auth, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    return (
                        data.get("html_path", ""),
                        data.get("pdf_path") or "",
                        data.get("file_url") or "",
                    )
                # Fall back to local multi-line rendering on non-200
                return _render_local_cart(items, customer, contact, validity, notes)
            except Exception as exc:
                log_exception("ui", "quote", "failed to create quote", exc)
                # Robust fallback to local multi-line rendering
                return _render_local_cart(items, customer, contact, validity, notes)

        quote_btn.click(
            _on_quote,
            inputs=[offer_select, customer, contact, validity, notes, cart_state],
            outputs=[html_out, pdf_out, file_url],
        )

    return demo


def main() -> None:
    iface = build_interface()
    iface.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
