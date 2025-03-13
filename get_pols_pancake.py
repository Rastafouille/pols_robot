"""
Script pour obtenir le prix spot de POLS et les soldes POLS/USDT sur PancakeSwap
"""

import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from web3 import Web3
import json
import requests
from decimal import Decimal
import time

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Adresses des contrats
PANCAKE_ROUTER_ADDRESS = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
PANCAKE_FACTORY_ADDRESS = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
POLS_ADDRESS = "0x7e624FA0E1c4AbFD309cC15719b7E2580887f570"  # POLS sur BSC
USDT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"  # USDT sur BSC
BSC_RPC = "https://bsc-dataseed.binance.org/"
BSCSCAN_API_ENDPOINT = "https://api.bscscan.com/api"

# ABI minimal du routeur PancakeSwap
ROUTER_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "address[]", "name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [
            {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# ABI minimal pour les tokens ERC20
ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ABI minimal pour la paire PancakeSwap
PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "_reserve0", "type": "uint112"},
            {"name": "_reserve1", "type": "uint112"},
            {"name": "_blockTimestampLast", "type": "uint32"}
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function"
    }
]

def load_env_file():
    """Charge et vérifie les variables d'environnement"""
    env_path = Path('.') / '.env'
    if not env_path.exists():
        logging.error("Le fichier .env n'existe pas. Création d'un modèle...")
        with open(env_path, 'w') as f:
            f.write("BSC_WALLET_ADDRESS=votre_adresse_portefeuille_ici\n")
            f.write("BSCSCAN_API_KEY=votre_api_key_bscscan_ici\n")
        raise ValueError("Veuillez configurer vos informations dans le fichier .env")

    load_dotenv()
    
    required_vars = ["BSC_WALLET_ADDRESS", "BSCSCAN_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")

def get_pair_address(web3, factory_contract, token0, token1):
    """Obtient l'adresse de la paire de trading"""
    try:
        # Appel à getPair sur le contrat factory
        pair_address = factory_contract.functions.getPair(token0, token1).call()
        return pair_address
    except Exception as e:
        logging.error(f"Erreur lors de la récupération de l'adresse de la paire: {e}")
        return None

def get_reserves(web3, pair_contract):
    """Obtient les réserves de la paire de trading"""
    try:
        reserves = pair_contract.functions.getReserves().call()
        return reserves
    except Exception as e:
        logging.error(f"Erreur lors de la récupération des réserves: {e}")
        return None

def calculate_average_price(orders, amount_target, is_buy=True):
    """Calcule le prix moyen pour un montant donné"""
    amount_filled = 0
    total_cost = 0
    
    for order in orders:
        price = float(order[0])
        available = float(order[1])
        
        if amount_filled + available <= amount_target:
            # Prendre tout le volume disponible
            amount_filled += available
            total_cost += available * price
        else:
            # Prendre seulement ce dont on a besoin
            remaining = amount_target - amount_filled
            amount_filled += remaining
            total_cost += remaining * price
            break
            
        if amount_filled >= amount_target:
            break
    
    if amount_filled == 0:
        return None
        
    average_price = total_cost / amount_filled
    slippage = ((average_price / orders[0][0]) - 1) * 100 if is_buy else ((orders[0][0] / average_price) - 1) * 100
    
    return {
        "average_price": average_price,
        "total_cost": total_cost,
        "amount_filled": amount_filled,
        "slippage": slippage
    }

