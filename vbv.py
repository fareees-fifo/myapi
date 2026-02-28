import re
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
import aiohttp
import json
from bin import get_bin_info  # Import get_bin_info function from bin.py
from database import get_or_create_user, update_user_credits, get_user_credits  # Import database functions
from plans import get_user_current_tier # Import the correct function for tier checking

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API endpoint
API_URL = "https://vbv.nikhilkhokhar.com/gateway=bin"
API_KEY = "rockysoon"

# Create a thread pool executor for background tasks
executor = ThreadPoolExecutor(max_workers=100)

# Dictionary to store last command time for each user (for cooldown)
last_command_time = {}

# Semaphore to limit concurrent API requests
MAX_CONCURRENT_REQUESTS = 5
request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def parse_card_details(card_string: str) -> Optional[Tuple[str, str, str, str]]:
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
        # Pattern: 4296190000711410:08:30:545
        r'^(\d{13,19})\|(\d{1,2}):(\d{2,4}):(\d{3,4})$',
        # Pattern: 4296190000711410:08:30:545
        r'^(\d{13,19})\|(\d{1,2}):(\d{2,4}):(\d{3,4})$',
        # Pattern: 4296190000711410|08:30:545
        r'^(\d{13,19})\|(\d{1,2}):(\d{2,4}):(\d{3,4})$',
        # Pattern: 4296190000711410|08:30:545
        r'^(\d{13,19})\|(\d{1,2}):(\d{2,4}):(\d{3,4})$',
        # Pattern: 4296190000711410 08 30 545
        r'^(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})$',
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

async def check_card(card_details: str, user_info: Dict) -> Optional[str]:
    """
    Check card details using VBV API asynchronously with aiohttp.
    
    Args:
        card_details: String containing card details in various formats
        user_info: Dictionary containing user information
        
    Returns:
        Formatted response string or None if there was an error
    """
    # Parse card details
    parsed = parse_card_details(card_details)
    if not parsed:
        return "⚠️ <b>Missing card details!</b>\n\n<i>Usage: /vbv card|mm|yy|cvv</i>"
    
    card_number, month, year, cvv = parsed
    
    # Get BIN information using the imported function
    bin_number = card_number[:6]
    try:
        bin_details = await get_bin_info(bin_number)
        brand = (bin_details.get("scheme") or "N/A").title()
        issuer = bin_details.get("bank") or "N/A"
        country_name = bin_details.get("country") or "Unknown"
        country_flag = bin_details.get("country_emoji", "")
    except Exception as e:
        logger.error(f"Error getting BIN info: {str(e)}")
        brand = "N/A"
        issuer = "N/A"
        country_name = "Unknown"
        country_flag = ""
    
    # Prepare API request parameters
    params = {
        "key": API_KEY,
        "card": card_number
    }
    
    # Use semaphore to limit concurrent requests
    async with request_semaphore:
        try:
            # Create an aiohttp session for async HTTP requests with timeout
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Make API request asynchronously
                async with session.get(API_URL, params=params) as response:
                    # Check if the request was successful
                    if response.status == 200:
                        api_response = await response.json()
                        logger.info(f"API Response for card {card_number[:6]}******: {json.dumps(api_response)}")
                    else:
                        error_text = await response.text()
                        logger.error(f"API returned status {response.status}: {error_text}")
                        return f"⚠️ <b>API Error:</b> <code>Server returned status {response.status}</code>"
            
            # Format and return the response
            return format_response(api_response, user_info, card_details, brand, issuer, country_name, country_flag)
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout checking card {card_number[:6]}******")
            return f"⚠️ <b>Timeout:</b> <code>Request timed out. Please try again.</code>"
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response for card {card_number[:6]}******")
            return f"⚠️ <b>API Error:</b> <code>Invalid response from server</code>"
        except Exception as e:
            logger.error(f"Error checking card: {str(e)}")
            return f"⚠️ <b>Error checking card:</b> <code>{str(e)}</code>"

