import logging
import re
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from config import BOT_TOKEN

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
WAIT_FOR_VIDEOS, WAIT_FOR_DETAILS = range(2)

# Accepted video MIME types
ACCEPTED_MIME_TYPES = [
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska",
    "video/webm", "video/x-flv", "video/3gpp", "video/ogg", "application/octet-stream"
]

# Video qualities
QUALITIES = ["480p", "720p", "1080p"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("👋 Send the 3 video files one by one (480p, 720p, 1080p).")
    context.user_data.clear()
    return WAIT_FOR_VIDEOS

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    video = update.message.video or update.message.document
    if not video or video.mime_type not in ACCEPTED_MIME_TYPES:
        await update.message.reply_text("❌ Invalid file. Please send a valid video format.")
        return WAIT_FOR_VIDEOS

    context.user_data.setdefault("videos", []).append(video.file_id)
    count = len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Received {count}/3 video(s).")

    if count == 3:
        await update.message.reply_text(
            "📝 Now send the details in 2 or 3 lines:\n"
            "1. Title (e.g., Attack on Titan)\n"
            "2. Season or Episode (e.g., S01 or E05 or S01E05)\n"
            "3. (Optional) Episode if not included above."
        )
        return WAIT_FOR_DETAILS

    return WAIT_FOR_VIDEOS

async def receive_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lines = update.message.text.strip().splitlines()
        if not lines:
            raise ValueError("Title is required.")

        title = lines[0].strip()
        season, episode = "01", "01"

        if len(lines) >= 2:
            match = re.search(r"[sS]?(\d{1,2})[eE]?(\d{1,2})?", lines[1])
            if match:
                season = match.group(1).zfill(2)
                if match.group(2):
                    episode = match.group(2).zfill(2)

        if len(lines) == 3:
            ep_line = re.sub(r"\D", "", lines[2])
            if ep_line:
                episode = ep_line.zfill(2)

        # Respond with success message
        await update.message.reply_text(
            f"<b>📥 {title} S{season}E{episode} Uploaded Successfully!</b>",
            parse_mode="HTML"
        )

        # Resend each video with correct caption
        for idx, file_id in enumerate(context.user_data["videos"]):
            quality = QUALITIES[idx] if idx < len(QUALITIES) else "Unknown"
            caption = f"<b>[@Rear_Animes] {title} S{season}E{episode} - {quality}</b>"
            await update.message.reply_video(
                video=file_id,
                caption=caption,
                parse_mode="HTML"
            )

        context.user_data.clear()
        return ConversationHandler.END

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}\nPlease resend the details properly.")
        return WAIT_FOR_DETAILS

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🚫 Cancelled. To start again, use /start.")
    context.user_data.clear()
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_FOR_VIDEOS: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video)],
            WAIT_FOR_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_details)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
