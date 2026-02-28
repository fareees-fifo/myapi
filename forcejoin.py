from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from functools import wraps

GROUP_USERNAME = "faresssteam"
CHANNEL_USERNAME = "faresssteam"

def force_join(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_id = update.effective_user.id
        bot = context.bot

        try:
            member_group = await bot.get_chat_member(f"@{GROUP_USERNAME}", user_id)
            member_channel = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)

            if member_group.status in ["left", "kicked"] or member_channel.status in ["left", "kicked"]:
                keyboard = [
                    [InlineKeyboardButton("Join Group", url=f"https://t.me/{GROUP_USERNAME}")],
                    [InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
                    [InlineKeyboardButton("I Joined", callback_data="check_joined")]
                ]

                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    "Please join the group and channel first.",
                    reply_markup=reply_markup
                )
                return

        except:
            pass

        return await func(update, context)

    return wrapper


async def check_joined_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Access Granted ✅")
