"""Model pricing catalog.

Cost accounting must never depend on prices hardcoded in Python business
logic. Prices live in a data file (config/model_pricing.json) and are loaded
into a PricingCatalog; business code asks the catalog for the applicable rate.

Reference: the goal explicitly forbids a Python pricing table in the routing
path; the catalog keeps the same information as *data* with provenance and
effective dates so it can be updated without a code change.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROTOCOL_VERSION: str = "1.0"

DEFAULT_PRICING_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "model_pricing.json"


@dataclass(frozen=True)
class ModelPricing:
    """Price of one model, effective from a given date.

    All prices are per 1M tokens unless a *_per_1k flag says otherwise.
    """

    provider: str
    model: str
    input_price: float = 0.0
    output_price: float = 0.0
    cached_input_price: float | None = None
    reasoning_price: float | None = None
    currency: str = "USD"
    effective_from: str = "1970-01-01"
    source: str = "manual"

    def is_effective(self, on: date) -> bool:
        try:
            return date.fromisoformat(self.effective_from) <= on
        except ValueError:
            return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _TokenRates:
    """Resolved per-1K-token rates for a single call."""

    input_price: float = 0.0
    output_price: float = 0.0


class PricingCatalog:
    """Resolves the applicable price for a model.

    Entries are keyed by model id; the most recent effective entry wins.
    Unknown models resolve to a zero-rate entry rather than raising, so cost
    accounting degrades to "cost unknown" instead of breaking a run.
    """

    protocol_version: str = PROTOCOL_VERSION

    def __init__(self, entries: list[ModelPricing] | None = None):
        self._entries: dict[str, list[ModelPricing]] = {}
        for entry in entries or []:
            self.register(entry)

    def register(self, entry: ModelPricing) -> None:
        self._entries.setdefault(entry.model, []).append(entry)
        self._entries[entry.model].sort(key=lambda e: e.effective_from)

    def models(self) -> list[str]:
        return sorted(self._entries)

    def get_pricing(self, model: str, on: date | None = None) -> ModelPricing | None:
        """Return the pricing entry effective on ``on`` (default: today)."""
        candidates = self._entries.get(model)
        if not candidates:
            return None
        today = on or date.today()
        applicable = [e for e in candidates if e.is_effective(today)]
        return applicable[-1] if applicable else candidates[-1]

    def get_rates(self, model: str, on: date | None = None) -> _TokenRates:
        entry = self.get_pricing(model, on)
        if entry is None:
            return _TokenRates()
        return _TokenRates(input_price=entry.input_price, output_price=entry.output_price)

    def cost_for(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Cost of a single call. Prices are per 1M tokens."""
        rates = self.get_rates(model)
        return (input_tokens / 1_000_000.0) * rates.input_price + (
            output_tokens / 1_000_000.0
        ) * rates.output_price

    def to_dict(self) -> dict[str, Any]:
        return {
            "models": {m: [e.to_dict() for e in v] for m, v in self._entries.items()},
            "protocol_version": self.protocol_version,
        }

    @classmethod
    def load_json(cls, path: str | Path) -> "PricingCatalog":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = [ModelPricing(**item) for item in data]
        logger.info("Loaded %d pricing entries from %s", len(entries), path)
        return cls(entries)

    @classmethod
    def default(cls) -> "PricingCatalog":
        """Load the shipped catalog, degrading to an empty catalog on error."""
        try:
            return cls.load_json(DEFAULT_PRICING_PATH)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Pricing catalog unavailable (%s); costs will be 0", exc)
            return cls()


def default_pricing_catalog() -> PricingCatalog:
    """Module-level accessor for the default catalog (lazily loaded)."""
    global _DEFAULT_CATALOG
    if _DEFAULT_CATALOG is None:
        _DEFAULT_CATALOG = PricingCatalog.default()
    return _DEFAULT_CATALOG


_DEFAULT_CATALOG: PricingCatalog | None = None

__all__ = ["ModelPricing", "PricingCatalog", "default_pricing_catalog"]
