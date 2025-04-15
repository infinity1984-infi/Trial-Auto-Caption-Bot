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

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
WAIT_FOR_VIDEOS, WAIT_FOR_DETAILS = range(2)

# Define accepted MIME types for various video formats
ACCEPTED_MIME_TYPES = [
    "video/mp4",
    "video/quicktime",    # MOV
    "video/x-msvideo",    # AVI
    "video/x-matroska",   # MKV
    "video/webm",         # WEBM
    "video/x-flv",        # FLV
    "video/3gpp",         # 3GP
    "video/ogg",          # OGV
    "application/octet-stream",  # Fallback for unknown types
]

# Define quality labels for the three expected videos
QUALITIES = ["480p", "720p", "1080p"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks the user to send videos."""
    await update.message.reply_text("👋 Hi! Please send the 3 video files (one by one).")
    context.user_data.clear()
    return WAIT_FOR_VIDEOS

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles video/document uploads with validation of multiple formats."""
    video = update.message.video or update.message.document

    if not video or (video.mime_type not in ACCEPTED_MIME_TYPES):
        await update.message.reply_text(
            "❌ Please send a valid video file (e.g., MP4, MOV, AVI, MKV, WEBM, FLV, 3GP, OGV)."
        )
        return WAIT_FOR_VIDEOS

    # Save the file_id from the received video
    context.user_data.setdefault("videos", []).append(video.file_id)
    current_count = len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Received video {current_count} of 3.")

    if current_count == 3:
        await update.message.reply_text(
            "📝 Now, send the details in 3 lines:\n"
            "1. Title (e.g., Naruto Shippuden)\n"
            "2. Season (e.g., 05 or S05)\n"
            "3. Episode (e.g., 12 or E12)"
        )
        return WAIT_FOR_DETAILS
    return WAIT_FOR_VIDEOS

async def receive_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Parses and validates the details provided by the user.
    Expected 3 lines: Title, Season, Episode.
    The season and episode can be provided either as numbers or with a leading letter (e.g., S05, E12).
    """
    try:
        lines = update.message.text.strip().splitlines()
        if len(lines) < 2:
            raise ValueError("Please provide at least a Title and an Episode number.")

        title = lines[0].strip()
        season_input = lines[1].strip() if len(lines) > 1 else "01"
        episode_input = lines[2].strip() if len(lines) > 2 else season_input

        # Remove any non-digit characters (allows inputs like "S05" or "05")
        season = re.sub(r"\D", "", season_input) or "01"
        episode = re.sub(r"\D", "", episode_input)
        if not episode:
            raise ValueError("Episode must contain numeric characters.")

        # Ensure two digit format
        season = season.zfill(2)
        episode = episode.zfill(2)

        # Send confirmation message in bold (using Markdown)
        await update.message.reply_text(
            f"<b>📥 Episode {episode} Added...!</b>", parse_mode="HTML"
        )

        # Repost videos with captions in bold text.
        # The caption now uses bold formatting and changes '@Rear_Animes' to '[@Rear_Animes]'.
        for idx, file_id in enumerate(context.user_data.get("videos", [])):
            quality = QUALITIES[idx] if idx < len(QUALITIES) else "Unknown"
            caption = f"<b>[@Rear_Animes] {title} S{season}E{episode} - {quality}</b>"
            await update.message.reply_video(
                video=file_id,
                caption=caption,
                parse_mode="HTML",
            )

        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {str(e)}\nPlease resend the details in the correct format."
        )
        return WAIT_FOR_DETAILS

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text("🚫 Operation cancelled. To start over, send /start.")
    context.user_data.clear()
    return ConversationHandler.END

def main():
    """Run the bot."""
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAIT_FOR_VIDEOS: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video)
            ],
            WAIT_FOR_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_details)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
