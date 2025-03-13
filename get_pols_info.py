"""
Script pour obtenir le prix spot de POLS et les soldes POLS/USDT sur Kucoin
"""

import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kucoin_universal_sdk.api.client import DefaultClient
from kucoin_universal_sdk.generate.spot.market import GetTickerReqBuilder, GetKlinesReqBuilder, GetFullOrderBookReqBuilder
from kucoin_universal_sdk.generate.account.account import GetSpotAccountListReqBuilder, GetSpotAccountListReq
from kucoin_universal_sdk.model import ClientOptionBuilder
from kucoin_universal_sdk.model import GLOBAL_API_ENDPOINT
from kucoin_universal_sdk.model import TransportOptionBuilder

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def load_env_file():
    """Charge et vérifie les variables d'environnement"""
    # Vérifier si le fichier .env existe
    env_path = Path('.') / '.env'
    if not env_path.exists():
        logging.error("Le fichier .env n'existe pas. Création d'un modèle...")
        with open(env_path, 'w') as f:
            f.write("KUCOIN_API_KEY=votre_api_key_ici\n")
            f.write("KUCOIN_API_SECRET=votre_api_secret_ici\n")
            f.write("KUCOIN_API_PASSPHRASE=votre_api_passphrase_ici\n")
        raise ValueError("Veuillez configurer vos clés API dans le fichier .env qui vient d'être créé")

    # Charger les variables d'environnement
    load_dotenv()
    
    # Vérifier les variables requises
    required_vars = ["KUCOIN_API_KEY", "KUCOIN_API_SECRET", "KUCOIN_API_PASSPHRASE"]
    missing_vars = [var for var in required_vars if not os.getenv(var) or os.getenv(var) == f"votre_{var.lower()}_ici"]
    
    if missing_vars:
        raise ValueError(f"Variables d'environnement manquantes ou non configurées: {', '.join(missing_vars)}")

def get_price_history(spot_service, symbol="POLS-USDT", interval="1hour", start_time=None, end_time=None):
    """
    Récupère l'historique des prix
    
    Intervalles disponibles:
    - 1min, 3min, 5min, 15min, 30min
    - 1hour, 2hour, 4hour, 6hour, 8hour, 12hour
    - 1day, 1week
    """
    try:
        # Si pas de dates spécifiées, prendre les dernières 24h
        if not start_time:
            start_time = int((datetime.now() - timedelta(days=1)).timestamp())
        if not end_time:
            end_time = int(datetime.now().timestamp())

        klines = spot_service.get_market_api().get_klines(
            GetKlinesReqBuilder()
            .set_symbol(symbol)
            .set_type(interval)
            .set_start_at(start_time)
            .set_end_at(end_time)
            .build()
        )

        # Formater les données
        history = []
        for k in klines:
            history.append({
                'timestamp': datetime.fromtimestamp(k[0]),
                'open': float(k[1]),
                'close': float(k[2]),
                'high': float(k[3]),
                'low': float(k[4]),
                'volume': float(k[5]),
                'turnover': float(k[6])
            })

        # Calculer quelques statistiques
        if history:
            current_price = history[-1]['close']
            start_price = history[0]['open']
            highest_price = max(h['high'] for h in history)
            lowest_price = min(h['low'] for h in history)
            total_volume = sum(h['volume'] for h in history)
            price_change = ((current_price - start_price) / start_price) * 100

            logging.info(f"\n=== Historique des prix {symbol} ===")
            logging.info(f"Période: {datetime.fromtimestamp(start_time)} à {datetime.fromtimestamp(end_time)}")
            logging.info(f"Prix de départ: {start_price:.4f} USDT")
            logging.info(f"Prix actuel: {current_price:.4f} USDT")
            logging.info(f"Variation: {price_change:+.2f}%")
            logging.info(f"Plus haut: {highest_price:.4f} USDT")
            logging.info(f"Plus bas: {lowest_price:.4f} USDT")
            logging.info(f"Volume total: {total_volume:.2f} POLS")

        return history

    except Exception as e:
        logging.error(f"Erreur lors de la récupération de l'historique: {e}")
        return None

