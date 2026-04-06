import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")   # токен от @BotFather
CHAT_ID = -1001234567890                  # ID вашей группы (число отрицательное)

# Время утреннего напоминания (о вчерашних должниках)
REMINDER_HOUR = 8
REMINDER_MINUTE = 0

# Время вечерней проверки (кто ещё не сделал 100 сегодня)
CHECK_HOUR = 22
CHECK_MINUTE = 0

DAILY_GOAL = 100