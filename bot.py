import asyncio
import logging
import re
from datetime import datetime, timedelta
from collections import defaultdict
import random
import json
import os
import aiohttp
import emoji

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- КОНФИГ ---
BOT_TOKEN = "8982540387:AAGUMaVJGbzSjC6RL8HbBFR_tBjYGwGGyWc"
CHAT_ID = -1003730201243
OWNER_ID = 8268613975

# Настройки модерации
SPAM_TIME_WINDOW = 5
SPAM_MESSAGE_LIMIT = 3
MUTE_DURATION = 60
MAX_WARNINGS = 3
BOT_CHECK_TIMEOUT = 60

# Настройки ночного режима
NIGHT_MODE_START = 23
NIGHT_MODE_END = 6

# Настройки анти-флуд эмоций
EMOJI_LIMIT = 5

# Настройки логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Хранилища
user_message_times = defaultdict(list)
warning_count = defaultdict(int)
user_messages_count = defaultdict(int)
chat_admins = set()
user_join_time = {}
user_emoji_counter = defaultdict(list)
user_activity = defaultdict(int)
user_levels = defaultdict(int)
user_xp = defaultdict(int)
user_rep = defaultdict(int)
reports = {}
report_counter = 0
custom_commands = {}
admin_logs = []
dynamic_bad_words = []

# Файлы для данных
ADMINS_FILE = "admins.json"
BANS_FILE = "bans.json"
WARNS_FILE = "warns.json"
MUTES_FILE = "mutes.json"
STATS_FILE = "stats.json"
LEVELS_FILE = "levels.json"
REPORTS_FILE = "reports.json"
COMMANDS_FILE = "commands.json"
LOGS_FILE = "logs.json"
BADWORDS_FILE = "badwords.json"
REP_FILE = "rep.json"

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ---
async def safe_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = None, reply_markup=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        except Exception:
            await update.callback_query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode=parse_mode, reply_markup=reply_markup)

# --- ЗАГРУЗКА/СОХРАНЕНИЕ ДАННЫХ ---
def load_admins():
    global chat_admins
    if os.path.exists(ADMINS_FILE):
        try:
            with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                chat_admins = set(data.get("admins", []))
        except Exception:
            chat_admins = set()

def save_admins():
    try:
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"admins": list(chat_admins)}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения админов: {e}")

