import logging
import random
from datetime import datetime, date, time
import pytz
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import config
from database import (
    init_db, register_user, add_or_update_pushups, set_pushups,
    get_user_today, get_today_debtors, get_yesterday_debtors,
    get_all_registered_users, get_leaderboard_today
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEZONE = pytz.timezone("Europe/Moscow")
awaiting_pushups = {}

# -------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ --------------------
async def send_private(update: Update, text: str):
    """Отправляет сообщение в личку пользователю. Если не получается – молча игнорирует."""
    try:
        await update.effective_user.send_message(text)
    except Exception:
        pass

def get_challenge_day():
    start = datetime.strptime(config.CHALLENGE_START_DATE, "%Y-%m-%d").date()
    today = date.today()
    delta = (today - start).days + 1
    if delta < 1:
        return 1, False
    if delta > config.CHALLENGE_TOTAL_DAYS:
        return config.CHALLENGE_TOTAL_DAYS, True
    return delta, False

# -------------------- ОБРАБОТЧИКИ КОМАНД --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💪 Бот для контроля отжиманий!\n"
        "Каждый должен сделать 100 в день.\n\n"
        "🇷🇺 Команды:\n"
        "/отжимания <числа> – добавить (можно несколько через пробел)\n"
        "/мои – ваш прогресс\n"
        "/статистика – прогресс группы\n"
        "/топ – лидеры дня\n"
        "/сброс – обнулить свои отжимания за сегодня\n"
        "/progress – прогресс челленджа\n"
        "💡 Если вы не укажете число, бот задаст вопрос в личные сообщения.\n"
        "📢 Результаты ваших отжиманий будут видны в группе."
    )

async def pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Разрешаем использовать команду в группе и в ЛС
    if update.effective_chat.type not in ("group", "supergroup", "private"):
        await update.message.reply_text("Работает только в группе или личке.")
        return

    user = update.effective_user
    register_user(user.id, user.username, user.first_name)

    # Если аргументов нет – запрашиваем число (только в ЛС, без уведомления в группе)
    if not context.args:
        awaiting_pushups[user.id] = True
        await send_private(update, "Сколько отжиманий вы сделали? Введите числа через пробел (например, 30 20 15):")
        return

    # Обработка чисел (суммирование)
    total_count = 0
    for arg in context.args:
        try:
            val = int(arg)
            if val <= 0:
                await update.message.reply_text(f"Число {val} не может быть отрицательным или нулём.")
                return
            total_count += val
        except ValueError:
            await update.message.reply_text(f"'{arg}' — не число. Вводите только числа.")
            return
    if total_count <= 0:
        await update.message.reply_text("Нужно указать хотя бы одно положительное число.")
        return

    new_total = add_or_update_pushups(user.id, total_count)
    result_text = f"✅ {user.first_name} добавил {total_count} отжиманий. За сегодня: {new_total}."
    if new_total >= config.DAILY_GOAL:
        result_text += " 🎉 Норма выполнена!"

    # Определяем, откуда пришёл ответ
    is_private = (update.effective_chat.type == "private")
    is_group = (update.effective_chat.type in ("group", "supergroup"))

    if is_group:
        # Ответили в группе – показываем результат в группе и дублируем в ЛС
        await update.message.reply_text(result_text)
        await send_private(update, result_text)
    else:
        # Ответили в ЛС – результат публикуем в группе (чтобы все видели) и дублируем в ЛС
        await send_private(update, result_text)
        try:
            await context.bot.send_message(chat_id=config.CHAT_ID, text=result_text)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение в группу: {e}")

async def mypushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup", "private"):
        await update.message.reply_text("Работает только в группе или личке.")
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
    lines, zero_users = [], []
    for user_id, username, first_name in users:
        count = get_user_today(user_id)
        status = "✅" if count >= config.DAILY_GOAL else "❌"
        name = first_name or str(user_id)
        if username:
            name += f" (@{username})"
        lines.append(f"{status} {name}: {count}/{config.DAILY_GOAL}")
        if count == 0:
            zero_users.append(name)
    text = "📊 Прогресс группы сегодня:\n" + "\n".join(lines)
    if zero_users:
        text += "\n\n⚠️ **Сегодня ещё не отжимались:**\n" + "\n".join(f"• {u}" for u in zero_users)
    else:
        text += "\n\n🎉 Отлично! Все уже сделали хотя бы одно отжимание!"
    await update.message.reply_text(text)

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

