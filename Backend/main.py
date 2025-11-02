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
    if 'myFile' not in request.files:
        return {"status": "error", "message": "No file uploaded"}, 400
    
    file = request.files['myFile']
    username = request.form.get('username')
    
    if file.filename == '':
        return {"status": "error", "message": "No file selected"}, 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    files_to_delete = [file_path]
    txt_file_path = None

    # Check if uploaded file is a ZIP or TXT
    if file.filename.lower().endswith('.zip'):
        # Handle ZIP file
        extract_to = UPLOAD_FOLDER
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            print(f"📂 Files extracted to: {extract_to}")
            
            # Find the WhatsApp chat file automatically
            for f in os.listdir(extract_to):
                if f.lower().endswith(".txt"):
                    txt_file_path = os.path.join(extract_to, f)
                    files_to_delete.append(txt_file_path)
                    break
            
            if not txt_file_path:
                # Cleanup
                for f in files_to_delete:
                    if os.path.exists(f):
                        os.remove(f)
                return {"status": "error", "message": "No .txt file found in ZIP"}, 400
        except zipfile.BadZipFile:
            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
            return {"status": "error", "message": "Invalid ZIP file"}, 400
    
    elif file.filename.lower().endswith('.txt'):
        # Handle direct TXT file upload
        txt_file_path = file_path
        print(f"📄 Direct TXT file uploaded: {txt_file_path}")
    
    else:
        # Unsupported file type
        if os.path.exists(file_path):
            os.remove(file_path)
        return {"status": "error", "message": "Unsupported file type. Please upload a .txt or .zip file"}, 400

    # Parse the chat
    try:
        parsed_data = clean_whatsapp_chats(txt_file_path)
    except Exception as e:
        # Cleanup on error
        for f in files_to_delete:
            if os.path.exists(f):
                os.remove(f)
        return {"status": "error", "message": f"Error parsing chat: {str(e)}"}, 500

    # Delete files after successful parsing
    for f in files_to_delete:
        if os.path.exists(f):
            os.remove(f)

    return {
        "status": "success",
        "filename": file.filename,
        "user": username,
        "parsed_data": parsed_data
    }


if __name__ == '__main__':
    app.run(debug=True, port="6969")