import os

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    PORT = int(os.getenv('PORT', 5000))
    HOST = '0.0.0.0'
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    AFFILIATE_TAG = "budgetlooks08-21"
    REQUEST_TIMEOUT = 10
