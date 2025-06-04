import telebot
import os
import json
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
import threading
import logging

# লগিং সেটআপ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask সার্ভার তৈরি
app = Flask(__name__)

@app.route('/')
def home():
    logger.info("Flask server accessed at /")
    return "Telegram Bot is running!"

# এনভায়রনমেন্ট ভ্যারিয়েবল লোড
load_dotenv()
try:
    TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))
    PAYMENT_NUMBER = os.getenv('PAYMENT_NUMBER')
    GROUP_LINK = os.getenv('GROUP_LINK')
    GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
    if not TOKEN or not GOOGLE_CREDENTIALS:
        raise ValueError("Missing BOT_TOKEN or GOOGLE_CREDENTIALS")
    logger.info("Environment variables loaded successfully")
except Exception as e:
    logger.error(f"Error loading environment variables: {e}")
    raise

# কনস্ট্যান্টস
ACTIVATION_FEE = 50
REFERRAL_REWARD = 20
MIN_WITHDRAW_AMOUNT = 50
MIN_RECHARGE_AMOUNT = 20

# Google Sheets সেটআপ
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(GOOGLE_CREDENTIALS)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("TelegramBotUsers").sheet1
    logger.info("Google Sheets connection established")
except Exception as e:
    logger.error(f"Error setting up Google Sheets: {e}")
    raise

bot = telebot.TeleBot(TOKEN)

def load_data():
    try:
        records = sheet.get_all_records()
        data = {}
        for record in records:
            user_id = str(record['user_id'])
            data[user_id] = {
                'username': record['username'],
                'ref': record['ref'] if record['ref'] else None,
                'activated': record['activated'] == 'True',
                'balance': record['balance'],
                'withdraw_history': json.loads(record['withdraw_history']) if record['withdraw_history'] else [],
                'recharge_history': json.loads(record['recharge_history']) if record['recharge_history'] else []
            }
        logger.info("Data loaded from Google Sheets")
        return data
    except Exception as e:
        logger.error(f"ডেটা লোড করতে ত্রুটি: {e}")
        return {}

def save_data(data):
    try:
        sheet.clear()
        headers = ['user_id', 'username', 'ref', 'activated', 'balance', 'withdraw_history', 'recharge_history']
        sheet.append_row(headers)
        for user_id, user_data in data.items():
            row = [
                user_id,
                user_data['username'],
                user_data.get('ref', ''),
                str(user_data['activated']),
                user_data['balance'],
                json.dumps(user_data['withdraw_history']),
                json.dumps(user_data['recharge_history'])
            ]
            sheet.append_row(row)
        logger.info("Data saved to Google Sheets")
    except Exception as e:
        logger.error(f"ডেটা সেভ করতে ত্রুটি: {e}")

def is_user_activated(user_id):
    data = load_data()
    return str(user_id) in data and data[str(user_id)]['activated']

def activate_user(user_id):
    data = load_data()
    user_id_str = str(user_id)
    if user_id_str in data:
        data[user_id_str]['activated'] = True
        ref = data[user_id_str].get('ref')
        if ref and str(ref) in data:
            data[str(ref)]['balance'] += REFERRAL_REWARD
            try:
                bot.send_message(int(ref), f"🎉 অভিনন্দন! আপনার রেফার করা ইউজার এক্টিভ হয়েছে। আপনি পেয়েছেন {REFERRAL_REWARD} টাকা।")
                logger.info(f"Referral reward sent to user {ref}")
            except Exception as e:
                logger.error(f"রেফারারকে মেসেজ পাঠাতে ত্রুটি: {e}")
        save_data(data)

def main_menu_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('আমার প্রোফাইল', 'রেফার')
    markup.row('উইথড্র', 'রিচার্জ')
    markup.row('ট্রানজ্যাকশন হিস্ট্রি', 'যোগাযোগ')
    return markup

