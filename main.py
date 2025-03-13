"""
Script principal pour la surveillance des prix POLS
"""
import time
import logging
import os
from datetime import datetime
import asyncio
from kucoin_exchange import KucoinExchange
from pancakeswap_exchange import PancakeSwapExchange
from telegram_notifier import TelegramNotifier
from dotenv import load_dotenv

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Configuration globale
POLS_QUANTITY = 1000  # Quantité de POLS pour les calculs d'arbitrage

def print_exchange_info(exchange_name: str, price_info, balance_info):
    """Affiche les informations d'un exchange"""
    logging.info(f"\n=== {exchange_name} ===")
    logging.info(f"Prix actuel: {price_info.current_price:.4f} USDT")
    logging.info(f"Prix d'achat ({POLS_QUANTITY} POLS): {price_info.buy_price:.4f} ")
    logging.info(f"Prix de vente ({POLS_QUANTITY} POLS): {price_info.sell_price:.4f} ")
    logging.info("\nSoldes:")
    logging.info(f"POLS disponible: {balance_info.pols_free:.4f}")
    logging.info(f"POLS bloqué: {balance_info.pols_locked:.4f}")
    logging.info(f"USDT disponible: {balance_info.usdt_free:.2f}")
    logging.info(f"USDT bloqué: {balance_info.usdt_locked:.2f}")

def calculate_arbitrage_gains(kucoin: KucoinExchange, pancakeswap: PancakeSwapExchange):
    """Calcule les gains d'arbitrage détaillés"""
    kucoin_info = kucoin.get_price_info()
    pancakeswap_info = pancakeswap.get_price_info()
    
    # Frais de transaction estimés
    KUCOIN_FEE = 0.001  # 0.1%
    PANCAKESWAP_FEE = 0.0025  # 0.25%
    BSC_TRANSFER_FEE = 0.001  # 0.1% pour le transfert BSC
    
    # KuCoin -> PancakeSwap
    # 1. Acheter sur KuCoin
    kucoin_buy_cost = kucoin_info.buy_cost * (1 + KUCOIN_FEE)
    # 2. Transferer vers BSC (perte de 0.1%)
    pols_after_transfer = POLS_QUANTITY * (1 - BSC_TRANSFER_FEE)
    # 3. Vendre sur PancakeSwap
    pancakeswap_sell_revenue = pols_after_transfer * pancakeswap_info.sell_price * (1 - PANCAKESWAP_FEE)
    kucoin_to_pancakeswap_profit = pancakeswap_sell_revenue - kucoin_buy_cost
    
    # PancakeSwap -> KuCoin
    # 1. Acheter sur PancakeSwap
    pancakeswap_buy_cost = pancakeswap_info.buy_cost * (1 + PANCAKESWAP_FEE)
    # 2. Transferer vers KuCoin (perte de 0.1%)
    pols_after_transfer = POLS_QUANTITY * (1 - BSC_TRANSFER_FEE)
    # 3. Vendre sur KuCoin
    kucoin_sell_revenue = pols_after_transfer * kucoin_info.sell_price * (1 - KUCOIN_FEE)
    pancakeswap_to_kucoin_profit = kucoin_sell_revenue - pancakeswap_buy_cost
    
    return {
        'kucoin_to_pancakeswap': {
            'profit': kucoin_to_pancakeswap_profit,
            'profit_percentage': (kucoin_to_pancakeswap_profit / kucoin_buy_cost) * 100,
            'steps': [
                f"Achat sur KuCoin: {kucoin_info.buy_cost:.2f} USDT",
                f"Frais KuCoin: {kucoin_info.buy_cost * KUCOIN_FEE:.2f} USDT",
                f"Transfert BSC: -{BSC_TRANSFER_FEE * 100:.1f}%",
                f"Vente sur PancakeSwap: {pancakeswap_sell_revenue:.2f} USDT",
                f"Frais PancakeSwap: {pols_after_transfer * pancakeswap_info.sell_price * PANCAKESWAP_FEE:.2f} USDT",
                f"Profit final: {kucoin_to_pancakeswap_profit:.2f} USDT ({kucoin_to_pancakeswap_profit/kucoin_buy_cost*100:.2f}%)"
            ]
        },
        'pancakeswap_to_kucoin': {
            'profit': pancakeswap_to_kucoin_profit,
            'profit_percentage': (pancakeswap_to_kucoin_profit / pancakeswap_buy_cost) * 100,
            'steps': [
                f"Achat sur PancakeSwap: {pancakeswap_info.buy_cost:.2f} USDT",
                f"Frais PancakeSwap: {pancakeswap_info.buy_cost * PANCAKESWAP_FEE:.2f} USDT",
                f"Transfert BSC: -{BSC_TRANSFER_FEE * 100:.1f}%",
                f"Vente sur KuCoin: {kucoin_sell_revenue:.2f} USDT",
                f"Frais KuCoin: {pols_after_transfer * kucoin_info.sell_price * KUCOIN_FEE:.2f} USDT",
                f"Profit final: {pancakeswap_to_kucoin_profit:.2f} USDT ({pancakeswap_to_kucoin_profit/pancakeswap_buy_cost*100:.2f}%)"
            ]
        }
    }

