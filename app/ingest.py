from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .logging_utils import log_event
from .models import (
    PNMapping,
    PriceHistory,
    Product,
    SessionLocal,
    SupplierOffer,
    create_all,
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
    log_event(
        "INFO",
        op="ingest",
        kind="ingest",
        message="ingest started",
        trace_id=None,
        extra={"products": len(core), "offers": len(offers)},
    )
    with SessionLocal() as db:
        stats = _upsert_products(db, core, stats)
        stats = _upsert_offers_and_mappings(db, offers, stats)
    log_event(
        "INFO",
        op="ingest",
        kind="ingest",
        message="ingest completed",
        trace_id=None,
        extra={
            "products_new": stats.products_new,
            "products_updated": stats.products_updated,
            "offers_upserted": stats.offers_upserted,
            "offers_skipped": stats.offers_skipped,
        },
    )
    return stats


def _upsert_products(
    db: Session, core: list[ProductInput], stats: IngestStats
) -> IngestStats:
    for p in core:
        existing = _find_existing_product(db, p)
        if existing is None:
            stats = _insert_product(db, p, stats)
        else:
            stats = _update_product(existing, p, stats)
    db.commit()
    return stats


def _insert_product(
    db: Session,
    p: ProductInput,
    stats: IngestStats,
) -> IngestStats:
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
    return IngestStats(
        products_new=stats.products_new + 1,
        products_updated=stats.products_updated,
        offers_upserted=stats.offers_upserted,
        offers_skipped=stats.offers_skipped,
    )


def _update_product(
    existing: Product,
    p: ProductInput,
    stats: IngestStats,
) -> IngestStats:
    existing.name = p.name or existing.name
    existing.category = p.category or existing.category
    existing.speed = p.speed or existing.speed
    existing.brake = p.brake or existing.brake
    existing.axle = p.axle or existing.axle
    existing.rotor = p.rotor or existing.rotor
    existing.freehub = p.freehub or existing.freehub
    return IngestStats(
        products_new=stats.products_new,
        products_updated=stats.products_updated + 1,
        offers_upserted=stats.offers_upserted,
        offers_skipped=stats.offers_skipped,
    )


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
        product = _product_for_offer(db, o)
        if product is None:
            stats = _increment_offer_skipped(stats)
            continue
        product_id = int(product.id)
        cache_key = (product_id, o.supplier)
        offer_existing, is_from_current_batch = _get_offer_from_cache_or_db(
            db, existing_offers, cache_key
        )
        stats, offer_existing, is_new_offer = _ensure_offer(
            db, product_id, o, existing_offers, cache_key, offer_existing, stats
        )
        if offer_existing is None:
            continue
        stats = _update_offer_and_history(
            db, offer_existing, o, is_new_offer, is_from_current_batch, stats
        )
        _upsert_pn_mapping(db, product, o)

    db.commit()
    return stats


def _product_for_offer(db: Session, offer: OfferInput) -> Product | None:
    return db.scalar(
        select(Product).where(
            Product.brand == offer.brand,
            Product.mpn == offer.mpn,
        )
    )


def _increment_offer_skipped(stats: IngestStats) -> IngestStats:
    return IngestStats(
        products_new=stats.products_new,
        products_updated=stats.products_updated,
        offers_upserted=stats.offers_upserted,
        offers_skipped=stats.offers_skipped + 1,
    )


def _get_offer_from_cache_or_db(
    db: Session,
    existing_offers: dict[tuple[int, str], SupplierOffer],
    cache_key: tuple[int, str],
) -> tuple[SupplierOffer | None, bool]:
    cached = existing_offers.get(cache_key)
    if cached is not None:
        return cached, True
    product_id, supplier = cache_key
    offer_existing = db.scalar(
        select(SupplierOffer).where(
            SupplierOffer.product_id == product_id,
            SupplierOffer.supplier == supplier,
        )
    )
    if offer_existing is not None:
        existing_offers[cache_key] = offer_existing
    return offer_existing, False


def _ensure_offer(
    db: Session,
    product_id: int,
    offer_input: OfferInput,
    existing_offers: dict[tuple[int, str], SupplierOffer],
    cache_key: tuple[int, str],
    offer_existing: SupplierOffer | None,
    stats: IngestStats,
) -> tuple[IngestStats, SupplierOffer | None, bool]:
    if offer_existing is not None:
        return stats, offer_existing, False
    return _create_or_recover_offer(
        db, product_id, offer_input, existing_offers, cache_key, stats
    )


def _create_or_recover_offer(
    db: Session,
    product_id: int,
    offer_input: OfferInput,
    existing_offers: dict[tuple[int, str], SupplierOffer],
    cache_key: tuple[int, str],
    stats: IngestStats,
) -> tuple[IngestStats, SupplierOffer | None, bool]:
    created_stats, created_offer = _try_create_offer(
        db,
        product_id=product_id,
        offer_input=offer_input,
        existing_offers=existing_offers,
        cache_key=cache_key,
        stats=stats,
    )
    if created_offer is not None:
        return created_stats, created_offer, True
    recovered = _recover_offer_after_integrity_error(
        db,
        product_id=product_id,
        supplier=offer_input.supplier,
    )
    if recovered is None:
        return _increment_offer_skipped(stats), None, False
    existing_offers[cache_key] = recovered
    return stats, recovered, False


def _try_create_offer(
    db: Session,
    *,
    product_id: int,
    offer_input: OfferInput,
    existing_offers: dict[tuple[int, str], SupplierOffer],
    cache_key: tuple[int, str],
    stats: IngestStats,
) -> tuple[IngestStats, SupplierOffer | None]:
    try:
        with db.begin_nested():
            offer = SupplierOffer(
                product_id=product_id,
                supplier=offer_input.supplier,
                price=offer_input.price,
                in_stock=offer_input.in_stock,
                lead_time_days=offer_input.lead_time_days,
            )
            db.add(offer)
            db.flush()
            existing_offers[cache_key] = offer
            updated_stats = IngestStats(
                products_new=stats.products_new,
                products_updated=stats.products_updated,
                offers_upserted=stats.offers_upserted + 1,
                offers_skipped=stats.offers_skipped,
            )
            return updated_stats, offer
    except IntegrityError:
        return stats, None


def _recover_offer_after_integrity_error(
    db: Session,
    *,
    product_id: int,
    supplier: str,
) -> SupplierOffer | None:
    return db.scalar(
        select(SupplierOffer).where(
            SupplierOffer.product_id == product_id,
            SupplierOffer.supplier == supplier,
        )
    )


def _update_offer_and_history(
    db: Session,
    offer_existing: SupplierOffer,
    offer_input: OfferInput,
    is_new_offer: bool,
    is_from_current_batch: bool,
    stats: IngestStats,
) -> IngestStats:
    if not is_new_offer:
        if offer_existing.price != offer_input.price and not is_from_current_batch:
            if offer_existing.id is not None:
                db.add(
                    PriceHistory(
                        offer_id=offer_existing.id,
                        price=offer_input.price,
                        source_hash=None,
                    )
                )
        offer_existing.price = offer_input.price
        offer_existing.in_stock = offer_input.in_stock
        offer_existing.lead_time_days = offer_input.lead_time_days
    if is_new_offer:
        return stats
    return IngestStats(
        products_new=stats.products_new,
        products_updated=stats.products_updated,
        offers_upserted=stats.offers_upserted + 1,
        offers_skipped=stats.offers_skipped,
    )


def _upsert_pn_mapping(db: Session, product: Product, offer: OfferInput) -> None:
    dealer_code = _dealer_code_from_offer(offer)
    if not dealer_code:
        return
    maker_norm = normalize_pn(product.mpn)
    dealer_norm = normalize_pn(dealer_code)
    row = _find_pn_mapping(db, offer.supplier, dealer_norm)
    if row:
        row.product_id = int(product.id)
        row.maker_pn_norm = maker_norm
    else:
        _insert_or_update_pn_mapping(
            db,
            product_id=int(product.id),
            dealer=offer.supplier,
            maker_norm=maker_norm,
            dealer_norm=dealer_norm,
        )


def _dealer_code_from_offer(offer: OfferInput) -> str | None:
    extra = offer.extra or {}
    if not isinstance(extra, dict):
        return None
    dealer_code_raw = extra.get("dealer_pn")
    if dealer_code_raw is None:
        return None
    text = str(dealer_code_raw).strip()
    return text or None


def _find_pn_mapping(
    db: Session,
    dealer: str,
    dealer_norm: str,
) -> PNMapping | None:
    return db.scalar(
        select(PNMapping).where(
            PNMapping.dealer == dealer, PNMapping.dealer_pn_norm == dealer_norm
        )
    )


def _insert_or_update_pn_mapping(
    db: Session,
    *,
    product_id: int,
    dealer: str,
    maker_norm: str,
    dealer_norm: str,
) -> None:
    try:
        with db.begin_nested():
            db.add(
                PNMapping(
                    product_id=product_id,
                    dealer=dealer,
                    maker_pn_norm=maker_norm,
                    dealer_pn_norm=dealer_norm,
                    confidence=1.0,
                )
            )
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(PNMapping).where(
                PNMapping.dealer == dealer, PNMapping.dealer_pn_norm == dealer_norm
            )
        )
        if existing:
            existing.product_id = product_id
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
