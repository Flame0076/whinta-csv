import telebot
import csv
import re
import os
from flask import Flask
import threading

# --- ENVIRONMENT VARIABLES ---
TOKEN = os.environ.get("BOT_TOKEN") 
OWNER_ID = int(os.environ.get("OWNER_ID", "0")) 
# -----------------------------

bot = telebot.TeleBot(TOKEN)
allowed_users = {OWNER_ID}
user_data = {}

# Dummy Web Server (Render ko awake rakhne ke liye)
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is Running 24/7!"

def is_auth(message):
    return message.from_user.id in allowed_users

# --- SMART NUMBER FORMATTER ---
def format_full_number(raw_text):
    """
    Sirf digits nikalta hai. Agar number 10 digit ka hai (bina country code),
    toh 91 add karta hai. Aur last me '+' laga deta hai.
    """
    digits = re.sub(r'\D', '', str(raw_text))
    if not digits:
        return None
        
    # Agar sirf 10 digit ka number hai, toh India ka code (91) aage laga do
    if len(digits) == 10:
        digits = "91" + digits
        
    return f"+{digits}"

# --- START COMMAND ---
@bot.message_handler(commands=['start'])
def start_command(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    text = (
        "Welcome To Text TO CSV BOT\n"
        "Follow The Commands Below To Start\n"
        "/start - To Start The Bot\n"
        "/Txt_To_CSV - Convert TXT File TO CSV\n"
        "/CSV_To_TXT - Convert CSV File To TXT\n"
        "/reset - Reset Command For Stopping Ongoing Procces\n\n"
        "Created By @Flame9906"
    )
    bot.send_message(message.chat.id, text)

# --- RESET COMMAND ---
@bot.message_handler(commands=['reset'])
def reset_command(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    if message.chat.id in user_data:
        del user_data[message.chat.id]
    bot.send_message(message.chat.id, "Process stopped immediately. Memory Cleared! Use commands to start again.")

# --- OWNER ACCESS SYSTEM ---
@bot.message_handler(commands=['add_user'])
def add_user(message):
    if message.from_user.id == OWNER_ID:
        try:
            new_user = int(message.text.split()[1])
            allowed_users.add(new_user)
            bot.reply_to(message, f"Access Granted to User ID: {new_user}")
        except:
            bot.reply_to(message, "Send command like this: /add_user 123456789")


# ==========================================
#             TXT TO CSV FLOW
# ==========================================
@bot.message_handler(commands=['Txt_To_CSV'])
def txt_to_csv_start(message):
    if not is_auth(message):
        bot.reply_to(message, "You do not have access to this bot.")
        return
    bot.clear_step_handler_by_chat_id(message.chat.id)
    msg = bot.send_message(message.chat.id, "Send Your Txt Format File")
    bot.register_next_step_handler(msg, process_txt_file)

def process_txt_file(message):
    if message.text == '/reset': return reset_command(message)
    if not message.document:
        msg = bot.send_message(message.chat.id, "Please send a valid TXT file.")
        bot.register_next_step_handler(msg, process_txt_file)
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8-sig', errors='ignore')
        
        numbers = []
        for line in content.splitlines():
            for part in line.split(','):
                formatted_num = format_full_number(part)
                if formatted_num:
                    numbers.append(formatted_num)
        
        if not numbers:
            bot.send_message(message.chat.id, "No numbers found in the file.")
            return
            
        user_data[message.chat.id] = {'numbers': numbers}
        
        # YAHAN CONTACT NAME NAHI PUCHEGA. SEEDHA FILE KA NAAM PUCHEGA
        msg = bot.send_message(
            message.chat.id, 
            f"✅ {len(numbers)} Contacts Found!\n\nAb apni nai CSV file ka NAAM bhejein (Example: MyContacts):"
        )
        bot.register_next_step_handler(msg, ask_csv_filename)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"Error processing file: {e}")

def ask_csv_filename(message):
    if message.text == '/reset': return reset_command(message)
    
    if message.chat.id not in user_data:
        bot.send_message(message.chat.id, "Session expired due to inactivity. Please use /Txt_To_CSV again.")
        return

    file_name = message.text.strip()
    if file_name.lower().endswith('.csv'):
        file_name = file_name[:-4]
        
    # Invalid characters hatana taaki file error na de
    file_name = re.sub(r'[\\/*?:"<>|]', '_', file_name).strip()
    if not file_name:
        file_name = "contacts_list"
        
    generate_csv(message.chat.id, file_name=file_name)

def generate_csv(chat_id, file_name):
    data = user_data.get(chat_id)
    if not data or 'numbers' not in data: 
        bot.send_message(chat_id, "Process interrupted. Please start again with /Txt_To_CSV")
        return
        
    try:
        numbers = data['numbers']
        filename = f"{file_name}.csv"
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['first_name', 'phone'])
            
            for num in numbers:
                # FIRST NAME AUR PHONE, DONO ME SAME NUMBER DAALEGA (+918090707888)
                writer.writerow([num, num])
                
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption="Your CSV File Is Ready\n\nTo make another file, please use /Txt_To_CSV again.")
            
        os.remove(filename)
    except Exception as e:
        bot.send_message(chat_id, f"Failed to generate file: {e}")
    finally:
        if chat_id in user_data:
            del user_data[chat_id]


