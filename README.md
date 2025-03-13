# Bot de Trading Kucoin avec Trailing Stop

Ce bot de trading surveille les marchés sur Kucoin et utilise une stratégie de trailing stop pour capturer les profits lors des hausses brutales de prix.

## Fonctionnalités

- Surveillance en temps réel des prix sur Kucoin
- Achat automatique à l'entrée
- Trailing stop de 2% activé après une hausse de 10%
- Gestion sécurisée des clés API via fichier .env

## Installation

1. Clonez ce dépôt
2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

## Configuration

1. Créez un compte sur Kucoin et générez vos clés API
2. Copiez le fichier `.env.example` vers `.env`
3. Remplissez vos clés API dans le fichier `.env` :
```
KUCOIN_API_KEY=votre_api_key_ici
KUCOIN_API_SECRET=votre_api_secret_ici
KUCOIN_API_PASSPHRASE=votre_api_passphrase_ici
```

## Utilisation

1. Configurez les paramètres dans `trading_bot.py` selon vos besoins :
   - `symbol` : La paire de trading (par défaut "BTC-USDT")
   - `initial_investment` : Montant initial en USDT
   - `profit_threshold` : Seuil de profit (par défaut 10%)
   - `trailing_distance` : Distance du trailing stop (par défaut 2%)

2. Lancez le bot :
```bash
python trading_bot.py
```

## Avertissement

Le trading de cryptomonnaies comporte des risques. Ce bot est fourni à titre éducatif uniquement. Utilisez-le à vos propres risques. 