def get_last_30min_history(spot_service, symbol="POLS-USDT"):
    """Récupère l'historique des 30 dernières minutes"""
    try:
        # Calculer les timestamps pour les 30 dernières minutes
        end_time = str(int(datetime.now().timestamp()))
        start_time = str(int((datetime.now() - timedelta(minutes=30)).timestamp()))

        response = spot_service.get_market_api().get_klines(
            GetKlinesReqBuilder()
            .set_symbol(symbol)
            .set_type("1min")  # Bougies de 1 minute
            .set_start_at(start_time)
            .set_end_at(end_time)
            .build()
        )

        # Vérifier si la réponse contient des données
        if not response or not hasattr(response, 'data'):
            logging.error("Pas de données historiques disponibles")
            return None

        # Formater les données
        history = []
        for k in response.data:
            try:
                timestamp = int(k[0])
                prix = float(k[2])
                volume = float(k[5])
                
                history.append({
                    'timestamp': datetime.fromtimestamp(timestamp).strftime('%H:%M:%S'),
                    'prix': prix,
                    'volume': volume
                })
            except (ValueError, IndexError) as e:
                logging.warning(f"Erreur lors du traitement d'une donnée: {e}")
                continue

        # Afficher les résultats de manière plus lisible
        if history:
            logging.info("\n=== Historique des 30 dernières minutes ===")
            logging.info(f"{'Heure':^10} {'Prix':^10} {'Volume':^10}")
            logging.info("-" * 32)
            
            for h in history:
                logging.info(f"{h['timestamp']:^10} {h['prix']:<10.4f} {h['volume']:>10.2f}")

            # Calculer les statistiques
            prix_debut = history[0]['prix']
            prix_fin = history[-1]['prix']
            variation = ((prix_fin - prix_debut) / prix_debut) * 100
            volume_total = sum(h['volume'] for h in history)
            prix_max = max(h['prix'] for h in history)
            prix_min = min(h['prix'] for h in history)

            logging.info("\n=== Résumé des 30 dernières minutes ===")
            logging.info(f"Prix de début: {prix_debut:.4f} USDT")
            logging.info(f"Prix de fin: {prix_fin:.4f} USDT")
            logging.info(f"Variation: {variation:+.2f}%")
            logging.info(f"Prix le plus haut: {prix_max:.4f} USDT")
            logging.info(f"Prix le plus bas: {prix_min:.4f} USDT")
            logging.info(f"Volume total: {volume_total:.2f} POLS")

        return history

    except Exception as e:
        logging.error(f"Erreur lors de la récupération de l'historique: {e}")
        logging.debug("Détails de l'erreur:", exc_info=True)
        return None

def calculate_moving_average(history, period=5):
    """Calcule la moyenne mobile sur une période donnée"""
    if not history or len(history) < period:
        return []
    
    moving_averages = []
    for i in range(len(history)):
        if i < period - 1:
            moving_averages.append(None)
            continue
            
        window = history[i-(period-1):i+1]
        average = sum(float(candle['close']) for candle in window) / period
        moving_averages.append(average)
    
    return moving_averages

