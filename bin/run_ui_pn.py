#!/usr/bin/env python3
"""Entry point for Panel (PN-first) UI interface.

This script launches the Panel UI without importing from CLI.
Avoids architectural boundary violation (CLI should not import UI).

Usage:
    python bin/run_ui_pn.py
    python bin/run_ui_pn.py --port 7861 --host 0.0.0.0
"""

from __future__ import annotations

import argparse


def main() -> None:
    """Launch Panel UI interface."""
    parser = argparse.ArgumentParser(description="Launch Panel UI (PN-first)")
    parser.add_argument(
        "--port",
        type=int,
        default=7861,
        help="Port to run the UI server on (default: 7861)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind to (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    # Import and launch UI with custom args
    from app.ui_pn import load_dealers, _build_pn_blocks, _scenario_options
    import gradio as gr

    dealers = load_dealers()
    scenario_options, scenario_value_map = _scenario_options()
    with gr.Blocks(title="PN-first — Preventivo") as demo:
        _build_pn_blocks(dealers, scenario_options, scenario_value_map)
    demo.launch(server_name=args.host, server_port=args.port)


if __name__ == "__main__":
    main()
