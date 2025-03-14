"""
Classe pour la gestion de la stratégie de trading automatique
"""
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from typing import Optional, Tuple

class TradingStrategy:
    """Gestion de la stratégie de trading automatique"""
    
    def __init__(self, kucoin_exchange, telegram_notifier):
        """Initialise la stratégie de trading
        
        Args:
            kucoin_exchange: Instance de KucoinExchange
            telegram_notifier: Instance de TelegramNotifier
        """
        self.kucoin = kucoin_exchange
        self.telegram = telegram_notifier
        self.last_check_time = None
        self.trailing_stop_price = None
        self.trailing_stop_order_id = None
        self.alert_sent = False
        
        # Paramètres de la stratégie
        self.MA_PERIODS = 10  # Périodes pour la moyenne mobile
        self.TIMEFRAME = "5min"  # Timeframe pour les données
        self.PRICE_INCREASE_THRESHOLD = 0.10  # 10% au-dessus de la MM
        self.DROP_THRESHOLD = 0.02  # 2% de baisse pour déclencher l'ordre
        self.LIMIT_ORDER_OFFSET = 0.01  # 1% sous le prix actuel pour l'ordre limit
        self.ORDER_SIZE = 10  # Quantité fixe de POLS pour les ordres
        
        # Historique des prix
        self.price_history = pd.DataFrame(columns=['timestamp', 'price'])
        self.highest_price = None
        self.is_monitoring = False
        
    def update_price_history(self):
        """Met à jour l'historique des prix"""
        try:
            current_price = self.kucoin.get_price_info().current_price
            current_time = datetime.now()
            
            # Ajouter le nouveau prix à l'historique
            self.price_history = self.price_history.append({
                'timestamp': current_time,
                'price': current_price
            }, ignore_index=True)
            
            # Garder uniquement les 100 derniers prix
            if len(self.price_history) > 100:
                self.price_history = self.price_history.tail(100)
                
            return current_price
            
        except Exception as e:
            logging.error(f"Erreur lors de la mise à jour de l'historique des prix: {e}")
            return None
            
    def calculate_ma(self) -> Optional[float]:
        """Calcule la moyenne mobile sur le timeframe 5 minutes"""
        try:
            if len(self.price_history) < self.MA_PERIODS:
                return None
                
            # Calculer la moyenne mobile
            ma = self.price_history['price'].rolling(window=self.MA_PERIODS).mean().iloc[-1]
            return ma
            
        except Exception as e:
            logging.error(f"Erreur lors du calcul de la moyenne mobile: {e}")
            return None
            
    def check_and_update(self):
        """Vérifie et met à jour la stratégie"""
        try:
            current_price = self.update_price_history()
            if current_price is None:
                return
                
            # Si on n'est pas en mode monitoring, vérifier la hausse sur 5 minutes
            if not self.is_monitoring:
                ma = self.calculate_ma()
                if ma is not None:
                    price_increase = (current_price - ma) / ma
                    
                    if price_increase > self.PRICE_INCREASE_THRESHOLD:
                        self.is_monitoring = True
                        self.highest_price = current_price
                        message = (
                            f"🚀 <b>Hausse détectée!</b>\n\n"
                            f"• Prix actuel: {current_price:.4f} USDT\n"
                            f"• Moyenne mobile: {ma:.4f} USDT\n"
                            f"• Hausse: {price_increase*100:.2f}%\n\n"
                            f"Surveillance du prix activée..."
                        )
                        self.telegram.send_message(message)
                        logging.info("Mode monitoring activé")
            
            # Si on est en mode monitoring, vérifier la baisse
            else:
                if current_price > self.highest_price:
                    self.highest_price = current_price
                
                price_drop = (self.highest_price - current_price) / self.highest_price
                
                if price_drop >= self.DROP_THRESHOLD:
                    # Calculer le prix de l'ordre limit (1% sous le prix actuel)
                    limit_price = current_price * (1 - self.LIMIT_ORDER_OFFSET)
                    
                    # Vérifier le solde disponible
                    balance = self.kucoin.get_balance()
                    if balance.pols_free >= self.ORDER_SIZE:
                        # Créer l'ordre limit
                        order = self.kucoin.create_limit_order(
                            symbol='POLS-USDT',
                            side='sell',
                            size=self.ORDER_SIZE,
                            price=limit_price
                        )
                        
                        if order:
                            message = (
                                f"🛑 <b>Ordre limit placé</b>\n\n"
                                f"• Prix actuel: {current_price:.4f} USDT\n"
                                f"• Prix le plus haut: {self.highest_price:.4f} USDT\n"
                                f"• Baisse détectée: {price_drop*100:.2f}%\n"
                                f"• Prix de l'ordre: {limit_price:.4f} USDT\n"
                                f"• Quantité: {self.ORDER_SIZE} POLS\n"
                                f"• Order ID: {order['orderId']}"
                            )
                            self.telegram.send_message(message)
                            logging.info("Ordre limit placé avec succès")
                            
                            # Réinitialiser le monitoring
                            self.is_monitoring = False
                            self.highest_price = None
                        else:
                            logging.error("Échec de la création de l'ordre limit")
                    else:
                        logging.warning(f"Solde insuffisant pour placer l'ordre: {balance.pols_free:.4f} POLS < {self.ORDER_SIZE} POLS")
                
        except Exception as e:
            logging.error(f"Erreur lors de la vérification de la stratégie: {e}")
            self.is_monitoring = False
            self.highest_price = None