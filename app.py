import os
import logging
from flask import Flask, request, jsonify
# import asyncio # Ab iski zaroorat nahi
import json
from telegram import Update
# from flask_asyncio import FlaskAsyncio # Is line ko hata dein

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
# FlaskAsyncio(app) # Is line ko hata dein

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

# Webhook route async hi rahega
@app.route('/webhook', methods=['POST'])
async def webhook(): # <- Ab yahan asyncio.run() nahi hoga
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
async def health_check(): # <- async rehne dein
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "message": "Amazon Affiliate Telegram Bot is running",
        "bot_token_set": bool(BOT_TOKEN),
        "webhook_url_set": bool(WEBHOOK_URL)
    })

@app.route('/', methods=['GET'])
async def home(): # <- async rehne dein
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
async def manual_webhook_setup(): # <- async rehne dein
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
    # Gunicorn with Uvicorn worker will manage worker processes.
    # get_bot_application will be called on first request for each worker.
    logger.info("Starting Flask app. Bot initialization will happen on first request.")
    
    # Set webhook for production - This block should ideally be handled externally
    # or via a Render Deploy Hook to avoid running on every worker restart.
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
    
    # Flask app will be run by Gunicorn, so app.run() is commented out.
    logger.info(f"Flask app is configured to be run by Gunicorn on port {PORT}")
    # app.run(host='0.0.0.0', port=PORT, debug=False)
