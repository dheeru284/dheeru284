"""The provider contract every market-data source implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..schemas import CandleSeries, DataSource, Instrument, Interval


class UnknownInstrument(LookupError):
    pass


class UnsupportedInterval(ValueError):
    pass


class MarketDataProvider(ABC):
    """Read-only market data. Providers never place, modify or cancel orders."""

    source: DataSource

    @abstractmethod
    def list_instruments(self) -> list[Instrument]: ...

    def get_instrument(self, symbol: str) -> Instrument:
        for instrument in self.list_instruments():
            if instrument.symbol == symbol.upper():
                return instrument
        raise UnknownInstrument(symbol)

    @abstractmethod
    def get_candles(
        self, symbol: str, interval: Interval, start: datetime, end: datetime
    ) -> CandleSeries:
        """Completed candles whose start is >= ``start`` and whose end is <= ``end``."""
