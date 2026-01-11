import json
import random
import re
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TZ_NAME = os.environ.get("TZ", "Europe/Zaporozhye")
TZ = ZoneInfo(TZ_NAME)
DTEK_TG_BOT_URL = "https://t.me/DTEKDniprovskiElektromerezhiBot"

DATA_FILE = "group_bot_data.json"


def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"ideas": [], "duty_index": 0}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_group(update: Update) -> bool:
    return update.effective_chat and update.effective_chat.type in ("group", "supergroup")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_group(update):
        await update.message.reply_text("Добавь меня в вашу группу — там я и работаю 🙂")
        return

    await update.message.reply_text(
        "Я ваш бот-организатор 🤝\n\n"
        "Команды:\n"
        "/idea <текст> — добавить идею\n"
        "/ideas — список идей\n"
        "/vote <номер> — голосование за идею\n"
        "/random — случайный план\n"
        "/remind HH:MM <текст> — напоминание сегодня\n"
        "/duty — кто дежурный на этой неделе\n"
        "/help — подсказка"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_group(update):
        return

    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Пример: /idea чай в 19:00 или /idea покатушки по набережной")
        return

    data = load_data()
    author = update.effective_user.first_name if update.effective_user else "Кто-то"
    data["ideas"].append({"text": text, "author": author, "ts": datetime.now(TZ).isoformat()})
    save_data(data)

    n = len(data["ideas"])
    await update.message.reply_text(f"✅ Идея добавлена под №{n}: {text}")


async def ideas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_group(update):
        return

    data = load_data()
    if not data["ideas"]:
        await update.message.reply_text("Пока нет идей. Добавь: /idea <текст>")
        return

    lines = ["📌 Ваши идеи:"]
    for i, it in enumerate(data["ideas"], start=1):
        lines.append(f"{i}) {it['text']} — {it.get('author','')}")
    await update.message.reply_text("\n".join(lines))


async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_group(update):
        return

    if not context.args:
        await update.message.reply_text("Пример: /vote 2")
        return

    try:
        idx = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("Номер должен быть числом. Пример: /vote 2")
        return

    data = load_data()
    if idx < 0 or idx >= len(data["ideas"]):
        await update.message.reply_text("Нет такой идеи. Список: /ideas")
        return

    idea_text = data["ideas"][idx]["text"]
    question = f"Голосуем: {idea_text}"

    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=question[:300],
        options=["За 🔥", "Против 🙅‍♀️", "Мне всё равно 😎"],
        is_anonymous=False,
        allows_multiple_answers=False,
    )


async def random_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_group(update):
        return

    data = load_data()
    base = [
        "чай + тупые истории",
        "покатушки лёгкие (без геройства)",
        "кофе/десерт + фотки",
        "настолки/фильм + пицца",
        "прогулка + болтовня",
    ]
    plan = random.choice(base)

    extra = ""
    if data["ideas"]:
        extra = f"\n💡 Из идей можно: {random.choice(data['ideas'])['text']}"

    await update.message.reply_text(f"🎲 Рандом-план недели: {plan}{extra}")


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_group(update):
        return

    raw = " ".join(context.args).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})\s+(.+)$", raw)
    if not m:
        await update.message.reply_text("Формат: /remind HH:MM текст\nПример: /remind 19:00 чай у Тани")
        return

    hh = int(m.group(1))
    mm = int(m.group(2))
    text = m.group(3).strip()

    now = datetime.now(TZ)
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        await update.message.reply_text("Это время уже прошло. Я ставлю напоминание только на сегодня 🙂")
        return

    delay = (target - now).total_seconds()

    async def fire(job_ctx: ContextTypes.DEFAULT_TYPE):
        await job_ctx.bot.send_message(chat_id=update.effective_chat.id, text=f"⏰ Напоминание: {text}")

    context.job_queue.run_once(fire, when=delay)
    await update.message.reply_text(f"✅ Ок, напомню в {hh:02d}:{mm:02d}: {text}")


async def duty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_group(update):
        return

    members = ["Таня", "Лена", "Ира", "Эллада"]

    data = load_data()
    i = data.get("duty_index", 0) % len(members)
    who = members[i]
    data["duty_index"] = i + 1
    save_data(data)

    await update.message.reply_text(f"🫡 Дежурная на эту неделю: {who}\n(она пишет всем и собирает план 😄)")

async def dtek_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_group(update):
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Открыть Telegram-бот ДТЭК", url=DTEK_TG_BOT_URL)]
    ])

    await update.message.reply_text(
        "⚡️ ДТЭК (Дніпро)\n\n"
        "Открой официальный Telegram-бот ДТЭК Дніпровські електромережі — там можно смотреть отключения/графики.",
        reply_markup=kb
    )

def main():
    if not TOKEN:
        raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN (добавь в Railway Variables).")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("idea", idea))
    app.add_handler(CommandHandler("ideas", ideas))
    app.add_handler(CommandHandler("vote", vote))
    app.add_handler(CommandHandler("random", random_plan))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("duty", duty))
app.add_handler(CommandHandler("dtek", dtek_cmd))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
