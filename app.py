import os
import logging
from flask import Flask, request, jsonify
import json
from telegram import Update
import threading
import asyncio

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Get configuration from environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_ACTUAL_BOT_TOKEN_HERE')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 5000))

if not BOT_TOKEN or BOT_TOKEN == 'YOUR_ACTUAL_BOT_TOKEN_HERE':
    logger.error("TELEGRAM_BOT_TOKEN environment variable is required and should be set on Render.")
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required and correctly set.")

# Initialize bot application (lazy loading to avoid import issues)
bot_application = None

def get_bot_application():
    """Lazy initialization of bot application and ensures it's properly initialized."""
    global bot_application
    if bot_application is None:
        try:
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
            from bot_handlers import start_handler, message_handler, help_handler
            
            bot_application = Application.builder().token(BOT_TOKEN).build()
            
            # Run initialization in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(bot_application.initialize())
            
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

def process_update_sync(update_data):
    """Process update in sync mode using asyncio"""
    try:
        application = get_bot_application()
        update = Update.de_json(update_data, application.bot)
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the async process_update
        loop.run_until_complete(application.process_update(update))
        loop.close()
        
        return True
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return False

# Webhook route - NOW SYNC
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook requests from Telegram"""
    try:
        update_data = request.get_json()
        if update_data:
            # Process update in a separate thread to avoid blocking
            thread = threading.Thread(target=process_update_sync, args=(update_data,))
            thread.start()
            return jsonify({"status": "ok"})
        else:
            return jsonify({"status": "error", "message": "No data received"}), 400
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

        webhook_url = f"{WEBHOOK_URL}/webhook"
        
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
    logger.info("Starting Flask app. Bot initialization will happen on first request.")
    
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
    
    logger.info(f"Flask app is configured to be run by Gunicorn on port {PORT}")
