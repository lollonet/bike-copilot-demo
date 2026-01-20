"""Helper functions for data CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from pydantic import BaseModel
from sqlalchemy import asc, select

from ..logging_utils import log_exception
from ..models import PNMapping, Product, SessionLocal, SupplierOffer

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# --- Types ---


class ExportRow(BaseModel):
    """Data export row for markdown table rendering."""

    brand: str
    mpn: str
    name: str
    category: str | None = None
    supplier: str
    price: float
    in_stock: bool
    lead_time_days: int | None = None


class AliasEntry(TypedDict, total=False):
    """Single PN alias entry from YAML."""

    maker_pn: str
    dealer_pn: str
    confidence: float


class AliasBlock(TypedDict, total=False):
    """Dealer block with PN aliases from YAML."""

    dealer: str | None
    aliases: list[AliasEntry]


# --- Markdown export helpers ---


def escape_md(text: str) -> str:
    """Escape pipe characters for markdown tables.

    Args:
        text: Text to escape

    Returns:
        Escaped text with pipes replaced
    """
    return text.replace("|", "\\|")


def query_export_rows(
    limit: int | None,
    supplier: str | None,
    brand: str | None,
    category: str | None,
) -> list[
    tuple[SupplierOffer, str, float, bool, int | None, str, str, str, str | None]
]:
    """Query database for export rows with filters.

    Args:
        limit: Maximum number of rows to return
        supplier: Filter by supplier name
        brand: Filter by product brand
        category: Filter by product category

    Returns:
        List of tuples containing offer and product data
    """
    with SessionLocal() as db:
        stmt = (
            select(
                SupplierOffer,
                SupplierOffer.supplier,
                SupplierOffer.price,
                SupplierOffer.in_stock,
                SupplierOffer.lead_time_days,
                Product.brand,
                Product.mpn,
                Product.name,
                Product.category,
            )
            .join(Product, SupplierOffer.product_id == Product.id)
            .order_by(asc(Product.brand), asc(Product.mpn), asc(SupplierOffer.supplier))
        )
        if supplier:
            stmt = stmt.where(SupplierOffer.supplier == supplier)
        if brand:
            stmt = stmt.where(Product.brand == brand)
        if category:
            stmt = stmt.where(Product.category == category)
        if isinstance(limit, int) and limit > 0:
            stmt = stmt.limit(limit)
        rows_raw = db.execute(stmt).all()
        rows = [tuple(r) for r in rows_raw]
    return rows


def build_export_rows(
    rows: list[
        tuple[SupplierOffer, str, float, bool, int | None, str, str, str, str | None]
    ],
) -> list[ExportRow]:
    """Build ExportRow objects from query results.

    Args:
        rows: Raw query result tuples

    Returns:
        List of ExportRow objects
    """
    items: list[ExportRow] = []
    for _offer, sup, price, in_stock, lead, br, mpn, name, cat in rows:
        items.append(
            ExportRow(
                brand=str(br or ""),
                mpn=str(mpn or ""),
                name=str(name or ""),
                category=str(cat) if cat is not None else None,
                supplier=str(sup or ""),
                price=float(price or 0.0),
                in_stock=bool(in_stock),
                lead_time_days=int(lead) if lead is not None else None,
            )
        )
    return items


def render_export_table(items: list[ExportRow]) -> str:
    """Render ExportRow objects as a markdown table.

    Args:
        items: List of export rows

    Returns:
        Markdown table string
    """
    header = "| brand | mpn | name | category | supplier | price | in_stock | lead_time_days |"
    sep = "|---|---|---|---|---|---:|---:|---:|"
    lines: list[str] = [header, sep]
    for it in items:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(it.brand),
                    escape_md(it.mpn),
                    escape_md(it.name),
                    escape_md(it.category or ""),
                    escape_md(it.supplier),
                    f"{it.price:.2f}",
                    ("yes" if it.in_stock else "no"),
                    (str(it.lead_time_days) if it.lead_time_days is not None else ""),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


# --- PN alias import helpers ---


def build_norm_mpn_index(db: Session) -> dict[str, int]:
    """Build a normalized MPN to product ID index.

    Args:
        db: Database session

    Returns:
        Dict mapping normalized MPN to product ID
    """
    from ..pn import normalize_pn

    rows = db.execute(
        select(Product.id, Product.mpn).where(Product.mpn.is_not(None))
    ).all()
    norm_to_product: dict[str, int] = {}
    for pid, mpn in rows:
        try:
            key = normalize_pn(str(mpn))
        except Exception as exc:
            log_exception(
                "cli",
                "pn-normalize",
                "failed to normalize mpn",
                exc,
                extra={"mpn": mpn},
            )
            continue
        if key:
            norm_to_product[key] = int(pid)
    return norm_to_product


def apply_pn_alias_blocks(
    db: Session,
    data: list[AliasBlock],
    norm_to_product: dict[str, int],
) -> tuple[int, int]:
    """Apply PN alias blocks from YAML data.

    Args:
        db: Database session
        data: List of alias blocks from YAML
        norm_to_product: Normalized MPN to product ID mapping

    Returns:
        Tuple of (inserted_count, updated_count)
    """
    from ..pn import normalize_pn

    inserted = 0
    updated = 0
    for block in data:
        dealer = dealer_from_block(block)
        block_inserted, block_updated = apply_aliases_for_block(
            db, dealer, block.get("aliases") or [], norm_to_product, normalize_pn
        )
        inserted += block_inserted
        updated += block_updated
    db.commit()
    return inserted, updated


def dealer_from_block(block: AliasBlock) -> str | None:
    """Extract dealer name from alias block.

    Args:
        block: Alias block from YAML

    Returns:
        Dealer name or None
    """
    dealer_raw = block.get("dealer")
    dealer = str(dealer_raw or "").strip()
    return dealer or None


def apply_aliases_for_block(
    db: Session,
    dealer: str | None,
    aliases: list[AliasEntry],
    norm_to_product: dict[str, int],
    normalize_pn,
) -> tuple[int, int]:
    """Apply aliases for a single dealer block.

    Args:
        db: Database session
        dealer: Dealer name
        aliases: List of alias entries
        norm_to_product: Normalized MPN to product ID mapping
        normalize_pn: PN normalization function

    Returns:
        Tuple of (inserted_count, updated_count)
    """
    inserted = 0
    updated = 0
    for alias in aliases:
        maker_norm, dealer_norm = normalized_alias_codes(alias, normalize_pn)
        if not maker_norm:
            continue
        target_id = norm_to_product.get(maker_norm)
        if not target_id:
            continue
        row = find_existing_alias_row(db, dealer, dealer_norm)
        confidence = alias_confidence(alias)
        if row:
            update_alias_row(row, target_id, maker_norm, confidence)
            updated += 1
        else:
            insert_alias_row(db, dealer, target_id, maker_norm, dealer_norm, confidence)
            inserted += 1
    return inserted, updated


def normalized_alias_codes(alias: AliasEntry, normalize_pn) -> tuple[str, str | None]:
    """Normalize maker and dealer PNs from alias entry.

    Args:
        alias: Alias entry from YAML
        normalize_pn: PN normalization function

    Returns:
        Tuple of (normalized_maker_pn, normalized_dealer_pn)
    """
    maker = normalize_pn(str(alias.get("maker_pn") or ""))
    dealer_pn = str(alias.get("dealer_pn") or "").strip()
    dealer_norm = normalize_pn(dealer_pn) if dealer_pn else None
    return maker, dealer_norm


def find_existing_alias_row(
    db: Session, dealer: str | None, dealer_norm: str | None
) -> PNMapping | None:
    """Find existing PNMapping row for dealer and normalized dealer PN.

    Args:
        db: Database session
        dealer: Dealer name
        dealer_norm: Normalized dealer PN

    Returns:
        Existing PNMapping row or None
    """
    return db.scalar(
        select(PNMapping).where(
            PNMapping.dealer == dealer,
            PNMapping.dealer_pn_norm == dealer_norm,
        )
    )


def alias_confidence(alias: AliasEntry) -> float:
    """Extract confidence score from alias entry.

    Args:
        alias: Alias entry from YAML

    Returns:
        Confidence score (default 1.0)
    """
    conf_raw = alias.get("confidence")
    return float(conf_raw) if conf_raw is not None else 1.0


def update_alias_row(
    row: PNMapping, target_id: int, maker_norm: str, confidence: float
) -> None:
    """Update existing PNMapping row.

    Args:
        row: PNMapping row to update
        target_id: Product ID
        maker_norm: Normalized maker PN
        confidence: Confidence score
    """
    row.product_id = int(target_id)
    row.maker_pn_norm = maker_norm
    row.confidence = confidence


def insert_alias_row(
    db: Session,
    dealer: str | None,
    target_id: int,
    maker_norm: str,
    dealer_norm: str | None,
    confidence: float,
) -> None:
    """Insert new PNMapping row.

    Args:
        db: Database session
        dealer: Dealer name
        target_id: Product ID
        maker_norm: Normalized maker PN
        dealer_norm: Normalized dealer PN
        confidence: Confidence score
    """
    db.add(
        PNMapping(
            product_id=int(target_id),
            dealer=dealer,
            maker_pn_norm=maker_norm,
            dealer_pn_norm=dealer_norm,
            confidence=confidence,
        )
    )
