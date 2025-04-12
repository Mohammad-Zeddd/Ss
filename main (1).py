# Salah Squad Telegram Bot (v1)
# Libraries needed: python-telegram-bot, APScheduler, sqlite3
# Install using: pip install python-telegram-bot APScheduler

from telegram import Update, Poll
from telegram.ext import ApplicationBuilder, CommandHandler, PollAnswerHandler, ContextTypes, CallbackContext, JobQueue
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3, datetime

TOKEN = 'YOUR_BOT_TOKEN_HERE'  # Replace with your bot token
CHAT_ID = 'YOUR_GROUP_CHAT_ID'  # Replace with your group chat ID

# Database setup
def init_db():
    conn = sqlite3.connect("salah_bot.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            xp INTEGER DEFAULT 50,
            level INTEGER DEFAULT 1,
            fine INTEGER DEFAULT 0,
            shields INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_prayer_date TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

# Utility functions
def update_user(user_id, username, prayed):
    conn = sqlite3.connect("salah_bot.db")
    c = conn.cursor()
    today = datetime.date.today().isoformat()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if not row:
        c.execute("INSERT INTO users (user_id, username, last_prayer_date) VALUES (?, ?, ?)", (user_id, username, today))
    else:
        xp, fine, shields, streak, last_date = row[2], row[3], row[4], row[5], row[6]

        if prayed:
            xp += 5
            if last_date == (datetime.date.today() - datetime.timedelta(days=1)).isoformat():
                streak += 1
            else:
                streak = 1
            if streak % 7 == 0:
                shields += 1
        else:
            xp -= 15
            if shields > 0:
                shields -= 1
            else:
                fine += 50
            streak = 0

        if xp <= 0:
            fine += 100
            xp = 0

        level = (xp // 100) + 1
        c.execute("""
            UPDATE users SET xp=?, level=?, fine=?, shields=?, streak=?, last_prayer_date=? WHERE user_id=?
        """, (xp, level, fine, shields, streak, today, user_id))

    conn.commit()
    conn.close()

async def send_prayer_poll(context: CallbackContext, prayer_name):
    await context.bot.send_poll(
        chat_id=CHAT_ID,
        question=f"Did you pray {prayer_name}?",
        options=["Prayed", "Missed"],
        is_anonymous=False,
        allows_multiple_answers=False,
        open_period=3600  # 1 hour to answer
    )

# Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salah Squad Bot Activated!")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("salah_bot.db")
    c = conn.cursor()
    c.execute("SELECT fine FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        await update.message.reply_text(f"Your balance: ₹{row[0]}")
    else:
        await update.message.reply_text("You have no fines!")

async def fine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect("salah_bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET fine=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("Your fines have been cleared.")

async def tahajjud(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now().time()
    if datetime.time(2,30) <= now <= datetime.time(4,30):
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        conn = sqlite3.connect("salah_bot.db")
        c = conn.cursor()
        c.execute("SELECT xp, shields FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            xp = row[0] + 20
            shields = row[1] + 3
            c.execute("UPDATE users SET xp=?, shields=? WHERE user_id=?", (xp, shields, user_id))
            conn.commit()
        conn.close()
        await update.message.reply_text("Tahajjud logged! +20 XP, +3 Shields.")
    else:
        await update.message.reply_text("Tahajjud time is 2:30 AM to 4:30 AM only.")

# Poll answer handler
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    user_id = poll_answer.user.id
    username = poll_answer.user.username or poll_answer.user.first_name
    voted_option = poll_answer.option_ids[0] == 0
    update_user(user_id, username, voted_option)

# Scheduler jobs
scheduler = BackgroundScheduler()
prayers = [
    ("Fajr", "05:00"),
    ("Dhuhr", "12:30"),
    ("Asr", "16:00"),
    ("Maghrib", "18:30"),
    ("Isha", "19:45")
]
for prayer_name, time_str in prayers:
    hour, minute = map(int, time_str.split(":"))
    scheduler.add_job(lambda prayer_name=prayer_name: application.job_queue.run_once(lambda ctx: send_prayer_poll(ctx, prayer_name), 0), 'cron', hour=hour, minute=minute)

scheduler.start()

# Bot setup
application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("balance", balance))
application.add_handler(CommandHandler("fine", fine))
application.add_handler(CommandHandler("tahajjud", tahajjud))
application.add_handler(PollAnswerHandler(handle_poll_answer))

init_db()
application.run_polling()