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

# Define conversation states
WAIT_FOR_VIDEOS, WAIT_FOR_DETAILS = range(2)
qualities = ["480p", "720p", "1080p"]

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles video/document uploads with validation."""
    video = update.message.video or update.message.document
    if not video or (video.mime_type not in ["video/mp4", "video/quicktime"]):
        await update.message.reply_text("❌ Please send a valid MP4 video.")
        return WAIT_FOR_VIDEOS

    context.user_data.setdefault("videos", []).append(video.file_id)
    current_count = len(context.user_data["videos"])
    await update.message.reply_text(f"Received video {current_count} of 3.")

    if current_count == 3:
        await update.message.reply_text(
            "📝 Send details in 3 lines:\n"
            "1. Title\n2. Season (e.g., 05 or S05)\n3. Episode (e.g., 12 or E12)"
        )
        return WAIT_FOR_DETAILS
    return WAIT_FOR_VIDEOS

async def receive_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Parses and validates details."""
    lines = update.message.text.strip().splitlines()
    if len(lines) < 2:
        await update.message.reply_text("❌ Please provide at least Title and Episode info.")
        return WAIT_FOR_DETAILS
    
    title = lines[0].strip()
    
    # Use regex to extract digits. Accepts formats like "05" or "S05"
    def extract_number(s: str) -> str:
        match = re.search(r"(\d+)", s)
        return match.group(1) if match else ""
    
    season_raw = lines[1].strip() if len(lines) > 1 else "01"
    season = extract_number(season_raw) or "01"
    if len(lines) > 2:
        episode_raw = lines[2].strip()
    else:
        episode_raw = season_raw  # Fallback if not provided
    episode = extract_number(episode_raw)
    
    if not season.isdigit() or not episode.isdigit():
        await update.message.reply_text("❌ Season/Episode must contain numeric values!")
        return WAIT_FOR_DETAILS

    # Standardize values with two digits
    season = season.zfill(2)
    episode = episode.zfill(2)
    context.user_data.update({
        "title": title,
        "season": season,
        "episode": episode,
    })
    
    # Optional: Confirm details before sending videos (could add inline buttons here)
    await update.message.reply_text(f"✅ Details accepted: {title} S{season}E{episode}")

    # Repost videos with caption for each quality
    for idx, file_id in enumerate(context.user_data.get("videos", [])):
        quality = qualities[idx]
        caption = f"**[ @Rear_Animes ] {title} S{season}E{episode} - {quality}**"
        await update.message.reply_video(
            video=file_id,
            caption=caption,
            parse_mode="Markdown",
        )
    
    # End conversation
    return ConversationHandler.END

def main():
    # Load the token from config or environment variables
    from config import TOKEN  # Assume TOKEN is defined in config.py
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", receive_video)],  # or a separate start function
        states={
            WAIT_FOR_VIDEOS: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video)
            ],
            WAIT_FOR_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_details)
            ],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)

    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == '__main__':
    main()
