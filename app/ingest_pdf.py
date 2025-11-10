from __future__ import annotations

import argparse
from pathlib import Path

from .adapters.pdf_adapter import extract_from_pdf
from .ingest import IngestStats, upsert
from .staging import stage_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=False)
    parser.add_argument("--provider", type=str, default="PDFProvider")
    args = parser.parse_args()

    stage_file(provider=args.provider, kind="pdf", path=args.pdf)
    products, offers = extract_from_pdf(args.pdf, args.mapping)
    stats: IngestStats = upsert(products, offers)
    print(stats)


if __name__ == "__main__":
    main()
