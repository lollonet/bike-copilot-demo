from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.parametrize("with_api_auth", [False, True])
def test_ui_builds_interface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, with_api_auth: bool
) -> None:
    """Smoke test: ui.build_interface() must construct Blocks without real HTTP or DB side effects."""
    import app.ui as ui_mod

    # Fake search to avoid DB access during _do_search.
    from app.types import SearchRequest, SearchResponse

    def fake_search(req: SearchRequest) -> SearchResponse:
        return SearchResponse(items=[])

    monkeypatch.setattr(ui_mod, "search", fake_search)

    # Patch httpx.post used in _create_quote and _on_search facets call.
    class DummyResp:
        def __init__(self, status_code: int, json_data: dict | None = None):
            self.status_code = status_code
            self._json_data = json_data or {}

        def json(self) -> dict:
            return self._json_data

    def fake_post(url: str, *args, **kwargs):  # type: ignore[override]
        if url.endswith("/facets"):
            return DummyResp(
                200,
                {
                    "speed": {},
                    "freehub": {},
                    "brake": {},
                    "axle": {},
                    "rotor": {},
                    "category": {},
                    "totals": {"products": 0},
                },
            )
        if url.endswith("/quote"):
            # Force non-200 to trigger local fallback; we do not care about result.
            return DummyResp(500, {})
        return DummyResp(200, {})

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post, raising=False)

    # Avoid real DB work inside _render_local_cart: patch SessionLocal and render_quote.
    import app.ui as app_ui

    def fake_render_quote(context: dict):
        html = tmp_path / "local_quote.html"
        html.write_text("demo", encoding="utf-8")
        return str(html), None

    monkeypatch.setattr(app_ui, "render_quote", fake_render_quote, raising=False)

    class DummySession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return None

        def add(self, *args, **kwargs):
            return None

        def commit(self):
            return None

    monkeypatch.setattr(app_ui, "SessionLocal", lambda: DummySession(), raising=False)

    # Configure or clear basic auth to visit both branches.
    if with_api_auth:
        monkeypatch.setenv("APP_BASIC_USER", "demo")
        monkeypatch.setenv("APP_BASIC_PASS", "demo123")
    else:
        monkeypatch.delenv("APP_BASIC_USER", raising=False)
        monkeypatch.delenv("APP_BASIC_PASS", raising=False)

    # Patch gradio.Blocks.launch to avoid starting a server if called.
    import gradio as gr

    def fake_launch(self, *args, **kwargs):  # type: ignore[override]
        return self

    monkeypatch.setattr(gr.Blocks, "launch", fake_launch, raising=False)

    # Calling build_interface must not raise.
    demo = ui_mod.build_interface()
    assert demo is not None