def get_last_hour_history(spot_service, symbol="POLS-USDT"):
    """Récupère l'historique de la dernière heure en bougies de 5 minutes"""
    try:
        # Calculer les timestamps pour la dernière heure
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(hours=1)).timestamp())

        response = spot_service.get_market_api().get_klines(
            GetKlinesReqBuilder()
            .set_symbol(symbol)
            .set_type("5min")  # Bougies de 5 minutes
            .set_start_at(str(start_time))
            .set_end_at(str(end_time))
            .build()
        )

        # Vérifier si la réponse contient des données
        if not response or not hasattr(response, 'data'):
            logging.error("Pas de données historiques disponibles")
            return None

        # Formater les données
        history = []
        for k in response.data:
            try:
                timestamp = int(k[0])
                open_price = float(k[1])
                close_price = float(k[2])
                high_price = float(k[3])
                low_price = float(k[4])
                volume = float(k[5])
                
                history.append({
                    'timestamp': datetime.fromtimestamp(timestamp).strftime('%H:%M'),
                    'open': open_price,
                    'close': close_price,
                    'high': high_price,
                    'low': low_price,
                    'volume': volume
                })
            except (ValueError, IndexError) as e:
                logging.warning(f"Erreur lors du traitement d'une donnée: {e}")
                continue

        # Calculer la moyenne mobile sur 5 périodes
        moving_averages = calculate_moving_average(history, 5)

        # Afficher les résultats de manière plus lisible
        if history:
            logging.info("\n=== Historique de la dernière heure (5min) ===")
            logging.info(f"{'Heure':^8} {'Open':^10} {'High':^10} {'Low':^10} {'Close':^10} {'MM5':^10} {'Volume':^10}")
            logging.info("-" * 72)
            
            for i, h in enumerate(history):
                ma = moving_averages[i]
                ma_str = f"{ma:.4f}" if ma is not None else "    -   "
                logging.info(f"{h['timestamp']:^8} {h['open']:<10.4f} {h['high']:<10.4f} {h['low']:<10.4f} {h['close']:<10.4f} {ma_str:^10} {h['volume']:>10.2f}")

            # Calculer les statistiques
            prix_debut = history[0]['open']
            prix_fin = history[-1]['close']
            variation = ((prix_fin - prix_debut) / prix_debut) * 100
            volume_total = sum(h['volume'] for h in history)
            prix_max = max(h['high'] for h in history)
            prix_min = min(h['low'] for h in history)

            logging.info("\n=== Résumé de la dernière heure ===")
            logging.info(f"Prix de début: {prix_debut:.4f} USDT")
            logging.info(f"Prix de fin: {prix_fin:.4f} USDT")
            logging.info(f"Variation: {variation:+.2f}%")
            logging.info(f"Plus haut: {prix_max:.4f} USDT")
            logging.info(f"Plus bas: {prix_min:.4f} USDT")
            logging.info(f"Volume total: {volume_total:.2f} POLS")
            
            # Afficher la dernière moyenne mobile
            last_ma = next((ma for ma in reversed(moving_averages) if ma is not None), None)
            if last_ma:
                logging.info(f"Dernière MM5: {last_ma:.4f} USDT")

        return history

    except Exception as e:
        logging.error(f"Erreur lors de la récupération de l'historique: {e}")
        logging.debug("Détails de l'erreur:", exc_info=True)
        return None

def get_order_book(spot_service, symbol="POLS-USDT", limit=20):
    """Récupère le carnet d'ordres"""
    try:
        order_book = spot_service.get_market_api().get_full_order_book(
            GetFullOrderBookReqBuilder()
            .set_symbol(symbol)
            .build()
        )

        if not order_book or not hasattr(order_book, 'data'):
            logging.error("Pas de données de carnet d'ordres disponibles")
            return None

        # Extraire les ordres d'achat et de vente
        bids = order_book.data.get('bids', [])[:limit]  # Ordres d'achat
        asks = order_book.data.get('asks', [])[:limit]  # Ordres de vente

        if not bids or not asks:
            logging.error("Carnet d'ordres vide")
            return None

        # Afficher le carnet d'ordres
        logging.info(f"\n=== Carnet d'ordres {symbol} ===")
        logging.info(f"{'VENTE':^45}")
        logging.info(f"{'Prix':^15} {'Quantité':^15} {'Total USDT':^15}")
        logging.info("-" * 45)
        
        total_ask_volume = 0
        for ask in reversed(asks):
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
        for bid in bids:
            prix = float(bid[0])
            quantite = float(bid[1])
            total = prix * quantite
            total_bid_volume += quantite
            logging.info(f"{prix:^15.4f} {quantite:^15.4f} {total:^15.2f}")

        # Afficher les totaux
        logging.info("\n=== Résumé du carnet d'ordres ===")
        logging.info(f"Volume total en vente: {total_ask_volume:.4f} POLS")
        logging.info(f"Volume total en achat: {total_bid_volume:.4f} POLS")
        
        spread = float(asks[0][0]) - float(bids[0][0])
        spread_percent = (spread / float(bids[0][0])) * 100
        logging.info(f"Spread: {spread:.4f} USDT ({spread_percent:.2f}%)")

        # Afficher l'horodatage du carnet d'ordres
        if hasattr(order_book.data, 'time'):
            timestamp = datetime.fromtimestamp(order_book.data.time / 1000)
            logging.info(f"Horodatage: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        return {
            "bids": bids,
            "asks": asks,
            "total_bid_volume": total_bid_volume,
            "total_ask_volume": total_ask_volume,
            "spread": spread,
            "spread_percent": spread_percent,
            "timestamp": order_book.data.get('time')
        }

    except Exception as e:
        logging.error(f"Erreur lors de la récupération du carnet d'ordres: {e}")
        logging.debug("Détails de l'erreur:", exc_info=True)
        return None