# ==========================================
#             CSV TO TXT FLOW
# ==========================================
@bot.message_handler(commands=['CSV_To_TXT'])
def csv_to_txt_start(message):
    if not is_auth(message):
        bot.reply_to(message, "You do not have access to this bot.")
        return
    bot.clear_step_handler_by_chat_id(message.chat.id)
    msg = bot.send_message(message.chat.id, "Send Me Your CSV File")
    bot.register_next_step_handler(msg, process_csv_file)

def process_csv_file(message):
    if message.text == '/reset': return reset_command(message)
    if not message.document:
        msg = bot.send_message(message.chat.id, "Please send a valid CSV file.")
        bot.register_next_step_handler(msg, process_csv_file)
        return
        
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        content = downloaded_file.decode('utf-8-sig', errors='ignore')
        
        reader = csv.reader(content.splitlines())
        next(reader, None) # Skip header
        
        numbers = []
        for row in reader:
            if not row:
                continue
            target_col = row[1] if len(row) > 1 else row[0]
            num = format_full_number(target_col)
            if num:
                numbers.append(num)
                    
        if not numbers:
            bot.send_message(message.chat.id, "No numbers found in the CSV.")
            return
            
        user_data[message.chat.id] = {'extracted_numbers': numbers}
        
        msg = bot.send_message(message.chat.id, "Send Me Name For Your Saved File (without .txt):")
        bot.register_next_step_handler(msg, ask_txt_filename)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"Error processing CSV: {e}")

def ask_txt_filename(message):
    if message.text == '/reset': return reset_command(message)
    
    if message.chat.id not in user_data:
        bot.send_message(message.chat.id, "Session expired due to inactivity. Please use /CSV_To_TXT again.")
        return
    
    file_name = message.text.strip()
    if file_name.lower().endswith('.txt'):
        file_name = file_name[:-4]
        
    file_name = re.sub(r'[\\/*?:"<>|]', '_', file_name).strip()
    if not file_name:
        file_name = "numbers"
        
    generate_txt(message.chat.id, file_name)

def generate_txt(chat_id, file_name):
    data = user_data.get(chat_id)
    if not data or 'extracted_numbers' not in data: 
        bot.send_message(chat_id, "Process interrupted. Please start again with /CSV_To_TXT")
        return
    
    try:
        numbers = data['extracted_numbers']
        filename = f"{file_name}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(numbers))
            
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption="Your TXT File Is Ready\n\nTo make another file, please use /CSV_To_TXT again.")
            
        os.remove(filename)
    except Exception as e:
        bot.send_message(chat_id, f"Failed to generate file: {e}")
    finally:
        if chat_id in user_data:
            del user_data[chat_id]

# ==========================================
#   GLOBAL HANDLERS (Guidance ke liye)
# ==========================================
@bot.message_handler(content_types=['document'])
def handle_unhandled_document(message):
    if is_auth(message):
        bot.send_message(message.chat.id, "Please select an option first:\n\n/Txt_To_CSV - Convert TXT File TO CSV\n/CSV_To_TXT - Convert CSV File To TXT")

@bot.message_handler(func=lambda message: True)
def handle_unhandled_text(message):
    if is_auth(message):
        bot.send_message(message.chat.id, "I didn't understand that. Please use commands to start a process:\n\n/Txt_To_CSV - TXT to CSV\n/CSV_To_TXT - CSV to TXT\n/reset - To reset ongoing process")


def run_bot():
    try:
        bot.remove_webhook()
    except Exception as e:
        print(f"Webhook remove error: {e}")
        
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
