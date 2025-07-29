import os

class Config:
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7643897489:AAEw_iLZgsqd4Beb4CPQGPwfMIzGhaOuW5E')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    
    # Server Configuration
    PORT = int(os.getenv('PORT', 5000))
    HOST = '0.0.0.0'
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Amazon Affiliate Configuration
    AFFILIATE_TAG = "budgetlooks08-21"
    
    # Request Configuration
    REQUEST_TIMEOUT = 10
    
    # Supported Amazon Domains
    SUPPORTED_DOMAINS = [
        'amazon.com', 'amazon.in', 'amazon.co.uk',
        'amazon.de', 'amazon.fr', 'amazon.it',
        'amazon.es', 'amazon.ca', 'amazon.com.mx'
    ]