def get_pols_info():
    """Obtenir le prix de POLS-USDT et les soldes"""
    try:
        # Charger et vérifier les variables d'environnement
        load_env_file()
        
        # Configuration du client
        http_transport_option = (
            TransportOptionBuilder()
            .set_keep_alive(True)
            .set_max_pool_size(10)
            .set_max_connection_per_pool(10)
            .build()
        )

        client_option = (
            ClientOptionBuilder()
            .set_key(os.getenv("KUCOIN_API_KEY"))
            .set_secret(os.getenv("KUCOIN_API_SECRET"))
            .set_passphrase(os.getenv("KUCOIN_API_PASSPHRASE"))
            .set_spot_endpoint(GLOBAL_API_ENDPOINT)
            .set_transport_option(http_transport_option)
            .build()
        )
        
        client = DefaultClient(client_option)
        rest_service = client.rest_service()
        spot_service = rest_service.get_spot_service()
        account_service = rest_service.get_account_service()

        # Récupérer le prix POLS actuel
        ticker = spot_service.get_market_api().get_ticker(
            GetTickerReqBuilder().set_symbol("POLS-USDT").build()
        )
        prix_pols = float(ticker.price)
        logging.info(f"\nPrix actuel de POLS: {prix_pols:.4f} USDT")

        # Récupérer le carnet d'ordres
        order_book = get_order_book(spot_service)

        # Récupérer l'historique de la dernière heure en 5min
        history_1h = get_last_hour_history(spot_service)

        # Récupérer les soldes
        accounts = account_service.get_account_api().get_spot_account_list(
            GetSpotAccountListReqBuilder()
            .set_type(GetSpotAccountListReq.TypeEnum.TRADE)
            .build()
        )
        
        solde_pols = 0
        solde_pols_bloque = 0
        solde_usdt = 0
        solde_usdt_bloque = 0
        
        for account in accounts.data:
            if account.currency == "POLS":
                solde_pols = float(account.available)
                solde_pols_bloque = float(account.holds)
            elif account.currency == "USDT":
                solde_usdt = float(account.available)
                solde_usdt_bloque = float(account.holds)

        # Afficher les résultats
        logging.info("\n=== Résumé des soldes ===")
        logging.info(f"POLS disponible: {solde_pols:.4f} POLS")
        logging.info(f"POLS bloqué: {solde_pols_bloque:.4f} POLS")
        logging.info(f"POLS valeur totale: {(solde_pols * prix_pols):.2f} USDT")
        logging.info(f"USDT disponible: {solde_usdt:.2f} USDT")
        logging.info(f"USDT bloqué: {solde_usdt_bloque:.2f} USDT")
        
        return {
            "prix_pols": prix_pols,
            "solde_pols": solde_pols,
            "solde_pols_bloque": solde_pols_bloque,
            "solde_usdt": solde_usdt,
            "solde_usdt_bloque": solde_usdt_bloque,
            "historique_1h": history_1h,
            "order_book": order_book
        }

    except ValueError as ve:
        logging.error(f"Erreur de configuration: {ve}")
        return None
    except Exception as e:
        logging.error(f"Erreur inattendue: {e}")
        return None

if __name__ == "__main__":
    get_pols_info()