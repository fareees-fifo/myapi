import logging
import random
import string
import os  # Required for file operations
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from database import (
    get_or_create_user,
    update_user_plan,
    get_user_plan,
    get_user_credits,
    update_user_credits,
    get_all_active_plans
)

from telegram import Update
from telegram.ext import ContextTypes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of admin user IDs who can use plan commands
ADMIN_IDS = [1710051635]  # Replace with your actual admin ID(s)

# Chat ID to send purchase logs to
LOG_CHANNEL_ID = None

# Plan configurations
PLANS = {
    "plan1": {
        "name": "𝑪𝒐𝒓𝒆 𝑨𝒄𝒄𝒆𝒔",
        "tier": "Core",
        "duration_days": 7,
        "emoji": "🛠️",
        "price": "$8.00"
    },
    "plan2": {
        "name": "𝑬𝒍𝒊𝒕𝒆 𝑨𝒄𝒄𝒆𝒔",
        "tier": "Elite",
        "duration_days": 15,
        "emoji": "👑",
        "price": "$14.00"
    },
    "plan3": {
        "name": "𝑹𝒐𝒐𝒕 𝑨𝒄𝒄𝒆𝒔",
        "tier": "Root",
        "duration_days": 30,
        "emoji": "⭐",
        "price": "$25.00"
    },
    "plan4": {
        "name": "𝑿-𝑨𝒄𝒄𝒆𝒔",
        "tier": "X",
        "duration_days": 90,
        "emoji": "💎",
        "price": "$60.00"
    }
}

def is_admin(user_id: int) -> bool:
    """Check if the user is an admin."""
    return user_id in ADMIN_IDS

def format_plan_response(success: bool, plan_name: str, user_id: int, 
                        user_name: str, tier: str, duration_days: int, 
                        emoji: str, error_msg: Optional[str] = None) -> str:
    """Format the plan response message."""
    if success:
        expiry_date = (datetime.now() + timedelta(days=duration_days)).strftime('%Y-%m-%d %H:%M:%S')
        return f"""
<pre><a href='https://t.me/farxxes'>✅</a> <b>Plan Updated Successfully</b></pre>

<a href='https://t.me/farxxes'>⊀</a> <b>User</b> ↬ <a href='tg://user?id={user_id}'>{user_name}</a>
<a href='https://t.me/farxxes'>⊀</a> <b>Plan</b> ↬ {emoji} {plan_name}
<a href='https://t.me/farxxes'>⊀</a> <b>Tier</b> ↬ <code>{tier}</code>
<a href='https://t.me/farxxes'>⊀</a> <b>Duration</b> ↬ <code>{duration_days} days</code>
<a href='https://t.me/farxxes'>⊀</a> <b>Expires</b> ↬ <code>{expiry_date}</code>
<a href='https://t.me/farxxes'>⌬</a> <b>Dev</b> ↬ <a href='https://t.me/farxxes'>farxxes</a>
"""
    else:
        return f"""
<pre><a href='https://t.me/farxxes'>❌</a> <b>Plan Update Failed</b></pre>

<a href='https://t.me/farxxes'>⊀</a> <b>Error</b> ↬ <code>{error_msg}</code>
<a href='https://t.me/farxxes'>⌬</a> <b>Dev</b> ↬ <a href='https://t.me/farxxes'>farxxes</a>
"""

def format_plan_congratulations(user_id: int, user_name: str, plan_name: str, 
                              tier: str, duration_days: int, emoji: str) -> str:
    """Format the congratulations message for the user."""
    expiry_date = (datetime.now() + timedelta(days=duration_days)).strftime('%Y-%m-%d %H:%M:%S')
    return f"""
<pre><a href='https://t.me/abtlnx'>🎉</a> <b>Congratulations! 🎉</b></pre>

<a href='https://t.me/farxxes'>⊀</a> <b>Your Plan Has Been Upgraded</b>
<a href='https://t.me/farxxes'>⊀</a> <b>Plan</b> ↬ {emoji} {plan_name}
<a href='https://t.me/farxxes'>⊀</a> <b>Tier</b> ↬ <code>{tier}</code>
<a href='https://t.me/farxxes'>⊀</a> <b>Duration</b> ↬ <code>{duration_days} days</code>
<a href='https://t.me/farxxes'>⊀</a> <b>Expires</b> ↬ <code>{expiry_date}</code>

<a href='https://t.me/farxxes'>ℭ</a> <b>Benefits:</b> <i>Unlimited credits until plan ends</i>
<a href='https://t.me/farxxes'>ℭ</a> <b>Access:</b> <i>No cooldowns on any commands</i>

<a href='https://t.me/farxxes'>⌬</a> <b>Thank you for choosing our service!</b>
<a href='https://t.me/farxxes'>⌬</a> <b>Dev</b> ↬ <a href='https://t.me/farxxes'>farxxes</a>
"""

