from __future__ import annotations

from typing import Any

import gradio as gr

from .logging_utils import log_exception
from .ui_handlers_cart import (
    handle_cart_add,
    handle_cart_adjust,
    handle_cart_clear,
    handle_cart_remove,
    handle_offer_select,
)
from .ui_handlers_quote import handle_quote_request
from .ui_handlers_search import handle_search_request
from typing import cast


__all__ = ["build_interface"]


def build_interface() -> gr.Blocks:
    css = """
    #filters-row { gap: 8px; }
    @media (max-width: 980px){
      #filters-row { flex-wrap: wrap; }
      #results-col { flex: 1 1 100% !important; }
    }
    """
    with gr.Blocks(title="Bike Copilot Demo") as demo:
        gr.HTML(f"<style>{css}</style>")
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
            remove_filters_btn = gr.Button(
                "Rimuovi filtri selezionati", variant="secondary"
            )

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
            """
            Gradio wrapper for search handler.

            Delegates business logic to handle_search_request() and
            converts SearchHandlerResult to gr.update() calls.
            """
            try:
                # Call business logic handler
                result = handle_search_request(
                    query=query,
                    speed=speed,
                    freehub=freehub,
                    brake=brake,
                    axle=axle,
                    rotor=rotor,
                    budget=budget,
                    category=category,
                    suppliers_sel=suppliers_sel,
                    in_stock_only=in_stock_only,
                )

                # Convert SearchHandlerResult to Gradio updates
                return (
                    result.rows,
                    gr.update(choices=result.offer_labels, value=result.default_label),
                    {k: v for k, v in result.mapping.items()},
                    result.message,
                    gr.update(choices=result.suppliers_choices),
                    gr.update(
                        choices=result.category.choices,
                        value=result.category.value,
                        interactive=result.category.interactive,
                        info=result.category.info,
                    ),
                    gr.update(info=result.budget.info),
                    gr.update(
                        minimum=result.budget.slider_min,
                        maximum=result.budget.slider_max,
                        value=result.budget.slider_value,
                    ),
                    gr.update(
                        choices=result.speed.choices[
                            1:
                        ],  # Remove empty prefix for Radio
                        value=None,
                        interactive=result.speed.interactive,
                        info=result.speed.info,
                    ),
                    gr.update(
                        choices=result.freehub.choices[1:],  # Remove empty prefix
                        value=None,
                        interactive=result.freehub.interactive,
                        info=result.freehub.info,
                    ),
                    gr.update(
                        choices=result.brake.choices[1:],  # Remove empty prefix
                        value=None,
                        interactive=result.brake.interactive,
                        info=result.brake.info,
                    ),
                    gr.update(
                        choices=result.rotor.choices[1:],  # Remove empty prefix
                        value=None,
                        interactive=result.rotor.interactive,
                        info=result.rotor.info,
                    ),
                    gr.update(
                        choices=result.axle.choices[1:],  # Remove empty prefix
                        value=None,
                        info=result.axle.info,
                    ),
                    gr.update(
                        choices=result.active_filters, value=result.active_filters
                    ),
                )
            except Exception as exc:
                log_exception("ui", "search", "search handler failed", exc)
                # Return safe empty state to prevent UI crash
                return (
                    [],  # empty rows
                    gr.update(choices=[], value=None),  # offer_select
                    {},  # mapping
                    "Errore durante la ricerca. Riprova.",  # message
                    gr.update(),  # suppliers (no change)
                    gr.update(),  # category (no change)
                    gr.update(),  # budget (no change)
                    gr.update(),  # budget_slider (no change)
                    gr.update(),  # speed facet
                    gr.update(),  # freehub facet
                    gr.update(),  # brake facet
                    gr.update(),  # rotor facet
                    gr.update(),  # axle facet
                    gr.update(choices=[], value=[]),  # active_filters
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

        # Helper function to create facet change handlers (reduces repetition)
        def _register_facet_handler(facet_component, state_component):
            """Register a facet radio change handler that updates state and triggers search."""
            facet_component.change(
                lambda v: (v or ""), inputs=[facet_component], outputs=[state_component]
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

        # Register all facet handlers using the factory function
        _register_facet_handler(facet_speed, speed)
        _register_facet_handler(facet_freehub, freehub)
        _register_facet_handler(facet_brake, brake)
        _register_facet_handler(facet_rotor, rotor)
        _register_facet_handler(facet_axle, axle)

        # Keep slider and number in sync (0 means no budget)
        def _sync_budget_from_slider(val: float | int | None):
            try:
                v = float(val or 0)
            except Exception as exc:
                log_exception(
                    "ui", "budget", "invalid slider value", exc, extra={"val": val}
                )
                v = 0.0
            if v <= 0:
                return gr.update(value=None)
            return gr.update(value=v)

        def _sync_slider_from_budget(val: float | None):
            try:
                v = float(val) if val is not None else 0.0
            except Exception as exc:
                log_exception(
                    "ui", "budget", "invalid budget value", exc, extra={"val": val}
                )
                v = 0.0
            return gr.update(value=(0 if v <= 0 else v))

        budget_slider.change(
            _sync_budget_from_slider, inputs=[budget_slider], outputs=[budget]
        )
        budget.change(
            _sync_slider_from_budget, inputs=[budget], outputs=[budget_slider]
        )

        def _on_select(offer_label: str | None, mapping: dict[int, dict[str, Any]]):
            """Gradio wrapper for offer selection handler."""
            return handle_offer_select(offer_label, mapping)

        cast(Any, offer_select).change(  # type: ignore[attr-defined]
            _on_select, inputs=[offer_select, results_state], outputs=preview
        )

        def _on_add(
            offer_label: str | None,
            qty: float | int,
            mapping: dict[int, dict[str, Any]],
            cart: dict[int, dict[str, Any]],
        ):
            """Gradio wrapper for cart add handler."""
            rows, updated_cart, labels, selected_label, totals = handle_cart_add(
                offer_label, qty, mapping, cart
            )
            return (
                rows,
                updated_cart,
                gr.update(choices=labels, value=selected_label),
                totals,
            )

        add_btn.click(
            _on_add,
            inputs=[offer_select, qty_input, results_state, cart_state],
            outputs=[cart_table, cart_state, cart_select, totals_md],
        )

        def _on_remove(cart_label: str | None, cart: dict[int, dict[str, Any]]):
            """Gradio wrapper for cart remove handler."""
            rows, updated_cart, labels, totals = handle_cart_remove(cart_label, cart)
            return rows, updated_cart, gr.update(choices=labels, value=None), totals

        remove_btn.click(
            _on_remove,
            inputs=[cart_select, cart_state],
            outputs=[cart_table, cart_state, cart_select, totals_md],
        )

        def _on_clear_cart():
            """Gradio wrapper for cart clear handler."""
            rows, cart, labels, totals = handle_cart_clear()
            return rows, cart, gr.update(choices=labels, value=None), totals

        clear_cart_btn.click(
            _on_clear_cart,
            inputs=[],
            outputs=[cart_table, cart_state, cart_select, totals_md],
        )

        def _on_adjust(
            sign: str, cart_label: str | None, cart: dict[int, dict[str, Any]]
        ):
            """Gradio wrapper for cart adjust handler."""
            rows, updated_cart, labels, selected_label, totals = handle_cart_adjust(
                sign, cart_label, cart
            )
            return (
                rows,
                updated_cart,
                gr.update(choices=labels, value=selected_label),
                totals,
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

        def _on_quote(
            offer_label: str | None,
            customer: str,
            contact: str,
            validity: int,
            notes: str,
            cart: dict[int, dict[str, Any]],
        ):
            """Gradio wrapper for quote generation handler."""
            return handle_quote_request(
                offer_label, customer, contact, validity, notes, cart
            )

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
