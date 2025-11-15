from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    PriceHistory,
    Product,
    SupplierOffer,
    SessionLocal,
    create_all,
    PNMapping,
)
from .pn import normalize_pn
from .types import OfferInput, ProductInput
from .adapters.csv_adapter import parse_offers_csv, parse_products_csv
from .staging import stage_file


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
        stats = _upsert_products(db, core, stats)
        stats = _upsert_offers_and_mappings(db, offers, stats)
    return stats


def _upsert_products(
    db: Session, core: list[ProductInput], stats: IngestStats
) -> IngestStats:
    for p in core:
        existing = _find_existing_product(db, p)
        if existing is None:
            obj = Product(
                brand=p.brand,
                mpn=p.mpn,
                ean=p.ean,
                name=p.name,
                category=p.category,
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
            existing.category = p.category or existing.category
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
    return stats


def _find_existing_product(db: Session, p: ProductInput) -> Product | None:
    existing: Product | None = None
    if p.ean:
        existing = db.scalar(select(Product).where(Product.ean == p.ean))
    if existing is None:
        existing = db.scalar(
            select(Product).where(Product.brand == p.brand, Product.mpn == p.mpn)
        )
    return existing


def _upsert_offers_and_mappings(
    db: Session, offers: list[OfferInput], stats: IngestStats
) -> IngestStats:
    existing_offers: dict[tuple[int, str], SupplierOffer] = {}
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

        product_id = int(product.id)
        cache_key = (product_id, o.supplier)
        offer_existing = existing_offers.get(cache_key)
        is_from_current_batch = (
            offer_existing is not None
        )  # If found in cache, it's from current batch
        if offer_existing is None:
            offer_existing = db.scalar(
                select(SupplierOffer).where(
                    SupplierOffer.product_id == product_id,
                    SupplierOffer.supplier == o.supplier,
                )
            )
            if offer_existing is not None:
                existing_offers[cache_key] = offer_existing
        is_new_offer = False
        if offer_existing is None:
            try:
                with db.begin_nested():
                    offer = SupplierOffer(
                        product_id=product_id,
                        supplier=o.supplier,
                        price=o.price,
                        in_stock=o.in_stock,
                        lead_time_days=o.lead_time_days,
                    )
                    db.add(offer)
                    db.flush()
                    existing_offers[cache_key] = offer
                    offer_existing = offer
                    is_new_offer = True
            except IntegrityError:
                offer_existing = db.scalar(
                    select(SupplierOffer).where(
                        SupplierOffer.product_id == product_id,
                        SupplierOffer.supplier == o.supplier,
                    )
                )
                if offer_existing is None:
                    stats = IngestStats(
                        products_new=stats.products_new,
                        products_updated=stats.products_updated,
                        offers_upserted=stats.offers_upserted,
                        offers_skipped=stats.offers_skipped + 1,
                    )
                    continue
                existing_offers[cache_key] = offer_existing

        # Update price/stock for existing offers (found in cache, DB, or after IntegrityError)
        if not is_new_offer:
            # Only create price history for existing offers from DB, not duplicates in same batch
            if offer_existing.price != o.price and not is_from_current_batch:
                if offer_existing.id is not None:
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
        _upsert_pn_mapping(db, product, o)

    db.commit()
    return stats


def _upsert_pn_mapping(db: Session, product: Product, offer: OfferInput) -> None:
    dealer_code: str | None = None
    try:
        dealer_code_raw = (offer.extra or {}).get("dealer_pn")  # type: ignore[union-attr]
        dealer_code = str(dealer_code_raw) if dealer_code_raw is not None else None
    except Exception:
        dealer_code = None
    if not dealer_code:
        return
    maker_norm = normalize_pn(product.mpn)
    dealer_norm = normalize_pn(dealer_code)
    row = (
        db.query(PNMapping)
        .filter(
            PNMapping.dealer == offer.supplier, PNMapping.dealer_pn_norm == dealer_norm
        )
        .first()
    )
    if row:
        row.product_id = int(product.id)
        row.maker_pn_norm = maker_norm
    else:
        try:
            with db.begin_nested():
                db.add(
                    PNMapping(
                        product_id=int(product.id),
                        dealer=offer.supplier,
                        maker_pn_norm=maker_norm,
                        dealer_pn_norm=dealer_norm,
                        confidence=1.0,
                    )
                )
                db.flush()
        except IntegrityError:
            existing = (
                db.query(PNMapping)
                .filter(
                    PNMapping.dealer == offer.supplier,
                    PNMapping.dealer_pn_norm == dealer_norm,
                )
                .first()
            )
            if existing:
                existing.product_id = int(product.id)
                existing.maker_pn_norm = maker_norm


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
