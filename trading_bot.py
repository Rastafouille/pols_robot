"""
Script pour obtenir le prix spot de POLS et les soldes POLS/USDT sur Kucoin
"""

import os
import logging
from dotenv import load_dotenv
from kucoin_universal_sdk.api import DefaultClient
from kucoin_universal_sdk.generate.spot.market import GetTickerReqBuilder
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

def get_pols_info():
    """Obtenir le prix de POLS-USDT et les soldes"""
    try:
        # Charger les clés API depuis le fichier .env
        load_dotenv()
        api_key = os.getenv("KUCOIN_API_KEY")
        api_secret = os.getenv("KUCOIN_API_SECRET")
        api_passphrase = os.getenv("KUCOIN_API_PASSPHRASE")

        if not all([api_key, api_secret, api_passphrase]):
            raise ValueError("Les clés API Kucoin sont manquantes dans le fichier .env")

        # Configuration du client
        client_option = (
            ClientOptionBuilder()
            .set_key(api_key)
            .set_secret(api_secret)
            .set_passphrase(api_passphrase)
            .set_spot_endpoint(GLOBAL_API_ENDPOINT)
            .set_transport_option(
                TransportOptionBuilder()
                .set_keep_alive(True)
                .build()
            )
            .build()
        )
        
        client = DefaultClient(client_option)
        rest_service = client.rest_service()
        spot_service = rest_service.get_spot_service()
        account_service = rest_service.get_account_service()

        # Récupérer le prix POLS
        ticker = spot_service.get_market_api().get_ticker(
            GetTickerReqBuilder().set_symbol("POLS-USDT").build()
        )
        prix_pols = float(ticker.price)
        logging.info(f"Prix actuel de POLS: {prix_pols:.4f} USDT")

        # Récupérer les soldes POLS et USDT
        account_req = GetSpotAccountListReqBuilder().set_type(GetSpotAccountListReq.TypeEnum.TRADE).build()
        accounts = account_service.get_account_api().get_spot_account_list(account_req)
        
        solde_pols = 0
        solde_usdt = 0
        
        for account in accounts.data:
            if account.currency == "POLS":
                solde_pols = float(account.available)
                solde_pols_bloque = float(account.holds)
            elif account.currency == "USDT":
                solde_usdt = float(account.available)
                solde_usdt_bloque = float(account.holds)

        # Afficher les résultats
        logging.info("=== Résumé des soldes ===")
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
            "solde_usdt_bloque": solde_usdt_bloque
        }

    except Exception as e:
        logging.error(f"Erreur: {e}")
        return None

if __name__ == "__main__":
    get_pols_info()