async def main():
    """Fonction principale"""
    try:
        # Initialiser les exchanges et Telegram
        kucoin = KucoinExchange(pols_quantity=POLS_QUANTITY)
        pancakeswap = PancakeSwapExchange(pols_quantity=POLS_QUANTITY)
        telegram = TelegramNotifier(pols_quantity=POLS_QUANTITY)
        
        # Initialiser le bot de manière asynchrone
        await telegram.initialize()
        
        logging.info("Démarrage de la surveillance des prix POLS...")
        await telegram.send_message("🚀 Démarrage de la surveillance des prix POLS...")
        
        # Stocker les instances des exchanges dans les données du bot
        telegram.app.bot_data['kucoin'] = kucoin
        telegram.app.bot_data['pancakeswap'] = pancakeswap
        
        # Démarrer le bot Telegram en mode polling
        await telegram.app.initialize()
        await telegram.app.start()
        await telegram.app.updater.start_polling()
        
        last_notification_time = time.time()
        
        while True:
            try:
                # KuCoin
                kucoin_price = kucoin.get_price_info()
                kucoin_balance = kucoin.get_balance()
                print_exchange_info("KuCoin", kucoin_price, kucoin_balance)
                
                # PancakeSwap
                pancake_price = pancakeswap.get_price_info()
                pancake_balance = pancakeswap.get_balance()
                print_exchange_info("PancakeSwap", pancake_price, pancake_balance)
                
                # Calculer les opportunités d'arbitrage
                arbitrage_gains = await telegram._calculate_arbitrage_gains(kucoin, pancakeswap)
                
                logging.info("\n=== Opportunités d'arbitrage détaillées ===")
                logging.info("\nKuCoin -> PancakeSwap:")
                for step in arbitrage_gains['kucoin_to_pancakeswap']['steps']:
                    logging.info(step)
                logging.info(f"\nPancakeSwap -> KuCoin:")
                for step in arbitrage_gains['pancakeswap_to_kucoin']['steps']:
                    logging.info(step)
                
                # Envoyer une notification Telegram toutes les 30 minutes
                current_time = time.time()
                # Envoyer un rapport complet toutes les 30 minutes
                # if current_time - last_notification_time > 60 * 30:  # 30 minutes
                #     await telegram.send_full_report(kucoin, pancakeswap)
                #     last_notification_time = current_time
                
                # Attendre 1 minute
                await asyncio.sleep(60)
                
            except Exception as e:
                error_msg = f"❌ Erreur pendant la surveillance: {str(e)}"
                logging.error(error_msg)
                await telegram.send_message(error_msg)
                await asyncio.sleep(60)  # Attendre 1 minute avant de réessayer
                
    except KeyboardInterrupt:
        logging.info("\nArrêt de la surveillance...")
        await telegram.send_message("🛑 Arrêt de la surveillance des prix POLS")
        # Arrêter proprement le bot Telegram
        if telegram.app:
            await telegram.app.updater.stop()
            await telegram.app.stop()
    except Exception as e:
        error_msg = f"❌ Erreur fatale: {str(e)}"
        logging.error(error_msg)
        await telegram.send_message(error_msg)
        # Arrêter proprement le bot Telegram
        if telegram.app:
            await telegram.app.updater.stop()
            await telegram.app.stop()

if __name__ == "__main__":
    asyncio.run(main()) 