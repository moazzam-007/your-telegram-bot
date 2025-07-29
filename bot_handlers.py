import re
import logging
import asyncio
from amazon_scraper import AmazonScraper
from url_shortener import URLShortener

logger = logging.getLogger(__name__)

# Initialize services
amazon_scraper = AmazonScraper()
url_shortener = URLShortener()

async def start_handler(update, context):
    """Handle /start command"""
    try:
        welcome_message = """
🛍️ Welcome to Amazon Affiliate Bot!

Mein aapka shopping assistant hun! 😊

✨ **Kya kar sakta hun:**

• Amazon product links bhejo mujhe
• Main product ki image aur details nikaal dunga
• Affiliate link banake dunga (budgetlooks08-21 tag ke saath)
• Shortened URL provide karunga

📝 **Kaise use kare:**
Bas koi bhi Amazon product ka link bhej do, main sab kuch handle kar dunga!

Type /help for more information! 🚀
"""
        
        await update.message.reply_text(welcome_message)
        logger.info(f"Start command handled for user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error in start_handler: {e}")
        try:
            await update.message.reply_text("Sorry, kuch technical problem hai! Please try again.")
        except:
            pass

async def help_handler(update, context):
    """Handle /help command"""
    try:
        help_message = """
🔧 **Help & Instructions:**

**Supported Amazon domains:**
• amazon.com
• amazon.in
• amazon.co.uk

**How to use:**
1️⃣ Copy any Amazon product URL
2️⃣ Send it to me in chat
3️⃣ I'll extract product image & details
4️⃣ Generate affiliate link with budgetlooks08-21 tag
5️⃣ Provide shortened URL via TinyURL

**Example:**
Send: https://amazon.in/dp/B08N5WRWNW
Get: Product image + affiliate link

Need more help? Just ask! 💬
"""
        
        await update.message.reply_text(help_message)
        logger.info(f"Help command handled for user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error in help_handler: {e}")
        try:
            await update.message.reply_text("Sorry, help load nahi ho paya! Please try again.")
        except:
            pass

async def message_handler(update, context):
    """Handle text messages"""
    try:
        message_text = update.message.text
        user_id = update.effective_user.id
        
        logger.info(f"Message received from user {user_id}: {message_text[:50]}...")
        
        # Check if message contains Amazon URL
        amazon_url_pattern = r'https?://(?:www\.)?amazon\.[a-z.]{2,6}/(?:[^/]+/)?(?:dp|gp/product)/([A-Z0-9]{10})'
        match = re.search(amazon_url_pattern, message_text)
        
        if match:
            await handle_amazon_url(update, context, message_text)
        else:
            await handle_general_message(update, context, message_text)
            
    except Exception as e:
        logger.error(f"Error in message_handler: {e}")
        try:
            await update.message.reply_text("Sorry, message process nahi ho paya! Please try again.")
        except:
            pass

async def handle_amazon_url(update, context, url):
    """Handle Amazon product URL"""
    try:
        processing_msg = await update.message.reply_text("🔍 Processing kar raha hun... Wait karo! ⏳")
        
        # Extract product information (run in thread to avoid blocking)
        loop = asyncio.get_event_loop()
        product_info = await loop.run_in_executor(None, amazon_scraper.extract_product_info, url)
        
        if not product_info:
            await processing_msg.edit_text(
                "😔 Sorry! Product information extract nahi kar paya.\n"
                "Kya aap sure hain ki ye valid Amazon product link hai? 🤔"
            )
            return
        
        # Generate affiliate link
        affiliate_url = amazon_scraper.generate_affiliate_link(url)
        
        # Shorten the affiliate link (run in thread)
        shortened_url = await loop.run_in_executor(None, url_shortener.shorten_url, affiliate_url)
        
        # Prepare response message
        response_message = f"🛍️ **{product_info['title']}**\n\n"
        
        if product_info.get('price'):
            response_message += f"💰 **Price:** {product_info['price']}\n\n"
            
        response_message += f"🔗 **Yahan hai aapka affiliate link:**\n{shortened_url}\n\n"
        response_message += "✨ Is link se purchase karne par mujhe commission milegi! Thank you! 😊"
        
        # Send product image if available
        if product_info.get('image_url'):
            try:
                await update.message.reply_photo(
                    photo=product_info['image_url'],
                    caption=response_message,
                    parse_mode='Markdown'
                )
                await processing_msg.delete()
            except Exception as e:
                logger.error(f"Error sending image: {e}")
                await processing_msg.edit_text(response_message, parse_mode='Markdown')
        else:
            await processing_msg.edit_text(response_message, parse_mode='Markdown')
            
        logger.info(f"Successfully processed Amazon URL for user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error handling Amazon URL: {e}")
        try:
            await update.message.reply_text(
                "😞 Kuch technical problem aa gayi hai!\n"
                "Please thodi der baad try karo ya dusra link bhejo. 🔧"
            )
        except:
            pass

async def handle_general_message(update, context, message):
    """Handle general conversation"""
    try:
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'namaste']):
            response = "Hey there! 👋 Main Amazon affiliate bot hun!\nAmazon ka koi product link bhejo! 🛍️✨"
        elif any(word in message_lower for word in ['thanks', 'thank you', 'shukriya']):
            response = "Welcome! Khushi hui help karke! 😊\nAur Amazon products chahiye toh link bhej dena! 🛒"
        elif any(word in message_lower for word in ['how', 'kaise', 'kya']):
            response = "Main Amazon affiliate bot hun! 🤖\n\n📝 **Kaise use kare:**\n1. Amazon product link bhejo\n2. Main image extract karunga\n3. Affiliate link banaunga\n4. Shortened URL dunga\n\nTry karo! 🚀"
        elif 'amazon' in message_lower:
            response = "Haan! Amazon ke liye hi bana hun! 🛍️\nKoi bhi Amazon product ka link bhejo! ⚡"
        else:
            response = "Main sirf Amazon product links handle karta hun! 🛒\n\nKoi Amazon product ka link bhejo jaise:\n• amazon.in/dp/PRODUCT_ID\n\nMain image aur affiliate link banake dunga! 😊"
            
        await update.message.reply_text(response)
        logger.info(f"General message handled for user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error in handle_general_message: {e}")
        try:
            await update.message.reply_text("Sorry, samajh nahi paya! Amazon link bhejo please! 🤖")
        except:
            pass
