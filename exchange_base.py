"""
Classe de base pour les échanges
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class PriceInfo:
    """Information sur les prix d'achat/vente"""
    current_price: float
    buy_price: float
    sell_price: float
    buy_cost: float
    sell_revenue: float
    timestamp: str

@dataclass
class BalanceInfo:
    """Information sur les soldes"""
    pols_free: float
    pols_locked: float
    usdt_free: float
    usdt_locked: float
    pols_value_usdt: float

class ExchangeBase(ABC):
    """Classe abstraite de base pour les échanges"""
    
    def __init__(self, name: str):
        self.name = name
        self._last_price_info: Optional[PriceInfo] = None
        self._last_balance: Optional[BalanceInfo] = None

    @abstractmethod
    def get_price_info(self, amount: float = 1000.0) -> PriceInfo:
        """Obtient les informations de prix pour un montant donné"""
        pass

    @abstractmethod
    def get_balance(self) -> BalanceInfo:
        """Obtient les informations de solde"""
        pass

    def __str__(self) -> str:
        return f"Exchange: {self.name}" 