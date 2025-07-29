import os
import logging
from flask import Flask, request, jsonify
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import asyncio
from concurrent.futures import ThreadPoolExecutor
import traceback
import threading
import queue
import time

# Configure logging with more details
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

# Global variables
bot_application = None
update_queue = queue.Queue()
bot_thread = None

def initialize_bot():
    """Initialize bot application"""
    global bot_application
    
    try:
        logger.info("Starting bot initialization...")
        from bot_handlers import start_handler, message_handler, help_handler
        
        # Initialize bot application
        bot_application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        bot_application.add_handler(CommandHandler("start", start_handler))
        bot_application.add_handler(CommandHandler("help", help_handler))
        bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        logger.info("Bot application initialized successfully")
        return bot_application
        
    except Exception as e:
        logger.error(f"Error initializing bot: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

async def process_single_update(update_data):
    """Process a single update"""
    try:
        global bot_application
        
        if bot_application is None:
            logger.error("Bot application not initialized")
            return False
            
        # Create update object
        update = Update.de_json(update_data, bot_application.bot)
        
        # Initialize bot if not done
        if not bot_application.bot.token:
            await bot_application.initialize()
            
        # Process update
        await bot_application.process_update(update)
        logger.info("Update processed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def bot_worker():
    """Background worker for processing updates"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Initialize bot in the worker thread
        loop.run_until_complete(bot_application.initialize())
        logger.info("Bot initialized in worker thread")
        
        while True:
            try:
                # Get update from queue with timeout
                update_data = update_queue.get(timeout=1)
                
                # Process the update
                loop.run_until_complete(process_single_update(update_data))
                
                # Mark task as done
                update_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in bot worker: {e}")
                
    except Exception as e:
        logger.error(f"Fatal error in bot worker: {e}")
    finally:
        loop.close()

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook from Telegram"""
    try:
        update_data = request.get_json()
        
        if not update_data:
            logger.warning("No data received in webhook")
            return jsonify({"status": "error", "message": "No data received"}), 400
            
        logger.info(f"Received update: {update_data.get('update_id', 'unknown')}")
        
        # Add update to queue for processing
        update_queue.put(update_data)
        
        return jsonify({"status": "ok"})
        
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
        "bot_initialized": bot_application is not None,
        "queue_size": update_queue.qsize()
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

def start_bot_worker():
    """Start the bot worker thread"""
    global bot_thread
    
    if bot_thread is None or not bot_thread.is_alive():
        bot_thread = threading.Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("Bot worker thread started")

if __name__ == '__main__':
    # Initialize bot
    initialize_bot()
    
    # Start bot worker thread
    start_bot_worker()
    
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
    
    # Initialize bot and start worker when imported by Gunicorn
    if bot_application is None:
        initialize_bot()
    start_bot_worker()
