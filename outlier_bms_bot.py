import logging
import requests
import base64
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# Load environment variables
load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# M-PESA API Credentials
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
SHORTCODE = os.getenv("SHORTCODE")
PASSKEY = os.getenv("PASSKEY")
CALLBACK_URL = os.getenv("CALLBACK_URL")

# Product Information
PRODUCT_NAME = "Outlier BMS"
PRODUCT_PRICE = 250
PRODUCT_PDF_URL = "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID"

# Set up logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def get_access_token():
    auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    auth_headers = {
        "Authorization": "Basic " + base64.b64encode(f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()).decode()
    }
    response = requests.get(auth_url, headers=auth_headers)
    return response.json()["access_token"]

def initiate_stk_push(phone_number, user_id, context):
    access_token = get_access_token()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(f"{SHORTCODE}{PASSKEY}{timestamp}".encode()).decode()
    
    payload = {
        "BusinessShortCode": SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": PRODUCT_PRICE,
        "PartyA": phone_number,
        "PartyB": SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": CALLBACK_URL,
        "AccountReference": "M-PESA Payment",
        "TransactionDesc": f"Payment for {PRODUCT_NAME}"
    }

    stk_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(stk_url, json=payload, headers=headers)
    result = response.json()
    if result.get("ResponseCode") == "0":
        context.user_data["pending_payment"] = {
            "user_id": user_id
        }
        return True
    return False

def start(update: Update, context: CallbackContext):
    update.message.reply_text(f"The price for {PRODUCT_NAME} is {PRODUCT_PRICE} KES.\nPlease enter your M-PESA phone number to proceed.")

def request_payment(update: Update, context: CallbackContext):
    phone_number = update.message.text.strip()
    if not phone_number.startswith("254"):
        update.message.reply_text("Please enter a valid M-PESA number starting with 254.")
        return
    
    if initiate_stk_push(phone_number, update.message.chat_id, context):
        update.message.reply_text("Payment request sent! Enter your M-PESA PIN to complete the transaction.")
    else:
        update.message.reply_text("Failed to initiate payment. Please try again.")

def payment_callback(update: Update, context: CallbackContext):
    payment_data = json.loads(update.message.text)
    if payment_data.get("ResultCode") == "0":
        user_id = context.user_data["pending_payment"]["user_id"]
        context.bot.send_message(user_id, f"Payment successful! Here is your download link: {PRODUCT_PDF_URL}")
    else:
        update.message.reply_text("Payment failed. Please try again.")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, request_payment))
    dp.add_handler(MessageHandler(Filters.text & Filters.regex(r'\{.*"ResultCode".*\}'), payment_callback))
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