def format_response(api_response: Dict, user_info: Dict, card_details: str, 
                   brand: str, issuer: str, country_name: str, country_flag: str) -> str:
    """
    Format the API response into a beautiful message with emojis.
    
    Args:
        api_response: Dictionary containing the API response
        user_info: Dictionary containing user information
        card_details: Full card details string
        brand: Card brand from BIN lookup
        issuer: Bank name from BIN lookup
        country_name: Country name from BIN lookup
        country_flag: Country emoji from BIN lookup
        
    Returns:
        Formatted string with emojis
    """
    response_text = api_response.get("response", "N/A")
    bin_info = api_response.get("bin", "N/A")
    
    # Check if BIN was found in the database
    bin_found = api_response.get("bin_found", False)
    
    # Parse and clean the response message
    response_text = response_text.replace("\\", "").replace("/", "").replace("\"", "").replace("'", "")
    
    # Determine status based on message content with stylish formatting
    status_emoji = "❓"
    status_text = "Unknown"
    status_style = ""
    
    # Check for success messages
    if "successful" in response_text.lower() or "non vbv" in response_text.lower() or "no 3d" in response_text.lower():
        status_emoji = "✅"
        status_text = "Non VBV"
        status_style = "<b>𝐍𝐨𝐧 𝐕𝐁𝐕</b> ✅"
    # Check for VBV/MSC messages
    elif "vbv" in response_text.lower() or "3d" in response_text.lower() or "msc" in response_text.lower():
        status_emoji = "❌"
        status_text = "VBV Required"
        status_style = "<b>𝐕𝐁𝐕 𝐑𝐞𝐪𝐮𝐢𝐫𝐞𝐝</b> ❌"
    # Check for challenge required messages
    elif "challenge" in response_text.lower():
        status_emoji = "❌"
        status_text = "Declined"
        status_style = "<b>𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝</b> ❌"
    # Handle case when BIN is not found in database
    elif not bin_found:
        status_emoji = "❌"
        status_text = "Declined"
        status_style = "<b>𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝</b> ❌"
    # Default status
    else:
        status_emoji = "❓"
        status_text = "Unknown"
        status_style = "<b>𝐔𝐧𝐤𝐧𝐨𝐰𝐧</b> ❓"
    
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
    
    # Format the response with the exact structure requested
    status_part = f"""<pre><a href='https://t.me/farxxes'>⩙</a> <b>𝑺𝒕𝒂𝒕𝒖𝒔</b> ↬ {status_style}</pre>"""
    
    bank_part = f"""<pre><b>𝑩𝒔𝒂𝒎𝒌</b> ↬ <code>{brand}</code>
<b>𝑩𝒂𝒏𝒌</b> ↬ <code>{issuer}</code>
<b>𝑪𝒐𝒖𝒏𝒕𝒓𝒚</b> ↬ <code>{country_name} {country_flag}</code></pre>"""
    
    card_part = f"""<a href='https://t.me/farxxes'>⊀</a> <b>𝐂𝐚𝐫𝐝</b>
⤷ <code>{card_details}</code>"""
    
    # Add credits info only if user has 0 credits and not unlimited
    credits_warning = ""
    if user_credits is not None and user_credits <= 0 and user_credits != float('inf'):
        credits_warning = f"\n<a href='https://t.me/farxxes'>⚠️</a> <b>𝙇𝙤𝙬𝙠𝙚𝙙𝙞𝙣𝙜:</b> <i>You have 0 credits left. Please recharge to continue using this service.</i>"
    
    # Combine all parts
    formatted_response = f"""{status_part}
{card_part}
<a href='https://t.me/farxxes'>⊀</a> <b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲</b> ↬ <i>𝟯𝗗𝗦 𝗟𝗼𝗼𝗸𝘂𝗽</i>
<a href='https://t.me/farxxes'>⊀</a> <b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞</b> ↬ <code>{response_text}</code>
{bank_part}
<a href='https://t.me/farxxes'>⊀</a> <b>𝐔𝐬𝐞𝐫</b> ↬ {user_link} 
<a href='https://t.me/farxxes'>⊀</a> <b>𝐃𝐞𝐯</b> ↬ <a href='https://t.me/farxxes'>kคli liຖนxx</a>"""
    
    return formatted_response + credits_warning

