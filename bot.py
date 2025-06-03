import os
import smtplib
import sqlite3
from dotenv import load_dotenv
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler,
    filters, ContextTypes
)

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# DB setup
DB_NAME = "appointments.db"
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                user_id INTEGER,
                username TEXT,
                email TEXT,
                datetime TEXT
            )
        ''')

# Conversation states
ASK_EMAIL, ASK_DATE = range(2)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Use /book to schedule an appointment.")

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Use /book to book an appointment.\n❌ Use /cancel to stop.")

# Cancel booking
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Booking cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# /book flow
async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📧 Please enter your email:")
    return ASK_EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["email"] = update.message.text.strip()
    await update.message.reply_text("🕒 Enter appointment datetime (YYYY-MM-DD HH:MM):")
    return ASK_DATE

async def save_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = context.user_data["email"]
    try:
        dt = datetime.strptime(update.message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("❗ Format should be YYYY-MM-DD HH:MM. Try again.")
        return ASK_DATE

    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name

    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "INSERT INTO appointments (user_id, username, email, datetime) VALUES (?, ?, ?, ?)",
            (user_id, username, email, dt.isoformat())
        )

    # Confirmation message
    msg = f"✅ Hi {username}, your appointment is confirmed for {dt.strftime('%Y-%m-%d %H:%M')}."
    await update.message.reply_text(msg)

    # Send emails to user and admin
    body = (
        f"Hi {username},\n\nYour appointment is confirmed:\n"
        f"🕒 {dt.strftime('%Y-%m-%d %H:%M')}\n📧 {email}\n\nThanks!"
    )
    send_email(email, "✅ Appointment Confirmation", body)
    send_email(ADMIN_EMAIL, f"📥 New Booking by {username}", body)

    return ConversationHandler.END

# Email sender
def send_email(to, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)

    except Exception as e:
        print(f"❌ Failed to send email to {to}: {e}")

# Auto reminders
async def reminder_loop(app):
    while True:
        now = datetime.now()
        check_time = now + timedelta(minutes=30)

        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT user_id, username, email, datetime FROM appointments").fetchall()

        for user_id, username, email, dt in rows:
            appt_dt = datetime.fromisoformat(dt)
            if now < appt_dt <= check_time:
                try:
                    # Telegram reminder
                    await app.bot.send_message(user_id, text=f"🔔 Reminder: Appointment at {appt_dt.strftime('%Y-%m-%d %H:%M')}")
                    # Email reminder
                    body = (
                        f"Hi {username},\n\nThis is a reminder for your appointment:\n"
                        f"🕒 {appt_dt.strftime('%Y-%m-%d %H:%M')}\n\nThanks!"
                    )
                    send_email(email, "🔔 Appointment Reminder", body)
                except Exception as e:
                    print(f"❌ Reminder error: {e}")

        await asyncio.sleep(60)

# Run bot
async def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("book", book)],
        states={
            ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            ASK_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_appointment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv)

    # Start the reminder loop as a background task
    asyncio.create_task(reminder_loop(app))

    print("🤖 Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
