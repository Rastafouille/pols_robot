"""
Classe pour l'échange KuCoin
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from kucoin.client import Client
from exchange_base import ExchangeBase, PriceInfo, BalanceInfo

class KucoinExchange(ExchangeBase):
    """Gestion des opérations sur KuCoin"""
    
    def __init__(self, pols_quantity: int = 1000):
        """Initialise l'exchange KuCoin"""
        super().__init__("KuCoin")
        self.pols_quantity = pols_quantity
        self._load_config()
        self._init_client()

    def _load_config(self):
        """Charge la configuration depuis .env"""
        load_dotenv()
        self.api_key = os.getenv("KUCOIN_API_KEY")
        self.api_secret = os.getenv("KUCOIN_API_SECRET")
        self.api_passphrase = os.getenv("KUCOIN_API_PASSPHRASE")
        
        if not all([self.api_key, self.api_secret, self.api_passphrase]):
            raise ValueError("Configuration KuCoin incomplète dans .env")

    def _init_client(self):
        """Initialise le client KuCoin"""
        self.client = Client(self.api_key, self.api_secret, self.api_passphrase)

    def get_price_info(self) -> PriceInfo:
        """Récupère les informations de prix"""
        try:
            # Récupérer le carnet d'ordres
            order_book = self.client.get_order_book("POLS-USDT")
            
            if not order_book or 'bids' not in order_book or 'asks' not in order_book:
                raise Exception("Impossible de récupérer le carnet d'ordres")
            
            # Calculer le prix moyen d'achat pour la quantité demandée
            total_buy_cost = 0
            remaining_quantity = self.pols_quantity
            
            for ask in order_book['asks']:
                price = float(ask[0])
                quantity = float(ask[1])
                
                if remaining_quantity <= 0:
                    break
                    
                if quantity <= remaining_quantity:
                    total_buy_cost += price * quantity
                    remaining_quantity -= quantity
                else:
                    total_buy_cost += price * remaining_quantity
                    remaining_quantity = 0
            
            if remaining_quantity > 0:
                raise Exception(f"Pas assez de liquidité pour acheter {self.pols_quantity} POLS")
            
            # Calculer le prix moyen de vente pour la quantité demandée
            total_sell_revenue = 0
            remaining_quantity = self.pols_quantity
            
            for bid in order_book['bids']:
                price = float(bid[0])
                quantity = float(bid[1])
                
                if remaining_quantity <= 0:
                    break
                    
                if quantity <= remaining_quantity:
                    total_sell_revenue += price * quantity
                    remaining_quantity -= quantity
                else:
                    total_sell_revenue += price * remaining_quantity
                    remaining_quantity = 0
            
            if remaining_quantity > 0:
                raise Exception(f"Pas assez de liquidité pour vendre {self.pols_quantity} POLS")
            
            # Calculer les prix moyens
            current_price = float(order_book['asks'][0][0])  # Prix spot
            buy_price = total_buy_cost / self.pols_quantity
            sell_price = total_sell_revenue / self.pols_quantity
            
            return PriceInfo(
                current_price=current_price,
                buy_price=buy_price,
                sell_price=sell_price,
                buy_cost=total_buy_cost,
                sell_revenue=total_sell_revenue,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des prix KuCoin: {e}")
            raise

    def get_balance(self) -> BalanceInfo:
        """Récupère les soldes du compte"""
        try:
            # Récupérer les soldes
            accounts = self.client.get_accounts()
            
            # Trouver les comptes POLS et USDT
            pols_account = next((acc for acc in accounts if acc["currency"] == "POLS"), None)
            usdt_account = next((acc for acc in accounts if acc["currency"] == "USDT"), None)
            
            # Récupérer les soldes avec les bons noms de champs
            pols_free = float(pols_account["available"]) if pols_account else 0
            pols_locked = float(pols_account["holds"]) if pols_account else 0
            usdt_free = float(usdt_account["available"]) if usdt_account else 0
            usdt_locked = float(usdt_account["holds"]) if usdt_account else 0
            
            # Calculer la valeur totale en USDT
            pols_value_usdt = pols_free * self.get_price_info().current_price
            
            return BalanceInfo(
                pols_free=pols_free,
                pols_locked=pols_locked,
                usdt_free=usdt_free,
                usdt_locked=usdt_locked,
                pols_value_usdt=pols_value_usdt
            )
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des soldes KuCoin: {e}")
            raise

    def create_market_buy_order(self, amount: int) -> str:
        """Crée un ordre d'achat au marché sur KuCoin
        
        Args:
            amount (int): Quantité de POLS à acheter
            
        Returns:
            str: ID de l'ordre d'achat
            
        Raises:
            Exception: Si l'achat échoue
        """
        try:
            # Vérifier le solde USDT disponible
            balance = self.get_balance()
            price_info = self.get_price_info()
            cost = amount * price_info.buy_price * 1.001  # Prix + 0.1% de frais
            
            if balance.usdt_free < cost:
                raise ValueError(f"Solde USDT insuffisant: {balance.usdt_free:.2f} USDT requis: {cost:.2f} USDT")
            
            # Créer l'ordre d'achat
            order = self.client.create_market_order(
                symbol='POLS-USDT',
                side='buy',
                size=amount
            )
            
            if order:
                logging.info(f"Achat de {amount} POLS effectué avec succès. Order ID: {order['orderId']}")
                return order['orderId']
            else:
                raise Exception("La création de l'ordre a échoué")
                
        except Exception as e:
            logging.error(f"Erreur lors de l'achat sur KuCoin: {e}")
            raise 

    def create_limit_order(self, symbol: str, side: str, size: float, price: float) -> dict:
        """Crée un ordre limit
        
        Args:
            symbol (str): Paire de trading (ex: 'POLS-USDT')
            side (str): 'buy' ou 'sell'
            size (float): Quantité à trader
            price (float): Prix de l'ordre
            
        Returns:
            dict: Réponse de l'API contenant les détails de l'ordre
        """
        try:
            # Vérifier le solde disponible
            balance = self.get_balance()
            if side == 'sell' and balance.pols_free < size:
                raise ValueError(f"Solde POLS insuffisant: {balance.pols_free:.4f} < {size:.4f}")
            elif side == 'buy' and balance.usdt_free < size * price:
                raise ValueError(f"Solde USDT insuffisant: {balance.usdt_free:.2f} < {size * price:.2f}")
            
            # Formater le prix avec exactement 4 décimales
            formatted_price = f"{price:.4f}"
            
            # Créer l'ordre
            order = self.client.create_limit_order(
                symbol=symbol,
                side=side,
                size=str(size),
                price=formatted_price
            )
            
            logging.info(f"Ordre limit créé: {side} {size:.4f} {symbol} @ {formatted_price}")
            return order
            
        except Exception as e:
            logging.error(f"Erreur lors de la création de l'ordre limit: {e}")
            raise
    
    def cancel_order(self, order_id: str) -> bool:
        """Annule un ordre
        
        Args:
            order_id (str): ID de l'ordre à annuler
            
        Returns:
            bool: True si l'ordre a été annulé avec succès
        """
        try:
            self.client.cancel_order(order_id)
            logging.info(f"Ordre {order_id} annulé avec succès")
            return True
            
        except Exception as e:
            logging.error(f"Erreur lors de l'annulation de l'ordre {order_id}: {e}")
            return False
    
    def get_order(self, order_id: str) -> dict:
        """Récupère les détails d'un ordre
        
        Args:
            order_id (str): ID de l'ordre
            
        Returns:
            dict: Détails de l'ordre
        """
        try:
            return self.client.get_order_details(order_id)
            
        except Exception as e:
            logging.error(f"Erreur lors de la récupération de l'ordre {order_id}: {e}")
            raise