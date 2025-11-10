from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from .models import PriceHistory, Product, SupplierOffer, SessionLocal, create_all
from .types import OfferInput, ProductInput
from .adapters.csv_adapter import parse_offers_csv, parse_products_csv
from .staging import stage_file


def normalize_text(s: str) -> str:
    return "".join(ch for ch in s.strip().lower() if ch.isalnum())


@dataclass(frozen=True)
class IngestStats:
    products_new: int = 0
    products_updated: int = 0
    offers_upserted: int = 0
    offers_skipped: int = 0


def upsert(core: list[ProductInput], offers: list[OfferInput]) -> IngestStats:
    create_all()
    stats = IngestStats()
    with SessionLocal() as db:
        # Products
        for p in core:
            # Prefer EAN; fallback to brand+mpn exact match
            existing: Product | None = None
            if p.ean:
                existing = db.scalar(select(Product).where(Product.ean == p.ean))
            if existing is None:
                existing = db.scalar(
                    select(Product).where(
                        Product.brand == p.brand, Product.mpn == p.mpn
                    )
                )
            if existing is None:
                obj = Product(
                    brand=p.brand,
                    mpn=p.mpn,
                    ean=p.ean,
                    name=p.name,
                    speed=p.speed,
                    brake=p.brake,
                    axle=p.axle,
                    rotor=p.rotor,
                    freehub=p.freehub,
                )
                db.add(obj)
                stats = IngestStats(
                    products_new=stats.products_new + 1,
                    products_updated=stats.products_updated,
                    offers_upserted=stats.offers_upserted,
                    offers_skipped=stats.offers_skipped,
                )
            else:
                existing.name = p.name or existing.name
                existing.speed = p.speed or existing.speed
                existing.brake = p.brake or existing.brake
                existing.axle = p.axle or existing.axle
                existing.rotor = p.rotor or existing.rotor
                existing.freehub = p.freehub or existing.freehub
                stats = IngestStats(
                    products_new=stats.products_new,
                    products_updated=stats.products_updated + 1,
                    offers_upserted=stats.offers_upserted,
                    offers_skipped=stats.offers_skipped,
                )
        db.commit()

        # Offers
        for o in offers:
            product = db.scalar(
                select(Product).where(Product.brand == o.brand, Product.mpn == o.mpn)
            )
            if not product:
                stats = IngestStats(
                    products_new=stats.products_new,
                    products_updated=stats.products_updated,
                    offers_upserted=stats.offers_upserted,
                    offers_skipped=stats.offers_skipped + 1,
                )
                continue

            offer_existing = db.scalar(
                select(SupplierOffer).where(
                    SupplierOffer.product_id == product.id,
                    SupplierOffer.supplier == o.supplier,
                )
            )
            if offer_existing is None:
                offer = SupplierOffer(
                    product_id=product.id,
                    supplier=o.supplier,
                    price=o.price,
                    in_stock=o.in_stock,
                    lead_time_days=o.lead_time_days,
                )
                db.add(offer)
            else:
                # Price history on change
                if offer_existing.price != o.price:
                    db.add(
                        PriceHistory(
                            offer_id=offer_existing.id, price=o.price, source_hash=None
                        )
                    )
                offer_existing.price = o.price
                offer_existing.in_stock = o.in_stock
                offer_existing.lead_time_days = o.lead_time_days
            stats = IngestStats(
                products_new=stats.products_new,
                products_updated=stats.products_updated,
                offers_upserted=stats.offers_upserted + 1,
                offers_skipped=stats.offers_skipped,
            )
        db.commit()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--products", type=Path, required=True)
    parser.add_argument("--offers", type=Path, required=True)
    args = parser.parse_args()

    # Stage files for provenance
    stage_file(provider="csv", kind="products", path=args.products)
    stage_file(provider="csv", kind="offers", path=args.offers)

    products = parse_products_csv(args.products)
    offers = parse_offers_csv(args.offers)
    stats = upsert(products, offers)
    print(
        {
            "products_new": stats.products_new,
            "products_updated": stats.products_updated,
            "offers_upserted": stats.offers_upserted,
            "offers_skipped": stats.offers_skipped,
        }
    )


if __name__ == "__main__":
    main()