@bot.message_handler(commands=['start'])
def handle_start(message):
    logger.info(f"Received /start command from user {message.chat.id}")
    user_id = str(message.chat.id)
    username = message.from_user.username or 'নাম নেই'
    args = message.text.split()
    ref = args[1] if len(args) > 1 else None

    data = load_data()
    if user_id not in data:
        data[user_id] = {
            'username': username,
            'ref': ref,
            'activated': False,
            'balance': 0,
            'withdraw_history': [],
            'recharge_history': []
        }
        save_data(data)
        logger.info(f"New user {user_id} registered")

    if is_user_activated(user_id):
        bot.send_message(message.chat.id, "✅ আপনার একাউন্ট ইতিমধ্যে এক্টিভ।", reply_markup=main_menu_keyboard())
    else:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton(text="👥 ইনকাম প্রুফ গ্রুপে জয়েন করুন", url=GROUP_LINK))
        welcome_message = (
            "👋 স্বাগতম!\n\n"
            "আপনি এখন একটি রিয়েল ইনকাম সিস্টেমে আছেন, যেখানে শুধু রেফার করেই আয় করতে পারবেন।\n\n"
            f"✅ প্রতি এক্টিভ রেফারে পাবেন {REFERRAL_REWARD} টাকা।\n\n"
            "📌 আমাদের সিস্টেম ১০০% বিশ্বাসযোগ্য, স্ক্যাম নয়।\n\n"
            f"🔓 একাউন্ট একটিভ করতে মাত্র {ACTIVATION_FEE} টাকা বিকাশ/নগদ করুন:\n"
            f"📲 নাম্বার: {PAYMENT_NUMBER}\n\n"
            "📩 স্ক্রিনশট পাঠিয়ে একটিভেশন নিশ্চিত করুন।\n\n"
            "🚀 শুরু করুন, বড় ইনকামের পথে!"
        )
        bot.send_message(message.chat.id, welcome_message, reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    user_id = str(message.chat.id)
    username = message.from_user.username or 'নাম নেই'
    logger.info(f"Received screenshot from user {user_id}")
    if is_user_activated(user_id):
        bot.reply_to(message, "✅ ইতিমধ্যে একটিভ।")
        return
    try:
        bot.forward_message(ADMIN_CHAT_ID, message.chat.id, message.message_id)
        bot.send_message(
            ADMIN_CHAT_ID,
            f"📸 নতুন স্ক্রিনশট পাঠানো হয়েছে:\nইউজার: @{username}\nচ্যাট আইডি: {user_id}\nঅ্যাপ্রুভ করতে: /approve {user_id}"
        )
        bot.reply_to(message, "✅ স্ক্রিনশট অ্যাডমিনের কাছে পাঠানো হয়েছে।")
        logger.info(f"Screenshot forwarded to admin for user {user_id}")
    except Exception as e:
        bot.reply_to(message, "⚠️ স্ক্রিনশট পাঠাতে ত্রুটি। আবার চেষ্টা করুন।")
        logger.error(f"স্ক্রিনশট ত্রুটি: {e}")

@bot.message_handler(commands=['approve'])
def approve_user(message):
    logger.info(f"Received /approve command from {message.chat.id}")
    if message.chat.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "⚠️ শুধু অ্যাডমিন এই কমান্ড ব্যবহার করতে পারেন।")
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ ব্যবহার: /approve <chat_id>")
        return
    target_id = args[1]
    data = load_data()
    if target_id not in data:
        bot.reply_to(message, "❌ ইউজার পাওয়া যায়নি।")
        return
    activate_user(target_id)
    try:
        bot.send_message(int(target_id), "✅ আপনার একাউন্ট অ্যাডমিন দ্বারা একটিভ করা হয়েছে।", reply_markup=main_menu_keyboard())
        bot.reply_to(message, f"✅ {target_id} একটিভেট করা হয়েছে।")
        logger.info(f"User {target_id} activated by admin")
    except Exception as e:
        bot.reply_to(message, f"⚠️ {target_id}-কে মেসেজ পাঠাতে ত্রুটি: {e}")
        logger.error(f"Approve error: {e}")

