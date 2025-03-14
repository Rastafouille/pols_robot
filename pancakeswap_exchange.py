"""
Classe pour l'échange PancakeSwap
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from web3 import Web3
from exchange_base import ExchangeBase, PriceInfo, BalanceInfo
import time

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
        },
        {
            "inputs": [
                {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                {"internalType": "address[]", "name": "path", "type": "address[]"},
                {"internalType": "address", "name": "to", "type": "address"},
                {"internalType": "uint256", "name": "deadline", "type": "uint256"}
            ],
            "name": "swapExactTokensForTokens",
            "outputs": [
                {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
            ],
            "stateMutability": "nonpayable",
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
        },
        {
            "inputs": [
                {"internalType": "address", "name": "spender", "type": "address"},
                {"internalType": "uint256", "name": "amount", "type": "uint256"}
            ],
            "name": "approve",
            "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"internalType": "address", "name": "owner", "type": "address"},
                {"internalType": "address", "name": "spender", "type": "address"}
            ],
            "name": "allowance",
            "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
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

    def create_market_sell_order(self, amount: float) -> str:
        """Crée un ordre de vente au marché sur PancakeSwap
        
        Args:
            amount (float): Quantité de POLS à vendre
            
        Returns:
            str: Hash de la transaction de vente
            
        Raises:
            Exception: Si la vente échoue
        """
        try:
            # Vérifier le solde disponible
            balance = self.get_balance()
            if balance.pols_free < amount:
                raise Exception(f"Solde insuffisant! Vous avez seulement {balance.pols_free:.4f} POLS disponible.")

            # Obtenir le prix actuel
            price_info = self.get_price_info()
            current_price = price_info.current_price

            # Récupérer l'adresse du wallet associée à la clé privée
            private_key = os.getenv("BSC_PRIVATE_KEY")
            account = self.web3.eth.account.from_key(private_key)
            wallet_address = account.address

            # Créer le contrat POLS
            pols_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(self.POLS_ADDRESS),
                abi=self.ERC20_ABI
            )

            # Obtenir le nonce actuel
            nonce = self.web3.eth.get_transaction_count(wallet_address)
            logging.info(f"Nonce actuel: {nonce}")

            # Vérifier l'approbation actuelle
            current_allowance = pols_contract.functions.allowance(wallet_address, self.ROUTER_ADDRESS).call()
            amount_in = int(amount * 1e18)  # Convertir en wei

            # Si l'approbation est insuffisante, approuver le routeur
            if current_allowance < amount_in:
                logging.info("Approbation du contrat PancakeSwap...")
                approve_txn = pols_contract.functions.approve(
                    self.ROUTER_ADDRESS,
                    amount_in  # On approuve exactement le montant nécessaire
                ).build_transaction({
                    'from': wallet_address,
                    'gas': 100000,
                    'gasPrice': self.web3.eth.gas_price,
                    'nonce': nonce
                })

                # Signer et envoyer la transaction d'approbation
                signed_approve_txn = self.web3.eth.account.sign_transaction(approve_txn, private_key=private_key)
                approve_tx_hash = self.web3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
                
                # Attendre la confirmation de l'approbation
                approve_receipt = self.web3.eth.wait_for_transaction_receipt(approve_tx_hash)
                if approve_receipt['status'] != 1:
                    raise Exception("L'approbation a échoué")
                logging.info(f"Approbation réussie. Hash: {approve_tx_hash.hex()}")
                
                # Incrémenter le nonce pour la prochaine transaction
                nonce += 1

            # Calculer le montant minimum à recevoir (avec 0.5% de slippage)
            min_amount_out = int(amount * current_price * 0.995 * 1e18)  # 0.5% de slippage

            # Chemin de swap POLS -> USDT
            path = [self.POLS_ADDRESS, self.USDT_ADDRESS]

            # Deadline de 5 minutes
            deadline = int(datetime.now().timestamp()) + 300

            # Créer la transaction de swap
            transaction = self.router_contract.functions.swapExactTokensForTokens(
                amount_in,
                min_amount_out,
                path,
                wallet_address,
                deadline
            ).build_transaction({
                'from': wallet_address,
                'gas': 200000,
                'gasPrice': self.web3.eth.gas_price,
                'nonce': nonce
            })

            # Signer et envoyer la transaction
            signed_txn = self.web3.eth.account.sign_transaction(transaction, private_key=private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Attendre la confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                logging.info(f"Vente de {amount} POLS effectuée avec succès. Hash: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                raise Exception("La transaction a échoué")

        except Exception as e:
            logging.error(f"Erreur lors de la vente sur PancakeSwap: {e}")
            raise 

    def create_market_buy_order(self, amount: int) -> str:
        """Crée un ordre d'achat au marché sur PancakeSwap"""
        try:
            # Récupérer l'adresse du wallet depuis la clé privée
            private_key = os.getenv("BSC_PRIVATE_KEY")
            if not private_key:
                raise ValueError("Clé privée BSC non configurée")
                
            wallet_address = self.web3.eth.account.from_key(private_key).address
            
            # Vérifier le solde USDT
            usdt_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(self.USDT_ADDRESS),
                abi=self.ERC20_ABI
            )
            usdt_balance = usdt_contract.functions.balanceOf(wallet_address).call()
            usdt_balance = self.web3.from_wei(usdt_balance, 'mwei')  # USDT a 6 décimales
            
            # Obtenir le prix actuel
            price_info = self.get_price_info()
            cost = amount * price_info.current_price * 1.0025  # Prix + 0.25% de frais
            
            if usdt_balance < cost:
                raise ValueError(f"Solde USDT insuffisant: {usdt_balance:.2f} USDT requis: {cost:.2f} USDT")
            
            # Vérifier l'approbation USDT pour le router
            router_address = self.web3.to_checksum_address(self.ROUTER_ADDRESS)
            current_allowance = usdt_contract.functions.allowance(wallet_address, router_address).call()
            current_allowance = self.web3.from_wei(current_allowance, 'mwei')
            
            # Si l'approbation est insuffisante, approuver le router
            if current_allowance < cost:
                approve_txn = usdt_contract.functions.approve(
                    router_address,
                    self.web3.to_wei(cost * 1.1, 'mwei')  # 10% de marge pour les variations de prix
                ).build_transaction({
                    'from': wallet_address,
                    'nonce': self.web3.eth.get_transaction_count(wallet_address),
                    'gas': 100000,
                    'gasPrice': self.web3.eth.gas_price
                })
                
                signed_txn = self.web3.eth.account.sign_transaction(approve_txn, private_key)
                tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
                self.web3.eth.wait_for_transaction_receipt(tx_hash)
                logging.info(f"Approbation USDT effectuée: {tx_hash.hex()}")
            
            # Obtenir le chemin de swap optimal
            path = [
                self.web3.to_checksum_address(self.USDT_ADDRESS),
                self.web3.to_checksum_address(self.POLS_ADDRESS)
            ]
            
            # Calculer le montant minimum de POLS à recevoir (avec 0.5% de slippage)
            amounts_out = self.router_contract.functions.getAmountsOut(
                self.web3.to_wei(cost, 'mwei'),
                path
            ).call()
            min_pols = int(amounts_out[-1] * 0.995)  # 0.5% de slippage
            
            # Créer la transaction de swap
            deadline = int(time.time()) + 300  # 5 minutes
            
            txn = self.router_contract.functions.swapExactTokensForTokens(
                self.web3.to_wei(cost, 'mwei'),  # Montant USDT exact
                min_pols,  # Montant minimum de POLS à recevoir
                path,
                wallet_address,  # Adresse de destination
                deadline
            ).build_transaction({
                'from': wallet_address,
                'nonce': self.web3.eth.get_transaction_count(wallet_address),
                'gas': 250000,
                'gasPrice': self.web3.eth.gas_price
            })
            
            # Signer et envoyer la transaction
            signed_txn = self.web3.eth.account.sign_transaction(txn, private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Attendre la confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                logging.info(f"Transaction d'achat réussie: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                raise Exception("La transaction a échoué")
                
        except Exception as e:
            logging.error(f"Erreur lors de l'achat: {str(e)}")
            raise 