# This function will be called from main.py
async def handle_vbv_command(update, context):
    """
    Handle the /vbv command with user-specific cooldown for Trial users.
    
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
    
    # Check cooldown for Trial users (user-specific)
    current_time = datetime.now()
    if user_tier == "Trial" and user_id in last_command_time:
        time_diff = current_time - last_command_time[user_id]
        if time_diff < timedelta(seconds=10):
            remaining_seconds = 10 - int(time_diff.total_seconds())
            await update.message.reply_text(
                f"⏳ <b>Please wait {remaining_seconds} seconds before using this command again.</b>\n\n"
                f"<i>Upgrade your plan to remove the time limit.</i>",
                parse_mode="HTML"
            )
            return
    
    # Get the card details from the command
    if not context.args:
        await update.message.reply_text("⚠️ <b>Missing card details!</b>\n\n<i>Usage: /vbv card|mm|yy|cvv</i>", parse_mode="HTML")
        return
    
    card_details = " ".join(context.args)
    
    # Get user credits
    user_credits = get_user_credits(user_id)
    
    # Check if user has enough credits (or unlimited)
    is_unlimited = user_credits == float('inf')
    has_credits = user_credits is not None and (is_unlimited or user_credits > 0)
    
    if not has_credits:
        # Still allow the request but show a warning
        progress_msg = f"""<pre>🔄 <b>𝗣𝗿𝗼𝗰𝗲𝘀𝗶𝗻𝗴 𝗥𝗲𝗾𝗲𝘀𝘁...</b></pre>
<pre>{card_details}</pre>
Gateway: <i>VBV Check</i>
<a href='https://t.me/abtlnx'>⚠️</a> <b>𝙇𝙚𝙬𝙠𝙚𝙙𝙞𝙣𝙜:</b> <i>You have 0 credits left. This will be your last check.</i>"""
    else:
        # Create a normal progress message without credit info
        progress_msg = f"""<pre>🔄 <b>𝗣𝗿𝗼𝗰𝗲𝘀𝗶𝗻𝗴 𝗥𝗲𝗾𝗲𝘀𝘁...</b></pre>
<pre>{card_details}</pre>
𝐆𝐚𝐭𝐞𝐰𝐚𝐲 ↬ <i>𝟯𝗗𝗦 𝗟𝗼𝗼𝗸𝘂𝗽</i>"""
    
    # Send the progress message
    checking_message = await update.message.reply_text(progress_msg, parse_mode="HTML")
    
    # Prepare user info
    user_info = {
        "id": user_id,
        "username": username,
        "first_name": first_name
    }
    
    # Update the last command time for Trial users immediately
    if user_tier == "Trial":
        last_command_time[user_id] = current_time
    
    # Create a background task for the card check to avoid blocking
    async def background_check():
        try:
            # Run the asynchronous card check
            result = await check_card(card_details, user_info)
            
            # Deduct 1 credit if the response was successful and user doesn't have unlimited credits
            if result and not result.startswith("⚠️ <b>Missing card details!</b>") and not result.startswith("⚠️ <b>Error checking card:</b>"):
                # Only deduct credits if the user doesn't have unlimited
                if not is_unlimited:
                    # Deduct 1 credit in the background
                    update_user_credits(user_id, -1)
                    
                    # Get updated credits for the response
                    updated_credits = get_user_credits(user_id)
                    
                    # Add warning if credits are now 0
                    if updated_credits is not None and updated_credits <= 0:
                        # Add warning message at the end of the result
                        result = result + f"\n<a href='https://t.me/abtlnx'>⚠️</a> <b>𝙇𝙚𝙬𝙠𝙚𝙙𝙞𝙣𝙜:</b> <i>You have 0 credits left. Please recharge to continue using this service.</i>"
            
            # Edit the checking message with the result
            try:
                await checking_message.edit_text(result, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Error editing message: {str(e)}")
                # If editing fails, try sending a new message
                await update.message.reply_text(result, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error in background check: {e}")
            error_msg = f"⚠️ <b>Error:</b> <code>{str(e)}</code>"
            try:
                await checking_message.edit_text(error_msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Error editing error message: {str(e)}")
                # If editing fails, try sending a new message
                await update.message.reply_text(error_msg, parse_mode="HTML")
    
    # Schedule the background task without awaiting it
    asyncio.create_task(background_check())

if __name__ == "__main__":
    # For testing purposes
    test_card = "373910674051056|07|29|9134"
    test_user = {
        "id": 123456789,
        "username": "testuser",
        "first_name": "Test"
    }
    asyncio.run(check_card(test_card, test_user))
