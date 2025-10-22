import zipfile
import os
import re
import json
from datetime import datetime
from collections import defaultdict
from flask import Flask, request
from flask_cors import CORS

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def clean_whatsapp_chats(txt_path):
    print(txt_path)
    with open(txt_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    chat_data = defaultdict(list)
    pattern = re.compile(
        r'^(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2})\s?(am|pm)? - (.+)$',
        re.IGNORECASE
    )

    for line in lines:
        match = pattern.match(line.strip())
        if not match:
            continue

        date_str, time_str, meridian, message_body = match.groups()
        formats = ['%d/%m/%Y', '%d/%m/%y', '%m/%d/%Y', '%m/%d/%y', '%d-%m-%Y', '%d.%m.%Y']

        for fmt in formats:
            try:
                date_iso = datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
                break
            except ValueError:
                continue
        else:
            print(f"⚠️ Unknown date format: {date_str}")
            date_iso = date_str  # fallback

        timestamp = f"{time_str} {meridian.upper()}" if meridian else time_str

        if "joined using this group's invite link" in message_body:
            content_item = {"type": "joined", "message": message_body}
        elif "Messages and calls are end-to-end encrypted" in message_body or "created group" in message_body:
            content_item = {"type": "settings", "message": message_body}
        elif "added" in message_body:
            content_item = {"type": "added", "message": message_body}
        elif ": " in message_body:
            sender, message = message_body.split(": ", 1)
            content_item = {
                "type": "message",
                "sender": sender,
                "message": message,
                "timestamp": timestamp,
                "isCurrentUser": (sender.lower() == 'arshad ali' or sender.lower() == 'you')
            }
        else:
            continue

        chat_data[date_iso].append(content_item)

    final_output = [
        {"date": date, "content": chat_data[date]}
        for date in sorted(chat_data.keys())
    ]

    print(final_output)
    print("✅ WhatsApp chat parsed successfully")
    return final_output


@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['myFile']
    username = request.form.get('username')

    # Save ZIP file
    zip_file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(zip_file_path)

    # Extract ZIP file
    extract_to = UPLOAD_FOLDER
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

    print(f"📂 Files extracted to: {extract_to}")

    # Find the WhatsApp chat file automatically
    txt_file_path = None
    for f in os.listdir(extract_to):
        if f.lower().endswith(".txt"):
            txt_file_path = os.path.join(extract_to, f)
            break

    if not txt_file_path:
        return {"status": "error", "message": "No .txt file found in ZIP"}, 400

    # Parse the chat
    parsed_data = clean_whatsapp_chats(txt_file_path)

    # Delete Files
    os.remove(zip_file_path)
    os.remove(txt_file_path)

    return {
        "status": "success",
        "filename": file.filename,
        "user": username,
        "parsed_data": parsed_data
    }

if __name__ == '__main__':
    app.run(debug=True, port="6969")