@bot.message_handler(commands=['remove'])
def remove_user(message):
    logger.info(f"Received /remove command from {message.chat.id}")
    if message.chat.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "⚠️ শুধু অ্যাডমিন এই কমান্ড ব্যবহার করতে পারেন।")
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ ব্যবহার: /remove <chat_id>")
        return
    target_id = args[1]
    data = load_data()
    if target_id in data:
        del data[target_id]
        save_data(data)
        bot.reply_to(message, f"✅ ইউজার {target_id} ডিলিট করা হয়েছে।")
        logger.info(f"User {target_id} removed by admin")
    else:
        bot.reply_to(message, "❌ ইউজার পাওয়া যায়নি।")

@bot.message_handler(func=lambda message: True)
def main_handler(message):
    user_id = str(message.chat.id)
    text = message.text
    logger.info(f"Received message '{text}' from user {user_id}")

    data = load_data()
    if user_id not in data:
        bot.send_message(message.chat.id, "অনুগ্রহ করে /start দিয়ে শুরু করুন।")
        return

    if text == 'আমার প্রোফাইল':
        user = data[user_id]
        profile_text = (
            f"👤 ইউজার: @{user.get('username', 'নাম নেই')}\n"
            f"💰 ব্যালেন্স: {user.get('balance', 0)} টাকা\n"
            f"🔗 রেফারার: @{data.get(str(user.get('ref', '')), {}).get('username', 'না আছে')}\n"
            f"🔓 একটিভেটেড: {'হ্যাঁ' if user.get('activated') else 'না'}"
        )
        bot.send_message(message.chat.id, profile_text, reply_markup=main_menu_keyboard())

    elif text == 'রেফার':
        try:
            bot_username = bot.get_me().username
            ref_link = f"https://t.me/{bot_username}?start={user_id}"
            bot.send_message(message.chat.id, f"আপনার রেফার লিংক:\n{ref_link}", reply_markup=main_menu_keyboard())
            logger.info(f"Referral link sent to user {user_id}")
        except Exception as e:
            bot.send_message(message.chat.id, "⚠️ রেফার লিংক তৈরি করতে ত্রুটি।", reply_markup=main_menu_keyboard())
            logger.error(f"রেফার লিংক ত্রুটি: {e}")

    elif text == 'উইথড্র':
        if not is_user_activated(user_id):
            bot.send_message(message.chat.id, "❌ আপনার একাউন্ট একটিভ নয়। একটিভেশন করুন।")
            return
        bot.send_message(message.chat.id, f"আপনার বর্তমান ব্যালেন্স: {data[user_id]['balance']} টাকা।\n"
                            f"সর্বনিম্ন উইথড্র: {MIN_WITHDRAW_AMOUNT} টাকা।\n"
                            "উইথড্র করতে /withdraw_amount <টাকা> লিখুন।", reply_markup=main_menu_keyboard())

    elif text.startswith('/withdraw_amount'):
        if not is_user_activated(user_id):
            bot.send_message(message.chat.id, "❌ আপনার একাউন্ট একটিভ নয়। একটিভেশন করুন।")
            return
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            bot.send_message(message.chat.id, "⚠️ সঠিক ফরম্যাট: /withdraw_amount <টাকা>")
            return
        amount = int(parts[1])
        if amount < MIN_WITHDRAW_AMOUNT:
            bot.send_message(message.chat.id, f"⚠️ সর্বনিম্ন উইথড্র: {MIN_WITHDRAW_AMOUNT} টাকা।")
            return
        if data[user_id]['balance'] < amount:
            bot.send_message(message.chat.id, "⚠️ আপনার ব্যালেন্স পর্যাপ্ত নয়।")
            return
        data[user_id]['balance'] -= amount
        data[user_id]['withdraw_history'].append(amount)
        save_data(data)
        try:
            bot.send_message(ADMIN_CHAT_ID, f"নতুন উইথড্র রিকোয়েস্ট: ইউজার {user_id}, পরিমাণ: {amount} টাকা")
            bot.send_message(message.chat.id, f"✅ আপনি {amount} টাকা উইথড্র রিকোয়েস্ট করেছেন। অ্যাডমিন যোগাযোগ করবে।")
            logger.info(f"Withdraw request processed for user {user_id}, amount: {amount}")
        except Exception as e:
            bot.send_message(message.chat.id, "⚠️ উইথড্র রিকোয়েস্ট প্রসেসে ত্রুটি। আবার চেষ্টা করুন।")
            logger.error(f"উইথড্র ত্রুটি: {e}")

    elif text == 'রিচার্জ':
        if not is_user_activated(user_id):
            bot.send_message(message.chat.id, "❌ আপনার একাউন্ট একটিভ নয়। একটিভেশন করুন।")
            return
        bot.send_message(message.chat.id, f"রিচার্জ করতে /recharge_amount <টাকা> লিখুন।\n"
                            f"সর্বনিম্ন রিচার্জ: {MIN_RECHARGE_AMOUNT} টাকা।\n"
                            f"পেমেন্ট নাম্বার: {PAYMENT_NUMBER}", reply_markup=main_menu_keyboard())

    elif text.startswith('/recharge_amount'):
        if not is_user_activated(user_id):
            bot.send_message(message.chat.id, "❌ আপনার একাউন্ট একটিভ নয়। একটিভেশন করুন।")
            return
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            bot.send_message(message.chat.id, "⚠️ সঠিক ফরম্যাট: /recharge_amount <টাকা>")
            return
        amount = int(parts[1])
        if amount < MIN_RECHARGE_AMOUNT:
            bot.send_message(message.chat.id, f"⚠️ সর্বনিম্ন রিচার্জ: {MIN_RECHARGE_AMOUNT} টাকা।")
            return
        data[user_id]['recharge_history'].append(amount)
        save_data(data)
        try:
            bot.send_message(ADMIN_CHAT_ID, f"নতুন রিচার্জ রিকোয়েস্ট: ইউজার {user_id}, পরিমাণ: {amount} টাকা")
            bot.send_message(message.chat.id, f"✅ {amount} টাকা রিচার্জ রিকোয়েস্ট পাঠানো হয়েছে। স্ক্রিনশট পাঠান।")
            logger.info(f"Recharge request processed for user {user_id}, amount: {amount}")
        except Exception as e:
            bot.send_message(message, "⚠️⚡ রিচার্জ রিকোয়েস্ট প্রসেসে ত্রুটি। আবার চেষ্টা করুনি।")
            logger.error(f"Recharge error: {e}")

    elif text == 'ট্রানজ্যাকশন হিস্ট্রি':
        user = data[user_id]
        withdraws = user.get('withdraw_history', [])
        recharges = user.get('recharge_history', [])
        history_text = "📜 ট্রানজ্যাকশন হিস্ট্রি:\n\n"
        history_text += "উইথড্র:\n" + "\n".join([f"- {amt} টাকা" for amt in withdraws]) + "\n\n" if withdraws else "উইথড্র: কোনো রেকর্ড নেই\n\n"
        history_text += "রিচার্জ:\n" + "\n".join([f"- {amt} টাকা" for amt in recharges]) if recharges else "রিচার্জ: কোনো রেকর্ড নেই"
        bot.send_message(message.chat.id, history_text, reply_markup=main_menu_keyboard())

    elif text == 'যোগাযোগ':
        bot.send_message(message.chat.id, "আপনি যোগাযোগ করতে পারেন @setusername00_00_is_available", reply_markup=main_menu_keyboard())

    else:
        bot.send_message(message.chat.id, "⚠️ বুঝতে পারিনি, দয়া করে নিচের বাটন থেকে অপশন বেছে নিন।", reply_markup=main_menu_keyboard())

def run_bot():
    try:
        logger.info("Starting bot polling")
        bot.remove_webhook()
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
        raise

if __name__ == '__main__':
    try:
        logger.info("Starting bot thread")
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.start()
        logger.info("Starting Flask server")
        port = int(os.getenv('PORT', 8080))
        app.run(host='0.0',.0.0', port=port)
    except Exception as e:
        logger.error(f"Main execution error: {e}")
        raise
