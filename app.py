import os
import logging
from flask import Flask, request, jsonify
import json
from telegram import Update
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback

# Configure logging with more details
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Changed to DEBUG for more info
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

# Global variables
bot_application = None
main_loop = None
executor = ThreadPoolExecutor(max_workers=2)

def initialize_bot_sync():
    """Initialize bot in the main thread with persistent event loop"""
    global bot_application, main_loop
    
    if bot_application is None:
        try:
            logger.info("Starting bot initialization...")
            
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
            from bot_handlers import start_handler, message_handler, help_handler
            
            # Create and set persistent event loop
            main_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(main_loop)
            
            # Initialize bot application
            bot_application = Application.builder().token(BOT_TOKEN).build()
            
            # Run initialization
            main_loop.run_until_complete(bot_application.initialize())
            
            # Add handlers
            bot_application.add_handler(CommandHandler("start", start_handler))
            bot_application.add_handler(CommandHandler("help", help_handler))
            bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
            
            logger.info("Bot application initialized successfully with persistent event loop")
            
        except Exception as e:
            logger.error(f"Error initializing bot: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    return bot_application

def process_update_in_main_loop(update_data):
    """Process update using the main event loop"""
    try:
        global bot_application, main_loop
        
        logger.debug(f"Processing update: {update_data}")
        
        if bot_application is None:
            logger.warning("Bot not initialized, initializing now...")
            initialize_bot_sync()
        
        # Create update object
        update = Update.de_json(update_data, bot_application.bot)
        logger.debug(f"Update object created: {update}")
        
        # Process update in main loop
        future = asyncio.run_coroutine_threadsafe(
            bot_application.process_update(update), 
            main_loop
        )
        
        # Wait for completion with timeout
        result = future.result(timeout=30)
        logger.debug(f"Update processed successfully: {result}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        logger.error(f"Update data: {update_data}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

# Initialize bot on startup
try:
    logger.info("Initializing bot on startup...")
    initialize_bot_sync()
    logger.info("Bot initialized successfully on startup")
except Exception as e:
    logger.error(f"Failed to initialize bot on startup: {e}")

# Webhook route - SYNC
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook requests from Telegram"""
    try:
        logger.debug("Webhook endpoint called")
        update_data = request.get_json()
        
        if update_data:
            logger.debug(f"Received update data: {update_data}")
            # Process in executor to avoid blocking
            future = executor.submit(process_update_in_main_loop, update_data)
            return jsonify({"status": "ok"})
        else:
            logger.warning("No data received in webhook")
            return jsonify({"status": "error", "message": "No data received"}), 400
            
    except Exception as e:
        logger.error(f"Error in webhook endpoint: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "message": "Amazon Affiliate Telegram Bot is running",
        "bot_token_set": bool(BOT_TOKEN),
        "webhook_url_set": bool(WEBHOOK_URL),
        "bot_initialized": bot_application is not None
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
    logger.info("Starting Flask app with initialized bot.")
    
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