def format_plan_revocation(user_name: str, plan_name: str, tier: str) -> str:
    """Format the plan revocation message for the user."""
    return f"""
<pre><a href='https://t.me/farxxes'>ℹ️</a> <b>Plan Status Update</b></pre>

<a href='https://t.me/farxxes'>⊀</a> <b>Hello {user_name},</b>
<a href='https://t.me/farxxes'>⊀</a> <b>Your {plan_name} ({tier}) has been ended.</b>

<a href='https://t.me/farxxes'>ℭ</a> <b>Current Status:</b> <i>You have been reverted to Trial tier</i>
<a href='https://t.me/farxxes'>ℭ</a> <b>Credits:</b> <i>Your credits have been restored</i>

<a href='https://t.me/farxxes'>⌬</a> <b>Thank you for using our service!</b>
<a href='https://t.me/farxxes'>⌬</a> <b>If you'd like to renew your plan, please contact</b> <a href='https://t.me/farxxes'>@farxxes</a>
<a href='https://t.me/farxxes'>⌬</a> <b>Dev</b> ↬ <a href='https://t.me/farxxes'>farxxes</a>
"""

async def handle_plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_type: str):
    """Handle the plan commands."""
    # Check if user is admin
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "<pre>⚠️ <b>Access Denied</b></pre>\n\n"
            "<i>You don't have permission to use this command.</i>",
            parse_mode="HTML"
        )
        return
    
    # Check if user ID was provided
    if not context.args:
        await update.message.reply_text(
            f"<pre>⚠️ <b>Missing User ID</b></pre>\n\n"
            f"<i>Usage: /{plan_type} user_id</i>",
            parse_mode="HTML"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "<pre>⚠️ <b>Invalid User ID</b></pre>\n\n"
            "<i>Please provide a valid numeric user ID.</i>",
            parse_mode="HTML"
        )
        return
    
    # Get plan details
    plan_info = PLANS.get(plan_type)
    if not plan_info:
        await update.message.reply_text(
            "<pre>⚠️ <b>Invalid Plan</b></pre>\n\n"
            "<i>This plan doesn't exist.</i>",
            parse_mode="HTML"
        )
        return
    
    # Get target user info
    try:
        target_user = await context.bot.get_chat(target_user_id)
        target_user_name = target_user.first_name or "Unknown"
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        target_user_name = "Unknown"
    
    # Check if user already has an active plan to determine if this is an upgrade
    current_tier = check_plan_expiry(target_user_id)
    is_upgrade = False
    
    if current_tier and current_tier != "Trial":
        is_upgrade = True

    # Calculate expiry date
    expiry_date = datetime.now() + timedelta(days=plan_info["duration_days"])
    
    # Update user plan in database
    success = update_user_plan(
        target_user_id, 
        plan_info["tier"], 
        expiry_date
    )
    
    # Send response to admin
    if success:
        response = format_plan_response(
            True, 
            plan_info["name"], 
            target_user_id, 
            target_user_name,
            plan_info["tier"],
            plan_info["duration_days"],
            plan_info["emoji"]
        )
        
        # 1. Send congratulations message to the user
        congrats_msg = format_plan_congratulations(
            target_user_id,
            target_user_name,
            plan_info["name"],
            plan_info["tier"],
            plan_info["duration_days"],
            plan_info["emoji"]
        )
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=congrats_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending congratulations message: {e}")

        # 2. Send Log Message to Channel
        try:
            # Generate 8-character alphanumeric suffix
            random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            
            # Mask the receipt ID: CARDX-XXXXXXX
            # Display format: CARDX-{First 2 chars}XXXX{Last 2 chars}
            # Example: CARDX-RJN4WKV1 -> CARDX-RJXXXXV1
            masked_suffix = f"{random_suffix[:2]}XXXX{random_suffix[-2:]}"
            receipt_id_display = f"CARDX-{masked_suffix}"
            
            # Determine Log Title based on whether it was an upgrade
            log_title = "Plan RENEWED 🔄" if is_upgrade else "New Plan Purchase 🛒"
            
            # Prepare compact log message (No Duration, No Tier, No spaces)
            log_msg = f"""<pre>{log_title}</pre>
<a href='https://t.me/farxxes'>⊀</a><b> User</b> ↬ <a href='tg://user?id={target_user_id}'>{target_user_name}</a>
<a href='https://t.me/farxxes'>⊀</a><b> Plan</b> ↬ {plan_info['emoji']}{plan_info['name']}
<a href='https://t.me/farxxes'>ℭ</a><b> Price</b> ↬ <code>{plan_info['price']}</code>
<a href='https://t.me/farxxes'>ℭ</a><b> Receipt</b> ↬ <code>{receipt_id_display}</code>
<a href='https://t.me/farxxes'>⌬</a><b> Dev</b> ↬ <a href='https://t.me/farxxes'>farxxes</a>
"""
            await context.bot.send_message(
                chat_id=LOG_CHANNEL_ID,
                text=log_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send log to channel {LOG_CHANNEL_ID}: {e}")

    else:
        response = format_plan_response(
            False, 
            plan_info["name"], 
            target_user_id, 
            target_user_name,
            plan_info["tier"],
            plan_info["duration_days"],
            plan_info["emoji"],
            "Failed to update plan in database"
        )
    
    await update.message.reply_text(response, parse_mode="HTML")


async def handle_planall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users with an active plan and sends the result as a .txt file."""

    # Admin check
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "<pre>⚠️ <b>Access Denied</b></pre>\n<i>You cannot use this command.</i>",
            parse_mode="HTML"
        )
        return

    plans = get_all_active_plans()

    if not plans:
        await update.message.reply_text(
            "<pre><a href='https://t.me/abtlnx'>ℹ️</a> <b>No Active Plans Found</b></pre>",
            parse_mode="HTML"
        )
        return
    
    # Prepare content for the .txt file (Plain text format)
    file_content = f"ACTIVE PLANS LIST\n"
    file_content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    file_content += f"Total Active Users: {len(plans)}\n"
    file_content += "=" * 40 + "\n\n"

    for user_id, tier, expiry_date in plans:

        # Find plan name + emoji
        plan_name = "Unknown"
        emoji = "❔"
        for p in PLANS.values():
            if p["tier"] == tier:
                plan_name = p["name"]
                emoji = p["emoji"]
                break

        # Expiry
        expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")

        # Username
        try:
            u = await context.bot.get_chat(user_id)
            uname = u.first_name or "Unknown"
        except:
            uname = "Unknown"

        # Append to file content (Clean text format)
        file_content += f"User: {uname}\n"
        file_content += f"User ID: {user_id}\n"
        file_content += f"Plan: {emoji} {plan_name}\n"
        file_content += f"Tier: {tier}\n"
        file_content += f"Expires: {expiry_str}\n"
        file_content += "-" * 40 + "\n"

    file_content += "\nGenerated by CARD-X Bot"

    # Define a filename with timestamp
    filename = f"active_plans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    # Write content to file
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(file_content)

        # Send the file
        with open(filename, "rb") as f:
            await update.message.reply_document(
                document=f,
                caption=f"<pre>📋 <b>Active Plans List</b></pre>\n<i>Total: {len(plans)} users</i>",
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error sending planall file: {e}")
        await update.message.reply_text("Failed to generate the plans list.")
    finally:
        # Cleanup: Delete the file after sending
        if os.path.exists(filename):
            os.remove(filename)


async def handle_decreds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Decrease user's credits by a specified amount."""

    # Admin check
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "<pre>⚠️ <b>Access Denied</b></pre>\n<i>You cannot use this command.</i>",
            parse_mode="HTML"
        )
        return

    # Validate args
    if len(context.args) < 2:
        await update.message.reply_text(
            "<pre>⚠️ <b>Missing Arguments</b></pre>\n"
            "<i>Usage: /decreds user_id amount</i>",
            parse_mode="HTML"
        )
        return

    # Extract arguments
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "<pre>⚠️ <b>Invalid Arguments</b></pre>\n"
            "<i>User ID and amount must be numbers.</i>",
            parse_mode="HTML"
        )
        return

    if amount <= 0:
        await update.message.reply_text(
            "<pre>⚠️ <b>Invalid Amount</b></pre>\n"
            "<i>Amount must be greater than 0.</i>",
            parse_mode="HTML"
        )
        return

    # Get current user credits
    current_credits = get_user_credits(user_id)

    if current_credits is None:
        await update.message.reply_text(
            "<pre>⚠️ <b>User Not Found</b></pre>",
            parse_mode="HTML"
        )
        return

    if current_credits == float("inf"):
        await update.message.reply_text(
            "<pre>⚠️ <b>Cannot Deduct Credits</b></pre>\n"
            "<i>User has an active plan (Unlimited credits)</i>",
            parse_mode="HTML"
        )
        return

    # Update credits (subtract)
    success = update_user_credits(user_id, -amount)

    if not success:
        await update.message.reply_text(
            "<pre>❌ <b>Failed to Update Credits</b></pre>",
            parse_mode="HTML"
        )
        return

    updated = get_user_credits(user_id)

    # Fetch user's display name
    try:
        user = await context.bot.get_chat(user_id)
        uname = user.first_name or "Unknown"
    except:
        uname = "Unknown"

    response = f"""
<pre><a href='https://t.me/abtlnx'>💰</a> <b>Credits Updated</b></pre>

<a href='https://t.me/abtlnx'>⊀</a> <b>User</b> ↬ <a href='tg://user?id={user_id}'>{uname}</a>
<a href='https://t.me/abtlnx'>⊀</a> <b>Credits Deducted</b> ↬ <code>-{amount}</code>
<a href='https://t.me/abtlnx'>⊀</a> <b>New Balance</b> ↬ <code>{updated}</code>

<a href='https://t.me/abtlnx'>⌬</a> <b>Dev</b> ↬ <a href='https://t.me/abtlnx'>farxxes</a>
"""

    await update.message.reply_text(response, parse_mode="HTML")


