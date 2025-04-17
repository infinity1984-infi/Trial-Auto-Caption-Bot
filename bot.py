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
from config import BOT_TOKEN, DEFAULT_QUALITIES, DEFAULT_FORMAT

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAIT_STICKER, MODE, SEASON_COUNT, VIDEOS, DETAILS = range(5)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greet user and show commands."""
    await update.message.reply_text(
        "Bot is Alive!\n"
        "/setsticker — Reply to a sticker to register it\n"
        "/setformat — Define a custom caption template\n"
        "/forepisode — Process 3 videos for one episode\n"
        "/forseason — Process whole season (3×N videos)"
    )
    return MODE

async def set_sticker_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register a sticker for later use."""
    msg = update.message
    if not msg.reply_to_message or not msg.reply_to_message.sticker:
        await msg.reply_text("❌ Reply to a sticker with /setsticker to register it.")
        return WAIT_STICKER
    context.chat_data["sticker_id"] = msg.reply_to_message.sticker.file_id
    await msg.reply_text("✅ Sticker registered!")
    return ConversationHandler.END

async def set_format_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow user to override the caption format."""
    parts = update.message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "❌ Usage: /setformat <HTML template with {title},{season},{episode},{quality}>"
        )
        return ConversationHandler.END
    template = parts[1].strip()
    # Optionally: validate placeholders present
    for placeholder in ("{title}", "{season}", "{episode}", "{quality}"):
        if placeholder not in template:
            await update.message.reply_text(f"❌ Missing placeholder {placeholder}.")
            return ConversationHandler.END
    context.chat_data["format"] = template
    await update.message.reply_text("✅ Caption format updated!")
    return ConversationHandler.END

async def forepisode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begin single-episode (3 videos) flow."""
    context.chat_data["mode"] = "EPISODE"
    context.user_data.clear()
    await update.message.reply_text("📥 Send exactly 3 video files now.")
    return VIDEOS

async def forseason_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Begin full-season flow by asking for episode count."""
    context.chat_data["mode"] = "SEASON"
    await update.message.reply_text("🔢 How many episodes in this season?")
    return SEASON_COUNT

async def receive_season_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the total number of episodes."""
    text = update.message.text.strip()
    if not text.isdigit() or (n := int(text)) < 1:
        await update.message.reply_text("❌ Send a positive integer.")
        return SEASON_COUNT
    context.chat_data["season_count"] = n
    context.chat_data["current_ep"] = 1
    await update.message.reply_text(f"✅ Season has {n} episodes. Now send {n*3} videos.")
    return VIDEOS

async def receive_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect video file_ids until we have enough."""
    v = update.message.video or update.message.document
    if not v or v.mime_type.split("/")[0] != "video":
        await update.message.reply_text("❌ Please send a video file.")
        return VIDEOS
    context.user_data.setdefault("videos", []).append(v.file_id)
    cnt = len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Received {cnt} video(s).")
    needed = 3 if context.chat_data["mode"] == "EPISODE" else context.chat_data["season_count"]*3
    if cnt >= needed:
        await update.message.reply_text(
            "📝 Now send details:\n"
            "1. Title\n"
            "2. Season (e.g., 01 or S01)\n"
            f"{'' if context.chat_data['mode']=='EPISODE' else ''}"  # no Episode line for season
        )
        return DETAILS
    return VIDEOS

async def receive_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse details and dispatch videos, stickers, and final broadcast."""
    try:
        lines = update.message.text.strip().splitlines()
        if len(lines) < 2:
            raise ValueError("Need Title and Season.")
        title = lines[0].strip()
        season = re.sub(r"\D", "", lines[1]).zfill(2)
        qualities = context.chat_data.get("qualities", DEFAULT_QUALITIES)
        fmt = context.chat_data.get("format", DEFAULT_FORMAT)
        sticker = context.chat_data.get("sticker_id")
        vids = context.user_data["videos"]

        async def send_batch(ep_num, batch):
            await update.message.reply_text(
                f"<b>Episode {str(ep_num).zfill(2)} Added...!</b>", parse_mode="HTML"
            )
            for i, file_id in enumerate(batch):
                quality = qualities[i] if i < len(qualities) else qualities[-1]
                caption = fmt.format(
                    title=title, season=season, episode=str(ep_num).zfill(2), quality=quality
                )
                await update.message.reply_video(video=file_id, caption=caption, parse_mode="HTML")
            if sticker:
                await update.message.reply_sticker(sticker=sticker)

        if context.chat_data["mode"] == "EPISODE":
            await send_batch(
                lines[2].strip() if len(lines) > 2 and re.search(r"\d+", lines[2]) else 1,
                vids[:3],
            )
        else:
            total = context.chat_data["season_count"]
            for ep in range(1, total+1):
                start = (ep-1)*3
                await send_batch(ep, vids[start:start+3])

        # Final broadcast
        for _ in range(3):
            await update.message.reply_text(
                "<b>Main channel : [ @INFI1984 ]</b>", parse_mode="HTML"
            )
        return ConversationHandler.END

    except Exception as e:
        logger.error("Error in receive_details: %s", e)
        await update.message.reply_text(f"❌ {e}\nUse /start to retry.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel everything."""
    await update.message.reply_text("🚫 Cancelled. Use /start again.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()  # 0
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_cmd),
            CommandHandler("setsticker", set_sticker_cmd),
            CommandHandler("setformat", set_format_cmd),            # new
            CommandHandler("forepisode", forepisode_start),
            CommandHandler("forseason", forseason_start),
        ],
        states={
            WAIT_STICKER: [MessageHandler(filters.Sticker.ALL, set_sticker_cmd)],        # 1
            MODE: [
                MessageHandler(filters.Regex("^/forepisode$"), forepisode_start),
                MessageHandler(filters.Regex("^/forseason$"), forseason_start),
            ],
            SEASON_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_season_count)],
            VIDEOS: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_videos)],  # 2
            DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_details)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
