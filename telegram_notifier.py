"""
Module de gestion des notifications Telegram
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, Update
from telegram.constants import ParseMode
from typing import Optional, Dict, Any

class TelegramNotifier:
    """Gestionnaire des notifications Telegram"""
    
    def __init__(self, pols_quantity: int = 5000):
        """Initialise le notificateur Telegram"""
        logging.info("Initialisation du TelegramNotifier...")
        load_dotenv()
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.app = None
        self.pols_quantity = pols_quantity
        self.arbitrage_threshold = 7.0  # Seuil d'arbitrage en pourcentage (modifié de 1.0 à 0.5)
        
        # Récupérer la liste des utilisateurs autorisés depuis .env
        authorized_users_str = os.getenv("AUTHORIZED_USERS", "")
        self.authorized_users = [int(user_id.strip()) for user_id in authorized_users_str.split(",") if user_id.strip()]
        
        logging.info(f"Token Telegram: {'Configuré' if self.token else 'Non configuré'}")
        logging.info(f"Chat ID Telegram: {'Configuré' if self.chat_id else 'Non configuré'}")
        logging.info(f"Utilisateurs autorisés: {self.authorized_users}")
        
        if not all([self.token, self.chat_id, self.authorized_users]):
            logging.error("Configuration Telegram incomplète dans .env")
            raise ValueError("Configuration Telegram incomplète dans .env")
            
    def is_user_authorized(self, user_id: int) -> bool:
        """Vérifie si l'utilisateur est autorisé à utiliser le bot"""
        return user_id in self.authorized_users
    
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
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            
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
            user_id = update.effective_user.id
            if not self.is_user_authorized(user_id):
                await update.message.reply_text(
                    "❌ Désolé, vous n'êtes pas autorisé à utiliser ce bot.\n"
                    "Contactez l'administrateur pour obtenir l'accès."
                )
                logging.warning(f"Tentative d'accès non autorisée de l'utilisateur {user_id}")
                return
                
            # Récupérer l'instance de la stratégie de trading
            strategy = context.bot_data.get('strategy')
            
            message = (
                f"⚙️ <b>Configuration actuelle</b>\n\n"
                f"<b>Paramètres de Monitoring:</b>\n"
                f"• Quantité POLS: {self.pols_quantity}\n"
                f"• Seuil d'arbitrage: {self.arbitrage_threshold}%\n\n"
                f"<b>Paramètres de Trading:</b>\n"
                f"• Périodes MA: {strategy.MA_PERIODS}\n"
                f"• Timeframe: {strategy.TIMEFRAME}\n"
                f"• Seuil de hausse: {strategy.PRICE_INCREASE_THRESHOLD*100}%\n"
                f"• Seuil de baisse: {strategy.DROP_THRESHOLD*100}%\n"
                f"• Offset ordre limit: {strategy.LIMIT_ORDER_OFFSET*100}%\n"
                f"• Taille des ordres: {strategy.ORDER_SIZE} POLS\n\n"
                f"<b>Statut:</b>\n"
                f"• Monitoring actif: {'✅' if strategy.is_monitoring else '❌'}\n"
            )
            
            # Ajouter le prix le plus haut si disponible
            if strategy.highest_price:
                message += f"• Prix le plus haut: {strategy.highest_price:.4f} USDT"
            else:
                message += "• Prix le plus haut: N/A"
                
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        except Exception as e:
            logging.error(f"Erreur lors de l'affichage de la configuration: {e}")
    
    async def _handle_set_threshold(self, update, context):
        """Définit le seuil d'arbitrage"""
        try:
            user_id = update.effective_user.id
            if not self.is_user_authorized(user_id):
                await update.message.reply_text(
                    "❌ Désolé, vous n'êtes pas autorisé à utiliser ce bot.\n"
                    "Contactez l'administrateur pour obtenir l'accès."
                )
                logging.warning(f"Tentative d'accès non autorisée de l'utilisateur {user_id}")
                return
                
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
            user_id = update.effective_user.id
            if not self.is_user_authorized(user_id):
                await update.message.reply_text(
                    "❌ Désolé, vous n'êtes pas autorisé à utiliser ce bot.\n"
                    "Contactez l'administrateur pour obtenir l'accès."
                )
                logging.warning(f"Tentative d'accès non autorisée de l'utilisateur {user_id}")
                return
                
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
            user_id = update.effective_user.id
            if not self.is_user_authorized(user_id):
                await update.message.reply_text(
                    "❌ Désolé, vous n'êtes pas autorisé à utiliser ce bot.\n"
                    "Contactez l'administrateur pour obtenir l'accès."
                )
                logging.warning(f"Tentative d'accès non autorisée de l'utilisateur {user_id}")
                return
                
            keyboard = [
                [
                    InlineKeyboardButton("📊 Rapport complet", callback_data="report"),
                    InlineKeyboardButton("📈 Opportunités d'arbitrage", callback_data="arbitrage")
                ],
                [
                    InlineKeyboardButton("🛒 Acheter POLS", callback_data="buy_pols"),
                    InlineKeyboardButton("💰 Vendre POLS", callback_data="sell_pols")
                ],
                [
                    InlineKeyboardButton("⚙️ Configuration", callback_data="config"),
                    InlineKeyboardButton("🟢 Trailing Stop", callback_data="trailing_stop")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"👋 Bienvenue! Je suis votre bot de surveillance des prix POLS.\n\n"
                f"Je surveille les prix sur KuCoin et PancakeSwap pour {self.pols_quantity} POLS.\n"
                f"Seuil d'arbitrage: {self.arbitrage_threshold}%\n\n",
                reply_markup=reply_markup
            )
            logging.info(f"Message de démarrage envoyé à l'utilisateur {user_id}")
        except Exception as e:
            logging.error(f"Erreur lors de l'envoi du message de démarrage: {e}")
    
    async def _handle_callback(self, update, context):
        """Gère les callbacks des boutons"""
        try:
            query = update.callback_query
            user_id = query.from_user.id
            
            if not self.is_user_authorized(user_id):
                await query.answer("❌ Vous n'êtes pas autorisé à utiliser ce bot.")
                logging.warning(f"Tentative d'accès non autorisée de l'utilisateur {user_id}")
                return
                
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
                # Récupérer l'instance de la stratégie de trading
                strategy = context.bot_data.get('strategy')
                message = (
                    f"⚙️ <b>Configuration actuelle</b>\n\n"
                    f"<b>Paramètres de Monitoring:</b>\n"
                    f"• Quantité POLS: {self.pols_quantity}\n"
                    f"• Seuil d'arbitrage: {self.arbitrage_threshold}%\n\n"
                    f"<b>Paramètres de Trading:</b>\n"
                    f"• Périodes MA: {strategy.MA_PERIODS}\n"
                    f"• Timeframe: {strategy.TIMEFRAME}\n"
                    f"• Seuil de hausse: {strategy.PRICE_INCREASE_THRESHOLD*100}%\n"
                    f"• Seuil de baisse: {strategy.DROP_THRESHOLD*100}%\n"
                    f"• Offset ordre limit: {strategy.LIMIT_ORDER_OFFSET*100}%\n"
                    f"• Taille des ordres: {strategy.ORDER_SIZE} POLS\n\n"
                    f"<b>Statut:</b>\n"
                    f"• Monitoring actif: {'✅' if strategy.is_monitoring else '❌'}\n"
                )
                # Ajouter le prix le plus haut si disponible
                if strategy.highest_price:
                    message += f"• Prix le plus haut: {strategy.highest_price:.4f} USDT"
                else:
                    message += "• Prix le plus haut: N/A"
                await query.message.reply_text(message, parse_mode=ParseMode.HTML)

            elif query.data == "trailing_stop":
                strategy = context.bot_data.get('strategy')
                if strategy is None:
                    await query.message.reply_text("❌ Stratégie non initialisée.")
                    return
                # Historique MA et calculs même si peu de valeurs
                if not strategy.price_history.empty:
                    current_price = strategy.price_history['price'].iloc[-1]
                    # MA sur toutes les valeurs disponibles
                    ma = strategy.price_history['price'].mean()
                    ma_history = strategy.price_history['price'].expanding().mean().tail(10)
                    ma_history_str = '\n'.join([f"{v:.4f}" for v in ma_history])
                    ecart = (current_price - ma) / ma * 100 if ma != 0 else 0
                    ecart_str = f"{ecart:.2f}%"
                    ma_str = f"{ma:.4f}"
                else:
                    current_price = None
                    ma_history_str = "Pas assez de données."
                    ecart_str = "N/A"
                    ma_str = "N/A"
                # Paramètres
                params = (
                    f"<b>Paramètres stratégie :</b>\n"
                    f"• MA_PERIODS : {strategy.MA_PERIODS}\n"
                    f"• TIMEFRAME : {strategy.TIMEFRAME}\n"
                    f"• PRICE_INCREASE_THRESHOLD : {strategy.PRICE_INCREASE_THRESHOLD*100:.2f}%\n"
                    f"• DROP_THRESHOLD : {strategy.DROP_THRESHOLD*100:.2f}%\n"
                    f"• LIMIT_ORDER_OFFSET : {strategy.LIMIT_ORDER_OFFSET*100:.2f}%\n"
                    f"• ORDER_SIZE : {strategy.ORDER_SIZE} POLS\n"
                )
                message = (
                    f"<b>🟢 Trailing Stop - Suivi MA</b>\n\n"
                    f"<b>Historique MA (10 derniers):</b>\n{ma_history_str}\n\n"
                    f"<b>Prix Kucoin actuel :</b> {current_price if current_price is not None else 'N/A'}\n"
                    f"<b>MA actuelle :</b> {ma_str}\n"
                    f"<b>Écart prix/MA :</b> {ecart_str}\n\n"
                    f"{params}"
                )
                await query.message.reply_text(message, parse_mode=ParseMode.HTML)
            elif query.data == "sell_pols":
                message = (
                    f"💰 <b>Vente de POLS</b>\n\n"
                    f"Veuillez entrer le montant de POLS à vendre.\n"
                    f"Exemple: <code>10</code>"
                )
                await query.message.reply_text(message, parse_mode=ParseMode.HTML)
                context.user_data['action'] = 'sell'
                context.user_data['awaiting_amount'] = True
            elif query.data == "buy_pols":
                message = (
                    f"🛒 <b>Achat de POLS</b>\n\n"
                    f"Veuillez entrer le montant de POLS à acheter.\n"
                    f"Exemple: <code>10</code>"
                )
                await query.message.reply_text(message, parse_mode=ParseMode.HTML)
                context.user_data['action'] = 'buy'
                context.user_data['awaiting_amount'] = True
            elif query.data.startswith(("sell_kucoin_", "sell_pancake_", "buy_kucoin_", "buy_pancake_")):
                if 'amount' not in context.user_data:
                    await query.message.reply_text("❌ Erreur: Montant non spécifié")
                    return
                    
                amount = context.user_data['amount']
                exchange = query.data.split('_')[1]  # kucoin ou pancake
                action = query.data.split('_')[0]  # buy ou sell
                
                if exchange == 'kucoin':
                    kucoin = context.bot_data.get('kucoin')
                    if kucoin:
                        try:
                            if action == 'sell':
                                # Vérifier le solde disponible
                                balance = kucoin.get_balance()
                                if balance.pols_free < amount:
                                    message = f"❌ Solde insuffisant! Vous avez seulement {balance.pols_free:.4f} POLS disponible."
                                    await query.message.reply_text(message)
                                    return

                                # Obtenir le prix actuel
                                price_info = kucoin.get_price_info()
                                current_price = price_info.current_price

                                # Créer l'ordre de vente
                                order = kucoin.client.create_market_order(
                                    symbol='POLS-USDT',
                                    side='sell',
                                    size=amount
                                )
                                
                                if order:
                                    message = (
                                        f"✅ <b>Vente de {amount} POLS effectuée sur KuCoin</b>\n\n"
                                        f"• Quantité: {amount} POLS\n"
                                        f"• Prix: <code>{current_price:.4f}</code> USDT\n"
                                        f"• Montant total: <code>{amount * current_price:.4f}</code> USDT\n"
                                        f"• Frais (0.1%): <code>{amount * current_price * 0.001:.4f}</code> USDT\n"
                                        f"• Montant net: <code>{amount * current_price * 0.999:.4f}</code> USDT\n\n"
                                        f"🔗 <a href='https://www.kucoin.com/trade/POLS-USDT'>Voir l'ordre sur KuCoin</a>"
                                    )
                                else:
                                    message = "❌ Erreur lors de la création de l'ordre de vente"
                            else:  # buy
                                # Vérifier le solde USDT disponible
                                balance = kucoin.get_balance()
                                cost = amount * kucoin.get_price_info().buy_price * 1.001  # Prix + 0.1% de frais
                                
                                if balance.usdt_free < cost:
                                    message = f"❌ Solde insuffisant! Vous avez seulement {balance.usdt_free:.4f} USDT disponible."
                                    await query.message.reply_text(message)
                                    return

                                # Obtenir le prix actuel
                                price_info = kucoin.get_price_info()
                                current_price = price_info.current_price

                                # Créer l'ordre d'achat
                                order = kucoin.client.create_market_order(
                                    symbol='POLS-USDT',
                                    side='buy',
                                    size=amount
                                )
                                
                                if order:
                                    message = (
                                        f"✅ <b>Achat de {amount} POLS effectué sur KuCoin</b>\n\n"
                                        f"• Quantité: {amount} POLS\n"
                                        f"• Prix: <code>{current_price:.4f}</code> USDT\n"
                                        f"• Montant total: <code>{amount * current_price:.4f}</code> USDT\n"
                                        f"• Frais (0.1%): <code>{amount * current_price * 0.001:.4f}</code> USDT\n"
                                        f"• Coût total: <code>{amount * current_price * 1.001:.4f}</code> USDT\n\n"
                                        f"🔗 <a href='https://www.kucoin.com/trade/POLS-USDT'>Voir l'ordre sur KuCoin</a>"
                                    )
                                else:
                                    message = "❌ Erreur lors de la création de l'ordre d'achat"
                                    
                            await query.message.reply_text(message, parse_mode=ParseMode.HTML)
                            
                        except Exception as e:
                            error_message = f"❌ Erreur lors de l'opération: {str(e)}"
                            logging.error(error_message)
                            await query.message.reply_text(error_message)
                else:  # pancakeswap
                    pancakeswap = context.bot_data.get('pancakeswap')
                    if pancakeswap:
                        try:
                            if action == 'sell':
                                # Vérifier le solde disponible
                                balance = pancakeswap.get_balance()
                                if balance.pols_free < amount:
                                    message = f"❌ Solde insuffisant! Vous avez seulement {balance.pols_free:.4f} POLS disponible."
                                    await query.message.reply_text(message)
                                    return

                                # Obtenir le prix actuel
                                price_info = pancakeswap.get_price_info()
                                current_price = price_info.current_price

                                # Créer l'ordre de vente
                                order = pancakeswap.create_market_sell_order(amount)
                                
                                if order:
                                    message = (
                                        f"✅ <b>Vente de {amount} POLS effectuée sur PancakeSwap</b>\n\n"
                                        f"• Quantité: {amount} POLS\n"
                                        f"• Prix: <code>{current_price:.4f}</code> USDT\n"
                                        f"• Montant total: <code>{amount * current_price:.4f}</code> USDT\n"
                                        f"• Frais (0.25%): <code>{amount * current_price * 0.0025:.4f}</code> USDT\n"
                                        f"• Montant net: <code>{amount * current_price * 0.9975:.4f}</code> USDT\n\n"
                                        f"🔗 <a href='https://bscscan.com/tx/{order}'>Voir la transaction sur BSCScan</a>"
                                    )
                                else:
                                    message = "❌ Erreur lors de la création de l'ordre de vente"
                            else:  # buy
                                # Vérifier le solde USDT disponible
                                balance = pancakeswap.get_balance()
                                cost = amount * pancakeswap.get_price_info().buy_price * 1.0025  # Prix + 0.25% de frais
                                
                                if balance.usdt_free < cost:
                                    message = f"❌ Solde insuffisant! Vous avez seulement {balance.usdt_free:.4f} USDT disponible."
                                    await query.message.reply_text(message)
                                    return

                                # Obtenir le prix actuel
                                price_info = pancakeswap.get_price_info()
                                current_price = price_info.current_price

                                # Créer l'ordre d'achat
                                order = pancakeswap.create_market_buy_order(amount)
                                
                                if order:
                                    message = (
                                        f"✅ <b>Achat de {amount} POLS effectué sur PancakeSwap</b>\n\n"
                                        f"• Quantité: {amount} POLS\n"
                                        f"• Prix: <code>{current_price:.4f}</code> USDT\n"
                                        f"• Montant total: <code>{amount * current_price:.4f}</code> USDT\n"
                                        f"• Frais (0.25%): <code>{amount * current_price * 0.0025:.4f}</code> USDT\n"
                                        f"• Coût total: <code>{amount * current_price * 1.0025:.4f}</code> USDT\n\n"
                                        f"🔗 <a href='https://bscscan.com/tx/{order}'>Voir la transaction sur BSCScan</a>"
                                    )
                                else:
                                    message = "❌ Erreur lors de la création de l'ordre d'achat"
                                    
                            await query.message.reply_text(message, parse_mode=ParseMode.HTML)
                            
                        except Exception as e:
                            error_message = f"❌ Erreur lors de l'opération: {str(e)}"
                            logging.error(error_message)
                            await query.message.reply_text(error_message)
                
                # Nettoyer les données utilisateur
                context.user_data.pop('amount', None)
                context.user_data.pop('action', None)
                context.user_data.pop('awaiting_amount', None)
            
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
            # Filtrer les messages contenant l'erreur spécifique
            if "KucoinAPIException 400201" in message:
                logging.info("Notification d'erreur KucoinAPIException 400201 ignorée.")
                return
            
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

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les messages reçus"""
        try:
            user_id = update.effective_user.id
            if not self.is_user_authorized(user_id):
                await update.message.reply_text(
                    "❌ Désolé, vous n'êtes pas autorisé à utiliser ce bot.\n"
                    "Contactez l'administrateur pour obtenir l'accès."
                )
                logging.warning(f"Tentative d'accès non autorisée de l'utilisateur {user_id}")
                return
                
            message = update.message.text
            
            # Si on attend un montant pour une opération d'achat/vente
            if context.user_data.get('awaiting_amount'):
                try:
                    amount = float(message)
                    if amount <= 0:
                        await update.message.reply_text("❌ Le montant doit être supérieur à 0")
                        return
                        
                    context.user_data['amount'] = amount
                    action = context.user_data['action']
                    
                    # Récupérer les prix sur les deux exchanges
                    kucoin = context.bot_data.get('kucoin')
                    pancakeswap = context.bot_data.get('pancakeswap')
                    
                    if kucoin and pancakeswap:
                        kucoin_price = kucoin.get_price_info()
                        pancake_price = pancakeswap.get_price_info()
                        
                        if action == 'sell':
                            # Calculer les revenus potentiels sur chaque exchange
                            kucoin_revenue = amount * kucoin_price.sell_price * (1 - 0.001)  # 0.1% de frais
                            pancake_revenue = amount * pancake_price.sell_price * (1 - 0.0025)  # 0.25% de frais
                            
                            message = (
                                f"💰 <b>Vente de {amount} POLS</b>\n\n"
                                f"<b>KuCoin:</b>\n"
                                f"• Prix de vente: <code>{kucoin_price.sell_price:.4f}</code> USDT\n"
                                f"• Frais (0.1%): <code>{amount * kucoin_price.sell_price * 0.001:.4f}</code> USDT\n"
                                f"• Revenu net: <code>{kucoin_revenue:.4f}</code> USDT\n\n"
                                f"<b>PancakeSwap:</b>\n"
                                f"• Prix de vente: <code>{pancake_price.sell_price:.4f}</code> USDT\n"
                                f"• Frais (0.25%): <code>{amount * pancake_price.sell_price * 0.0025:.4f}</code> USDT\n"
                                f"• Revenu net: <code>{pancake_revenue:.4f}</code> USDT\n\n"
                                f"<b>Différence:</b> <code>{abs(kucoin_revenue - pancake_revenue):.4f}</code> USDT"
                            )
                            
                            # Ajouter des boutons pour choisir l'exchange
                            keyboard = [
                                [
                                    InlineKeyboardButton("Vendre sur KuCoin", callback_data=f"sell_kucoin_{amount}"),
                                    InlineKeyboardButton("Vendre sur PancakeSwap", callback_data=f"sell_pancake_{amount}")
                                ]
                            ]
                        else:  # buy
                            # Calculer les coûts potentiels sur chaque exchange
                            kucoin_cost = amount * kucoin_price.buy_price * (1 + 0.001)  # 0.1% de frais
                            pancake_cost = amount * pancake_price.buy_price * (1 + 0.0025)  # 0.25% de frais
                            
                            message = (
                                f"🛒 <b>Achat de {amount} POLS</b>\n\n"
                                f"<b>KuCoin:</b>\n"
                                f"• Prix d'achat: <code>{kucoin_price.buy_price:.4f}</code> USDT\n"
                                f"• Frais (0.1%): <code>{amount * kucoin_price.buy_price * 0.001:.4f}</code> USDT\n"
                                f"• Coût total: <code>{kucoin_cost:.4f}</code> USDT\n\n"
                                f"<b>PancakeSwap:</b>\n"
                                f"• Prix d'achat: <code>{pancake_price.buy_price:.4f}</code> USDT\n"
                                f"• Frais (0.25%): <code>{amount * pancake_price.buy_price * 0.0025:.4f}</code> USDT\n"
                                f"• Coût total: <code>{pancake_cost:.4f}</code> USDT\n\n"
                                f"<b>Différence:</b> <code>{abs(kucoin_cost - pancake_cost):.4f}</code> USDT"
                            )
                            
                            # Ajouter des boutons pour choisir l'exchange
                            keyboard = [
                                [
                                    InlineKeyboardButton("Acheter sur KuCoin", callback_data=f"buy_kucoin_{amount}"),
                                    InlineKeyboardButton("Acheter sur PancakeSwap", callback_data=f"buy_pancake_{amount}")
                                ]
                            ]
                            
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
                        
                except ValueError:
                    await update.message.reply_text("❌ Veuillez entrer un nombre valide")
                return

        except Exception as e:
            logging.error(f"Erreur lors de la gestion du message: {e}")
            await update.message.reply_text("❌ Erreur lors de la gestion du message")

        # Met à jour l'historique des prix à chaque minute
        strategy.update_price_history()
        await asyncio.sleep(60) 