"""
Module de gestion des notifications Telegram
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from typing import Optional, Dict, Any

class TelegramNotifier:
    """Gestionnaire des notifications Telegram"""
    
    def __init__(self, pols_quantity: int = 1000):
        """Initialise le notificateur Telegram"""
        logging.info("Initialisation du TelegramNotifier...")
        load_dotenv()
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.app = None
        self.pols_quantity = pols_quantity
        self.arbitrage_threshold = 0.5  # Seuil d'arbitrage en pourcentage (modifié de 1.0 à 0.5)
        
        logging.info(f"Token Telegram: {'Configuré' if self.token else 'Non configuré'}")
        logging.info(f"Chat ID Telegram: {'Configuré' if self.chat_id else 'Non configuré'}")
        
        if not all([self.token, self.chat_id]):
            logging.error("Configuration Telegram incomplète dans .env")
            raise ValueError("Configuration Telegram incomplète dans .env")
            
    async def _init_bot(self):
        """Initialise le bot Telegram"""
        try:
            logging.info("Tentative d'initialisation du bot Telegram...")
            self.app = ApplicationBuilder().token(self.token).build()
            
            # Ajouter les gestionnaires de commandes
            self.app.add_handler(CommandHandler("start", self._handle_start))
            self.app.add_handler(CommandHandler("set_threshold", self._handle_set_threshold))
            self.app.add_handler(CommandHandler("set_quantity", self._handle_set_quantity))
            self.app.add_handler(CommandHandler("config", self._handle_config))
            self.app.add_handler(CallbackQueryHandler(self._handle_callback))
            
            # Configurer les commandes pour l'autocomplétion
            await self._setup_commands()
            
            logging.info("Bot Telegram initialisé avec succès")
        except Exception as e:
            logging.error(f"Erreur lors de l'initialisation du bot Telegram: {e}")
            raise
    
    async def _setup_commands(self):
        """Configure les commandes du bot avec leurs descriptions pour l'autocomplétion"""
        commands = [
            BotCommand("start", "Démarrer le bot et afficher le menu principal"),
            BotCommand("config", "Afficher la configuration actuelle"),
            BotCommand("set_quantity", "Définir la quantité de POLS à surveiller"),
            BotCommand("set_threshold", "Définir le seuil d'arbitrage en pourcentage")
        ]
        
        try:
            await self.app.bot.set_my_commands(commands)
            logging.info("Commandes du bot configurées avec succès")
        except Exception as e:
            logging.error(f"Erreur lors de la configuration des commandes: {e}")
    
    async def _handle_config(self, update, context):
        """Affiche la configuration actuelle"""
        try:
            message = (
                f"⚙️ <b>Configuration actuelle</b>\n\n"
                f"• Quantité POLS: {self.pols_quantity}\n"
                f"• Seuil d'arbitrage: {self.arbitrage_threshold}%\n\n"
                f"Pour modifier:\n"
                f"/set_quantity [nombre] - Définir la quantité de POLS\n"
                f"/set_threshold [pourcentage] - Définir le seuil d'arbitrage"
            )
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        except Exception as e:
            logging.error(f"Erreur lors de l'affichage de la configuration: {e}")
    
    async def _handle_set_threshold(self, update, context):
        """Définit le seuil d'arbitrage"""
        try:
            if not context.args or not context.args[0].replace('.', '').isdigit():
                await update.message.reply_text(
                    "❌ Usage: /set_threshold <pourcentage>\n"
                    "Exemple: /set_threshold 1.5"
                )
                return

            new_threshold = float(context.args[0])
            if new_threshold <= 0:
                await update.message.reply_text("❌ Le seuil doit être supérieur à 0")
                return

            self.arbitrage_threshold = new_threshold
            await update.message.reply_text(
                f"✅ Seuil d'arbitrage mis à jour: {new_threshold}%"
            )
        except Exception as e:
            logging.error(f"Erreur lors de la mise à jour du seuil: {e}")
            await update.message.reply_text("❌ Erreur lors de la mise à jour du seuil")
    
    async def _handle_set_quantity(self, update, context):
        """Définit la quantité de POLS"""
        try:
            if not context.args or not context.args[0].isdigit():
                await update.message.reply_text(
                    "❌ Usage: /set_quantity [nombre]\n"
                    "Exemple: /set_quantity 1000"
                )
                return

            new_quantity = int(context.args[0])
            if new_quantity <= 0:
                await update.message.reply_text("❌ La quantité doit être supérieure à 0")
                return

            # Mettre à jour la quantité dans les instances des exchanges
            if 'kucoin' in context.bot_data:
                context.bot_data['kucoin'].pols_quantity = new_quantity
            if 'pancakeswap' in context.bot_data:
                context.bot_data['pancakeswap'].pols_quantity = new_quantity
            
            # Mettre à jour la quantité dans le notificateur
            self.pols_quantity = new_quantity
            
            await update.message.reply_text(
                f"✅ Quantité POLS mise à jour: {new_quantity}"
            )
        except Exception as e:
            logging.error(f"Erreur lors de la mise à jour de la quantité: {e}")
            await update.message.reply_text("❌ Erreur lors de la mise à jour de la quantité")
    
    async def _handle_start(self, update, context):
        """Gère la commande /start"""
        try:
            keyboard = [
                [
                    InlineKeyboardButton("📊 Rapport complet", callback_data="report"),
                    InlineKeyboardButton("📈 Opportunités d'arbitrage", callback_data="arbitrage")
                ],
                [
                    InlineKeyboardButton("⚙️ Configuration", callback_data="config")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"👋 Bienvenue! Je suis votre bot de surveillance des prix POLS.\n\n"
                f"Je surveille les prix sur KuCoin et PancakeSwap pour {self.pols_quantity} POLS.\n"
                f"Seuil d'arbitrage: {self.arbitrage_threshold}%\n\n"
                f"Commandes disponibles:\n"
                f"/config - Afficher la configuration\n"
                f"/set_quantity <nombre> - Définir la quantité de POLS\n"
                f"/set_threshold <pourcentage> - Définir le seuil d'arbitrage\n\n",
                reply_markup=reply_markup
            )
            logging.info("Message de démarrage envoyé avec succès")
        except Exception as e:
            logging.error(f"Erreur lors de l'envoi du message de démarrage: {e}")
    
    async def _handle_callback(self, update, context):
        """Gère les callbacks des boutons"""
        try:
            query = update.callback_query
            await query.answer()
            
            if query.data == "report":
                await self.send_full_report(context.bot_data.get('kucoin'), context.bot_data.get('pancakeswap'))
            elif query.data == "arbitrage":
                kucoin = context.bot_data.get('kucoin')
                pancakeswap = context.bot_data.get('pancakeswap')
                
                if kucoin and pancakeswap:
                    arbitrage_gains = await self._calculate_arbitrage_gains(kucoin, pancakeswap)
                    
                    message = (
                        f"📈 <b>Opportunités d'arbitrage pour {self.pols_quantity} POLS</b>\n\n"
                        f"🔄 <b>KuCoin ➡️ PancakeSwap</b>\n"
                        f"• Achat sur kucoin: <code>{arbitrage_gains['kucoin_to_pancakeswap']['steps'][0].split(': ')[1]}</code>\n"
                        f"• Frais KuCoin: <code>{arbitrage_gains['kucoin_to_pancakeswap']['steps'][1].split(': ')[1]}</code>\n"
                        f"• Vente sur pancakeswap: <code>{arbitrage_gains['kucoin_to_pancakeswap']['steps'][2].split(': ')[1]}</code>\n"
                        f"• Frais PancakeSwap: <code>{arbitrage_gains['kucoin_to_pancakeswap']['steps'][3].split(': ')[1]}</code>\n"
                        f"• <b>Profit final: {arbitrage_gains['kucoin_to_pancakeswap']['steps'][4].split(': ')[1]}</b>\n\n"
                        f"🔄 <b>PancakeSwap ➡️ KuCoin</b>\n"
                        f"• Achat sur pancakeswap: <code>{arbitrage_gains['pancakeswap_to_kucoin']['steps'][0].split(': ')[1]}</code>\n"
                        f"• Frais PancakeSwap: <code>{arbitrage_gains['pancakeswap_to_kucoin']['steps'][1].split(': ')[1]}</code>\n"
                        f"• Vente sur kucoin: <code>{arbitrage_gains['pancakeswap_to_kucoin']['steps'][2].split(': ')[1]}</code>\n"
                        f"• Frais KuCoin: <code>{arbitrage_gains['pancakeswap_to_kucoin']['steps'][3].split(': ')[1]}</code>\n"
                        f"• <b>Profit final: {arbitrage_gains['pancakeswap_to_kucoin']['steps'][4].split(': ')[1]}</b>"
                    )
                    await query.message.reply_text(message, parse_mode=ParseMode.HTML)
            elif query.data == "config":
                message = (
                    f"⚙️ <b>Configuration actuelle</b>\n\n"
                    f"• Quantité POLS: {self.pols_quantity}\n"
                    f"• Seuil d'arbitrage: {self.arbitrage_threshold}%\n\n"
                    f"Pour modifier:\n"
                    f"/set_quantity [nombre] - Définir la quantité de POLS\n"
                    f"/set_threshold [pourcentage] - Définir le seuil d'arbitrage"
                )
                await query.message.reply_text(message, parse_mode=ParseMode.HTML)
            
            logging.info(f"Callback {query.data} traité avec succès")
        except Exception as e:
            logging.error(f"Erreur lors du traitement du callback: {e}")
    
    async def _calculate_arbitrage_gains(self, kucoin, pancakeswap):
        """Calcule les gains d'arbitrage détaillés"""
        kucoin_info = kucoin.get_price_info()
        pancakeswap_info = pancakeswap.get_price_info()
        
        # Frais de transaction estimés
        KUCOIN_FEE = 0.001  # 0.1%
        PANCAKESWAP_FEE = 0.0025  # 0.25%
        
        # KuCoin -> PancakeSwap
        # 1. Acheter sur KuCoin
        kucoin_buy_cost = kucoin_info.buy_cost
        kucoin_fee = kucoin_buy_cost * KUCOIN_FEE
        # 2. Vendre sur PancakeSwap
        pancakeswap_sell_revenue = pancakeswap_info.sell_revenue
        pancakeswap_fee = pancakeswap_sell_revenue * PANCAKESWAP_FEE
        kucoin_to_pancakeswap_profit = pancakeswap_sell_revenue - kucoin_buy_cost - kucoin_fee - pancakeswap_fee
        
        # PancakeSwap -> KuCoin
        # 1. Acheter sur PancakeSwap
        pancakeswap_buy_cost = pancakeswap_info.buy_cost
        pancakeswap_fee = pancakeswap_buy_cost * PANCAKESWAP_FEE
        # 2. Vendre sur KuCoin
        kucoin_sell_revenue = kucoin_info.sell_revenue
        kucoin_fee = kucoin_sell_revenue * KUCOIN_FEE
        pancakeswap_to_kucoin_profit = kucoin_sell_revenue - pancakeswap_buy_cost - pancakeswap_fee - kucoin_fee
        
        # Vérifier les opportunités d'arbitrage importantes
        await self._check_significant_arbitrage(
            kucoin_to_pancakeswap_profit,
            pancakeswap_to_kucoin_profit,
            kucoin_buy_cost,
            pancakeswap_buy_cost
        )
        
        return {
            'kucoin_to_pancakeswap': {
                'profit': kucoin_to_pancakeswap_profit,
                'profit_percentage': (kucoin_to_pancakeswap_profit / kucoin_buy_cost) * 100,
                'steps': [
                    f"Achat sur KuCoin: {kucoin_buy_cost:.2f} USDT",
                    f"Frais KuCoin: {kucoin_fee:.2f} USDT",
                    f"Vente sur PancakeSwap: {pancakeswap_sell_revenue:.2f} USDT",
                    f"Frais PancakeSwap: {pancakeswap_fee:.2f} USDT",
                    f"Profit final: {kucoin_to_pancakeswap_profit:.2f} USDT ({kucoin_to_pancakeswap_profit/kucoin_buy_cost*100:.2f}%)"
                ]
            },
            'pancakeswap_to_kucoin': {
                'profit': pancakeswap_to_kucoin_profit,
                'profit_percentage': (pancakeswap_to_kucoin_profit / pancakeswap_buy_cost) * 100,
                'steps': [
                    f"Achat sur PancakeSwap: {pancakeswap_buy_cost:.2f} USDT",
                    f"Frais PancakeSwap: {pancakeswap_fee:.2f} USDT",
                    f"Vente sur kucoin: {kucoin_sell_revenue:.2f} USDT",
                    f"Frais KuCoin: {kucoin_fee:.2f} USDT",
                    f"Profit final: {pancakeswap_to_kucoin_profit:.2f} USDT ({pancakeswap_to_kucoin_profit/pancakeswap_buy_cost*100:.2f}%)"
                ]
            }
        }

    async def _check_significant_arbitrage(self, kucoin_to_pancake_profit, pancake_to_kucoin_profit, kucoin_buy_cost, pancake_buy_cost):
        """Vérifie et notifie les opportunités d'arbitrage importantes"""
        try:
            logging.info("=== Détails des calculs d'arbitrage ===")
            logging.info(f"kucoin_to_pancake_profit: {kucoin_to_pancake_profit}")
            logging.info(f"pancake_to_kucoin_profit: {pancake_to_kucoin_profit}")
            logging.info(f"kucoin_buy_cost: {kucoin_buy_cost}")
            logging.info(f"pancake_buy_cost: {pancake_buy_cost}")
            
            kucoin_to_pancake_percentage = (kucoin_to_pancake_profit / kucoin_buy_cost) * 100
            pancake_to_kucoin_percentage = (pancake_to_kucoin_profit / pancake_buy_cost) * 100
            
            logging.info(f"=== Pourcentages calculés ===")
            logging.info(f"kucoin_to_pancake_percentage: {kucoin_to_pancake_percentage:.2f}%")
            logging.info(f"pancake_to_kucoin_percentage: {pancake_to_kucoin_percentage:.2f}%")
            logging.info(f"seuil: {self.arbitrage_threshold}%")
            
            if kucoin_to_pancake_percentage > self.arbitrage_threshold or pancake_to_kucoin_percentage > self.arbitrage_threshold:
                message = f"🚨 <b>Opportunité d'arbitrage importante détectée!</b>\n\n"
                
                if kucoin_to_pancake_percentage > self.arbitrage_threshold:
                    message += (
                        f"🔄 <b>KuCoin ➡️ PancakeSwap</b>\n"
                        f"• Achat sur kucoin: {kucoin_buy_cost:.2f} USDT\n"
                        f"• Frais KuCoin: {kucoin_buy_cost * 0.001:.2f} USDT\n"
                        f"• Transfert BSC: -0.1%\n"
                        f"• Vente sur pancakeswap: {pancake_buy_cost:.2f} USDT\n"
                        f"• Frais PancakeSwap: {pancake_buy_cost * 0.0025:.2f} USDT\n"
                        f"• <b>Profit final: {kucoin_to_pancake_profit:.2f} USDT ({kucoin_to_pancake_percentage:.2f}%)</b>\n\n"
                    )
                
                if pancake_to_kucoin_percentage > self.arbitrage_threshold:
                    message += (
                        f"🔄 <b>PancakeSwap ➡️ KuCoin</b>\n"
                        f"• Achat sur pancakeswap: {pancake_buy_cost:.2f} USDT\n"
                        f"• Frais PancakeSwap: {pancake_buy_cost * 0.0025:.2f} USDT\n"
                        f"• Transfert BSC: -0.1%\n"
                        f"• Vente sur kucoin: {kucoin_buy_cost:.2f} USDT\n"
                        f"• Frais KuCoin: {kucoin_buy_cost * 0.001:.2f} USDT\n"
                        f"• <b>Profit final: {pancake_to_kucoin_profit:.2f} USDT ({pancake_to_kucoin_percentage:.2f}%)</b>"
                    )
                
                logging.info(f"Envoi de la notification d'arbitrage: {message}")
                await self.send_message(message)
                logging.info("Notification d'opportunité d'arbitrage importante envoyée")
            else:
                logging.info("Aucune opportunité d'arbitrage significative détectée")
                
        except Exception as e:
            logging.error(f"Erreur lors de la vérification des opportunités d'arbitrage: {e}")
            logging.error(f"kucoin_to_pancake_profit: {kucoin_to_pancake_profit}")
            logging.error(f"pancake_to_kucoin_profit: {pancake_to_kucoin_profit}")
            logging.error(f"kucoin_buy_cost: {kucoin_buy_cost}")
            logging.error(f"pancake_buy_cost: {pancake_buy_cost}")

    async def send_message(self, message: str):
        """Envoie un message sur Telegram"""
        try:
            logging.info("Tentative d'envoi d'un message Telegram...")
            logging.info(f"Chat ID: {self.chat_id}")
            logging.info(f"Message: {message[:100]}...")
            
            if self.app:
                if not self.app.bot:
                    logging.error("Bot non initialisé dans l'application")
                    return
                    
                result = await self.app.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
                logging.info(f"Message envoyé avec succès. Message ID: {result.message_id}")
            else:
                logging.error("Application Telegram non initialisée")
        except Exception as e:
            logging.error(f"Erreur lors de l'envoi du message Telegram: {e}")
            logging.error(f"Contenu du message qui a échoué: {message[:100]}...")

    def format_exchange_info(self, exchange, price_info, balance_info) -> str:
        """Formate les informations d'un exchange pour Telegram"""
        logging.info(f"Formatage des informations pour l'exchange {exchange.name}")
        message = f"""
🏦 <b>{exchange.name}</b>

💰 <b>Prix</b>
• Actuel: <code>{price_info.current_price:.4f}</code> USDT
• Achat ({self.pols_quantity} POLS): <code>{price_info.buy_price:.4f}</code> USDT (Total: <code>{price_info.buy_cost:.2f}</code> USDT)
• Vente ({self.pols_quantity} POLS): <code>{price_info.sell_price:.4f}</code> USDT (Total: <code>{price_info.sell_revenue:.2f}</code> USDT)

💼 <b>Soldes</b>
• POLS disponible: <code>{balance_info.pols_free:.4f}</code>
• POLS bloqué: <code>{balance_info.pols_locked:.4f}</code>
• USDT disponible: <code>{balance_info.usdt_free:.2f}</code>
• USDT bloqué: <code>{balance_info.usdt_locked:.2f}</code>
• Valeur totale POLS: <code>{balance_info.pols_value_usdt:.2f}</code> USDT"""
        logging.info("Message formaté avec succès")
        return message

    

    async def send_full_report(self, kucoin, pancakeswap):
        """Envoie un rapport complet avec les informations des exchanges"""
        try:
            logging.info("Préparation du rapport complet...")
            
            # Récupérer les informations des exchanges
            kucoin_price = kucoin.get_price_info()
            kucoin_balance = kucoin.get_balance()
            
            pancake_price = pancakeswap.get_price_info()
            pancake_balance = pancakeswap.get_balance()
            
            # Calculer les opportunités d'arbitrage
            arbitrage_gains = await self._calculate_arbitrage_gains(kucoin, pancakeswap)
            
            # En-tête avec la date
            header = f"📈 <b>Rapport des exchanges</b> - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            # Informations des exchanges
            exchanges_info = (
                self.format_exchange_info(kucoin, kucoin_price, kucoin_balance) + "\n\n" +
                self.format_exchange_info(pancakeswap, pancake_price, pancake_balance)
            )
            
            
            # Assemblage du message complet
            full_message = f"{header}\n{exchanges_info}\n\n"
            
            # Envoi du message
            await self.send_message(full_message)
            logging.info("Rapport complet envoyé avec succès")
            
        except Exception as e:
            error_msg = f"❌ Erreur lors de l'envoi du rapport complet: {str(e)}"
            logging.error(error_msg)
            await self.send_message(error_msg)

    async def initialize(self):
        """Initialisation asynchrone du bot"""
        await self._init_bot() 