async def handle_revoke_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the plan revocation command."""
    # Check if user is admin
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "<pre>⚠️ <b>Access Denied</b></pre>\n\n"
            "<i>You don't have permission to use this command.</i>",
            parse_mode="HTML"
        )
        return
    
    # Check if user ID was provided
    if not context.args:
        await update.message.reply_text(
            "<pre>⚠️ <b>Missing User ID</b></pre>\n\n"
            "<i>Usage: /rplan user_id</i>",
            parse_mode="HTML"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "<pre>⚠️ <b>Invalid User ID</b></pre>\n\n"
            "<i>Please provide a valid numeric user ID.</i>",
            parse_mode="HTML"
        )
        return
    
    # Get current plan info
    current_plan = get_user_plan(target_user_id)
    if not current_plan:
        await update.message.reply_text(
            "<pre>⚠️ <b>User Not Found</b></pre>\n\n"
            "<i>This user doesn't have any active plan.</i>",
            parse_mode="HTML"
        )
        return
    
    current_tier, _ = current_plan
    
    # Find the plan name based on tier
    plan_name = "Unknown"
    for plan_id, plan_info in PLANS.items():
        if plan_info["tier"] == current_tier:
            plan_name = plan_info["name"]
            break
    
    # Get target user info
    try:
        target_user = await context.bot.get_chat(target_user_id)
        target_user_name = target_user.first_name or "Unknown"
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        target_user_name = "Unknown"
    
    # Update user plan to Trial in database
    success = update_user_plan(target_user_id, "Trial", None)
    
    # Send response to admin
    if success:
        response = f"""
