from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

from .config import settings


class Base(DeclarativeBase):
    pass


def get_engine():
    engine = create_engine(settings.db_url, echo=False, future=True)

    if settings.db_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-redef]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=5000;")
            cursor.close()

    return engine


SessionLocal = sessionmaker(
    bind=get_engine(), autoflush=False, autocommit=False, future=True
)


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand: Mapped[str] = mapped_column(String(100), index=True)
    mpn: Mapped[str] = mapped_column(String(100), index=True)
    ean: Mapped[str | None] = mapped_column(String(32), unique=False, index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    speed: Mapped[str | None] = mapped_column(String(10))
    brake: Mapped[str | None] = mapped_column(String(20))
    axle: Mapped[str | None] = mapped_column(String(20))
    rotor: Mapped[str | None] = mapped_column(String(20))
    freehub: Mapped[str | None] = mapped_column(String(20))

    offers: Mapped[list[SupplierOffer]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


Index("ix_product_brand_mpn", Product.brand, Product.mpn)


class SupplierOffer(Base):
    __tablename__ = "supplier_offer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"), index=True)
    supplier: Mapped[str] = mapped_column(String(100), index=True)
    price: Mapped[float] = mapped_column(Float)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    extra: Mapped[dict[str, str | int | float | bool | None] | None] = mapped_column(
        JSON, nullable=True
    )

    product: Mapped[Product] = relationship(back_populates="offers")

    __table_args__ = (
        UniqueConstraint("product_id", "supplier", name="uq_offer_product_supplier"),
    )


class EventLog(Base):
    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    type: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[dict[str, str | int | float | bool | None] | None] = mapped_column(
        JSON, nullable=True
    )


def create_all() -> None:
    engine = get_engine()
    # Lightweight migration for SQLite: add missing columns if needed
    if settings.db_url.startswith("sqlite"):
        with engine.connect() as conn:
            try:
                cols = [
                    row[1]
                    for row in conn.exec_driver_sql(
                        "PRAGMA table_info(product)"
                    ).fetchall()
                ]
                if cols and "category" not in cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE product ADD COLUMN category VARCHAR(100)"
                    )
            except Exception:
                pass
    Base.metadata.create_all(engine)


class RawIngest(Base):
    __tablename__ = "raw_ingest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)
    uri: Mapped[str] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    stored_path: Mapped[str] = mapped_column(String(500))


Index("ix_raw_ingest_hash", RawIngest.content_hash)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("supplier_offer.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