def load_bans():
    if os.path.exists(BANS_FILE):
        try:
            with open(BANS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_bans(bans):
    try:
        with open(BANS_FILE, 'w', encoding='utf-8') as f:
            json.dump(bans, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения банов: {e}")

def load_warns():
    if os.path.exists(WARNS_FILE):
        try:
            with open(WARNS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_warns(warns):
    try:
        with open(WARNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(warns, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения варнов: {e}")

def load_mutes():
    if os.path.exists(MUTES_FILE):
        try:
            with open(MUTES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_mutes(mutes):
    try:
        with open(MUTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(mutes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения мутов: {e}")

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"total_messages": 0, "total_bans": 0, "total_mutes": 0, "total_warns": 0}
    return {"total_messages": 0, "total_bans": 0, "total_mutes": 0, "total_warns": 0}

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения статистики: {e}")

def load_levels():
    if os.path.exists(LEVELS_FILE):
        try:
            with open(LEVELS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_levels.update({int(k): v for k, v in data.get("levels", {}).items()})
                user_xp.update({int(k): v for k, v in data.get("xp", {}).items()})
        except Exception:
            pass

def save_levels():
    try:
        data = {
            "levels": {str(k): v for k, v in user_levels.items()},
            "xp": {str(k): v for k, v in user_xp.items()}
        }
        with open(LEVELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения уровней: {e}")

def load_reports():
    global reports, report_counter
    if os.path.exists(REPORTS_FILE):
        try:
            with open(REPORTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                reports = {int(k): v for k, v in data.get("reports", {}).items()}
                report_counter = data.get("counter", 0)
        except Exception:
            reports = {}
            report_counter = 0

def save_reports():
    try:
        data = {
            "reports": {str(k): v for k, v in reports.items()},
            "counter": report_counter
        }
        with open(REPORTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения жалоб: {e}")

def load_commands():
    global custom_commands
    if os.path.exists(COMMANDS_FILE):
        try:
            with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
                custom_commands = json.load(f)
        except Exception:
            custom_commands = {}

def save_commands():
    try:
        with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(custom_commands, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения команд: {e}")

def load_logs():
    global admin_logs
    if os.path.exists(LOGS_FILE):
        try:
            with open(LOGS_FILE, 'r', encoding='utf-8') as f:
                admin_logs = json.load(f)
        except Exception:
            admin_logs = []

def save_logs():
    try:
        if len(admin_logs) > 1000:
            admin_logs = admin_logs[-1000:]
        with open(LOGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(admin_logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения логов: {e}")

def load_badwords():
    global dynamic_bad_words
    if os.path.exists(BADWORDS_FILE):
        try:
            with open(BADWORDS_FILE, 'r', encoding='utf-8') as f:
                dynamic_bad_words = json.load(f)
        except Exception:
            dynamic_bad_words = []

def save_badwords():
    try:
        with open(BADWORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(dynamic_bad_words, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения плохих слов: {e}")

def load_rep():
    if os.path.exists(REP_FILE):
        try:
            with open(REP_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_rep.update({int(k): v for k, v in data.items()})
        except Exception:
            pass

def save_rep():
    try:
        with open(REP_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in user_rep.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения репутации: {e}")

# Загружаем все данные при старте
load_admins()
bans = load_bans()
warns = load_warns()
mutes = load_mutes()
stats = load_stats()
load_levels()
load_reports()
load_commands()
load_logs()
load_badwords()
load_rep()

# --- ПРАВИЛА ЧАТА ---
RULES_TEXT = """
📜 **ПРАВИЛА ДЛЯ 403Team » Чат:**

**В чате запрещено:**

1️⃣ **Флудить и спамить** - засорять чат бессмысленными сообщениями
2️⃣ **Оскорблять администрацию, родных, участников** - уважайте друг друга, блять!
3️⃣ **Реклама** - любые ссылки на сторонние ресурсы, каналы, чаты
4️⃣ **Обсуждение политики** - это не место для политических баталий
5️⃣ **Отправлять 18+ и NSFW** - контент для взрослых запрещен
6️⃣ **Угрожать участникам чата** (в том числе и администрации)

**⚠️ Наказания:**
- За нарушение правил - **мут/варн/бан** по решению администрации
- 3 предупреждения = **бан**, блять!
- Грубые нарушения = **моментальный бан**

📌 **Со временем правила могут обновляться**
"""

BAD_WORDS_PATTERN = r'(сука|бля|хуй|пизд|ебал|нах|залупа|мудак|гандон|редиска|петух|козел|лох|пидор|гнида|тварь|шлюха|блядь|хуесос|пиздец|ебать|заебал|нахер|нахуй|похуй|схуя|долбоеб|залупа|пиздить|нахуя|ебашить)'

# --- АВТО-ОТВЕТЫ С ВАЙБОМ ЖДУНЯРЫ ---
AUTO_RESPONSES = {
    "бот": "⏳ Сижу тут, жду, пока ты что-то путное напишешь, блять!",
    "привет": "⏳ Здарова, ебать! Стою тут, жду движухи.",
    "пока": "⏳ Ну пиздуй, жду твоего возвращения, сука!",
    "когда": "⏳ Жди ответа, нахуй, всему свое время!",
    "обнова": "⏳ Ждем обнову вместе, у меня уже лапки устали ждать, блять!",
    "что делать": "⏳ Сидеть и ждать, как настоящий ждуняра, сука!",
    "спасибо": "⏳ Пожалуйста, ебать! Обращайся еще, пока я никуда не ушел.",
    "помощь": "⏳ /help ждет тебя, сука, нажимай давай!",
}

def is_night_mode() -> bool:
    current_hour = datetime.now().hour
    if NIGHT_MODE_START > NIGHT_MODE_END:
        return current_hour >= NIGHT_MODE_START or current_hour < NIGHT_MODE_END
    return NIGHT_MODE_START <= current_hour < NIGHT_MODE_END

def is_admin(user_id: int) -> bool:
    return user_id == OWNER_ID or user_id in chat_admins

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

async def get_user_name(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    try:
        user = await context.bot.get_chat_member(chat_id=CHAT_ID, user_id=user_id)
        if user.user.username:
            return f"@{user.user.username}"
        return user.user.first_name or str(user_id)
    except Exception:
        return str(user_id)

async def get_target_id_from_reply(update: Update) -> int:
    if update.message and update.message.reply_to_message and update.message.reply_to_message.from_user:
        return update.message.reply_to_message.from_user.id
    return None

async def get_user_id_by_username(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str) -> int:
    try:
        username = username.replace('@', '')
        admins = await context.bot.get_chat_administrators(chat_id=CHAT_ID)
        for admin in admins:
            if admin.user.username and admin.user.username.lower() == username.lower():
                return admin.user.id
        return None
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return None

async def add_log(action: str, admin_id: int, target_id: int, reason: str = ""):
    log_entry = {
        "time": datetime.now().isoformat(),
        "action": action,
        "admin": admin_id,
        "target": target_id,
        "reason": reason
    }
    admin_logs.append(log_entry)
    save_logs()

async def add_xp(user_id: int, xp: int = 1):
    user_xp[user_id] += xp
    xp_needed = (user_levels[user_id] + 1) * 10
    if user_xp[user_id] >= xp_needed:
        user_levels[user_id] += 1
        user_xp[user_id] = 0
        save_levels()
        return True
    save_levels()
    return False

async def get_rank(user_id: int) -> str:
    level = user_levels.get(user_id, 0)
    if level < 5:
        return "⏳ Ждуняра-новичок"
    elif level < 15:
        return "⏳ Терпеливый"
    elif level < 30:
        return "⏳ Профессиональный ждун"
    elif level < 50:
        return "⏳ Ветеран ожидания"
    elif level < 75:
        return "⏳ Мастер хайпа"
    elif level < 100:
        return "⏳ Легендарный Ждуняра"
    else:
        return "👑 Бог Ожидания"

# --- МОДЕРАЦИЯ ---
async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, reason: str, target_name: str = None):
    warning_count[user_id] += 1
    current_warnings = warning_count[user_id]
    stats["total_warns"] += 1
    save_stats(stats)
    
    warns[str(user_id)] = {
        "count": current_warnings,
        "last_reason": reason,
        "last_time": datetime.now().isoformat()
    }
    save_warns(warns)
    
    if not target_name:
        target_name = await get_user_name(context, user_id)
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏳ Предупреждение {current_warnings}/{MAX_WARNINGS} пока ты ждал бан, блять!\nПричина: {reason}"
        )
    except Exception:
        pass
    
    warning_msg = f"⏳ {target_name} дождался предупреждения {current_warnings}/{MAX_WARNINGS}!\nПричина: {reason}"
    
    if current_warnings >= MAX_WARNINGS:
        await ban_user(update, context, user_id, target_name, reason)
        warning_msg += f"\n🔨 {target_name} дождался пермача, сука!"
        del warning_count[user_id]
        if str(user_id) in warns:
            del warns[str(user_id)]
            save_warns(warns)
    else:
        await mute_user(update, context, user_id, MUTE_DURATION, target_name)
    
    await context.bot.send_message(chat_id=CHAT_ID, text=warning_msg)
    await add_log(f"WARN {current_warnings}/{MAX_WARNINGS}", update.effective_user.id, user_id, reason)

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, duration: int = 60, target_name: str = None):
    try:
        until_date = datetime.now() + timedelta(seconds=duration)
        await context.bot.restrict_chat_member(
            chat_id=CHAT_ID,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False, can_send_media_messages=False),
            until_date=until_date
        )
        stats["total_mutes"] += 1
        save_stats(stats)
        
        mutes[str(user_id)] = {
            "duration": duration,
            "until": until_date.isoformat(),
            "reason": "Нарушение правил чата"
        }
        save_mutes(mutes)
        
        if not target_name:
            target_name = await get_user_name(context, user_id)
        await context.bot.send_message(chat_id=CHAT_ID, text=f"⏳ {target_name} получил мут на {duration} сек — сиди и жди размута, молча!")
        await add_log(f"MUTE {duration}s", update.effective_user.id, user_id, "Нарушение правил")
    except Exception as e:
        logger.error(f"Не удалось замутить: {e}")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, target_name: str = None, reason: str = "Нарушение правил"):
    try:
        await context.bot.ban_chat_member(chat_id=CHAT_ID, user_id=user_id)
        stats["total_bans"] += 1
        save_stats(stats)
        
        bans[str(user_id)] = {
            "reason": reason,
            "time": datetime.now().isoformat(),
            "banned_by": update.effective_user.id
        }
        save_bans(bans)
        
        if not target_name:
            target_name = await get_user_name(context, user_id)
        await context.bot.send_message(chat_id=CHAT_ID, text=f"⏳ {target_name} дождался бана навсегда, нахуй!\n📜 Причина: {reason}")
        await add_log("BAN", update.effective_user.id, user_id, reason)
    except Exception as e:
        logger.error(f"Не удалось забанить: {e}")

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, target_name: str = None):
    try:
        await context.bot.ban_chat_member(chat_id=CHAT_ID, user_id=user_id)
        await context.bot.unban_chat_member(chat_id=CHAT_ID, user_id=user_id)
        if not target_name:
            target_name = await get_user_name(context, user_id)
        await context.bot.send_message(chat_id=CHAT_ID, text=f"⏳ {target_name} получил пенделя и вылетел!")
        await add_log("KICK", update.effective_user.id, user_id, "Кик")
    except Exception as e:
        logger.error(f"Не удалось кикнуть: {e}")

# --- ФИШКИ ЖДУНЯРЫ ---
async def wait_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wait_phrases = [
        "⏳ Ждем вместе уже хрен знает сколько, блять...",
        "⏳ Терпение — это ключ. Ждуняра одобряет!",
        "⏳ Сижу, смотрю в окно, жду чуда и новой обновы, сука.",
        "⏳ Ожидание — моя суперсила, а в чем твоя сила, ебать?",
        "⏳ Ждем пацанов, ждем погоды, ждем лето..."
    ]
    await safe_reply(update, context, random.choice(wait_phrases))

async def rep_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    target_id = await get_target_id_from_reply(update)
    
    if not target_id and context.args:
        target = context.args[0]
        if target.startswith('@'):
            target_id = await get_user_id_by_username(update, context, target)
            
    if not target_id:
        await safe_reply(update, context, "⭐ Ответь на сообщение пользователя или укажи его `@username`, чтобы поднять репутацию!")
        return
        
    if target_id == user_id:
        await safe_reply(update, context, "🤡 Себе репутацию поднимать нельзя, ждуняра!")
        return
        
    user_rep[target_id] += 1
    save_rep()
    target_name = await get_user_name(context, target_id)
    await safe_reply(update, context, f"⏳ Репутация ждуна {target_name} выросла! Теперь у него ⭐ {user_rep[target_id]} репки.")

async def replist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_rep:
        await safe_reply(update, context, "⏳ Ни у кого еще нет репки, сидим ждем первых героев.")
        return
    top_rep = sorted(user_rep.items(), key=lambda x: x[1], reverse=True)[:10]
    text = "⏳ **ТОП-10 Главных Ждунян по репутации:**\n\n"
    for i, (uid, rep) in enumerate(top_rep, 1):
        name = await get_user_name(context, uid)
        text += f"{i}. {name} — ⭐ {rep}\n"
    await safe_reply(update, context, text, parse_mode='Markdown')

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = random.choice(["🪙 Орёл! Жди следующего броска.", "🪙 Решка! Судьба решает, блять."])
    await safe_reply(update, context, res)

async def ball8_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await safe_reply(update, context, "🔮 Задай вопрос шару ждуна: `/8ball [вопрос]`", parse_mode='Markdown')
        return
    answers = [
        "Бесспорно, жди", "Предрешено, блять", "Никаких сомнений, жди чуда", "Определенно да",
        "Можешь сидеть и ждать", "Мне кажется — да", "Вероятнее всего, жди",
        "Пока не ясно, сиди жди дальше", "Спроси позже, я занят ожиданием"
    ]
    await safe_reply(update, context, f"🔮 {random.choice(answers)}")

async def add_badword_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Только для админов!")
        return
    if not context.args:
        await safe_reply(update, context, "Используй: `/addbadword [слово]`", parse_mode='Markdown')
        return
    word = context.args[0].lower()
    if word not in dynamic_bad_words:
        dynamic_bad_words.append(word)
        save_badwords()
        await safe_reply(update, context, f"✅ Слово `{word}` добавлено в черный список ждунярской модерации.")
    else:
        await safe_reply(update, context, f"⚠️ Слово `{word}` уже есть в списке.")

async def clear_logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await safe_reply(update, context, "⛔ Доступно только владельцу бота!")
        return
    global admin_logs
    admin_logs = []
    save_logs()
    await safe_reply(update, context, "🧹 Логи стерты, сидим ждем новые действия.")

# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    user_id = user.id
    message_text = update.message.text or ""

    if is_admin(user_id):
        return

    if is_night_mode():
        await update.message.delete()
        return

    # Авто-ответы по ключевым словам
    lower_text = message_text.lower()
    for kw, resp in AUTO_RESPONSES.items():
        if kw in lower_text:
            await update.message.reply_text(resp)
            break

    # Проверка матов из динамического списка
    for bw in dynamic_bad_words:
        if bw in lower_text:
            await warn_user(update, context, user_id, f"Запрещенное слово: {bw}")
            await update.message.delete()
            return

    # Проверка регуляркой мата
    if re.search(BAD_WORDS_PATTERN, message_text, re.IGNORECASE):
        await warn_user(update, context, user_id, "Использование ненормативной лексики")
        await update.message.delete()
        return

    stats["total_messages"] += 1
    save_stats(stats)
    user_messages_count[user_id] += 1
    await add_xp(user_id, random.randint(1, 3))

# --- ЗАПУСК БОТА ---
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("wait", wait_command))
    application.add_handler(CommandHandler("жду", wait_command))
    application.add_handler(CommandHandler("rep", rep_command))
    application.add_handler(CommandHandler("replist", replist_command))
    application.add_handler(CommandHandler("coin", coin_command))
    application.add_handler(CommandHandler("8ball", ball8_command))
    application.add_handler(CommandHandler("addbadword", add_badword_command))
    application.add_handler(CommandHandler("clearlogs", clear_logs_command))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Бот-Ждуняра 403Team запущен и ждет!")
    application.run_polling()

if __name__ == "__main__":
    main()
