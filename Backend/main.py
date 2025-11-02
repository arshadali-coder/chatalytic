import zipfile
import os
import re
import json
from datetime import datetime
from collections import defaultdict
from flask import Flask, request
import requests
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


@app.route('/ai', methods=['POST'])
def ai_proxy():
    """Proxy endpoint to call Hugging Face Inference API from the server side.
    Expects JSON: { message: string, chatSummary: string }
    Requires environment variable HF_API_KEY to be set on the server.
    """
    try:
        payload = request.get_json(force=True)
    except Exception:
        return {"error": "Invalid JSON payload"}, 400

    user_message = payload.get('message', '')
    chat_summary = payload.get('chatSummary', '')

    hf_key = os.environ.get('HF_API_KEY')
    if not hf_key:
        return {"error": "HF_API_KEY not configured on server"}, 500

    # Construct prompt for the model (keep it concise to avoid token limits)
    prompt = (
        "<s>[INST] You are a helpful WhatsApp chat analyzer assistant. Analyze the following chat data and answer the user's question.\n\n"
        f"Chat Data:\n{chat_summary}\n\n"
        f"User Question: {user_message}\n\n"
        "Provide a clear, concise, and helpful answer based on the chat data. [/INST]"
    )

    hf_url = 'https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2'
    headers = {
        'Authorization': f'Bearer {hf_key}',
        'Content-Type': 'application/json'
    }

    body = {
        'inputs': prompt,
        'parameters': {
            'max_new_tokens': 500,
            'temperature': 0.7,
            'top_p': 0.95,
            'return_full_text': False
        }
    }

    try:
        resp = requests.post(hf_url, headers=headers, json=body, timeout=60)
    except requests.exceptions.RequestException as e:
        return {"error": "Error contacting Hugging Face API", "detail": str(e)}, 502

    # Forward non-200 responses
    if not resp.ok:
        # Return HF error body to help debugging (status code preserved)
        return {"error": "Hugging Face API error", "status_code": resp.status_code, "detail": resp.text}, resp.status_code

    try:
        data = resp.json()
    except ValueError:
        return {"error": "Invalid JSON from Hugging Face", "detail": resp.text}, 502

    # Attempt to extract generated text from common response shapes
    generated = None
    if isinstance(data, list) and len(data) > 0:
        # Many HF Inference responses return a list with generated_text
        generated = data[0].get('generated_text') or data[0].get('generated_text')
    elif isinstance(data, dict) and 'generated_text' in data:
        generated = data.get('generated_text')
    else:
        # As a fallback, include full response
        generated = json.dumps(data)

    return {"generated_text": generated}


if __name__ == '__main__':
    app.run(debug=True, port="6969")
