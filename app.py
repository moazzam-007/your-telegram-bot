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
import requests

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
bot_initialized = False
webhook_set = False

def set_telegram_webhook():
    """Set Telegram webhook"""
    global webhook_set
    
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL not set, cannot configure webhook")
        return False
        
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        
        logger.info(f"Setting webhook to: {webhook_url}")
        
        response = requests.post(
            telegram_api_url, 
            json={"url": webhook_url},
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                logger.info(f"✅ Webhook set successfully to: {webhook_url}")
                webhook_set = True
                return True
            else:
                logger.error(f"❌ Telegram API error: {result}")
                return False
        else:
            logger.error(f"❌ HTTP error setting webhook: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception setting webhook: {e}")
        return False

def get_bot_handlers():
    """Import and return bot handlers"""
    try:
        from bot_handlers import start_handler, message_handler, help_handler
        logger.info("✅ Bot handlers imported successfully")
        return start_handler, message_handler, help_handler
    except ImportError as e:
        logger.error(f"Failed to import bot handlers: {e}")
        # Fallback handlers
        async def fallback_start(update, context):
            await update.message.reply_text("🤖 Bot is working! Send me Amazon links!")
            logger.info("Fallback start handler executed")
        
        async def fallback_message(update, context):
            await update.message.reply_text("I received your message! Send Amazon product links for affiliate conversion!")
            logger.info("Fallback message handler executed")
            
        async def fallback_help(update, context):
            await update.message.reply_text("Send me Amazon product URLs and I'll create affiliate links for you!")
            logger.info("Fallback help handler executed")
            
        return fallback_start, fallback_message, fallback_help

def initialize_bot():
    """Initialize bot application"""
    global bot_application, bot_initialized
    
    try:
        logger.info("🚀 Starting bot initialization...")
        
        # Get handlers
        start_handler, message_handler, help_handler = get_bot_handlers()
        
        # Initialize bot application
        bot_application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        bot_application.add_handler(CommandHandler("start", start_handler))
        bot_application.add_handler(CommandHandler("help", help_handler))
        bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        bot_initialized = True
        logger.info("✅ Bot application initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error initializing bot: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        bot_initialized = False
        return False

async def process_single_update(update_data):
    """Process a single update"""
    try:
        global bot_application
        
        if bot_application is None:
            logger.error("❌ Bot application not initialized")
            return False
            
        update_id = update_data.get('update_id', 'unknown')
        logger.info(f"🔄 Starting to process update: {update_id}")
        
        # Create update object
        update = Update.de_json(update_data, bot_application.bot)
        logger.info(f"✅ Update object created for: {update_id}")
        
        # Process update
        await bot_application.process_update(update)
        logger.info(f"✅ Update {update_id} processed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error processing update: {e}")
        logger.error(f"Update data: {update_data}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def bot_worker():
    """Background worker for processing updates"""
    global bot_application, bot_initialized
    
    logger.info("🚀 Bot worker thread started")
    
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Initialize the bot application if needed
        if bot_application and not bot_initialized:
            logger.info("🔄 Initializing bot in worker thread...")
            if not initialize_bot():
                logger.error("❌ Failed to initialize bot in worker thread")
                return
        
        # Initialize the bot application
        if bot_application:
            logger.info("🔄 Initializing bot application in worker thread...")
            loop.run_until_complete(bot_application.initialize())
            logger.info("✅ Bot initialized successfully in worker thread")
        else:
            logger.error("❌ Bot application is None in worker thread")
            return
        
        # Main processing loop
        logger.info("🔄 Starting update processing loop...")
        processed_count = 0
        
        while True:
            try:
                # Get update from queue with timeout
                logger.debug("🔍 Waiting for updates in queue...")
                update_data = update_queue.get(timeout=3)
                
                update_id = update_data.get('update_id', 'unknown')
                logger.info(f"📥 Got update from queue: {update_id} (Total processed: {processed_count})")
                
                # Process the update with timeout
                try:
                    success = asyncio.wait_for(
                        process_single_update(update_data), 
                        timeout=30.0
                    )
                    success = loop.run_until_complete(success)
                except asyncio.TimeoutError:
                    logger.error(f"⏰ Timeout processing update {update_id}")
                    success = False
                
                if success:
                    processed_count += 1
                    logger.info(f"✅ Successfully processed update {update_id} (Total: {processed_count})")
                else:
                    logger.error(f"❌ Failed to process update {update_id}")
                
                # Mark task as done
                update_queue.task_done()
                
            except queue.Empty:
                # No updates in queue, continue waiting
                logger.debug("📭 No updates in queue, waiting...")
                continue
            except Exception as e:
                logger.error(f"❌ Error in bot worker loop: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                # Don't break the loop, continue processing
                
    except Exception as e:
        logger.error(f"💥 Fatal error in bot worker: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        try:
            loop.close()
            logger.info("🔚 Bot worker loop closed")
        except:
            pass

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook from Telegram"""
    try:
        update_data = request.get_json()
        
        if not update_data:
            logger.warning("⚠️ No data received in webhook")
            return jsonify({"status": "error", "message": "No data received"}), 400
            
        update_id = update_data.get('update_id', 'unknown')
        message_text = ""
        if 'message' in update_data and 'text' in update_data['message']:
            message_text = update_data['message']['text'][:50]
            
        logger.info(f"📨 Received update: {update_id} - Message: '{message_text}'")
        
        # Add update to queue for processing
        update_queue.put(update_data)
        logger.info(f"📋 Update {update_id} added to queue. Queue size: {update_queue.qsize()}")
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"❌ Error in webhook endpoint: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "message": "Amazon Affiliate Telegram Bot is running",
        "bot_token_set": bool(BOT_TOKEN and BOT_TOKEN != 'YOUR_ACTUAL_BOT_TOKEN_HERE'),
        "webhook_url_set": bool(WEBHOOK_URL),
        "webhook_configured": webhook_set,
        "bot_initialized": bot_initialized,
        "queue_size": update_queue.qsize(),
        "worker_thread_alive": bot_thread.is_alive() if bot_thread else False
    })

@app.route('/', methods=['GET'])
def home():
    """Root endpoint"""
    return jsonify({
        "message": "Amazon Affiliate Telegram Bot is running! 🤖",
        "endpoints": {
            "webhook": "/webhook (POST only)",
            "health": "/health",
            "debug": "/debug",
            "set_webhook": "/set_webhook"
        },
        "status": "active",
        "bot_status": "initialized" if bot_initialized else "not_initialized",
        "webhook_status": "configured" if webhook_set else "not_configured"
    })

@app.route('/debug', methods=['GET'])
def debug_info():
    """Debug endpoint"""
    return jsonify({
        "bot_initialized": bot_initialized,
        "bot_application_exists": bot_application is not None,
        "queue_size": update_queue.qsize(),
        "worker_thread_alive": bot_thread.is_alive() if bot_thread else False,
        "bot_token_length": len(BOT_TOKEN) if BOT_TOKEN else 0,
        "webhook_url": WEBHOOK_URL,
        "webhook_configured": webhook_set,
        "port": PORT,
        "bot_token_valid": BOT_TOKEN != 'YOUR_ACTUAL_BOT_TOKEN_HERE'
    })

@app.route('/set_webhook', methods=['POST', 'GET'])
def manual_webhook_setup():
    """Manual webhook setup endpoint"""
    try:
        result = set_telegram_webhook()
        
        if result:
            return jsonify({
                "status": "success", 
                "webhook_url": f"{WEBHOOK_URL}/webhook",
                "message": "Webhook configured successfully"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "Failed to configure webhook"
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Error in manual webhook setup: {e}")
        return jsonify({"error": str(e)}), 500

def start_bot_worker():
    """Start the bot worker thread"""
    global bot_thread
    
    if bot_thread is None or not bot_thread.is_alive():
        bot_thread = threading.Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        logger.info("🚀 Bot worker thread started")
        
        # Wait a moment for thread to start
        time.sleep(2)
        
        if bot_thread.is_alive():
            logger.info("✅ Bot worker thread is running")
        else:
            logger.error("❌ Bot worker thread failed to start")
    else:
        logger.info("ℹ️ Bot worker thread already running")

# Initialize when module is imported (for Gunicorn)
logger.info("🔧 Initializing application...")

# Initialize bot
if initialize_bot():
    logger.info("✅ Bot initialized successfully")
    
    # Start worker thread
    start_bot_worker()
    
    # Set webhook (important: do this after bot initialization)
    if WEBHOOK_URL:
        # Wait a bit for everything to initialize
        time.sleep(1)
        set_telegram_webhook()
    else:
        logger.warning("⚠️ WEBHOOK_URL not set, skipping webhook configuration")
else:
    logger.error("❌ Failed to initialize bot")

logger.info("🎉 Application ready!")

if __name__ == '__main__':
    logger.info(f"🚀 Flask app ready on port {PORT}")
