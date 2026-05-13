from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from hot_products.models import ProductSignal


class ProductSource(ABC):
    @abstractmethod
    def collect(self) -> Iterable[ProductSignal]:
        """Collect product signals from one source."""
