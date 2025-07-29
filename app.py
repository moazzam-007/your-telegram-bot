import os
import logging
from flask import Flask, request, jsonify
import asyncio
import json

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Get configuration from environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7643897489:AAEw_iLZgsqd4Beb4CPQGPwfMIzGhaOuW5E')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 5000))

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

# Initialize bot application (lazy loading to avoid import issues)
bot_application = None

def get_bot_application():
    """Lazy initialization of bot application"""
    global bot_application
    if bot_application is None:
        try:
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
            from bot_handlers import start_handler, message_handler, help_handler
            
            # Initialize Telegram bot application
            bot_application = Application.builder().token(BOT_TOKEN).build()
            
            # Add handlers
            bot_application.add_handler(CommandHandler("start", start_handler))
            bot_application.add_handler(CommandHandler("help", help_handler))
            bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
            
            logger.info("Bot application initialized successfully")
            
        except ImportError as e:
            logger.error(f"Import error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error initializing bot: {e}")
            raise
    
    return bot_application

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook requests from Telegram"""
    try:
        update_data = request.get_json()
        
        if update_data:
            from telegram import Update
            application = get_bot_application()
            update = Update.de_json(update_data, application.bot)
            asyncio.run(application.process_update(update))
            
        return jsonify({"status": "ok"})
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "message": "Amazon Affiliate Telegram Bot is running",
        "bot_token_set": bool(BOT_TOKEN),
        "webhook_url_set": bool(WEBHOOK_URL)
    })

@app.route('/', methods=['GET'])
def home():
    """Root endpoint"""
    return jsonify({
        "message": "Amazon Affiliate Telegram Bot is running! 🤖",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health"
        },
        "status": "active"
    })

@app.route('/set_webhook', methods=['POST'])
def manual_webhook_setup():
    """Manual webhook setup endpoint"""
    try:
        if not WEBHOOK_URL:
            return jsonify({"error": "WEBHOOK_URL not configured"}), 400
            
        application = get_bot_application()
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # Use synchronous approach for webhook setting
        import requests
        telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        response = requests.post(telegram_api_url, json={"url": webhook_url})
        
        if response.status_code == 200:
            logger.info(f"Webhook set successfully to: {webhook_url}")
            return jsonify({"status": "success", "webhook_url": webhook_url})
        else:
            logger.error(f"Failed to set webhook: {response.text}")
            return jsonify({"error": "Failed to set webhook"}), 500
            
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Initialize bot application on startup
    try:
        get_bot_application()
        logger.info("Bot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")
    
    # Set webhook for production
    if WEBHOOK_URL:
        try:
            import requests
            webhook_url = f"{WEBHOOK_URL}/webhook"
            telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            response = requests.post(telegram_api_url, json={"url": webhook_url}, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Webhook set successfully to: {webhook_url}")
            else:
                logger.warning(f"Failed to set webhook: {response.text}")
                
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
    
    # Run Flask app
    logger.info(f"Starting Flask app on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
