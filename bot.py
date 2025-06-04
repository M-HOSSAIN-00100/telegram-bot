import telebot
import os
from dotenv import load_dotenv
from pymongo import MongoClient

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
MONGO_URI = os.getenv('MONGO_URI')

# MongoDB সংযোগ
client = MongoClient(MONGO_URI)
db = client['telegram_bot']
collection = db['users']

bot = telebot.TeleBot(TOKEN)

def load_data():
    try:
        return {doc['_id']: doc for doc in collection.find()}
    except Exception as e:
        print(f"ডেটা লোড করতে ত্রুটি: {e}")
        return {}

def save_data(data):
    try:
        for user_id, user_data in data.items():
            collection.update_one({'_id': user_id}, {'$set': user_data}, upsert=True)
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

@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    user_id = str(message.chat.id)
    if is_user_activated(user_id):
        bot.reply_to(message, "✅ আপনার একাউন্ট ইতিমধ্যে এক্টিভ।")
        return
    try:
        bot.forward_message(ADMIN_CHAT_ID, message.chat.id, message.message_id)
        bot.reply_to(message, "✅ স্ক্রিনশট পাঠানো হয়েছে। অ্যাডমিন শীঘ্রই যাচাই করবে।")
    except Exception as e:
        bot.reply_to(message, "⚠️ স্ক্রিনশট পাঠাতে ত্রুটি। আবার চেষ্টা করুন।")
        print(f"স্ক্রিনশট ফরোয়ার্ডে ত্রুটি: {e}")

@bot.message_handler(commands=['approve'])
def approve_user(message):
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
        bot.send_message(int(target_id), "✅ আপনার একাউন্ট অ্যাডমিন দ্বারা এক্টিভ করা হয়েছে। এখন আপনি রেফার করতে পারবেন।", reply_markup=main_menu_keyboard())
        bot.reply_to(message, f"✅ {target_id} একাউন্ট এক্টিভেট করা হয়েছে।")
    except Exception as e:
        bot.reply_to(message, f"⚠️ {target_id}-কে মেসেজ পাঠাতে ত্রুটি: {e}")

@bot.message_handler(commands=['remove'])
def remove_user(message):
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
        collection.delete_one({'_id': target_id})
        bot.reply_to(message, f"✅ ইউজার {target_id} ডিলিট করা হয়েছে।")
    else:
        bot.reply_to(message, "❌ ইউজার পাওয়া যায়নি।")

@bot.message_handler(func=lambda message: True)
def main_handler(message):
    user_id = str(message.chat.id)
    text = message.text

    data = load_data()
    if user_id not in data:
        bot.send_message(message.chat.id, "অনুগ্রহ করে /start দিয়ে শুরু করুন।")
        return

    if text == 'আমার প্রোফাইল':
        user = data[user_id]
        profile_text = (
            f"👤 ইউজার: @{user.get('username', 'নাম নেই')}\n"
            f"💰 ব্যালেন্স: {user.get('balance', 0)} টাকা\n"
            f"🔗 রেফারার: @{data.get(str(user.get('ref')), {}).get('username', 'না আছে')}\n"
            f"🔓 এক্টিভেটেড: {'হ্যাঁ' if user.get('activated') else 'না'}"
        )
        bot.send_message(message.chat.id, profile_text, reply_markup=main_menu_keyboard())

    elif text == 'রেফার':
        try:
            bot_username = bot.get_me().username
            ref_link = f"https://t.me/{bot_username}?start={user_id}"
            bot.send_message(message.chat.id, f"আপনার রেফার লিংক:\n{ref_link}", reply_markup=main_menu_keyboard())
        except Exception as e:
            bot.send_message(message.chat.id, "⚠️ রেফার লিংক তৈরি করতে ত্রুটি।", reply_markup=main_menu_keyboard())
            print(f"রেফার লিংক ত্রুটি: {e}")

    elif text == 'উইথড্র':
        if not is_user_activated(user_id):
            bot.send_message(message.chat.id, "❌ আপনার একাউন্ট এক্টিভ নয়। এক্টিভেশন করুন।")
            return
        bot.send_message(message.chat.id, f"আপনার বর্তমান ব্যালেন্স: {data[user_id]['balance']} টাকা।\n"
                                          f"সর্বনিম্ন উইথড্র: {MIN_WITHDRAW_AMOUNT} টাকা।\n"
                                          "উইথড্র করতে /withdraw_amount <টাকা> লিখুন।", reply_markup=main_menu_keyboard())

    elif text.startswith('/withdraw_amount'):
        if not is_user_activated(user_id):
            bot.send_message(message.chat.id, "❌ আপনার একাউন্ট এক্টিভ নয়। এক্টিভেশন করুন।")
            return
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            bot.send_message(message.chat.id, "⚠️ সঠিক ফরম্যাট: /withdraw_amount <টাকা>")
            return
        amount = int(parts[1])
        if amount < MIN_WITHDRAW_AMOUNT:
            bot.send_message(message.chat.id, f"⚠️ সর্বনিম্ন উইথড্র {MIN_WITHDRAW_AMOUNT} টাকা।")
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
        except Exception as e:
            bot.send_message(message.chat.id, "⚠️ উইথড্র রিকোয়েস্ট প্রসেসে ত্রুটি। আবার চেষ্টা করুন।")
            print(f"উইথড্র ত্রুটি: {e}")

    elif text == 'রিচার্জ':
        if not is_user_activated(user_id):
            bot.send_message(message.chat.id, "❌ আপনার একাউন্ট এক্টিভ নয়। এক্টিভেশন করুন।")
            return
        bot.send_message(message.chat.id, f"রিচার্জ করতে /recharge_amount <টাকা> লিখুন।\n"
                                          f"সর্বনিম্ন রিচার্জ: {MIN_RECHARGE_AMOUNT} টাকা।\n"
                                          f"পেমেন্ট নাম্বার: {PAYMENT_NUMBER}", reply_markup=main_menu_keyboard())

    elif text.startswith('/recharge_amount'):
        if not is_user_activated(user_id):
            bot.send_message(message.chat.id, "❌ আপনার একাউন্ট এক্টিভ নয়। এক্টিভেশন করুন।")
            return
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            bot.send_message(message.chat.id, "⚠️ সঠিক ফরম্যাট: /recharge_amount <টাকা>")
            return
        amount = int(parts[1])
        if amount < MIN_RECHARGE_AMOUNT:
            bot.send_message(message.chat.id, f"⚠️ সর্বনিম্ন রিচার্জ {MIN_RECHARGE_AMOUNT} টাকা।")
            return
        data[user_id]['recharge_history'].append(amount)
        save_data(data)
        try:
            bot.send_message(ADMIN_CHAT_ID, f"নতুন রিচার্জ রিকোয়েস্ট: ইউজার {user_id}, পরিমাণ: {amount} টাকা")
            bot.send_message(message.chat.id, f"✅ আপনার {amount} টাকা রিচার্জ রিকোয়েস্ট পাঠানো হয়েছে। স্ক্রিনশট পাঠান।")
        except Exception as e:
            bot.send_message(message.chat.id, "⚠️ রিচার্জ রিকোয়েস্ট প্রসেসে ত্রুটি। আবার চেষ্টা করুন।")
            print(f"রিচার্জ ত্রুটি: {e}")

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

if __name__ == '__main__':
    bot.remove_webhook()
    bot.polling(none_stop=True)
