import os
import logging
from flask import Flask, request, jsonify
# import asyncio # Ab iski direct zaroorat nahi padegi for running coroutines
import json
from telegram import Update
from flask_asyncio import FlaskAsyncio # Naya import

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
FlaskAsyncio(app) # Flask-Asyncio ko app ke saath initialize karein

# Get configuration from environment variables
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_ACTUAL_BOT_TOKEN_HERE') 
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
PORT = int(os.getenv('PORT', 5000))

if not BOT_TOKEN or BOT_TOKEN == 'YOUR_ACTUAL_BOT_TOKEN_HERE':
    logger.error("TELEGRAM_BOT_TOKEN environment variable is required and should be set on Render.")
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required and correctly set.")

# Initialize bot application (lazy loading to avoid import issues)
bot_application = None

# get_bot_application ab bhi async rahega
async def get_bot_application():
    """Lazy initialization of bot application and ensures it's properly initialized."""
    global bot_application
    if bot_application is None:
        try:
            from telegram.ext import Application, CommandHandler, MessageHandler, filters
            from bot_handlers import start_handler, message_handler, help_handler
            
            bot_application = Application.builder().token(BOT_TOKEN).build()
            await bot_application.initialize() 

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

# Webhook route ko async banaya gaya
@app.route('/webhook', methods=['POST'])
async def webhook(): # <- Make this function async
    """Handle incoming webhook requests from Telegram"""
    try:
        update_data = request.get_json()
        
        if update_data:
            application = await get_bot_application() # <- await karein
            
            update = Update.de_json(update_data, application.bot)
            await application.process_update(update) # <- await karein
            
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
async def health_check(): # <- Make this function async (optional but good practice if it ever uses async ops)
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "message": "Amazon Affiliate Telegram Bot is running",
        "bot_token_set": bool(BOT_TOKEN),
        "webhook_url_set": bool(WEBHOOK_URL)
    })

@app.route('/', methods=['GET'])
async def home(): # <- Make this function async (optional)
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
async def manual_webhook_setup(): # <- Make this function async
    """Manual webhook setup endpoint"""
    try:
        if not WEBHOOK_URL:
            return jsonify({"error": "WEBHOOK_URL not configured"}), 400
            
        application = await get_bot_application() # <- await karein
        webhook_url = f"{WEBHOOK_URL}/webhook"
        
        # requests library synchronous hai, isko aise hi rehne dein
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
    # Initializing bot_application outside of the Flask app context.
    # Gunicorn will manage worker processes, so this block might behave differently.
    # Best practice is to ensure get_bot_application() is called when a request comes in.
    # We remove asyncio.run() here as Flask-Asyncio will manage the loop.
    try:
        # Instead of directly calling asyncio.run(get_bot_application())
        # The bot application should be initialized in a way that Flask-Asyncio can manage it.
        # Since get_bot_application is lazy, it will be called on first webhook hit.
        logger.info("Starting Flask app. Bot initialization will happen on first request.")
    except Exception as e:
        logger.error(f"Failed to prepare bot initialization: {e}")
    
    # Set webhook for production
    # This block should ideally run only once on deployment, not on every app start by Gunicorn workers.
    # You might want to remove this block from app.py and instead call /set_webhook endpoint once manually after deploy.
    # Or, use Render's "Deploy Hook" feature to run a one-time script for webhook setup.
    if WEBHOOK_URL:
        try:
            import requests
            webhook_url = f"{WEBHOOK_URL}/webhook"
            telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            
            # This part should be non-blocking or happen in a separate thread/process
            # for a true async Flask app, but for now we'll keep it as is,
            # trusting it mostly runs once on initial setup.
            response = requests.post(telegram_api_url, json={"url": webhook_url}, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Webhook set successfully to: {webhook_url}")
            else:
                logger.warning(f"Failed to set webhook: {response.text}")
                
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
    
    # Run Flask app
    logger.info(f"Starting Flask app on port {PORT}")
    # Flask-Asyncio provides an async run method, but for Gunicorn,
    # you just use 'gunicorn app:app' and Flask-Asyncio integrates automatically.
    # app.run(host='0.0.0.0', port=PORT, debug=False) # This is not needed when using Gunicorn
