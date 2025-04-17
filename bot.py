import logging
import re
from telegram import Update, Sticker
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from config import BOT_TOKEN, DEFAULT_QUALITIES, DEFAULT_CAPTION

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(
    WAIT_SET_STICKER,
    MODE_SELECTION,
    WAIT_SEASON_COUNT,
    WAIT_VIDEOS,
    WAIT_DETAILS,
) = range(5)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets and prompts mode selection."""
    await update.message.reply_text(
        "Bot is Alive!\n"
        "/setsticker – Register a sticker (reply to a sticker)\n"
        "/forepisode – Process 3 videos for a single episode\n"
        "/forseason – Process multiple episodes (3 videos each)"
    )
    return MODE_SELECTION

async def set_sticker_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registers a sticker for later use."""
    if not update.message.reply_to_message or not update.message.reply_to_message.sticker:
        await update.message.reply_text(
            "❌ Please reply to a sticker with /setsticker."
        )
        return WAIT_SET_STICKER
    sticker: Sticker = update.message.reply_to_message.sticker
    context.chat_data["sticker_id"] = sticker.file_id
    await update.message.reply_text("✅ Sticker registered!")
    return ConversationHandler.END

async def forepisode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates single episode flow."""
    context.chat_data["mode"] = "EPISODE"
    context.user_data.clear()
    await update.message.reply_text("📥 Send exactly 3 video files.")
    return WAIT_VIDEOS

async def forseason_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates full season flow."""
    context.chat_data["mode"] = "SEASON"
    await update.message.reply_text("🔢 How many episodes in this season?")
    return WAIT_SEASON_COUNT

async def receive_season_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stores total episode count for /forseason."""
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("❌ Send a positive integer.")
        return WAIT_SEASON_COUNT
    total = int(text)
    context.chat_data["season_count"] = total
    context.chat_data["current_ep"] = 1
    await update.message.reply_text(
        f"✅ Season has {total} episodes. Now send {total*3} videos."
    )
    return WAIT_VIDEOS

async def receive_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collects uploaded videos until expected count reached."""
    video = update.message.video or update.message.document
    if not video or video.mime_type.split("/")[0] != "video":
        await update.message.reply_text("❌ Please send a video file.")
        return WAIT_VIDEOS
    context.user_data.setdefault("videos", []).append(video.file_id)
    count = len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Received {count} video(s).")
    # Determine expected total
    if context.chat_data["mode"] == "EPISODE":
        needed = 3
    else:
        needed = context.chat_data["season_count"] * 3
    if count >= needed:
        await update.message.reply_text(
            "📝 Now send details:\n1. Title\n2. Season (e.g., 01 or S01)"
        )
        return WAIT_DETAILS
    return WAIT_VIDEOS

async def receive_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses details and dispatches videos with captions and sticker."""
    try:
        lines = update.message.text.strip().splitlines()
        if len(lines) < 2:
            raise ValueError("Title and Season are required.")
        title = lines[0].strip()
        season_raw = lines[1].strip()
        season = re.sub(r"\D", "", season_raw).zfill(2)
        qualities = context.chat_data.get("qualities", DEFAULT_QUALITIES)
        sticker_id = context.chat_data.get("sticker_id")
        videos = context.user_data["videos"]

        if context.chat_data["mode"] == "SEASON":
            total = context.chat_data["season_count"]
            ep = context.chat_data["current_ep"]
            for batch_start in range(0, total * 3, 3):
                for i in range(3):
                    idx = batch_start + i
                    quality = qualities[i] if i < len(qualities) else qualities[-1]
                    caption = DEFAULT_CAPTION.format(
                        title=title, season=season, episode=str(ep).zfill(2), quality=quality
                    )
                    await update.message.reply_video(
                        video=videos[idx], caption=caption, parse_mode="HTML"
                    )
                if sticker_id:
                    await update.message.reply_sticker(sticker=sticker_id)
                context.chat_data["current_ep"] += 1
                ep += 1
        else:
            # Expect exactly 3 videos
            episode = "01"
            if len(lines) > 2:
                ep_raw = lines[2].strip()
                ep_num = re.sub(r"\D", "", ep_raw)
                if ep_num:
                    episode = ep_num.zfill(2)
            for i in range(3):
                quality = qualities[i] if i < len(qualities) else qualities[-1]
                caption = DEFAULT_CAPTION.format(
                    title=title, season=season, episode=episode, quality=quality
                )
                await update.message.reply_video(
                    video=videos[i], caption=caption, parse_mode="HTML"
                )
            if sticker_id:
                await update.message.reply_sticker(sticker=sticker_id)

        # Final main-channel broadcast
        for _ in range(3):
            await update.message.reply_text(
                "<b>Main channel : [ @INFI1984 ]</b>", parse_mode="HTML"
            )
        return ConversationHandler.END

    except Exception as e:
        logger.error("receive_details error: %s", e)
        await update.message.reply_text(
            f"❌ Error: {e}\nPlease restart with /start."
        )
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels the conversation."""
    await update.message.reply_text("🚫 Cancelled. Use /start to try again.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_cmd),
            CommandHandler("setsticker", set_sticker_cmd),
            CommandHandler("forepisode", forepisode_start),
            CommandHandler("forseason", forseason_start),
        ],
        states={
            WAIT_SET_STICKER: [MessageHandler(filters.STICKER, set_sticker_cmd)],
            MODE_SELECTION: [MessageHandler(filters.Regex("^/forepisode$"), forepisode_start),
                             MessageHandler(filters.Regex("^/forseason$"), forseason_start)],
            WAIT_SEASON_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_season_count)],
            WAIT_VIDEOS: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_videos)],
            WAIT_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_details)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
