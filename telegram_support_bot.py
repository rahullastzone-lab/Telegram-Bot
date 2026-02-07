"""
# LastZone Support Bot
# --------------------
# A Telegram Support Bot for "LastZone" gaming platform.
# Built with python-telegram-bot v20+ (Async).

# INSTRUCTIONS:
# ------------
# 1. Install dependencies:
#    pip install python-telegram-bot
#
# 2. Add your BOT TOKEN:
#    Replace 'YOUR_BOT_TOKEN_HERE' in the Main Execution block below with your actual token
#    from BotFather.
#
# 3. Run the bot:
#    python telegram_support_bot.py
#
# Note: Ensure you are using Python 3.7+
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import io
import uuid

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# -------------------------------------------------------------------------------------
# SUPABASE SETUP (Via REST API)
# -------------------------------------------------------------------------------------
import httpx
import json

# REPLACE WITH YOUR ACTUAL KEYS
SUPABASE_URL = "https://jadbjketgcaoogpkieab.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImphZGJqa2V0Z2Nhb29ncGtpZWFiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY0OTg3NzUsImV4cCI6MjA4MjA3NDc3NX0.bLgpVQQQgS7QoB0ApCAXOh9hf1NoNl2IhhcF5laT_K0"

# HEADERS for Supabase
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates" # For upsert behavior
}

async def save_user_to_supabase(user_id, username, first_name):
    """Save user to Supabase using REST API"""
    url = f"{SUPABASE_URL}/rest/v1/telegram_users"
    data = {
        "id": user_id,
        "username": username,
        "first_name": first_name
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=data, headers=SUPABASE_HEADERS)
            # print("User saved to Supabase")
    except Exception as e:
        print(f"Error saving user: {e}")

async def create_support_ticket(user_id, issue_type, details):
    """Create a ticket in Supabase using REST API"""
    url = f"{SUPABASE_URL}/rest/v1/support_tickets"
    data = {
        "user_id": user_id,
        "issue_type": issue_type,
        "status": "open",
        "details": details
    }
    # Remove 'Prefer' header for simple insert if needed, relying on default
    headers = SUPABASE_HEADERS.copy()
    if "Prefer" in headers:
        del headers["Prefer"] # Default insert is fine

    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=data, headers=headers)
            # print("Ticket created in Supabase")
    except Exception as e:
        print(f"Error creating ticket: {e}")

async def upload_file_to_storage(file_content, file_name, content_type):
    """Upload file to Supabase Storage via REST API"""
    bucket = "support-files"
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{file_name}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": content_type
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Convert bytearray to bytes to ensure httpx treats it as body, not iterator
            response = await client.post(url, content=bytes(file_content), headers=headers)
            if response.status_code == 200:
                # Return Public URL
                return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{file_name}", None
            else:
                error_msg = f"Storage Upload Failed: {response.text}"
                print(error_msg)
                return None, error_msg
    except Exception as e:
        error_msg = f"Error uploading file: {e}"
        print(error_msg)
        return None, error_msg

async def log_message(user_id, message_type, content, file_url=None):
    """Log user message to Supabase"""
    url = f"{SUPABASE_URL}/rest/v1/support_messages"
    data = {
        "user_id": user_id,
        "message_type": message_type,
        "content": content,
        "file_url": file_url
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=data, headers=SUPABASE_HEADERS)
    except Exception as e:
        print(f"Error logging message: {e}")

# -------------------------------------------------------------------------------------
# BUTTON CALLBACK DATA CONSTANTS
# -------------------------------------------------------------------------------------
CB_DEPOSIT = 'deposit'
CB_WITHDRAW = 'withdraw'
CB_LOGIN = 'login'
CB_MATCH = 'match'
CB_TRANSACTION = 'transaction'
CB_ADMIN = 'admin'
CB_FAQ = 'faq'
CB_MAIN_MENU = 'main_menu'

# -------------------------------------------------------------------------------------
# KEYBOARD HELPER
# -------------------------------------------------------------------------------------
def get_main_menu_keyboard():
    """Returns the vertical inline keyboard as requested."""
    keyboard = [
        [InlineKeyboardButton("💰 Deposit Issues", callback_data=CB_DEPOSIT)],
        [InlineKeyboardButton("💸 Withdraw Problems", callback_data=CB_WITHDRAW)],
        [InlineKeyboardButton("🔐 Login / Account Help", callback_data=CB_LOGIN)],
        [InlineKeyboardButton("🎮 Match-Related Issues", callback_data=CB_MATCH)],
        [InlineKeyboardButton("📄 Transaction Not Showing", callback_data=CB_TRANSACTION)],
        [InlineKeyboardButton("👨💻 Contact Admin", callback_data=CB_ADMIN)],
        [InlineKeyboardButton("❓ FAQs", callback_data=CB_FAQ)],
        [InlineKeyboardButton("💬 Join WhatsApp Community", url="https://chat.whatsapp.com/CqntEdO4vRXDNbLC5cjZlE")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_button():
    """Returns a 'Back to Menu' button."""
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data=CB_MAIN_MENU)]]
    return InlineKeyboardMarkup(keyboard)

# -------------------------------------------------------------------------------------
# HANDLERS
# -------------------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command.
    Sends the welcome message and saves user to Supabase.
    """
    admin_welcome_text = (
        "👋 *Welcome to LastZone Support!*\n\n"
        "I am here to help you with your tournament and payment queries.\n"
        "Please select a topic from the menu below:"
    )
    
    user = update.effective_user
    
    # Save user to Supabase
    await save_user_to_supabase(user.id, user.username, user.first_name)

    # Send message
    await update.message.reply_text(
        text=admin_welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles callback queries. Logs tickets to Supabase.
    """
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    response_text = ""
    reply_markup = get_back_button()

    # Log the ticket/interaction in Supabase
    if data not in [CB_MAIN_MENU, CB_FAQ]:
        await create_support_ticket(user.id, data, f"User clicked {data}")

    if data == CB_DEPOSIT:
        response_text = (
            "*💰 Deposit Issues*\n\n"
            "Please upload the following details here:\n"
            "1. Your User ID\n"
            "2. Amount Deposited\n"
            "3. A clear screenshot of the payment\n\n"
            "Our team will verify and update your balance shortly."
        )
        
    elif data == CB_WITHDRAW:
        response_text = (
            "*💸 Withdraw Problems*\n\n"
            "Withdrawals are usually processed within **24 Hours**.\n"
            "If the status is 'Complete', please check your account statement.\n"
            "If 'Pending' for >24 hours, contact Admin."
        )

    elif data == CB_LOGIN:
        response_text = (
            "*🔐 Login / Account Help*\n\n"
            "• Forgot Password? Use the 'Forgot Password' link on the login page.\n"
            "• Account Blocked? Contact @lastzonecare immediately."
        )

    elif data == CB_MATCH:
        response_text = (
            "*🎮 Match-Related Issues*\n\n"
            "Please provide:\n"
            "• Match ID\n"
            "• Detailed description of the issue (e.g., scoring error, connection loss)."
        )

    elif data == CB_TRANSACTION:
        response_text = (
            "*📄 Transaction Not Showing*\n\n"
            "Sometimes banking networks are slow.\n"
            "Please wait up to **30 minutes**.\n"
            "If it still doesn't show, send us the Transaction Reference ID."
        )

    elif data == CB_ADMIN:
        response_text = (
            "*👨💻 Contact Admin*\n\n"
            "For urgent or unresolved issues, contact our official admin:\n"
            "👉 @lastzonecare"
        )

    elif data == CB_FAQ:
        response_text = (
            "*❓ Frequently Asked Questions*\n\n"
            "• **Min Deposit:** ₹1\n"
            "• **Min Withdrawal:** ₹50\n"
            "• **Withdrawal Time:** 24 Hours\n"
            "• **Support Hours:** 24/7 Live Support 🟢"
        )

    elif data == CB_MAIN_MENU:
        response_text = (
            "👋 *Welcome to LastZone Support!*\n\n"
            "How can we assist you today? Select an option below:"
        )
        reply_markup = get_main_menu_keyboard()

    else:
        response_text = "Unknown selection. Please type /start to restart."

    await query.edit_message_text(
        text=response_text,
        reply_markup=reply_markup,
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles text and photo messages from the user.
    """
    user = update.effective_user
    
    # Ensure user exists in DB first (in case they didn't start)
    await save_user_to_supabase(user.id, user.username, user.first_name)

    message_type = "text"
    content = ""
    file_url = None

    if update.message.text:
        message_type = "text"
        content = update.message.text
        
        # Simple auto-reply only if it's not a command
        if not content.startswith('/'):
            await update.message.reply_text("✅ Message received! Our support team will check it.")

    elif update.message.photo:
        message_type = "photo"
        content = update.message.caption if update.message.caption else "No caption"
        
        # Get the largest photo (highest resolution)
        photo_file = await update.message.photo[-1].get_file()
        
        # Download file to memory
        file_byte_array = await photo_file.download_as_bytearray()
        
        # Generate a unique filename
        file_ext = ".jpg" # Telegram photos are usually jpg
        file_name = f"{user.id}/{uuid.uuid4()}{file_ext}"
        
        # Upload to Supabase
        await update.message.reply_text("🔄 Uploading your screenshot...")
        file_url, error = await upload_file_to_storage(file_byte_array, file_name, "image/jpeg")
        
        if file_url:
            await update.message.reply_text("✅ Screenshot uploaded successfully!")
        else:
            await update.message.reply_text(f"⚠️ Failed to upload screenshot. Error: {error}")

    # Log to Supabase
    await log_message(user.id, message_type, content, file_url)

# -------------------------------------------------------------------------------------
# MAIN EXECUTION
# -------------------------------------------------------------------------------------

if __name__ == '__main__':
    # Load token from environment variable
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in .env file.")
        exit(1)

    print("Starting LastZone Support Bot...")
    
    # Create the Application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Message Handler (Text & Photos) - Must be after commands
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) | filters.PHOTO, handle_message))

    # Run the bot (Polling)
    print("Bot is polling...")
    app.run_polling()