def get_order_book(web3, router_contract, pair_contract, token0_decimals=18, token1_decimals=18, depth=20):
    """Simule un carnet d'ordres à partir des réserves de la pool"""
    try:
        # Obtenir le prix réel via getAmountsOut
        current_price = get_token_price(web3, router_contract)
        if not current_price:
            return None

        # Simuler des ordres autour du prix actuel
        bids = []  # Ordres d'achat
        asks = []  # Ordres de vente
        
        # Base volume (plus réaliste)
        base_volume = 1000  # Volume de base de 1000 POLS
        
        # Créer des ordres simulés avec des volumes plus réalistes
        for i in range(depth):
            # Variation de prix de 0.1% par niveau
            price_step = 0.001
            
            # Ordres de vente (asks) - prix plus élevés
            price_up = current_price * (1 + (i + 1) * price_step)
            # Volume décroissant avec le prix
            volume_up = base_volume / (1 + i * 0.2)
            asks.append([price_up, volume_up])
            
            # Ordres d'achat (bids) - prix plus bas
            price_down = current_price * (1 - (i + 1) * price_step)
            # Volume croissant quand le prix baisse
            volume_down = base_volume * (1 + i * 0.1)
            bids.append([price_down, volume_down])

        # Trier les ordres
        bids.sort(key=lambda x: x[0], reverse=True)
        asks.sort(key=lambda x: x[0])

        # Calculer les prix moyens pour 1000 POLS
        target_amount = 1000
        buy_info = calculate_average_price(asks, target_amount, True)
        sell_info = calculate_average_price(bids, target_amount, False)

        # Afficher le carnet d'ordres
        logging.info(f"\n=== Carnet d'ordres simulé POLS-USDT ===")
        logging.info(f"{'VENTE':^45}")
        logging.info(f"{'Prix':^15} {'Quantité':^15} {'Total USDT':^15}")
        logging.info("-" * 45)
        
        total_ask_volume = 0
        for ask in reversed(asks[:10]):
            prix = float(ask[0])
            quantite = float(ask[1])
            total = prix * quantite
            total_ask_volume += quantite
            logging.info(f"{prix:^15.4f} {quantite:^15.4f} {total:^15.2f}")

        logging.info("\n" + "-" * 45)
        logging.info(f"{'ACHAT':^45}")
        logging.info(f"{'Prix':^15} {'Quantité':^15} {'Total USDT':^15}")
        logging.info("-" * 45)

        total_bid_volume = 0
        for bid in bids[:10]:
            prix = float(bid[0])
            quantite = float(bid[1])
            total = prix * quantite
            total_bid_volume += quantite
            logging.info(f"{prix:^15.4f} {quantite:^15.4f} {total:^15.2f}")

        # Afficher les totaux
        spread = asks[0][0] - bids[0][0]
        spread_percent = (spread / bids[0][0]) * 100
        
        logging.info("\n=== Résumé du carnet d'ordres ===")
        logging.info(f"Volume total en vente: {total_ask_volume:.4f} POLS")
        logging.info(f"Volume total en achat: {total_bid_volume:.4f} POLS")
        logging.info(f"Spread: {spread:.4f} USDT ({spread_percent:.2f}%)")
        logging.info(f"Prix actuel: {current_price:.4f} USDT")

        # Afficher les prix moyens pour 1000 POLS
        logging.info(f"\n=== Simulation pour {target_amount} POLS ===")
        if buy_info:
            logging.info(f"Prix moyen d'achat: {buy_info['average_price']:.4f} USDT")
            logging.info(f"Coût total d'achat: {buy_info['total_cost']:.2f} USDT")
            logging.info(f"Slippage à l'achat: {buy_info['slippage']:.2f}%")
        if sell_info:
            logging.info(f"Prix moyen de vente: {sell_info['average_price']:.4f} USDT")
            logging.info(f"Montant total de vente: {sell_info['total_cost']:.2f} USDT")
            logging.info(f"Slippage à la vente: {sell_info['slippage']:.2f}%")

        return {
            "bids": bids,
            "asks": asks,
            "total_bid_volume": total_bid_volume,
            "total_ask_volume": total_ask_volume,
            "spread": spread,
            "spread_percent": spread_percent,
            "current_price": current_price,
            "buy_info": buy_info,
            "sell_info": sell_info
        }

    except Exception as e:
        logging.error(f"Erreur lors de la récupération du carnet d'ordres: {e}")
        return None

def get_historical_trades():
    """Récupère l'historique des transactions de la dernière heure"""
    try:
        api_key = os.getenv("BSCSCAN_API_KEY")
        end_time = int(time.time())
        start_time = end_time - 3600  # 1 heure

        # Paramètres de la requête
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": POLS_ADDRESS,
            "address": PANCAKE_ROUTER_ADDRESS,
            "starttime": start_time,
            "endtime": end_time,
            "sort": "desc",
            "apikey": api_key
        }

        # Faire la requête à l'API BSCScan
        response = requests.get(BSCSCAN_API_ENDPOINT, params=params)
        data = response.json()

        if data["status"] == "1" and data["result"]:
            trades = []
            for tx in data["result"]:
                timestamp = datetime.fromtimestamp(int(tx["timeStamp"]))
                amount = float(tx["value"]) / (10 ** 18)  # 18 décimales pour POLS
                trades.append({
                    "timestamp": timestamp,
                    "amount": amount,
                    "price": 0  # À calculer
                })

            # Trier par timestamp
            trades.sort(key=lambda x: x["timestamp"])

            # Afficher l'historique
            if trades:
                logging.info("\n=== Historique des transactions (1h) ===")
                logging.info(f"{'Heure':^10} {'Quantité':^15} {'Prix':^10}")
                logging.info("-" * 35)
                
                for trade in trades:
                    logging.info(f"{trade['timestamp'].strftime('%H:%M:%S'):^10} "
                               f"{trade['amount']:^15.4f} "
                               f"{trade['price']:^10.4f}")

            return trades

    except Exception as e:
        logging.error(f"Erreur lors de la récupération de l'historique: {e}")
        return None

