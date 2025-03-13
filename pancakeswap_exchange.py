"""
Classe pour l'échange PancakeSwap
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from web3 import Web3
from exchange_base import ExchangeBase, PriceInfo, BalanceInfo

class PancakeSwapExchange(ExchangeBase):
    """Gestion des opérations sur PancakeSwap"""
    
    # Adresses des contrats
    ROUTER_ADDRESS = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
    FACTORY_ADDRESS = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
    POLS_ADDRESS = "0x7e624FA0E1c4AbFD309cC15719b7E2580887f570"
    USDT_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"
    BSC_RPC = "https://bsc-dataseed.binance.org/"

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

    def __init__(self, pols_quantity: int = 1000):
        """Initialise l'exchange PancakeSwap"""
        super().__init__("PancakeSwap")
        self.pols_quantity = pols_quantity
        self._load_config()
        self._init_web3()

    def _load_config(self):
        """Charge la configuration depuis .env"""
        load_dotenv()
        self.wallet_address = os.getenv("BSC_WALLET_ADDRESS")
        
        if not self.wallet_address:
            raise ValueError("Configuration PancakeSwap incomplète dans .env")

    def _init_web3(self):
        """Initialise la connexion Web3"""
        self.web3 = Web3(Web3.HTTPProvider(self.BSC_RPC))
        if not self.web3.is_connected():
            raise Exception("Impossible de se connecter à la Binance Smart Chain")
            
        self.router_contract = self.web3.eth.contract(
            address=self.web3.to_checksum_address(self.ROUTER_ADDRESS),
            abi=self.ROUTER_ABI
        )

    def get_price_info(self) -> PriceInfo:
        """Récupère les informations de prix"""
        try:
            # Obtenir le prix pour la quantité de POLS spécifiée
            path = [self.POLS_ADDRESS, self.USDT_ADDRESS]
            amounts = self.router_contract.functions.getAmountsOut(
                int(self.pols_quantity * 1e18),  # Convertir la quantité en wei
                path
            ).call()
            
            # Calculer le prix moyen par POLS
            current_price = float(amounts[1]) / (self.pols_quantity * 1e18)
            
            # Calculer les prix d'achat et de vente avec le slippage
            buy_price = current_price * 1.001  # +0.1% pour l'achat
            sell_price = current_price * 0.999  # -0.1% pour la vente
            
            # Calculer les coûts totaux
            buy_cost = buy_price * self.pols_quantity
            sell_revenue = sell_price * self.pols_quantity
            
            return PriceInfo(
                current_price=current_price,
                buy_price=buy_price,
                sell_price=sell_price,
                buy_cost=buy_cost,
                sell_revenue=sell_revenue,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des prix PancakeSwap: {e}")
            raise

    def get_balance(self) -> BalanceInfo:
        """Récupère les soldes du compte"""
        try:
            # Créer les contrats pour POLS et USDT
            pols_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(self.POLS_ADDRESS),
                abi=self.ERC20_ABI
            )
            usdt_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(self.USDT_ADDRESS),
                abi=self.ERC20_ABI
            )
            
            # Obtenir les soldes
            pols_balance = float(pols_contract.functions.balanceOf(self.wallet_address).call()) / 1e18
            usdt_balance = float(usdt_contract.functions.balanceOf(self.wallet_address).call()) / 1e18
            
            # Calculer la valeur en USDT
            current_price = self.get_price_info().current_price
            pols_value = pols_balance * current_price
            
            return BalanceInfo(
                pols_free=pols_balance,
                pols_locked=0,  # PancakeSwap n'a pas de concept de "bloqué"
                usdt_free=usdt_balance,
                usdt_locked=0,  # PancakeSwap n'a pas de concept de "bloqué"
                pols_value_usdt=pols_value
            )
        except Exception as e:
            logging.error(f"Erreur lors de la récupération des soldes PancakeSwap: {e}")
            raise 