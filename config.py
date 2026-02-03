import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8569990381:AAG9wr0L9g5pUn9bp1H2wwfDZju3vIuVOBI")
ADMIN_CHAT_IDS = list(map(int, os.getenv("ADMIN_CHAT_IDS", "7884533080").split(',')))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "tyufj123")
