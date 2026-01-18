#!/usr/bin/env python3
"""Entry point for Gradio UI interface.

This script launches the main Gradio UI without importing from CLI.
Avoids architectural boundary violation (CLI should not import UI).

Usage:
    python bin/run_ui.py
    python bin/run_ui.py --port 7860 --host 0.0.0.0
"""

from __future__ import annotations

import argparse


def main() -> None:
    """Launch Gradio UI interface."""
    parser = argparse.ArgumentParser(description="Launch Gradio UI")
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to run the UI server on (default: 7860)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind to (default: 0.0.0.0)",
    )
    args = parser.parse_args()

    from app.ui import build_interface

    iface = build_interface()
    iface.launch(server_name=args.host, server_port=args.port)


if __name__ == "__main__":
    main()