<pre><a href='https://t.me/abtlnx'>✅</a> <b>Plan Revoked Successfully</b></pre>

<a href='https://t.me/farxxes'>⊀</a> <b>User</b> ↬ <a href='tg://user?id={target_user_id}'>{target_user_name}</a>
<a href='https://t.me/farxxes'>⊀</a> <b>Previous Plan</b> ↬ {plan_name} ({current_tier})
<a href='https://t.me/farxxes'>⊀</a> <b>New Plan</b> ↬ <code>Trial</code>
<a href='https://t.me/farxxes'>⌬</a> <b>Dev</b> ↬ <a href='https://t.me/farxxes'>farxxes</a>
"""
        
        # Send revocation message to the user
        revoke_msg = format_plan_revocation(target_user_name, plan_name, current_tier)
        
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=revoke_msg,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending revocation message: {e}")
    else:
        response = """
<pre><a href='https://t.me/abtlnx'>❌</a> <b>Plan Revocation Failed</b></pre>

<a href='https://t.me/abtlnx'>⊀</a> <b>Error</b> ↬ <code>Failed to update plan in database</code>
<a href='https://t.me/abtlnx'>⌬</a> <b>Dev</b> ↬ <a href='https://t.me/abtlnx'>farxxes</a>
"""
    
    await update.message.reply_text(response, parse_mode="HTML")

# Individual command handlers
async def handle_plan1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_plan_command(update, context, "plan1")

async def handle_plan2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_plan_command(update, context, "plan2")

async def handle_plan3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_plan_command(update, context, "plan3")

async def handle_plan4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_plan_command(update, context, "plan4")

async def handle_rplan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_revoke_plan(update, context)

def check_plan_expiry(user_id: int) -> Optional[str]:
    """
    Check if a user's plan has expired and update their tier if needed.
    
    Args:
        user_id: The user ID to check
        
    Returns:
        The user's current tier (after potential update) or None if not found
    """
    user_plan = get_user_plan(user_id)
    if not user_plan:
        return None
    
    tier, expiry_date = user_plan
    
    # Check if plan has expired
    if expiry_date and datetime.now() > expiry_date:
        # Update to Trial tier
        update_user_plan(user_id, "Trial", None)
        return "Trial"
    
    return tier

# Function to be called from other modules to check if a user has an active plan
def get_user_current_tier(user_id: int) -> str:

    # OWNER CHECK (1710051635)
    if user_id == 1710051635:
        return "owner"

    tier = check_plan_expiry(user_id)

    if tier is None:
        user_data = get_or_create_user(user_id, None)
        if user_data:
            _, _, tier, _ = user_data

    return tier or "Trial"
    