def get_token_price(web3, router_contract, amount_in=1e18):
    """Obtient le prix de POLS en USDT"""
    try:
        # Chemin de swap POLS -> USDT
        path = [POLS_ADDRESS, USDT_ADDRESS]
        
        # Obtenir les montants
        amounts = router_contract.functions.getAmountsOut(
            int(amount_in),
            path
        ).call()
        
        # Convertir le résultat en USDT (18 décimales pour POLS, 18 pour USDT)
        price = Decimal(amounts[1]) / Decimal(1e18)
        return float(price)
    except Exception as e:
        logging.error(f"Erreur lors de la récupération du prix: {e}")
        return None

def get_token_balance(web3, token_address, wallet_address):
    """Obtient le solde d'un token pour une adresse donnée"""
    try:
        token_contract = web3.eth.contract(address=token_address, abi=ERC20_ABI)
        balance = token_contract.functions.balanceOf(wallet_address).call()
        decimals = token_contract.functions.decimals().call()
        return float(balance) / (10 ** decimals)
    except Exception as e:
        logging.error(f"Erreur lors de la récupération du solde: {e}")
        return 0

def calculate_moving_average(prices, period=5):
    """Calcule la moyenne mobile sur une période donnée"""
    if not prices or len(prices) < period:
        return []
    
    moving_averages = []
    for i in range(len(prices)):
        if i < period - 1:
            moving_averages.append(None)
            continue
            
        window = prices[i-(period-1):i+1]
        average = sum(window) / period
        moving_averages.append(average)
    
    return moving_averages

def get_pols_pancake_info():
    """Obtenir le prix de POLS-USDT et les soldes sur PancakeSwap"""
    try:
        # Charger et vérifier les variables d'environnement
        load_env_file()
        wallet_address = os.getenv("BSC_WALLET_ADDRESS")

        # Initialiser Web3
        web3 = Web3(Web3.HTTPProvider(BSC_RPC))
        if not web3.is_connected():
            raise Exception("Impossible de se connecter à la Binance Smart Chain")

        # Initialiser les contrats
        router_contract = web3.eth.contract(
            address=web3.to_checksum_address(PANCAKE_ROUTER_ADDRESS),
            abi=ROUTER_ABI
        )

        # Obtenir l'adresse de la paire POLS-USDT
        factory_contract = web3.eth.contract(
            address=web3.to_checksum_address(PANCAKE_FACTORY_ADDRESS),
            abi=[{"constant":True,"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"}],"name":"getPair","outputs":[{"internalType":"address","name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"}]
        )
        
        pair_address = get_pair_address(web3, factory_contract, POLS_ADDRESS, USDT_ADDRESS)
        if pair_address:
            pair_contract = web3.eth.contract(address=pair_address, abi=PAIR_ABI)
            
            # Obtenir le carnet d'ordres
            order_book = get_order_book(web3, router_contract, pair_contract)

        # Obtenir l'historique des transactions
        trades = get_historical_trades()

        # Obtenir le prix actuel
        prix_pols = get_token_price(web3, router_contract)
        if prix_pols:
            logging.info(f"\nPrix actuel de POLS sur PancakeSwap: {prix_pols:.4f} USDT")

        # Obtenir les soldes
        solde_pols = get_token_balance(web3, POLS_ADDRESS, wallet_address)
        solde_usdt = get_token_balance(web3, USDT_ADDRESS, wallet_address)

        # Afficher les résultats
        logging.info("\n=== Résumé des soldes ===")
        logging.info(f"POLS disponible: {solde_pols:.4f} POLS")
        if prix_pols:
            logging.info(f"POLS valeur totale: {(solde_pols * prix_pols):.2f} USDT")
        logging.info(f"USDT disponible: {solde_usdt:.2f} USDT")
        
        return {
            "prix_pols": prix_pols,
            "solde_pols": solde_pols,
            "solde_usdt": solde_usdt,
            "order_book": order_book,
            "trades": trades
        }

    except ValueError as ve:
        logging.error(f"Erreur de configuration: {ve}")
        return None
    except Exception as e:
        logging.error(f"Erreur inattendue: {e}")
        return None

if __name__ == "__main__":
    get_pols_pancake_info() 