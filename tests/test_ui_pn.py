from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize("have_auth", [False, True])
def test_ui_pn_builds_interface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, have_auth: bool
) -> None:
    """Smoke test: ui_pn.ui() must build Blocks without hitting real HTTP APIs."""
    # Avoid real HTTP calls to /dealers and other endpoints.
    import app.ui_pn as ui_pn

    def fake_api_get(path: str):
        # Simula /dealers
        if path == "/dealers":
            return {"dealers": [{"name": "DealerA"}, {"name": "DealerB"}]}
        return {}

    def fake_api_post(path: str, payload: dict):
        # Simula risposte minime per /search_pn_batch, /optimize e /quote
        if path == "/search_pn_batch":
            items = payload.get("items", [])
            results = []
            for pn in items:
                results.append(
                    {
                        "maker_pn": pn,
                        "offers": [
                            {
                                "offer_id": 1,
                                "dealer": "DealerA",
                                "price": 10.0,
                                "in_stock": True,
                                "lead_time_days": 2,
                            }
                        ],
                    }
                )
            return {"results": results}
        if path == "/optimize":
            return {
                "lines": [],
                "dealers": [],
                "costs": {
                    "subtotal": 0.0,
                    "shipping": 0.0,
                    "penalties": 0.0,
                    "total": 0.0,
                },
                "notes": [],
            }
        if path == "/quote":
            return {
                "content_type": "text/html",
                "html_path": str(tmp_path / "quote.html"),
                "pdf_path": None,
            }
        return {}

    # Patch the api_client functions that ui_pn now imports
    import app.api_client as api_client

    monkeypatch.setattr(api_client, "api_get", fake_api_get)
    monkeypatch.setattr(api_client, "api_post", fake_api_post)

    # Configure or clear basic auth credentials to cover both branches.
    if have_auth:
        monkeypatch.setenv("APP_BASIC_USER", "demo")
        monkeypatch.setenv("APP_BASIC_PASS", "demo123")
    else:
        monkeypatch.delenv("APP_BASIC_USER", raising=False)
        monkeypatch.delenv("APP_BASIC_PASS", raising=False)

    # Do not start a real server; only ensure ui() builds without raising.
    # Patch gradio.Blocks.launch to avoid network side effects.
    import gradio as gr

    def fake_launch(self, *args, **kwargs):  # type: ignore[override]
        return self

    monkeypatch.setattr(gr.Blocks, "launch", fake_launch, raising=False)

    # The call must not raise.
    ui_pn.ui()
