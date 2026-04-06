import logging
import random
from datetime import time
import pytz
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)
import config
from database import (
    init_db, register_user, add_or_update_pushups,
    get_user_today, get_today_debtors, get_yesterday_debtors,
    get_all_registered_users, get_leaderboard_today
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEZONE = pytz.timezone("Europe/Moscow")

# ----- РАСШИРЕННЫЙ СПИСОК МОТИВАЦИОННЫХ ФРАЗ (46 штук) -----
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

# ---------- ОБРАБОТЧИКИ КОМАНД ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💪 Я бот для личного контроля отжиманий в группе!\n"
        "Каждый должен сделать 100 отжиманий в день.\n\n"
        "🇷🇺 Команды:\n"
        "/отжимания <число> – добавить отжимания за сегодня\n"
        "/мои – сколько вы сделали сегодня\n"
        "/статистика – прогресс всех участников за сегодня\n"
        "/топ – лидеры дня по количеству отжиманий\n"
        "/помощь – это сообщение\n\n"
        "Также работают английские команды: /pushups, /mypushups, /today, /leaderboard, /help"
    )

async def pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить отжимания (рус. /отжимания)."""
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в групповом чате.")
        return

    user = update.effective_user
    register_user(user.id, user.username, user.first_name)

    if not context.args:
        await update.message.reply_text("Укажите количество: /отжимания 30")
        return

    try:
        count = int(context.args[0])
        if count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Пожалуйста, укажите положительное число.")
        return

    new_total = add_or_update_pushups(user.id, count)
    await update.message.reply_text(f"✅ Добавлено {count}. За сегодня: {new_total}.")

    if new_total >= config.DAILY_GOAL:
        await update.message.reply_text(f"🎉 Поздравляю! Вы выполнили дневную норму ({config.DAILY_GOAL} отжиманий)!")

async def mypushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать мой прогресс (рус. /мои)."""
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в групповом чате.")
        return

    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    count = get_user_today(user.id)
    remain = max(0, config.DAILY_GOAL - count)
    await update.message.reply_text(f"Вы отжались {count} раз сегодня. Осталось: {remain}.")

async def today_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать прогресс всех участников за сегодня (рус. /статистика)."""
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в групповом чате.")
        return

    users = get_all_registered_users()
    if not users:
        await update.message.reply_text("Пока никто не зарегистрирован. Начните с /отжимания.")
        return

    lines = []
    for user_id, username, first_name in users:
        count = get_user_today(user_id)
        status = "✅" if count >= config.DAILY_GOAL else "❌"
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"
        lines.append(f"{status} {name}: {count}/{config.DAILY_GOAL}")

    text = "📊 Прогресс группы сегодня:\n" + "\n".join(lines)
    await update.message.reply_text(text)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ участников за сегодня (рус. /топ)."""
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в групповом чате.")
        return

    lb = get_leaderboard_today()
    if not lb:
        await update.message.reply_text("Сегодня ещё никто не отжимался.")
        return

    text = "🏆 Топ отжиманий за сегодня:\n"
    for i, (name, username, count) in enumerate(lb, 1):
        display = f"{name} (@{username})" if username else name
        text += f"{i}. {display} – {count}\n"
    await update.message.reply_text(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# ---------- ПЛАНОВЫЕ ЗАДАЧИ ----------
async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Утром (8:00): список вчерашних должников + мотивационная фраза."""
    debtors = get_yesterday_debtors()
    quote = random.choice(MOTIVATIONAL_QUOTES)

    if not debtors:
        await context.bot.send_message(
            chat_id=config.CHAT_ID,
            text=f"🌞 Доброе утро! Вчера все выполнили норму отжиманий! Молодцы!\n\n{quote}\n\nСегодня тоже нужно сделать 100 каждому."
        )
        return

    lines = []
    for _, username, first_name, count in debtors:
        name = first_name or str(_)
        if username:
            name += f" (@{username})"
        lines.append(f"• {name} – {count}/100")
    debtor_text = "\n".join(lines)

    await context.bot.send_message(
        chat_id=config.CHAT_ID,
        text=f"🌞 Доброе утро!\nВчера следующие участники НЕ выполнили норму в 100 отжиманий:\n{debtor_text}\n\n{quote}\n\nСегодня новый день – каждому нужно сделать 100! Не забывайте отжиматься и записывать результаты командой /отжимания."
    )

async def evening_check(context: ContextTypes.DEFAULT_TYPE):
    """В 22:00 – предупреждение для тех, кто ещё не сделал 100 сегодня."""
    debtors = get_today_debtors()
    if not debtors:
        await context.bot.send_message(
            chat_id=config.CHAT_ID,
            text="🏆 Отлично! На данный момент все уже выполнили норму отжиманий за сегодня. Так держать!"
        )
        return

    lines = []
    for _, username, first_name, count in debtors:
        name = first_name or str(_)
        if username:
            name += f" (@{username})"
        lines.append(f"• {name} – {count}/100")
    debtor_text = "\n".join(lines)

    await context.bot.send_message(
        chat_id=config.CHAT_ID,
        text=f"⚠️ Внимание! До конца дня осталось 2 часа (до 23:59).\nСледующие участники ещё не сделали 100 отжиманий:\n{debtor_text}\n\nУ вас есть время – подтянитесь!"
    )

# ---------- ПЛАНИРОВЩИК ----------
async def post_init(application: Application):
    """Настройка периодических задач."""
    # Удаляем старые джобы при перезапуске
    for job in application.job_queue.jobs():
        job.schedule_removal()

    # Утреннее напоминание (8:00)
    reminder_time = time(config.REMINDER_HOUR, config.REMINDER_MINUTE, tzinfo=TIMEZONE)
    application.job_queue.run_daily(
        morning_reminder,
        time=reminder_time,
        days=tuple(range(7)),
        name="morning_reminder"
    )

    # Вечерняя проверка (22:00)
    check_time = time(config.CHECK_HOUR, config.CHECK_MINUTE, tzinfo=TIMEZONE)
    application.job_queue.run_daily(
        evening_check,
        time=check_time,
        days=tuple(range(7)),
        name="evening_check"
    )

# ---------- MAIN ----------
def main():
    init_db()
    application = Application.builder().token(config.TOKEN).post_init(post_init).build()

    # Русские команды
    application.add_handler(CommandHandler("отжимания", pushups))
    application.add_handler(CommandHandler("мои", mypushups))
    application.add_handler(CommandHandler("статистика", today_stats))
    application.add_handler(CommandHandler("топ", leaderboard))
    application.add_handler(CommandHandler("помощь", help_command))

    # Английские команды (для совместимости)
    application.add_handler(CommandHandler("pushups", pushups))
    application.add_handler(CommandHandler("mypushups", mypushups))
    application.add_handler(CommandHandler("today", today_stats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", start))

    # Установка команд в интерфейсе бота (пользователи увидят русские подсказки)
    application.bot.set_my_commands([
        BotCommand("отжимания", "Добавить отжимания (например /отжимания 30)"),
        BotCommand("мои", "Сколько вы отжались сегодня"),
        BotCommand("статистика", "Прогресс всех участников за сегодня"),
        BotCommand("топ", "Лидеры дня по отжиманиям"),
        BotCommand("помощь", "Показать справку")
    ])

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()