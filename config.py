import os
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env file
TOKEN = os.getenv("YOUR_BOT_TOKEN")  # ensure TELEGRAM_BOT_TOKEN is set in your .env
