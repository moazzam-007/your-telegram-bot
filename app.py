import os
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import asyncio
from bot_handlers import start_handler, message_handler, help_handler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Get configuration from environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 5000))

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

# Initialize Telegram bot application
application = Application.builder().token(BOT_TOKEN).build()

# Add handlers
application.add_handler(CommandHandler("start", start_handler))
application.add_handler(CommandHandler("help", help_handler))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook requests from Telegram"""
    try:
        update_data = request.get_json()
        
        if update_data:
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
        "message": "Amazon Affiliate Telegram Bot is running"
    })

@app.route('/', methods=['GET'])
def home():
    """Root endpoint"""
    return jsonify({
        "message": "Amazon Affiliate Telegram Bot is running! 🤖",
        "endpoints": {
            "webhook": "/webhook",
            "health": "/health"
        }
    })

async def set_webhook():
    """Set webhook URL for the bot"""
    try:
        if WEBHOOK_URL:
            webhook_url = f"{WEBHOOK_URL}/webhook"
            await application.bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to: {webhook_url}")
        else:
            logger.warning("WEBHOOK_URL not set")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")

if __name__ == '__main__':
    # Set webhook for production
    if WEBHOOK_URL:
        try:
            asyncio.run(set_webhook())
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=PORT, debug=False)