async def challenge_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day, finished = get_challenge_day()
    total = config.CHALLENGE_TOTAL_DAYS
    if finished:
        await update.message.reply_text(f"🏁 Челлендж завершён! Вы прошли все {total} дней. 💪")
    else:
        remain = total - day
        await update.message.reply_text(f"📅 Сегодня **{day}-й день** из {total}. Осталось дней: {remain}.")

async def reset_pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup", "private"):
        await update.message.reply_text("Работает только в группе или личке.")
        return
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    set_pushups(user.id, 0)
    new_count = get_user_today(user.id)
    text = f"🔄 Ваши отжимания за сегодня сброшены. Теперь у вас {new_count} отжиманий.\nВведите верное количество командой /отжимания."
    await update.message.reply_text(text)
    if update.effective_chat.type in ("group", "supergroup"):
        await send_private(update, text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# -------------------- ОБРАБОТЧИК РУССКИХ КОМАНД --------------------
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
    elif text.startswith("/сброс"):
        await reset_pushups(update, context)
    elif text.startswith("/progress") or text.startswith("/прогресс"):
        await challenge_progress(update, context)
    elif text.startswith("/помощь"):
        await help_command(update, context)

# -------------------- ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ (интерактивный ввод) --------------------
async def handle_pushups_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if awaiting_pushups.get(user_id):
        text = update.message.text.strip()
        parts = text.split()
        total_count = 0
        for part in parts:
            try:
                val = int(part)
                if val <= 0:
                    await update.message.reply_text(f"Число {val} не может быть отрицательным или нулём.")
                    return
                total_count += val
            except ValueError:
                await update.message.reply_text(f"'{part}' — не число. Вводите только числа через пробел.")
                return
        if total_count <= 0:
            await update.message.reply_text("Нужно указать хотя бы одно положительное число.")
            return
        del awaiting_pushups[user_id]
        context.args = [total_count]
        await pushups(update, context)

# -------------------- ПЛАНОВЫЕ ЗАДАЧИ --------------------
MOTIVATIONAL_QUOTES = [
     "«То, что причиняет боль сегодня, делает тебя сильнее завтра» — Станислав Корчагин",
    "«Если нет борьбы, нет прогресса» — Фредерик Дуглас",
    "«Будь сильнее своих оправданий»",
    "«Независимо от того, думаете ли вы, что можете, или вы думаете, что не можете, вы правы» — Генри Форд",
    "«Вам не обязательно идти быстро … вам просто нужно идти»",
    "«Последние три или четыре повторения — это то, что заставляет мышцы расти. Эта область боли отличает чемпиона от того, кто им не является» — Арнольд Шварценеггер",
    "«Хватит находить себе оправдания! Оправдания — это удел слабых»",
    "«Пот — это слезы жира»",
    "«Уставшый сегодня — сильный завтра!»",
    "«Никто не говорил, что будет легко»",
    "«Помни, почему ты начал. Продолжай делать отжимания»",
    "«Каждое отжимание имеет значение»",
    "«Сделайте сегодня что-нибудь такое, за что ваше будущее 'я' скажет вам спасибо»",
    "«Боль, которую ты преодолеваешь сегодня, превратится в силу, которую ты почувствуешь завтра»",
    "«Пока у тебя еще есть попытка — ты не проиграл. Поражение — это временное состояние, отказ от борьбы делает его постоянным»",
    "«Твоё тело может выдержать почти всё. Это твой разум нужно убедить»",
    "«Не останавливайся, когда устал. Останавливайся, когда сделал»",
    "«Каждый день ты выбираешь: лёгкий путь оправданий или трудный путь результатов»",
    "«Слабость — это выбор. Сила — тоже. Выбирай с умом»",
    "«Сегодняшние 100 отжиманий — это завтрашняя лёгкость в движениях»",
    "«Пропустишь один день — и привычка начнёт умирать»",
    "«Ты не обязан быть великим, чтобы начать, но ты должен начать, чтобы стать великим»",
    "«Дисциплина — это память о том, что ты действительно хочешь»",
    "«Чем больше ты жалеешь себя сегодня, тем больше будешь жалеть завтра»",
    "«Отжимания лечат лень, прокрастинацию и плохое настроение»",
    "«Твои мышцы растут именно в тот момент, когда ты хочешь остановиться»",
    "«Сделай это ради того, кто смотрит на тебя и ждёт примера»",
    "«Результат приходит не от действий, которые ты делаешь иногда, а от тех, что делаешь каждый день»",
    "«Утром кажется тяжело, вечером — гордость»",
    "«Если тебе тяжело — значит, ты на правильном пути»",
    "«Твоё тело — единственное место, где тебе жить всю жизнь. Содержи его в порядке»",
    "«Одна тренировка ничего не меняет. Сто — меняют всё»",
    "«Оправдания — это обещание себе, что ты слабак. Выполни обещание быть сильным»",
    "«Вчера ты сказал \"начну с понедельника\". Понедельник уже много раз был»",
    "«Боль от дисциплины весит граммы. Боль от сожалений — тонны»",
    "«Когда ты не хочешь — сделай первый подход. Дальше само пойдёт»",
    "«Сила не в том, чтобы никогда не падать, а в том, чтобы каждый раз вставать»",
    "«Чем раньше ты отожмёшься, тем быстрее забудешь об этом и займёшься делами»",
    "«100 раз — это всего 4 минуты твоего дня. Неужели это сложно?»",
    "«Герои не рождаются, они отжимаются каждое утро»",
    "«Если ты читаешь это сообщение, значит, у тебя есть руки. Используй их»",
    "«Закончил? Нет, закончил — когда 100 сделано»",
]

async def morning_reminder(context: ContextTypes.DEFAULT_TYPE):
    day, finished = get_challenge_day()
    total = config.CHALLENGE_TOTAL_DAYS
    day_str = "🏁 Челлендж завершён!" if finished else f"🏆 День {day} из {total} нашего челленджа!"
    debtors = get_yesterday_debtors()
    quote = random.choice(MOTIVATIONAL_QUOTES)
    if not debtors:
        await context.bot.send_message(
            chat_id=config.CHAT_ID,
            text=f"🌞 Доброе утро!\n{day_str}\n\nВчера все выполнили норму!\n\n{quote}"
        )
        return
    lines = [f"• {name or str(uid)} (@{username}) – {count}/100" for uid, username, name, count in debtors]
    await context.bot.send_message(
        chat_id=config.CHAT_ID,
        text=f"🌞 Доброе утро!\n{day_str}\n\nВчера не сделали 100:\n" + "\n".join(lines) + f"\n\n{quote}"
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
    if application.job_queue:
        for job in application.job_queue.jobs():
            job.schedule_removal()
        reminder_time = time(config.REMINDER_HOUR, config.REMINDER_MINUTE, tzinfo=TIMEZONE)
        application.job_queue.run_daily(morning_reminder, reminder_time, days=tuple(range(7)))
        check_time = time(config.CHECK_HOUR, config.CHECK_MINUTE, tzinfo=TIMEZONE)
        application.job_queue.run_daily(evening_check, check_time, days=tuple(range(7)))

# -------------------- MAIN --------------------
def main():
    init_db()
    application = (Application.builder()
                   .token(config.TOKEN)
                   .connect_timeout(30.0)
                   .read_timeout(30.0)
                   .post_init(post_init)
                   .build())

    # Английские команды
    for cmd, handler in [("pushups", pushups), ("mypushups", mypushups), ("today", today_stats),
                         ("leaderboard", leaderboard), ("reset", reset_pushups), ("progress", challenge_progress),
                         ("help", help_command), ("start", start)]:
        application.add_handler(CommandHandler(cmd, handler))

    # Русские команды через MessageHandler
    for pattern in ["/отжимания", "/мои", "/статистика", "/топ", "/сброс", "/progress", "/прогресс", "/помощь"]:
        application.add_handler(MessageHandler(filters.Regex(rf'^{pattern}\b'), russian_commands))

    # Интерактивный ввод чисел
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pushups_number))

    # Меню команд
    application.bot.set_my_commands([
        BotCommand("pushups", "Добавить отжимания (можно несколько чисел)"),
        BotCommand("mypushups", "Сколько вы отжались сегодня"),
        BotCommand("today", "Прогресс всех участников"),
        BotCommand("leaderboard", "Лидеры дня"),
        BotCommand("reset", "Сбросить свои отжимания за сегодня"),
        BotCommand("progress", "Прогресс челленджа"),
        BotCommand("help", "Справка")
    ])

    application.run_polling()

if __name__ == "__main__":
    main()
