import logging
import random
from datetime import time
import pytz
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import config
from database import (
    init_db, register_user, add_or_update_pushups,
    get_user_today, get_today_debtors, get_yesterday_debtors,
    get_all_registered_users, get_leaderboard_today
)

logging.basicConfig(level=logging.INFO)
TIMEZONE = pytz.timezone("Europe/Moscow")

MOTIVATIONAL_QUOTES = [
    "«То, что причиняет боль сегодня, делает тебя сильнее завтра» — Станислав Корчагин",
    "«Если нет борьбы, нет прогресса» — Фредерик Дуглас",
    "«Будь сильнее своих оправданий»",
    "«Независимо от того, думаете ли вы, что можете, или вы думаете, что не можете, вы правы» — Генри Форд",
    "«Вам не обязательно идти быстро … вам просто нужно идти»",
    "«Последние три или четыре повторения — это то, что заставляет мышцы расти. Эта область боли отличает чемпиона от того, кто им не является» — Арнольд Шварценеггер",
    "«Хватит находить себе оправдания! Оправдания — это удел слабых»",
    "«Пот — это слезы жира»",
    "«Уставшая сегодня — сильная завтра!»",
    "«Никто не говорил, что будет легко»",
    "«Помни, почему ты начал. Продолжай делать отжимания»",
    "«Каждое отжимание имеет значение»",
    "«Сделайте сегодня что-нибудь такое, за что ваше будущее 'я' скажет вам спасибо»",
    "«Боль, которую ты преодолеваешь сегодня, превратится в силу, которую ты почувствуешь завтра»",
    "«Пока у тебя еще есть попытка — ты не проиграл. Поражение — это временное состояние, отказ от борьбы делает его постоянным»",
    "«Бизнес — это сочетание войны и спорта»",
    "«Твоё тело может выдержать почти всё. Это твой разум нужно убедить»",
    "«Не останавливайся, когда устал. Останавливайся, когда сделал»",
    "«Каждый день ты выбираешь: лёгкий путь оправданий или трудный путь результатов»",
    "«Слабость — это выбор. Сила — тоже. Выбирай с умом»",
    "«Сегодняшние 100 отжиманий — это завтрашняя лёгкость в движениях»",
    "«Пропустишь один день — и привычка начнёт умирать»",
    "«Ты не обязан быть великим, чтобы начать, но ты должен начать, чтобы стать великим»",
    "«Никто не вспотел от лёгкой тренировки»",
    "«Дисциплина — это память о том, что ты действительно хочешь»",
    "«Чем больше ты жалеешь себя сегодня, тем больше будешь жалеть завтра»",
    "«Отжимания лечат лень, прокрастинацию и плохое настроение»",
    "«Твои мышцы растут именно в тот момент, когда ты хочешь остановиться»",
    "«Сделай это ради того, кто смотрит на тебя и ждёт примера»",
    "«Результат приходит не от действий, которые ты делаешь иногда, а от тех, что делаешь каждый день»",
    "«Утром кажется тяжело, вечером — гордость»",
    "«Если тебе тяжело — значит, ты на правильном пути»",
    "«Твоё тело — единственное место, где тебе жить всю жизнь. Содержи его в порядке»",
    "«Не жди вдохновения. Делай, и оно придёт»",
    "«Одна тренировка ничего не меняет. Сто — меняют всё»",
    "«Оправдания — это обещание себе, что ты слабак. Выполни обещание быть сильным»",
    "«Вчера ты сказал \"начну с понедельника\". Понедельник уже много раз был»",
    "«Боль от дисциплины весит граммы. Боль от сожалений — тонны»",
    "«Когда ты не хочешь — сделай первый подход. Дальше само пойдёт»",
    "«Сила не в том, чтобы никогда не падать, а в том, чтобы каждый раз вставать»",
    "«Сделай сегодня столько, чтобы завтрашний ты сказал спасибо»",
    "«Чем раньше ты отожмёшься, тем быстрее забудешь об этом и займёшься делами»",
    "«100 раз — это всего 4 минуты твоего дня. Неужели это сложно?»",
    "«Герои не рождаются, они отжимаются каждое утро»",
    "«Если ты читаешь это сообщение, значит, у тебя есть руки. Используй их»",
    "«Закончил? Нет, закончил — когда 100 сделано»"
]

# ---------- ОБРАБОТЧИКИ КОМАНД (английские) ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💪 Бот контроля отжиманий!\nКаждый должен сделать 100 в день.\n\n"
        "🇷🇺 Команды (можно на русском):\n"
        "/отжимания 30 – добавить\n"
        "/мои – ваш прогресс\n"
        "/статистика – прогресс группы\n"
        "/топ – лидеры дня\n"
        "/помощь – справка\n\n"
        "🇬🇧 Английские команды тоже работают: /pushups, /mypushups, /today, /leaderboard"
    )

