import asyncio
import logging
import re
from datetime import datetime, timedelta
from collections import defaultdict
import random
import json
import os
import aiohttp

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
reports = {}
report_counter = 0
custom_commands = {}
admin_logs = []

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

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ---
async def safe_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = None, reply_markup=None):
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        except:
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
        except:
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
        except:
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
        except:
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
        except:
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
        except:
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
        except:
            pass

def save_levels():
    try:
        data = {
            "levels": dict(user_levels),
            "xp": dict(user_xp)
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
        except:
            reports = {}
            report_counter = 0

def save_reports():
    try:
        data = {
            "reports": reports,
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
        except:
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
        except:
            admin_logs = []

def save_logs():
    try:
        if len(admin_logs) > 1000:
            admin_logs = admin_logs[-1000:]
        with open(LOGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(admin_logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения логов: {e}")

# Загружаем данные
load_admins()
bans = load_bans()
warns = load_warns()
mutes = load_mutes()
stats = load_stats()
load_levels()
load_reports()
load_commands()
load_logs()

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

💬 **По всем вопросам к администрации!**
"""

# --- МАТ ДЛЯ РЕГУЛЯРКИ ---
BAD_WORDS_PATTERN = r'(сука|бля|хуй|пизд|ебал|нах|залупа|мудак|гандон|редиска|петух|козел|лох|пидор|гнида|тварь|шлюха|блядь|хуесос|пиздец|ебать|заебал|нахер|нахуй|похуй|схуя|долбоеб|хуесос|залупа|бляд|пиздить|нахуя|ебашить)'

# --- АВТО-ОТВЕТЫ ---
AUTO_RESPONSES = {
    "бот": "🤖 Я здесь, блять! Что надо?",
    "привет": "👋 Здарова, ебать!",
    "пока": "👋 Пока-пока, сука!",
    "кто админ": "👑 Админы: /admins, блять!",
    "правила": "📜 Правила: /rules, нахуй!",
    "спасибо": "🙏 Не за что, ебать!",
    "помощь": "🆘 /help - вся помощь, сука!",
    "кто тут главный": "👑 Владелец: /owner, блять!",
    "баг": "🐛 Баги фиксим, блять! Сообщи админу!",
    "тест": "✅ Бот работает, нахуй!",
    "как дела": "🤖 Нормально, ебать! А у тебя?",
    "работает": "✅ Работает как часы, сука!",
    "ааа": "😱 Чего орешь, блять?!",
    "ой": "😳 Что случилось, нахуй?",
    "красава": "😎 Спасибо, ебать! Я знаю!",
}

# --- ФУНКЦИИ ---
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
    except:
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
        return "🟢 Новичок"
    elif level < 15:
        return "🟡 Активный"
    elif level < 30:
        return "🟠 Постоянный"
    elif level < 50:
        return "🔴 Ветеран"
    elif level < 75:
        return "🔵 Мастер"
    elif level < 100:
        return "🟣 Легенда"
    else:
        return "👑 Бог"

# --- ФУНКЦИИ МОДЕРАЦИИ ---
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
            text=f"⚠️ Ты получил предупреждение {current_warnings}/{MAX_WARNINGS}, блять!\nПричина: {reason}\nНарушишь еще - вылетишь, нахуй!"
        )
    except:
        pass
    
    warning_msg = f"⚠️ Ебать, {target_name} получил предупреждение {current_warnings}/{MAX_WARNINGS}!\nПричина: {reason}\n\n📜 Нарушены правила чата! Используй /rules чтобы посмотреть!"
    
    if current_warnings >= MAX_WARNINGS:
        await ban_user(update, context, user_id, target_name, reason)
        warning_msg += f"\n🔨 {target_name} вылетел в бан, сука! Заебал!"
        del warning_count[user_id]
        if str(user_id) in warns:
            del warns[str(user_id)]
            save_warns(warns)
    else:
        await mute_user(update, context, user_id, MUTE_DURATION, target_name)
    
    await context.bot.send_message(chat_id=CHAT_ID, text=warning_msg)
    await add_log(f"WARN {current_warnings}/{MAX_WARNINGS}", update.effective_user.id, user_id, reason)
    logger.info(f"Warned user {user_id}: {reason} (count: {current_warnings})")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, duration: int = 60, target_name: str = None):
    try:
        until_date = datetime.now() + timedelta(seconds=duration)
        await context.bot.restrict_chat_member(
            chat_id=CHAT_ID,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False, can_send_media_messages=False),
            until_date=until_date
        )
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔇 Тебя замутили на {duration} секунд, блять!\nПричина: нарушение правил чата\nВремя: {until_date.strftime('%d.%m.%Y %H:%M')}"
            )
        except:
            pass
        
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
        await context.bot.send_message(chat_id=CHAT_ID, text=f"🤫 {target_name} заткнулся на {duration} секунд, блять!\n📜 Нарушены правила чата!")
        await add_log(f"MUTE {duration}s", update.effective_user.id, user_id, "Нарушение правил")
        logger.info(f"Muted user {user_id} for {duration}s")
    except Exception as e:
        logger.error(f"Не удалось замутить: {e}")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, target_name: str = None, reason: str = "Нарушение правил"):
    try:
        await context.bot.ban_chat_member(chat_id=CHAT_ID, user_id=user_id)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🚀 Тебя забанили, нахуй!\nПричина: {reason}\nВремя: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
        except:
            pass
        
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
        await context.bot.send_message(chat_id=CHAT_ID, text=f"🚀 {target_name} вылетел в бан, нахуй!\n📜 {reason}")
        await add_log("BAN", update.effective_user.id, user_id, reason)
        
        if user_id in warning_count:
            del warning_count[user_id]
        if user_id in user_message_times:
            del user_message_times[user_id]
        if user_id in user_messages_count:
            del user_messages_count[user_id]
        if str(user_id) in mutes:
            del mutes[str(user_id)]
            save_mutes(mutes)
        if str(user_id) in warns:
            del warns[str(user_id)]
            save_warns(warns)
            
        logger.info(f"Banned user {user_id}")
    except Exception as e:
        logger.error(f"Не удалось забанить: {e}")

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, target_name: str = None):
    try:
        await context.bot.ban_chat_member(chat_id=CHAT_ID, user_id=user_id)
        await context.bot.unban_chat_member(chat_id=CHAT_ID, user_id=user_id)
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"👢 Тебя кикнули из чата, сука!\nВремя: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
        except:
            pass
        
        if not target_name:
            target_name = await get_user_name(context, user_id)
        await context.bot.send_message(chat_id=CHAT_ID, text=f"👢 {target_name} вылетел киком, сука!\n📜 Нарушены правила чата!")
        await add_log("KICK", update.effective_user.id, user_id, "Нарушение правил")
        logger.info(f"Kicked user {user_id}")
    except Exception as e:
        logger.error(f"Не удалось кикнуть: {e}")

# --- СИСТЕМА ЖАЛОБ ---
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global report_counter
    
    user_id = update.effective_user.id
    target_id = await get_target_id_from_reply(update)
    
    if not target_id:
        if not context.args:
            await safe_reply(update, context,
                "📝 **Как пожаловаться:**\n"
                "1. Ответь на сообщение нарушителя и напиши /report [причина]\n"
                "2. Или напиши: /report @username [причина]\n\n"
                "Пример: /report @petrov Спамит, блять!",
                parse_mode='Markdown'
            )
            return
        
        target = context.args[0]
        if target.startswith('@'):
            target_id = await get_user_id_by_username(update, context, target)
            if not target_id:
                await safe_reply(update, context, f"❌ Не найден пользователь {target}, блять!")
                return
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Не указана"
        elif target.isdigit():
            target_id = int(target)
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Не указана"
        else:
            reason = " ".join(context.args)
    else:
        reason = " ".join(context.args) if context.args else "Не указана"
    
    if target_id == user_id:
        await safe_reply(update, context, "😈 Ты че, на себя жалуешься?! Иди нахуй!")
        return
    
    if target_id == OWNER_ID:
        await safe_reply(update, context, "⛔ На владельца нельзя жаловаться, сука!")
        return
    
    if target_id == context.bot.id:
        await safe_reply(update, context, "🤖 На меня жалуешься?! Пиздец, я тебя запомнил, блять!")
        return
    
    report_counter += 1
    reports[report_counter] = {
        "user": user_id,
        "target": target_id,
        "reason": reason,
        "time": datetime.now().isoformat(),
        "status": "active"
    }
    save_reports()
    
    user_name = await get_user_name(context, user_id)
    target_name = await get_user_name(context, target_id)
    
    for admin_id in chat_admins:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 **НОВАЯ ЖАЛОБА #{report_counter}**\n"
                     f"👤 От: {user_name}\n"
                     f"👤 На: {target_name}\n"
                     f"📌 Причина: {reason}\n"
                     f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                     f"\n/reports - посмотреть все жалобы",
                parse_mode='Markdown'
            )
        except:
            pass
    
    await safe_reply(update, context,
        f"✅ Жалоба #{report_counter} отправлена, блять!\n"
        f"Администрация рассмотрит, нахуй!\n"
        f"Нарушитель: {target_name}"
    )
    await add_log(f"REPORT #{report_counter}", user_id, target_id, reason)

async def reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not reports:
        await safe_reply(update, context, "📋 Жалоб нет, сука! Все тихо!")
        return
    
    active_reports = {k: v for k, v in reports.items() if v.get("status") == "active"}
    
    if not active_reports:
        await safe_reply(update, context, "📋 Активных жалоб нет, блять!")
        return
    
    report_text = "🔔 **Активные жалобы:**\n\n"
    for report_id, data in active_reports.items():
        user_name = await get_user_name(context, data["user"])
        target_name = await get_user_name(context, data["target"])
        report_text += f"#{report_id}\n"
        report_text += f"   👤 От: {user_name}\n"
        report_text += f"   👤 На: {target_name}\n"
        report_text += f"   📌 Причина: {data['reason']}\n"
        report_text += f"   🕐 Время: {data['time'][:19]}\n\n"
    
    if len(report_text) > 4000:
        report_text = report_text[:4000] + "\n... (слишком много, блять!)"
    
    report_text += "\n/resolve [номер] - закрыть жалобу"
    
    await safe_reply(update, context, report_text, parse_mode='Markdown')

async def resolve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not context.args:
        await safe_reply(update, context, "/resolve [номер жалобы]")
        return
    
    try:
        report_id = int(context.args[0])
    except:
        await safe_reply(update, context, "❌ Введи номер жалобы, блять!")
        return
    
    if report_id not in reports:
        await safe_reply(update, context, f"❌ Жалоба #{report_id} не найдена, нахуй!")
        return
    
    if reports[report_id].get("status") == "resolved":
        await safe_reply(update, context, f"⚠️ Жалоба #{report_id} уже закрыта, блять!")
        return
    
    reports[report_id]["status"] = "resolved"
    reports[report_id]["resolved_by"] = update.effective_user.id
    reports[report_id]["resolved_time"] = datetime.now().isoformat()
    save_reports()
    
    await safe_reply(update, context, f"✅ Жалоба #{report_id} закрыта, сука!")
    await add_log(f"RESOLVE REPORT #{report_id}", update.effective_user.id, 0, "Жалоба рассмотрена")

# --- КОМАНДА ЗАКРЕПЛЕНИЯ ---
async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not update.message or not update.message.reply_to_message:
        await safe_reply(update, context, "📌 Ответь на сообщение, которое хочешь закрепить, блять!")
        return
    
    try:
        await context.bot.pin_chat_message(
            chat_id=CHAT_ID,
            message_id=update.message.reply_to_message.message_id,
            disable_notification=False
        )
        await safe_reply(update, context, "📌 Сообщение закреплено, сука!")
        await add_log("PIN", update.effective_user.id, 0, "Закреплено сообщение")
    except Exception as e:
        await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")

async def unpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not update.message or not update.message.reply_to_message:
        await safe_reply(update, context, "📌 Ответь на сообщение, которое хочешь открепить, блять!")
        return
    
    try:
        await context.bot.unpin_chat_message(
            chat_id=CHAT_ID,
            message_id=update.message.reply_to_message.message_id
        )
        await safe_reply(update, context, "📌 Сообщение откреплено, сука!")
        await add_log("UNPIN", update.effective_user.id, 0, "Откреплено сообщение")
    except Exception as e:
        await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")

async def pinned_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pinned = await context.bot.get_chat(chat_id=CHAT_ID)
        if pinned.pinned_message:
            await safe_reply(update, context,
                f"📌 **Закрепленное сообщение:**\n\n"
                f"{pinned.pinned_message.text or 'Сообщение без текста, блять!'}",
                parse_mode='Markdown'
            )
        else:
            await safe_reply(update, context, "📌 Закрепленных сообщений нет, нахуй!")
    except Exception as e:
        await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")

# --- КАСТОМНЫЕ КОМАНДЫ ---
async def addcmd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if len(context.args) < 2:
        await safe_reply(update, context,
            "/addcmd [название] [ответ]\n"
            "Пример: /addcmd привет Привет, ебать!"
        )
        return
    
    cmd_name = context.args[0].lower()
    response = " ".join(context.args[1:])
    
    if cmd_name in ['help', 'menu', 'rules', 'stats', 'profile', 'top', 'nightmode']:
        await safe_reply(update, context, f"❌ Команда /{cmd_name} уже существует, блять!")
        return
    
    custom_commands[cmd_name] = response
    save_commands()
    await safe_reply(update, context, f"✅ Команда /{cmd_name} добавлена, сука!\nОтвет: {response}")
    await add_log(f"ADDCMD /{cmd_name}", update.effective_user.id, 0, response)

async def delcmd_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not context.args:
        await safe_reply(update, context, "/delcmd [название]")
        return
    
    cmd_name = context.args[0].lower()
    
    if cmd_name not in custom_commands:
        await safe_reply(update, context, f"❌ Команда /{cmd_name} не найдена, блять!")
        return
    
    del custom_commands[cmd_name]
    save_commands()
    await safe_reply(update, context, f"✅ Команда /{cmd_name} удалена, сука!")
    await add_log(f"DELCMD /{cmd_name}", update.effective_user.id, 0, "Команда удалена")

async def cmds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not custom_commands:
        await safe_reply(update, context, "📋 Кастомных команд нет, блять! Добавьте через /addcmd")
        return
    
    cmd_list = "📋 **Кастомные команды:**\n\n"
    for cmd, response in custom_commands.items():
        cmd_list += f"🔹 /{cmd} - {response[:50]}{'...' if len(response) > 50 else ''}\n"
    
    await safe_reply(update, context, cmd_list, parse_mode='Markdown')

# --- ПОГОДА ---
async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await safe_reply(update, context, "🌤️ Используй: /weather [город]\nПример: /weather Москва")
        return
    
    city = " ".join(context.args)
    
    WEATHER_API_KEY = "ТВОЙ_API_КЛЮЧ_ДЛЯ_ПОГОДЫ"
    if not WEATHER_API_KEY or WEATHER_API_KEY == "ТВОЙ_API_КЛЮЧ_ДЛЯ_ПОГОДЫ":
        await safe_reply(update, context, "❌ API ключ для погоды не настроен, блять!")
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
            async with session.get(url) as response:
                data = await response.json()
                
                if data.get("cod") != 200:
                    await safe_reply(update, context, f"❌ Город {city} не найден, блять!")
                    return
                
                weather_data = data["main"]
                weather_desc = data["weather"][0]["description"]
                wind = data["wind"]["speed"]
                
                weather_text = f"""
🌤️ **Погода в {city}:**

🌡️ Температура: {weather_data['temp']}°C
🤔 Ощущается: {weather_data['feels_like']}°C
💧 Влажность: {weather_data['humidity']}%
☁️ Описание: {weather_desc.capitalize()}
💨 Ветер: {wind} м/с
                """
                await safe_reply(update, context, weather_text, parse_mode='Markdown')
    except Exception as e:
        await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")

# --- ЛОГИ ---
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not admin_logs:
        await safe_reply(update, context, "📋 Логов нет, сука!")
        return
    
    logs_to_show = admin_logs[-20:]
    log_text = "📋 **Последние логи модерации:**\n\n"
    
    for log in reversed(logs_to_show):
        time = log.get("time", "Неизвестно")[:19]
        action = log.get("action", "Неизвестно")
        admin = await get_user_name(context, log.get("admin", 0))
        target = await get_user_name(context, log.get("target", 0))
        reason = log.get("reason", "")
        
        log_text += f"🕐 {time}\n"
        log_text += f"   ⚡ {action}\n"
        log_text += f"   👤 Админ: {admin}\n"
        log_text += f"   👤 Цель: {target}\n"
        if reason:
            log_text += f"   📌 Причина: {reason}\n"
        log_text += "\n"
    
    if len(log_text) > 4000:
        log_text = log_text[:4000] + "\n... (слишком много, блять!)"
    
    await safe_reply(update, context, log_text, parse_mode='Markdown')

# --- ЕЖЕДНЕВНЫЙ ОТЧЕТ ---
async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    today = now.date().isoformat()
    day_stats = {"messages": 0, "bans": 0, "mutes": 0, "warns": 0}
    
    for user_id, times in user_message_times.items():
        for t in times:
            if t.date().isoformat() == today:
                day_stats["messages"] += 1
    
    for log in admin_logs:
        if log.get("time", "").startswith(today):
            action = log.get("action", "")
            if "BAN" in action:
                day_stats["bans"] += 1
            elif "MUTE" in action:
                day_stats["mutes"] += 1
            elif "WARN" in action:
                day_stats["warns"] += 1
    
    report_text = f"""
📊 **ЕЖЕДНЕВНЫЙ ОТЧЕТ 403Team**
📅 Дата: {now.strftime('%d.%m.%Y')}

📝 **Статистика за день:**
• Сообщений: {day_stats['messages']}
• Банов: {day_stats['bans']}
• Мутов: {day_stats['mutes']}
• Варнов: {day_stats['warns']}

👥 **Активность:**
• Активных пользователей: {len([u for u, t in user_message_times.items() if any(tm.date().isoformat() == today for tm in t)])}
    """
    
    for admin_id in chat_admins:
        try:
            await context.bot.send_message(chat_id=admin_id, text=report_text, parse_mode='Markdown')
        except:
            pass
    
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=report_text, parse_mode='Markdown')
    except:
        pass
    
    logger.info("Ежедневный отчет отправлен")

# --- ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.from_user:
        return

    user = update.message.from_user
    user_id = user.id
    message_text = update.message.text or ""
    message_caption = update.message.caption or ""

    if is_admin(user_id):
        return

    # --- КАСТОМНЫЕ КОМАНДЫ ---
    if message_text.startswith('/'):
        cmd = message_text[1:].split()[0].lower()
        if cmd in custom_commands:
            await update.message.reply_text(custom_commands[cmd])
            return

    # --- НОЧНОЙ РЕЖИМ ---
    if is_night_mode():
        await update.message.delete()
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🌙 {await get_user_name(context, user_id)}, ночной режим, блять! Пиши с {NIGHT_MODE_END}:00!"
        )
        return

    # --- АВТО-ОТВЕТЫ ---
    lower_text = message_text.lower()
    for keyword, response in AUTO_RESPONSES.items():
        if keyword in lower_text:
            await update.message.reply_text(response)
            break

    # --- СТАТИСТИКА СООБЩЕНИЙ ---
    stats["total_messages"] += 1
    save_stats(stats)
    user_messages_count[user_id] += 1
    
    # --- СИСТЕМА УРОВНЕЙ ---
    leveled_up = await add_xp(user_id, random.randint(1, 3))
    if leveled_up:
        new_level = user_levels.get(user_id, 0)
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🎉 {await get_user_name(context, user_id)} повысил уровень до {new_level}, блять!"
        )

    # --- АНТИ-ФЛУД ЭМОДЗИ ---
    full_text = message_text + message_caption
    import emoji
    emojis_found = [c for c in full_text if c in emoji.EMOJI_DATA]
    
    if emojis_found:
        emoji_counts = {}
        for e in emojis_found:
            emoji_counts[e] = emoji_counts.get(e, 0) + 1
        
        for e, count in emoji_counts.items():
            if count > EMOJI_LIMIT:
                await warn_user(update, context, user_id, f"Флуд эмодзи '{e}' (Правило 1)", await get_user_name(context, user_id))
                await update.message.delete()
                return

    # --- ПРОВЕРКА НА МАТ ---
    if re.search(BAD_WORDS_PATTERN, message_text, re.IGNORECASE):
        await warn_user(update, context, user_id, "Использование мата, блять! (Правило 2)", await get_user_name(context, user_id))
        await update.message.delete()
        return

    # --- АНТИСПАМ ---
    current_time = datetime.now()
    user_message_times[user_id].append(current_time)
    
    user_message_times[user_id] = [
        t for t in user_message_times[user_id] 
        if (current_time - t).total_seconds() < SPAM_TIME_WINDOW
    ]

    if len(user_message_times[user_id]) > SPAM_MESSAGE_LIMIT:
        await warn_user(update, context, user_id, "Спам, пиздец! (Правило 1)", await get_user_name(context, user_id))
        await mute_user(update, context, user_id, MUTE_DURATION * 2, await get_user_name(context, user_id))
        await update.message.delete()
        user_message_times[user_id] = []
        return

    # --- ПРОВЕРКА НА ССЫЛКИ ---
    if 'http' in message_text.lower() or 'www.' in message_text.lower():
        await warn_user(update, context, user_id, "Реклама/ссылки запрещены! (Правило 3)", await get_user_name(context, user_id))
        await update.message.delete()
        return

    # --- ПРОВЕРКА НА ДЛИНУ ---
    if len(message_text) > 500:
        await warn_user(update, context, user_id, "Слишком длинное сообщение! (Правило 1)", await get_user_name(context, user_id))
        await update.message.delete()
        return

    # --- ПРОВЕРКА НА КАПС ---
    if len(message_text) > 10:
        caps_ratio = sum(1 for c in message_text if c.isupper()) / len(message_text)
        if caps_ratio > 0.7:
            await warn_user(update, context, user_id, "Кричал капсом! (Правило 2)", await get_user_name(context, user_id))
            await update.message.delete()
            return

    # --- ПРОВЕРКА НА ПОЛИТИКУ ---
    politics_words = ['путин', 'зеленский', 'война', 'политика', 'навальный', 'кремль', 'санкции', 'донбасс', 'крым']
    if any(word in message_text.lower() for word in politics_words):
        await warn_user(update, context, user_id, "Обсуждение политики запрещено! (Правило 4)", await get_user_name(context, user_id))
        await update.message.delete()
        return

    # --- ПРОВЕРКА НА УГРОЗЫ ---
    threats = ['убью', 'убьют', 'смерть', 'закопаю', 'сломаю', 'уничтожу', 'убей', 'мочить']
    if any(word in message_text.lower() for word in threats):
        await ban_user(update, context, user_id, await get_user_name(context, user_id), "Угрозы участникам (Правило 6)")
        await update.message.delete()
        return

# --- АДМИНСКИЕ КОМАНДЫ ---
async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    admin_id = update.effective_user.id
    target_id = await get_target_id_from_reply(update)
    target_name = None
    
    if target_id:
        if target_id == admin_id:
            await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя кикнуть хочешь?! Иди нахуй!")
            return
        target_name = await get_user_name(context, target_id)
        if target_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя кикнуть, блять!")
            return
        await kick_user(update, context, target_id, target_name)
        return
    
    if not context.args:
        await safe_reply(update, context, "Используй: /kick @username или /kick user_id\nИли ответь на сообщение!")
        return
    
    try:
        target = context.args[0]
        if target.startswith('@'):
            target_id = await get_user_id_by_username(update, context, target)
            if target_id:
                if target_id == admin_id:
                    await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя кикнуть хочешь?! Иди нахуй!")
                    return
                target_name = target
                if target_id == OWNER_ID:
                    await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя кикнуть, блять!")
                    return
                await kick_user(update, context, target_id, target_name)
        elif target.isdigit():
            target_id = int(target)
            if target_id == admin_id:
                await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя кикнуть хочешь?! Иди нахуй!")
                return
            target_name = await get_user_name(context, target_id)
            if target_id == OWNER_ID:
                await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя кикнуть, блять!")
                return
            await kick_user(update, context, target_id, target_name)
        else:
            await safe_reply(update, context, "Неверный формат, сука!")
    except Exception as e:
        await safe_reply(update, context, f"Ошибка: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять!")
        return
    
    admin_id = update.effective_user.id
    duration = 60
    if context.args and context.args[0].isdigit():
        duration = int(context.args[0])
    
    target_id = await get_target_id_from_reply(update)
    target_name = None
    
    if target_id:
        if target_id == admin_id:
            await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя замутить хочешь?! Иди нахуй!")
            return
        target_name = await get_user_name(context, target_id)
        if target_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя замутить, блять!")
            return
        await mute_user(update, context, target_id, duration, target_name)
        return
    
    if len(context.args) < 1:
        await safe_reply(update, context, "/mute [секунды] @username\nИли ответь на сообщение!")
        return
    
    try:
        if not context.args[0].isdigit():
            target = context.args[0]
            if target.startswith('@'):
                target_id = await get_user_id_by_username(update, context, target)
                if target_id:
                    if target_id == admin_id:
                        await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя замутить хочешь?! Иди нахуй!")
                        return
                    target_name = target
                    if target_id == OWNER_ID:
                        await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя замутить, блять!")
                        return
                    await mute_user(update, context, target_id, duration, target_name)
            else:
                await safe_reply(update, context, "Неверный формат, нахуй!")
        else:
            if len(context.args) >= 2:
                duration = int(context.args[0])
                target = context.args[1]
                if target.startswith('@'):
                    target_id = await get_user_id_by_username(update, context, target)
                    if target_id:
                        if target_id == admin_id:
                            await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя замутить хочешь?! Иди нахуй!")
                            return
                        target_name = target
                        if target_id == OWNER_ID:
                            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя замутить, блять!")
                            return
                        await mute_user(update, context, target_id, duration, target_name)
                elif target.isdigit():
                    target_id = int(target)
                    if target_id == admin_id:
                        await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя замутить хочешь?! Иди нахуй!")
                        return
                    target_name = await get_user_name(context, target_id)
                    if target_id == OWNER_ID:
                        await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя замутить, блять!")
                        return
                    await mute_user(update, context, target_id, duration, target_name)
            else:
                await safe_reply(update, context, "Неверный формат, блять!")
    except Exception as e:
        await safe_reply(update, context, f"Ошибка: {e}")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять!")
        return
    
    admin_id = update.effective_user.id
    target_id = await get_target_id_from_reply(update)
    target_name = None
    
    if target_id:
        if target_id == admin_id:
            await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя забанить хочешь?! Иди нахуй!")
            return
        target_name = await get_user_name(context, target_id)
        if target_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя забанить, блять!")
            return
        await ban_user(update, context, target_id, target_name)
        return
    
    if not context.args:
        await safe_reply(update, context, "/ban @username\nИли ответь на сообщение!")
        return
    
    try:
        target = context.args[0]
        if target.startswith('@'):
            target_id = await get_user_id_by_username(update, context, target)
            if target_id:
                if target_id == admin_id:
                    await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя забанить хочешь?! Иди нахуй!")
                    return
                target_name = target
                if target_id == OWNER_ID:
                    await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя забанить, блять!")
                    return
                await ban_user(update, context, target_id, target_name)
        elif target.isdigit():
            target_id = int(target)
            if target_id == admin_id:
                await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себя забанить хочешь?! Иди нахуй!")
                return
            target_name = await get_user_name(context, target_id)
            if target_id == OWNER_ID:
                await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя забанить, блять!")
                return
            await ban_user(update, context, target_id, target_name)
        else:
            await safe_reply(update, context, "Неверный формат, сука!")
    except Exception as e:
        await safe_reply(update, context, f"Ошибка: {e}")

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять!")
        return
    
    admin_id = update.effective_user.id
    target_id = await get_target_id_from_reply(update)
    target_name = None
    reason = "Ручное предупреждение"
    
    if target_id:
        if target_id == admin_id:
            await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себе варн хочешь выдать?! Иди нахуй!")
            return
        target_name = await get_user_name(context, target_id)
        if target_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя предупредить, блять!")
            return
        if context.args:
            reason = " ".join(context.args)
        await warn_user(update, context, target_id, reason, target_name)
        return
    
    if len(context.args) < 1:
        await safe_reply(update, context, "/warn @username [причина]\nИли ответь на сообщение!")
        return
    
    try:
        target = context.args[0]
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Ручное предупреждение"
        
        if target.startswith('@'):
            target_id = await get_user_id_by_username(update, context, target)
            if target_id:
                if target_id == admin_id:
                    await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себе варн хочешь выдать?! Иди нахуй!")
                    return
                target_name = target
                if target_id == OWNER_ID:
                    await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя предупредить, блять!")
                    return
                await warn_user(update, context, target_id, reason, target_name)
        elif target.isdigit():
            target_id = int(target)
            if target_id == admin_id:
                await safe_reply(update, context, "😈 Ты че, ебаный мазохист? Сам себе варн хочешь выдать?! Иди нахуй!")
                return
            target_name = await get_user_name(context, target_id)
            if target_id == OWNER_ID:
                await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя предупредить, блять!")
                return
            await warn_user(update, context, target_id, reason, target_name)
        else:
            await safe_reply(update, context, "Неверный формат, сука!")
    except Exception as e:
        await safe_reply(update, context, f"Ошибка: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not context.args:
        await safe_reply(update, context, "/unban @username\nИли ответь на сообщение!")
        return
    
    target = context.args[0]
    if target.startswith('@'):
        user_id = await get_user_id_by_username(update, context, target)
        if user_id:
            if user_id == OWNER_ID:
                await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя трогать!")
                return
            try:
                await context.bot.unban_chat_member(chat_id=CHAT_ID, user_id=user_id)
                if str(user_id) in bans:
                    del bans[str(user_id)]
                    save_bans(bans)
                await safe_reply(update, context, f"✅ {target} разбанен, сука!")
                await add_log("UNBAN", update.effective_user.id, user_id, "Разбанен")
                logger.info(f"Unbanned user {user_id}")
            except Exception as e:
                await safe_reply(update, context, f"Ошибка: {e}")
    elif target.isdigit():
        user_id = int(target)
        target_name = await get_user_name(context, user_id)
        if user_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя трогать!")
            return
        try:
            await context.bot.unban_chat_member(chat_id=CHAT_ID, user_id=user_id)
            if str(user_id) in bans:
                del bans[str(user_id)]
                save_bans(bans)
            await safe_reply(update, context, f"✅ {target_name} разбанен, сука!")
            await add_log("UNBAN", update.effective_user.id, user_id, "Разбанен")
        except Exception as e:
            await safe_reply(update, context, f"Ошибка: {e}")
    else:
        await safe_reply(update, context, "Неверный формат, нахуй!")

async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    target_id = await get_target_id_from_reply(update)
    target_name = None
    
    if target_id:
        target_name = await get_user_name(context, target_id)
        if target_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя трогать!")
            return
        if str(target_id) not in warns:
            await safe_reply(update, context, f"⚠️ У {target_name} нет предупреждений, блять!")
            return
        del warns[str(target_id)]
        save_warns(warns)
        if target_id in warning_count:
            del warning_count[target_id]
        await safe_reply(update, context, f"✅ {target_name} сняты все предупреждения, сука!")
        await add_log("UNWARN", update.effective_user.id, target_id, "Сняты предупреждения")
        return
    
    if not context.args:
        await safe_reply(update, context, "/unwarn @username\nИли ответь на сообщение!")
        return
    
    target = context.args[0]
    if target.startswith('@'):
        target_id = await get_user_id_by_username(update, context, target)
        if target_id:
            target_name = target
            if target_id == OWNER_ID:
                await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя трогать!")
                return
            if str(target_id) not in warns:
                await safe_reply(update, context, f"⚠️ У {target_name} нет предупреждений, блять!")
                return
            del warns[str(target_id)]
            save_warns(warns)
            if target_id in warning_count:
                del warning_count[target_id]
            await safe_reply(update, context, f"✅ {target_name} сняты все предупреждения, сука!")
            await add_log("UNWARN", update.effective_user.id, target_id, "Сняты предупреждения")
    elif target.isdigit():
        target_id = int(target)
        target_name = await get_user_name(context, target_id)
        if target_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя трогать!")
            return
        if str(target_id) not in warns:
            await safe_reply(update, context, f"⚠️ У {target_name} нет предупреждений, блять!")
            return
        del warns[str(target_id)]
        save_warns(warns)
        if target_id in warning_count:
            del warning_count[target_id]
        await safe_reply(update, context, f"✅ {target_name} сняты все предупреждения, сука!")
        await add_log("UNWARN", update.effective_user.id, target_id, "Сняты предупреждения")
    else:
        await safe_reply(update, context, "Неверный формат, нахуй!")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    target_id = await get_target_id_from_reply(update)
    target_name = None
    
    if target_id:
        target_name = await get_user_name(context, target_id)
        if target_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя трогать!")
            return
        if str(target_id) not in mutes:
            await safe_reply(update, context, f"⚠️ {target_name} не в муте, блять!")
            return
        try:
            await context.bot.restrict_chat_member(
                chat_id=CHAT_ID,
                user_id=target_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
            )
            del mutes[str(target_id)]
            save_mutes(mutes)
            await safe_reply(update, context, f"✅ {target_name} размучен, сука! Может говорить!")
            await add_log("UNMUTE", update.effective_user.id, target_id, "Размучен")
        except Exception as e:
            await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")
        return
    
    if not context.args:
        await safe_reply(update, context, "/unmute @username\nИли ответь на сообщение!")
        return
    
    target = context.args[0]
    if target.startswith('@'):
        target_id = await get_user_id_by_username(update, context, target)
        if target_id:
            target_name = target
            if target_id == OWNER_ID:
                await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя трогать!")
                return
            if str(target_id) not in mutes:
                await safe_reply(update, context, f"⚠️ {target_name} не в муте, блять!")
                return
            try:
                await context.bot.restrict_chat_member(
                    chat_id=CHAT_ID,
                    user_id=target_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_change_info=False,
                        can_invite_users=False,
                        can_pin_messages=False
                    )
                )
                del mutes[str(target_id)]
                save_mutes(mutes)
                await safe_reply(update, context, f"✅ {target_name} размучен, сука! Может говорить!")
                await add_log("UNMUTE", update.effective_user.id, target_id, "Размучен")
            except Exception as e:
                await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")
    elif target.isdigit():
        target_id = int(target)
        target_name = await get_user_name(context, target_id)
        if target_id == OWNER_ID:
            await safe_reply(update, context, "⛔ Это владелец бота, сука! Его нельзя трогать!")
            return
        if str(target_id) not in mutes:
            await safe_reply(update, context, f"⚠️ {target_name} не в муте, блять!")
            return
        try:
            await context.bot.restrict_chat_member(
                chat_id=CHAT_ID,
                user_id=target_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
            )
            del mutes[str(target_id)]
            save_mutes(mutes)
            await safe_reply(update, context, f"✅ {target_name} размучен, сука! Может говорить!")
            await add_log("UNMUTE", update.effective_user.id, target_id, "Размучен")
        except Exception as e:
            await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")
    else:
        await safe_reply(update, context, "Неверный формат, нахуй!")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    count = 5
    if context.args and context.args[0].isdigit():
        count = min(int(context.args[0]), 100)
    
    try:
        if not update.message:
            await safe_reply(update, context, "❌ Эта команда доступна только через текстовое сообщение!")
            return
        message_id = update.message.message_id
        deleted = 0
        for i in range(count):
            try:
                await context.bot.delete_message(chat_id=CHAT_ID, message_id=message_id - i)
                deleted += 1
            except:
                pass
        await safe_reply(update, context, f"🧹 Очищено {deleted} сообщений, ебать!")
        await add_log(f"CLEAR {deleted}", update.effective_user.id, 0, f"Очищено {deleted} сообщений")
    except Exception as e:
        await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")

# --- КОМАНДЫ СПИСКОВ ---
async def banlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not bans:
        await safe_reply(update, context, "📋 Список банов пуст, сука! Никого не забанили еще!")
        return
    
    ban_list = "🚫 **Список забаненных пользователей:**\n\n"
    for user_id_str, data in bans.items():
        user_id = int(user_id_str)
        user_name = await get_user_name(context, user_id)
        reason = data.get("reason", "Не указана")
        time = data.get("time", "Неизвестно")
        ban_list += f"👤 {user_name}\n   📌 Причина: {reason}\n   🕐 Время: {time[:19]}\n\n"
    
    if len(ban_list) > 4000:
        ban_list = ban_list[:4000] + "\n... (слишком много банов, блять!)"
    
    await safe_reply(update, context, ban_list, parse_mode='Markdown')

async def warnlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    if not warns:
        await safe_reply(update, context, "📋 Список предупреждений пуст, сука! Все хорошие!")
        return
    
    warn_list = "⚠️ **Список пользователей с предупреждениями:**\n\n"
    for user_id_str, data in warns.items():
        user_id = int(user_id_str)
        user_name = await get_user_name(context, user_id)
        count = data.get("count", 0)
        last_reason = data.get("last_reason", "Не указана")
        warn_list += f"👤 {user_name}\n   ⚠️ Предупреждений: {count}/{MAX_WARNINGS}\n   📌 Последнее: {last_reason}\n\n"
    
    if len(warn_list) > 4000:
        warn_list = warn_list[:4000] + "\n... (слишком много, блять!)"
    
    await safe_reply(update, context, warn_list, parse_mode='Markdown')

async def mutelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    current_time = datetime.now()
    active_mutes = {}
    for user_id_str, data in mutes.items():
        until_str = data.get("until")
        if until_str:
            try:
                until = datetime.fromisoformat(until_str)
                if until > current_time:
                    active_mutes[user_id_str] = data
            except:
                pass
    
    if not active_mutes:
        await safe_reply(update, context, "📋 Список мутов пуст, сука! Все разговорились!")
        return
    
    mute_list = "🔇 **Список замьюченных пользователей:**\n\n"
    for user_id_str, data in active_mutes.items():
        user_id = int(user_id_str)
        user_name = await get_user_name(context, user_id)
        duration = data.get("duration", 60)
        until_str = data.get("until", "Неизвестно")
        try:
            until = datetime.fromisoformat(until_str)
            remaining = int((until - current_time).total_seconds())
            minutes = remaining // 60
            seconds = remaining % 60
            time_left = f"{minutes}м {seconds}с"
        except:
            time_left = "Неизвестно"
        
        mute_list += f"👤 {user_name}\n   ⏱️ Осталось: {time_left}\n   📌 Длительность: {duration} сек\n\n"
    
    if len(mute_list) > 4000:
        mute_list = mute_list[:4000] + "\n... (слишком много, блять!)"
    
    await safe_reply(update, context, mute_list, parse_mode='Markdown')

# --- КОМАНДЫ ПРАВИЛ ---
async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Я ознакомился с правилами!", callback_data="rules_accepted")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await safe_reply(update, context, RULES_TEXT, parse_mode='Markdown', reply_markup=reply_markup)

async def rules_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_name = await get_user_name(context, update.effective_user.id)
    await query.edit_message_text(f"✅ {user_name}, спасибо что ознакомился с правилами, блять!\nНарушишь - получишь бан, нахуй!")
    await asyncio.sleep(5)
    await query.delete_message()

# --- КОМАНДЫ СТАТИСТИКИ ---
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    try:
        chat_members_count = await context.bot.get_chat_member_count(chat_id=CHAT_ID)
        total_messages = stats.get("total_messages", 0)
        total_bans = stats.get("total_bans", 0)
        total_mutes = stats.get("total_mutes", 0)
        total_warns = stats.get("total_warns", 0)
        active_users = len([u for u, t in user_message_times.items() if len(t) > 0])
        
        stats_text = f"""
📊 **СТАТИСТИКА 403Team:**

👥 **Участники:**
• Всего: {chat_members_count}
• Активных за день: {active_users}

📝 **Сообщения:**
• Всего: {total_messages}

🛡️ **Модерация:**
• Банов: {total_bans}
• Мутов: {total_mutes}
• Варнов: {total_warns}

📋 **Жалобы:**
• Всего: {len(reports)}
• Активных: {len([r for r in reports.values() if r.get('status') == 'active'])}

🏆 **Уровни:**
• Всего: {len(user_levels)}
• Максимальный: {max(user_levels.values()) if user_levels else 0}
        """
        await safe_reply(update, context, stats_text, parse_mode='Markdown')
    except Exception as e:
        await safe_reply(update, context, f"❌ Ошибка: {e}, блять!")

# --- КОМАНДА ПРОФИЛЯ ---
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    target_id = user_id
    
    if context.args:
        target = context.args[0]
        if target.startswith('@'):
            target_id = await get_user_id_by_username(update, context, target)
            if not target_id:
                await safe_reply(update, context, f"❌ Не найден пользователь {target}, блять!")
                return
        elif target.isdigit():
            target_id = int(target)
        else:
            await safe_reply(update, context, "Неверный формат, нахуй!")
            return
    
    target_name = await get_user_name(context, target_id)
    level = user_levels.get(target_id, 0)
    xp = user_xp.get(target_id, 0)
    xp_needed = (level + 1) * 10
    rank = await get_rank(target_id)
    messages = user_messages_count.get(target_id, 0)
    warns_count = warning_count.get(target_id, 0)
    is_banned = str(target_id) in bans
    
    profile_text = f"""
👤 **ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ**

**{target_name}**

🏆 **Ранг:** {rank}
📊 **Уровень:** {level}
⭐ **Опыт:** {xp}/{xp_needed} XP
💬 **Сообщений:** {messages}
⚠️ **Предупреждений:** {warns_count}/{MAX_WARNINGS}
🚫 **В бане:** {"ДА, сука!" if is_banned else "Нет, блять!"}
    """
    await safe_reply(update, context, profile_text, parse_mode='Markdown')

# --- ТОП ПОЛЬЗОВАТЕЛЕЙ ---
async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_messages_count:
        await safe_reply(update, context, "📊 Статистики пока нет, блять!")
        return
    
    top_text = "🏆 **ТОП ПОЛЬЗОВАТЕЛЕЙ 403Team:**\n\n"
    top_text += "**По сообщениям:**\n"
    
    top_users = sorted(user_messages_count.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (user_id, count) in enumerate(top_users, 1):
        user_name = await get_user_name(context, user_id)
        level = user_levels.get(user_id, 0)
        rank = await get_rank(user_id)
        top_text += f"{i}. {user_name}\n   💬 {count} сообщений | Уровень {level} | {rank}\n"
    
    await safe_reply(update, context, top_text, parse_mode='Markdown')

# --- КОМАНДА НОЧНОГО РЕЖИМА ---
async def nightmode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await safe_reply(update, context, "⛔ Ты не админ бота, блять! Иди нахуй!")
        return
    
    is_night = is_night_mode()
    status = "🟢 ВКЛЮЧЕН" if is_night else "🔴 ВЫКЛЮЧЕН"
    time_range = f"{NIGHT_MODE_START}:00 - {NIGHT_MODE_END}:00"
    
    await safe_reply(update, context,
        f"🌙 **Ночной режим:**\n"
        f"Статус: {status}\n"
        f"Время: {time_range}\n\n"
        f"В ночной режим сообщения от обычных пользователей блокируются, блять!"
    )

# --- КОМАНДЫ УПРАВЛЕНИЯ АДМИНАМИ ---
async def setadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await safe_reply(update, context, "⛔ Ты не владелец бота, блять! Только создатель может добавлять админов!")
        return
    
    if not context.args:
        await safe_reply(update, context, "Используй: /setadmin @username или /setadmin user_id")
        return
    
    target = context.args[0]
    target_id = None
    target_name = target
    
    if target.startswith('@'):
        target_id = await get_user_id_by_username(update, context, target)
        if not target_id:
            await safe_reply(update, context, f"❌ Не найден пользователь {target}, блять!")
            return
        target_name = target
    elif target.isdigit():
        target_id = int(target)
        target_name = await get_user_name(context, target_id)
    else:
        await safe_reply(update, context, "❌ Неверный формат, нахуй! Используй @username или ID")
        return
    
    if target_id == OWNER_ID:
        await safe_reply(update, context, "⚠️ Это владелец бота, он и так админ, ебать!")
        return
    
    if target_id in chat_admins:
        await safe_reply(update, context, f"⚠️ {target_name} уже админ, ебать!")
        return
    
    chat_admins.add(target_id)
    save_admins()
    await safe_reply(update, context, f"✅ {target_name} теперь админ, сука! Может пользоваться ботом!")
    await add_log("SETADMIN", user_id, target_id, "Добавлен админ")

async def removeadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await safe_reply(update, context, "⛔ Только владелец бота может удалять админов, блять!")
        return
    
    if not context.args:
        await safe_reply(update, context, "Используй: /removeadmin @username или /removeadmin user_id")
        return
    
    target = context.args[0]
    target_id = None
    target_name = target
    
    if target.startswith('@'):
        target_id = await get_user_id_by_username(update, context, target)
        if not target_id:
            await safe_reply(update, context, f"❌ Не найден пользователь {target}, блять!")
            return
        target_name = target
    elif target.isdigit():
        target_id = int(target)
        target_name = await get_user_name(context, target_id)
    else:
        await safe_reply(update, context, "❌ Неверный формат, нахуй!")
        return
    
    if target_id == OWNER_ID:
        await safe_reply(update, context, "⚠️ Это владелец бота, его нельзя удалить, ебать!")
        return
    
    if target_id not in chat_admins:
        await safe_reply(update, context, f"⚠️ {target_name} не админ, ебать!")
        return
    
    chat_admins.remove(target_id)
    save_admins()
    await safe_reply(update, context, f"✅ {target_name} больше не админ, сука!")
    await add_log("REMOVEADMIN", user_id, target_id, "Удален админ")

async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner_name = await get_user_name(context, OWNER_ID)
    admin_list = f"👑 **Владелец:** {owner_name}\n\n"
    
    if not chat_admins:
        admin_list += "📋 Других админов нет, блять!"
    else:
        admin_list += "📋 **Админы бота:**\n\n"
        for admin_id in chat_admins:
            admin_name = await get_user_name(context, admin_id)
            admin_list += f"👮 {admin_name}\n"
    
    await safe_reply(update, context, admin_list, parse_mode='Markdown')

# --- МЕНЮ ---
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📜 Правила", callback_data="menu_rules"),
            InlineKeyboardButton("📊 Статистика", callback_data="menu_stats")
        ],
        [
            InlineKeyboardButton("👤 Мой профиль", callback_data="menu_profile"),
            InlineKeyboardButton("🏆 Топ", callback_data="menu_top")
        ],
        [
            InlineKeyboardButton("📋 Админы", callback_data="menu_admins"),
            InlineKeyboardButton("🌙 Ночной режим", callback_data="menu_night")
        ],
        [
            InlineKeyboardButton("📝 Жалобы", callback_data="menu_reports"),
            InlineKeyboardButton("📌 Закрепленные", callback_data="menu_pinned")
        ],
        [
            InlineKeyboardButton("📋 Команды", callback_data="menu_cmds"),
            InlineKeyboardButton("🌤️ Погода", callback_data="menu_weather")
        ],
        [
            InlineKeyboardButton("🆘 Помощь", callback_data="menu_help")
        ]
    ]
    
    if is_admin(update.effective_user.id):
        keyboard.append([
            InlineKeyboardButton("🔧 Админ-панель", callback_data="menu_admin_panel")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🤖 **Главное меню 403Team Bot**\n"
            "Выбери нужный раздел, блять!",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🤖 **Главное меню 403Team Bot**\n"
            "Выбери нужный раздел, блять!",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "menu_rules":
        await query.edit_message_text(RULES_TEXT, parse_mode='Markdown')
        await asyncio.sleep(2)
        await query.delete_message()
        await menu_command(update, context)
    
    elif action == "menu_stats":
        await stats_command(update, context)
        await query.delete_message()
    
    elif action == "menu_profile":
        await profile_command(update, context)
        await query.delete_message()
    
    elif action == "menu_top":
        await top_command(update, context)
        await query.delete_message()
    
    elif action == "menu_admins":
        await admins_command(update, context)
        await query.delete_message()
    
    elif action == "menu_night":
        await nightmode_command(update, context)
        await query.delete_message()
    
    elif action == "menu_reports":
        await reports_command(update, context)
        await query.delete_message()
    
    elif action == "menu_pinned":
        await pinned_command(update, context)
        await query.delete_message()
    
    elif action == "menu_cmds":
        await cmds_command(update, context)
        await query.delete_message()
    
    elif action == "menu_weather":
        await query.edit_message_text(
            "🌤️ **Погода**\n"
            "Используй команду: /weather [город]\n"
            "Пример: /weather Москва\n\n"
            "Нажми /menu чтобы вернуться, блять!",
            parse_mode='Markdown'
        )
        await asyncio.sleep(2)
        await query.delete_message()
        await menu_command(update, context)
    
    elif action == "menu_help":
        await help_command(update, context)
        await query.delete_message()
    
    elif action == "menu_admin_panel":
        if not is_admin(update.effective_user.id):
            await query.edit_message_text("⛔ Ты не админ, блять! Иди нахуй!")
            await asyncio.sleep(2)
            await query.delete_message()
            await menu_command(update, context)
            return
        
        keyboard = [
            [
                InlineKeyboardButton("👢 Кикнуть", callback_data="admin_kick"),
                InlineKeyboardButton("🔇 Замутить", callback_data="admin_mute")
            ],
            [
                InlineKeyboardButton("🚫 Забанить", callback_data="admin_ban"),
                InlineKeyboardButton("⚠️ Выдать варн", callback_data="admin_warn")
            ],
            [
                InlineKeyboardButton("📊 Списки", callback_data="admin_lists"),
                InlineKeyboardButton("🧹 Очистить", callback_data="admin_clear")
            ],
            [
                InlineKeyboardButton("📝 Жалобы", callback_data="admin_reports"),
                InlineKeyboardButton("📋 Логи", callback_data="admin_logs")
            ],
            [
                InlineKeyboardButton("➕ Добавить команду", callback_data="admin_addcmd"),
                InlineKeyboardButton("🗑️ Удалить команду", callback_data="admin_delcmd")
            ],
            [
                InlineKeyboardButton("🔙 Главное меню", callback_data="menu_back")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🔧 **Админ-панель**\n"
            "Выбери действие, блять!",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif action == "admin_lists":
        keyboard = [
            [
                InlineKeyboardButton("🚫 Банлист", callback_data="admin_banlist"),
                InlineKeyboardButton("⚠️ Варнлист", callback_data="admin_warnlist")
            ],
            [
                InlineKeyboardButton("🔇 Мутлист", callback_data="admin_mutelist"),
                InlineKeyboardButton("🔙 Назад", callback_data="menu_admin_panel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📊 **Списки нарушений**\n"
            "Выбери нужный список, сука!",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif action == "admin_banlist":
        await banlist_command(update, context)
        await query.delete_message()
    
    elif action == "admin_warnlist":
        await warnlist_command(update, context)
        await query.delete_message()
    
    elif action == "admin_mutelist":
        await mutelist_command(update, context)
        await query.delete_message()
    
    elif action == "admin_clear":
        await query.edit_message_text(
            "🧹 **Очистка**\n"
            "Используй команду: /clear [кол-во]\n"
            "Пример: /clear 10\n\n"
            "Нажми /menu чтобы вернуться, блять!",
            parse_mode='Markdown'
        )
        await asyncio.sleep(3)
        await query.delete_message()
        await menu_command(update, context)
    
    elif action == "admin_reports":
        await reports_command(update, context)
        await query.delete_message()
    
    elif action == "admin_logs":
        await logs_command(update, context)
        await query.delete_message()
    
    elif action == "admin_addcmd":
        await query.edit_message_text(
            "➕ **Добавление команды**\n"
            "Используй: /addcmd [название] [ответ]\n"
            "Пример: /addcmd привет Привет, ебать!\n\n"
            "Нажми /menu чтобы вернуться, блять!",
            parse_mode='Markdown'
        )
        await asyncio.sleep(3)
        await query.delete_message()
        await menu_command(update, context)
    
    elif action == "admin_delcmd":
        await query.edit_message_text(
            "🗑️ **Удаление команды**\n"
            "Используй: /delcmd [название]\n"
            "Пример: /delcmd привет\n\n"
            "Нажми /menu чтобы вернуться, блять!",
            parse_mode='Markdown'
        )
        await asyncio.sleep(3)
        await query.delete_message()
        await menu_command(update, context)
    
    elif action in ["admin_kick", "admin_mute", "admin_ban", "admin_warn"]:
        action_name = action.replace("admin_", "").upper()
        await query.edit_message_text(
            f"🔧 **{action_name}**\n"
            f"Используй команду: /{action.replace('admin_', '')} @username\n"
            f"Или ответь на сообщение!\n\n"
            f"Нажми /menu чтобы вернуться, блять!"
        )
        await asyncio.sleep(3)
        await query.delete_message()
        await menu_command(update, context)
    
    elif action == "menu_back":
        await query.delete_message()
        await menu_command(update, context)

# --- ОБРАБОТЧИК НОВЫХ УЧАСТНИКОВ ---
async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for new_user in update.message.new_chat_members:
        user_id = new_user.id
        
        keyboard = [
            [InlineKeyboardButton("Я не бот, я человек!", callback_data=f"botcheck_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"🔍 {new_user.first_name}, добро пожаловать, блять! Докажи, что не бот: нажми кнопку за {BOT_CHECK_TIMEOUT} секунд!\n\n📜 Ознакомься с правилами: /rules",
            reply_markup=reply_markup
        )
        
        context.user_data[f'bot_check_{user_id}'] = datetime.now()
        context.user_data[f'bot_check_timeout_{user_id}'] = True
        
        asyncio.create_task(check_bot_response(user_id, context, update))

async def check_bot_response(user_id: int, context: ContextTypes.DEFAULT_TYPE, update: Update):
    await asyncio.sleep(BOT_CHECK_TIMEOUT)
    
    if context.user_data.get(f'bot_check_timeout_{user_id}', False):
        try:
            await context.bot.ban_chat_member(chat_id=CHAT_ID, user_id=user_id)
            await context.bot.send_message(chat_id=CHAT_ID, text=f"🤖 {user_id} - бот, вылетел нахуй!")
            await add_log("BOT KICK", 0, user_id, "Бот удален")
            logger.info(f"Bot {user_id} was kicked")
        except Exception as e:
            logger.error(f"Не удалось удалить бота: {e}")

async def handle_bot_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split('_')[1])
    actual_user_id = update.effective_user.id
    
    if user_id != actual_user_id:
        await query.edit_message_text("❌ Ты че, на чужую кнопку нажал, блять?!")
        await asyncio.sleep(2)
        await query.delete_message()
        return
    
    context.user_data[f'bot_check_timeout_{user_id}'] = False
    await query.edit_message_text(f"✅ Ок, {update.effective_user.first_name}, ты не бот, проходи, сука!\n📜 Ознакомься с правилами: /rules")
    await asyncio.sleep(2)
    await query.delete_message()
    await context.bot.send_message(chat_id=CHAT_ID, text=f"👋 Привет, {update.effective_user.first_name}! Добро пожаловать в 403Team!")

# --- РАЗВЛЕЧЕНИЯ ---
JOKES = [
    "Почему программисты путают Хэллоуин и Рождество? Потому что 31 Oct = 25 Dec, блять!",
    "Сколько программистов нужно, чтобы заменить лампочку? Ни одного, это аппаратная проблема, нахуй!",
    "Программист - это устройство для преобразования кофе в код, пиздец!",
    "В чем разница между разработчиком и программистом? Разработчик может запилить целый проект, программист - только кодить, ебать!",
    "Почему программисты не любят природу? Слишком много багов, сука!",
]

ROASTS = [
    "Ты как Wi-Fi в деревне - ни сигнала, ни толку, блять!",
    "Твой код работает как зонтик из бумаги, нахуй!",
    "Ты похож на баг в программе - не понятно зачем ты здесь, сука!",
    "Твои навыки общения как C++ - сложные и непонятные, пиздец!",
    "Ты быстрее тормозишь, чем мой интернет, ебать!",
    "Твои шутки как Python без индентации - не работают, блять!",
    "Ты как батарейка в пульте - всегда не вовремя садишься, нахуй!",
    "Твой мозг работает как Windows 95 - постоянно зависает, сука!",
]

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    joke = random.choice(JOKES)
    await safe_reply(update, context, f"😂 {joke}")

async def dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dice = random.randint(1, 6)
    await safe_reply(update, context, f"🎲 Выпало: {dice}, блять!")

async def roast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        target = " ".join(context.args)
        roast = random.choice(ROASTS)
        await safe_reply(update, context, f"🔥 {target}, {roast}")
    else:
        await safe_reply(update, context, "🔥 Используй: /roast @username чтобы подколоть, ебать!")

# --- ИНФОРМАЦИЯ ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 **403Team Бот - Ебать-модератор!**

**📜 Правила:**
/rules - Показать правила

**🎮 Развлечения:**
/joke - Шутка
/dice - Кубик
/roast @username - Подкол

**📊 Профиль и статистика:**
/stats - Статистика чата (админы)
/profile [@username] - Профиль пользователя
/top - Топ пользователей
/nightmode - Ночной режим

**📝 Жалобы:**
/report @username [причина] - Пожаловаться
/reports - Список жалоб (админы)
/resolve [номер] - Закрыть жалобу (админы)

**📌 Закрепление:**
/pin - Закрепить (админы)
/unpin - Открепить (админы)
/pinned - Закрепленные сообщения

**📋 Кастомные команды:**
/addcmd [название] [ответ] - Добавить (админы)
/delcmd [название] - Удалить (админы)
/cmds - Список кастомных команд

**🌤️ Погода:**
/weather [город] - Погода

**📋 Логи:**
/logs - Логи модерации (админы)

**🔧 Админские команды:**
/kick, /mute, /ban, /warn, /unban, /unmute, /unwarn, /clear

**👑 Управление админами (владелец):**
/setadmin, /removeadmin, /admins, /owner

**🎮 Меню:**
/menu - Интерактивное меню

🛡️ **Защита:** Владельца нельзя трогать! Админ не может наказать себя!
    """
    await safe_reply(update, context, help_text, parse_mode='Markdown')

async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    owner_name = await get_user_name(context, OWNER_ID)
    await safe_reply(update, context, f"👑 Владелец бота: {owner_name}")

# --- ЗАПУСК ---
def main():
    print(f"Запускаю бота 403Team с кучей новых фич!")
    print(f"Владелец: {OWNER_ID}")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # --- КОМАНДЫ ---
    # Правила
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CallbackQueryHandler(rules_callback, pattern="rules_accepted"))
    
    # Развлечения
    application.add_handler(CommandHandler("joke", joke_command))
    application.add_handler(CommandHandler("dice", dice_command))
    application.add_handler(CommandHandler("roast", roast_command))
    
    # Управление админами
    application.add_handler(CommandHandler("setadmin", setadmin_command))
    application.add_handler(CommandHandler("removeadmin", removeadmin_command))
    application.add_handler(CommandHandler("admins", admins_command))
    application.add_handler(CommandHandler("owner", owner_command))
    
    # Админские команды
    application.add_handler(CommandHandler("kick", kick_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("warn", warn_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("unwarn", unwarn_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Списки
    application.add_handler(CommandHandler("banlist", banlist_command))
    application.add_handler(CommandHandler("warnlist", warnlist_command))
    application.add_handler(CommandHandler("mutelist", mutelist_command))
    
    # Статистика и профили
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("nightmode", nightmode_command))
    
    # Жалобы
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("reports", reports_command))
    application.add_handler(CommandHandler("resolve", resolve_command))
    
    # Закрепление
    application.add_handler(CommandHandler("pin", pin_command))
    application.add_handler(CommandHandler("unpin", unpin_command))
    application.add_handler(CommandHandler("pinned", pinned_command))
    
    # Кастомные команды
    application.add_handler(CommandHandler("addcmd", addcmd_command))
    application.add_handler(CommandHandler("delcmd", delcmd_command))
    application.add_handler(CommandHandler("cmds", cmds_command))
    
    # Погода
    application.add_handler(CommandHandler("weather", weather_command))
    
    # Логи
    application.add_handler(CommandHandler("logs", logs_command))
    
    # Меню
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="menu_.*"))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="admin_.*"))
    
    # Информация
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчики
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    application.add_handler(CallbackQueryHandler(handle_bot_check_callback, pattern="botcheck_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # --- ЕЖЕДНЕВНЫЙ ОТЧЕТ ---
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_daily(daily_report, time=datetime.strptime("00:00", "%H:%M").time())
        print("Ежедневный отчет запланирован на 00:00, блять!")
    
    print("Бот запущен, блять! Погнали модерять!")
    application.run_polling()

if __name__ == "__main__":
    main()