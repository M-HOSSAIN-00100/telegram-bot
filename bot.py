import telebot
import os
import json
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask
import threading

# Flask সার্ভার তৈরি
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is running!"

# এনভায়রনমেন্ট ভ্যারিয়েবল লোড
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))
ACTIVATION_FEE = 50
REFERRAL_REWARD = 20
MIN_WITHDRAW_AMOUNT = 50
MIN_RECHARGE_AMOUNT = 20
PAYMENT_NUMBER = os.getenv('PAYMENT_NUMBER')
GROUP_LINK = os.getenv('GROUP_LINK')
GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')

# Google Sheets সেটআপ
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(GOOGLE_CREDENTIALS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("TelegramBotUsers").sheet1

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
        return data
    except Exception as e:
        print(f"ডেটা লোড করতে ত্রুটি: {e}")
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
    except Exception as e:
        print(f"ডেটা সেভ করতে ত্রুটি: {e}")

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
            except Exception as e:
                print(f"রেফারারকে মেসেজ পাঠাতে ত্রুটি: {e}")
        save_data(data)

def main_menu_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('আমার প্রোফাইল', 'রেফার')
    markup.row('উইথড্র', 'রিচার্জ')
    markup.row('ট্রানজ্যাকশন হিস্ট্রি', 'যোগাযোগ')
    return markup

@bot.message_handler(commands=['start'])
def handle_start(message):
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
            f"🔓 একাউন্ট এক্টিভ করতে মাত্র {ACTIVATION_FEE} টাকা বিকাশ/নগদ করুন:\n"
            f"📲 নাম্বার: {PAYMENT_NUMBER}\n\n"
            "📩 স্ক্রিনশট পাঠিয়ে এক্টিভেশন নিশ্চিত করুন।\n\n"
            "🚀 শুরু করুন, বড় ইনকামের পথে!"
        )
        bot.send_message(message.chat.id, welcome_message, reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = str(message.chat.id)
    text = message.text

    data = load_data()
    if user_id in data:
        if text == 'আমার প্রোফাইল':
            user_data = data[user_id]
            profile_text = (
                f"User: @{user_data.get('username', 'No name')}\n"
                f"Balance: {user_data.get('balance', 0)} BDT\n"
                f"Referer: @{data.get(user_data.get('ref', ''), {}).get('username', 'None')}\n"
                f"Activated: {'Yes' if user_data.get('activated') else 'No'}"
            )
            bot.send_message(message.chat.id, profile_text, reply_markup=main_menu_keyboard())

        elif text == 'রেফার':
            try:
                bot_username = bot.get_me().username
                ref_link = f"https://t.me/{bot_username}?start={user_id}"
                bot.send_message(message.chat.id, f"Your referral link: {ref_link}", reply_markup=main_menu_keyboard.hex())
            except Exception as e:
                bot.send_message(message.chat.id, "Error generating referral link.", reply_markup=main_menu_keyboard())
                print(f"Referral link error: {e}")

        elif text == 'উইথড্র':
            if not is_user_activated(user_id):
                bot.send_message(message.chat.id, "❌ Your account is not activated. Please activate first.")
                return
            bot.send_message(message.chat.id, f"Balance: {data[user_id]['balance']} BDT.\nMinimum withdraw: {MIN_WITHDRAW_AMOUNT} BDT.\nUse /withdraw_amount <amount>", reply_markup=main_menu_keyboard())

        elif text.startswith('/withdraw_amount'):
            if not is_user_activated(user_id):
                bot.send_message(message.chat.id, "❌ Not activated.")
                return
            parts = text.split()
            if len(parts) != 2 or not parts[1].isdigit():
                bot.send_message(message.chat.id, "⚠️ Format: /withdraw_amount <amount>")
                return
            amount = int(parts[1])
            if amount < MIN_WITHDRAW_AMOUNT:
                bot.send_message(message.chat.id, f"⚠️ Minimum: {MIN_WITHDRAW_AMOUNT} BDT.")
                return
            if data[user_id]['balance'] < amount:
                bot.send_message(message.chat.id, "⚠️ Insufficient balance.")
                return
            data[user_id]['balance'] -= amount
            data[user_id]['withdraw_history'].append(amount)
            save_data(data)
            try:
                bot.send_message(ADMIN_CHAT_ID, f"New withdraw request: User {user_id}, Amount: {amount} BDT")
                bot.send_message(message.chat.id, f"✅ Withdraw request for {amount} sent to admin.")
            except Exception as e:
                print(f"Withdraw error: {e}")

        elif text == 'রিচার্জ':
            if not is_user_activated(user_id):
                bot.send_message(message.chat.id, "❌ Not activated.")
                return
            bot.send_message(message.chat.id, f"Minimum recharge: {MIN_RECHARGE_AMOUNT} BDT.\nPayment number: {PAYMENT_NUMBER}\nUse /recharge_amount <amount>", reply_markup=main_menu_keyboard())

        elif text.startswith('/recharge_amount'):
            if not is_user_activated(user_id):
                bot.send_message(message.chat.id, "❌ Not activated.")
                return
            parts = text.split()
            if len(parts) != 2 or not parts[1].isdigit():
                bot.send_message(message.chat.id, "⚠️ Format: /recharge_amount <amount>")
                return
            amount = int(parts[1])
            if amount < MIN_RECHARGE_AMOUNT:
                bot.send_message(message.chat.id, f"⚠️ Minimum: {MIN_RECHARGE_AMOUNT} BDT.")
                return
            data[user_id]['recharge_history'].append(amount)
            save_data(data)
            try:
                bot.send_message(ADMIN_CHAT_ID, f"New recharge: User {user_id}, Amount: {amount} BDT")
                bot.send_message(message.chat.id, f"✅ Recharge request for {amount} sent. Send screenshot.")
            except Exception as e:
                print(f"Recharge error: {e}")

        elif text == 'ট্রানজ্যাকশন হিস্ট্রি':
            user_data = data[user_id]
            withdraws = user_data.get('withdraw_history', [])
            recharges = user_data.get('recharge_history', [])
            history_text = "📜 Transaction History:\n\n"
            history_text += "Withdraws:\n" + "\n".join([f"- {amt} BDT" for amt in withdraws]) + "\n\n" if withdraws else "Withdraws: None\n\n"
            history_text += "Recharges:\n" + "\n".join([f"- {amt} BDT" for amt in recharges]) if recharges else "Recharges: None"
            bot.send_message(message.chat.id, history_text, reply_markup=main_menu_keyboard())

        elif text == 'যোগাযোগ':
            bot.send_message(message.chat.id, "Contact: @setusername00_00_is_available", reply_markup=main_menu_keyboard())

        else:
            bot.send_message(message.chat.id, "⚠️ Invalid option. Choose from buttons.", reply_to=main_menu_keyboard())

@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    user_id = str(message.chat.id)
    if is_user_activated(user_id):
        bot.reply_to(message, "✅ Already activated.")
        return
    try:
        bot.forward_message(ADMIN_CHAT_ID, message.chat.id, message.message_id)
        bot.reply_to(message, "✅ Screenshot forwarded to admin.")
    except Exception as e:
        bot.reply_to(message, "⚠️ Error forwarding screenshot.")
        print(f"Screenshot error: {e}")

@bot.message_handler(commands=['approve'])
def approve_user(message):
    if message.chat.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "Only admin can use this.")
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Use: /approve <chat_id>")
        return
    target_id = args[1]
    data = load_data()
    if target_id not in data:
        bot.reply_to(message, "❌ User not found.")
        return
    activate_user(target_id)
    try:
        bot.send_message(int(target_id), "✅ Account activated by admin.", reply_to=message_menu_keyboard())
        bot.reply_to(message, f"✅ {target_id} activated.")
        except Exception as e:
            print(f"Approve error: {e}")

@bot.message_handler(commands=['delete'])
def delete_user(message):
    if message.chat.id != ADMIN_CHAT_ID:
        bot.reply_to(message, "Only admin can use this.")
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        bot.reply_to(message, "⚠️ Use: /delete <chat_id>")
        return
    target_id = args[1]
    data = load_data()
    if target_id in data:
        del data[target_id]
        save_data(data)
        bot.reply_to(message, f"✅ User {target_id} deleted.")
    else:
        bot.reply_to(message, "❌ User not found.")

def run_bot():
    bot.remove_webhook()
    bot.polling(none_stop=True)

if __name__ == '__main__':
    # বটকে আলাদা থ্রেডে চালানো
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    # Flask সার্ভার চালানো
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