async def pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Работает только в группе.")
        return
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    if not context.args:
        await update.message.reply_text("Укажите число: /pushups 30")
        return
    try:
        count = int(context.args[0])
        if count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Нужно положительное число.")
        return
    new_total = add_or_update_pushups(user.id, count)
    await update.message.reply_text(f"✅ Добавлено {count}. За сегодня: {new_total}.")
    if new_total >= config.DAILY_GOAL:
        await update.message.reply_text("🎉 Норма выполнена!")

async def mypushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Работает только в группе.")
        return
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    count = get_user_today(user.id)
    remain = max(0, config.DAILY_GOAL - count)
    await update.message.reply_text(f"Вы отжались {count} раз. Осталось: {remain}.")

async def today_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Работает только в группе.")
        return
    users = get_all_registered_users()
    if not users:
        await update.message.reply_text("Пока никто не зарегистрирован.")
        return
    lines = []
    for user_id, username, first_name in users:
        count = get_user_today(user_id)
        status = "✅" if count >= config.DAILY_GOAL else "❌"
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"
        lines.append(f"{status} {name}: {count}/{config.DAILY_GOAL}")
    await update.message.reply_text("📊 Прогресс группы:\n" + "\n".join(lines))

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Работает только в группе.")
        return
    lb = get_leaderboard_today()
    if not lb:
        await update.message.reply_text("Сегодня ещё никто не отжимался.")
        return
    text = "🏆 Топ за сегодня:\n"
    for i, (name, username, count) in enumerate(lb, 1):
        display = f"{name} (@{username})" if username else name
        text += f"{i}. {display} – {count}\n"
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ---------- ОБРАБОТЧИК РУССКИХ КОМАНД (MessageHandler) ----------
async def russian_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("/отжимания"):
        parts = text.split()
        context.args = parts[1:] if len(parts) > 1 else []
        await pushups(update, context)
    elif text.startswith("/мои"):
        await mypushups(update, context)
    elif text.startswith("/статистика"):
        await today_stats(update, context)
    elif text.startswith("/топ"):
        await leaderboard(update, context)
    elif text.startswith("/помощь"):
        await help_command(update, context)

# ---------- ПЛАНОВЫЕ ЗАДАЧИ ----------
async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    debtors = get_yesterday_debtors()
    quote = random.choice(MOTIVATIONAL_QUOTES)
    if not debtors:
        await context.bot.send_message(
            chat_id=config.CHAT_ID,
            text=f"🌞 Доброе утро! Вчера все выполнили норму!\n\n{quote}"
        )
        return
    lines = [f"• {name or str(uid)} (@{username}) – {count}/100" for uid, username, name, count in debtors]
    await context.bot.send_message(
        chat_id=config.CHAT_ID,
        text=f"🌞 Вчера не сделали 100:\n" + "\n".join(lines) + f"\n\n{quote}"
    )

async def evening_check(context: ContextTypes.DEFAULT_TYPE):
    debtors = get_today_debtors()
    if not debtors:
        await context.bot.send_message(chat_id=config.CHAT_ID, text="🏆 Все выполнили норму за сегодня!")
        return
    lines = [f"• {name or str(uid)} (@{username}) – {count}/100" for uid, username, name, count in debtors]
    await context.bot.send_message(
        chat_id=config.CHAT_ID,
        text=f"⚠️ До 23:59 осталось 2 часа! Не сделали 100:\n" + "\n".join(lines)
    )

async def post_init(application: Application):
    for job in application.job_queue.jobs():
        job.schedule_removal()
    reminder_time = time(config.REMINDER_HOUR, config.REMINDER_MINUTE, tzinfo=TIMEZONE)
    application.job_queue.run_daily(morning_reminder, reminder_time, days=tuple(range(7)))
    check_time = time(config.CHECK_HOUR, config.CHECK_MINUTE, tzinfo=TIMEZONE)
    application.job_queue.run_daily(evening_check, check_time, days=tuple(range(7)))

# ---------- MAIN ----------
def main():
    init_db()
    application = (Application.builder()
                   .token(config.TOKEN)
                   .connect_timeout(30.0)
                   .read_timeout(30.0)
                   .post_init(post_init)
                   .build())

    # Английские команды
    application.add_handler(CommandHandler("pushups", pushups))
    application.add_handler(CommandHandler("mypushups", mypushups))
    application.add_handler(CommandHandler("today", today_stats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", start))

    # Русские команды через MessageHandler
    application.add_handler(MessageHandler(filters.Regex(r'^/отжимания\b'), russian_commands))
    application.add_handler(MessageHandler(filters.Regex(r'^/мои\b'), russian_commands))
    application.add_handler(MessageHandler(filters.Regex(r'^/статистика\b'), russian_commands))
    application.add_handler(MessageHandler(filters.Regex(r'^/топ\b'), russian_commands))
    application.add_handler(MessageHandler(filters.Regex(r'^/помощь\b'), russian_commands))

    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
