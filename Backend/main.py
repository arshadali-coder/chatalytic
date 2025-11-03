import zipfile
import os
import re
import json
import uuid
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, request, jsonify
import requests
from flask_cors import CORS

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# In-memory session store (use Redis or database in production)
# Structure: { session_id: { 'history': [...], 'chat_summary': '...', 'last_active': datetime } }
sessions = {}
SESSION_TIMEOUT = timedelta(hours=2)  # Sessions expire after 2 hours of inactivity


def clean_expired_sessions():
    """Remove expired sessions to prevent memory leaks"""
    now = datetime.now()
    expired = [sid for sid, data in sessions.items() 
               if now - data['last_active'] > SESSION_TIMEOUT]
    for sid in expired:
        del sessions[sid]
        print(f"🗑️ Cleaned up expired session: {sid}")


def clean_whatsapp_chats(txt_path):
    print(f"📄 Processing file: {txt_path}")
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
                "isCurrentUser": (sender.lower() == 'you')
            }
        else:
            continue

        chat_data[date_iso].append(content_item)

    final_output = [
        {"date": date, "content": chat_data[date]}
        for date in sorted(chat_data.keys())
    ]

    print(f"✅ WhatsApp chat parsed successfully - {len(final_output)} days of messages")
    return final_output


@app.route('/upload', methods=['POST'])
def upload_file():
    print("\n" + "="*50)
    print("📤 NEW UPLOAD REQUEST")
    print("="*50)
    
    if 'myFile' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['myFile']
    username = request.form.get('username', 'User')
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)
    
    print(f"📁 File saved: {file.filename}")
    
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
                return jsonify({"status": "error", "message": "No .txt file found in ZIP"}), 400
        except zipfile.BadZipFile:
            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"status": "error", "message": "Invalid ZIP file"}), 400
    
    elif file.filename.lower().endswith('.txt'):
        # Handle direct TXT file upload
        txt_file_path = file_path
        print(f"📄 Direct TXT file uploaded: {txt_file_path}")
    
    else:
        # Unsupported file type
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"status": "error", "message": "Unsupported file type. Please upload a .txt or .zip file"}), 400

    # Parse the chat
    try:
        parsed_data = clean_whatsapp_chats(txt_file_path)
    except Exception as e:
        print(f"❌ Error parsing chat: {str(e)}")
        # Cleanup on error
        for f in files_to_delete:
            if os.path.exists(f):
                os.remove(f)
        return jsonify({"status": "error", "message": f"Error parsing chat: {str(e)}"}), 500

    # Delete files after successful parsing
    for f in files_to_delete:
        if os.path.exists(f):
            os.remove(f)

    # Create a new session for this upload
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        'history': [],
        'chat_summary': json.dumps(parsed_data),
        'last_active': datetime.now(),
        'username': username
    }
    
    # Clean up old sessions
    clean_expired_sessions()
    
    print(f"✨ Created new session: {session_id}")
    print(f"👤 Username: {username}")
    print(f"💬 Messages parsed: {sum(len([c for c in day['content'] if c['type'] == 'message']) for day in parsed_data)}")
    print(f"🗄️ Active sessions: {len(sessions)}")
    print("="*50 + "\n")

    response_data = {
        "status": "success",
        "filename": file.filename,
        "user": username,
        "parsed_data": parsed_data,
        "session_id": session_id
    }
    
    print(f"📦 Response keys: {list(response_data.keys())}")
    print(f"🔑 Session ID in response: {response_data['session_id']}")
    
    return jsonify(response_data), 200


@app.route('/ai', methods=['POST'])
def ai_proxy():
    """Proxy endpoint to call Gemini API with session management.
    Expects JSON: { 
        message: string,
        session_id: string (required)
    }
    """
    print("\n" + "="*50)
    print("🤖 AI REQUEST")
    print("="*50)
    
    try:
        payload = request.get_json(force=True)
        print(f"📥 Received payload: {payload}")
    except Exception as e:
        print(f"❌ Invalid JSON: {str(e)}")
        return jsonify({"error": "Invalid JSON payload"}), 400

    user_message = payload.get('message', '')
    session_id = payload.get('session_id', '')

    print(f"💬 Message: {user_message[:50]}...")
    print(f"🔑 Session ID: {session_id}")

    if not session_id:
        print("❌ No session_id provided")
        return jsonify({"error": "session_id is required"}), 400

    # Check if session exists
    if session_id not in sessions:
        print(f"❌ Session not found: {session_id}")
        print(f"Available sessions: {list(sessions.keys())}")
        return jsonify({"error": "Invalid or expired session. Please upload your chat file again."}), 404

    # Get session data
    session = sessions[session_id]
    chat_summary = session['chat_summary']
    conversation_history = session['history']
    
    # Update last active time
    session['last_active'] = datetime.now()
    
    print(f"✅ Session found")
    print(f"📚 Conversation history: {len(conversation_history)} messages")

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("❌ No GEMINI_API_KEY configured")
        return jsonify({"error": "GEMINI_API_KEY not configured on server"}), 500

    # Gemini API endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {
        'Content-Type': 'application/json'
    }

    # Build the contents array for Gemini
    contents = []
    
    # System prompt for the first message
    system_prompt = (
        "You are a helpful WhatsApp chat analyzer assistant. "
        "You have access to the following chat data and should use it to answer questions accurately.\n\n"
        f"Chat Data:\n{chat_summary}\n\n"
        "Provide clear, concise, and helpful answers based on the chat data. "
        "Format your answers in markdown and keep them under 500 words."
    )
    
    # If this is the first message in the conversation
    if not conversation_history:
        contents.append({
            "role": "user",
            "parts": [{"text": f"{system_prompt}\n\nUser Question: {user_message}"}]
        })
    else:
        # Add conversation history
        for msg in conversation_history:
            role = msg.get('role', 'user')
            text = msg.get('text', '')
            
            if role in ['user', 'model']:
                contents.append({
                    "role": role,
                    "parts": [{"text": text}]
                })
        
        # Add the new user message
        contents.append({
            "role": "user",
            "parts": [{"text": user_message}]
        })
    
    print(f"📤 Calling Gemini API - Message #{len(conversation_history)//2 + 1}")
    
    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 1024,
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=60)
    except requests.exceptions.RequestException as e:
        print(f"❌ Error contacting Gemini: {str(e)}")
        return jsonify({"error": "Error contacting Gemini API", "detail": str(e)}), 502

    if not resp.ok:
        print(f"❌ Gemini API error: {resp.status_code}")
        print(f"Response: {resp.text}")
        return jsonify({
            "error": "Gemini API error",
            "status_code": resp.status_code,
            "detail": resp.text
        }), resp.status_code

    try:
        data = resp.json()
        if 'candidates' in data and len(data['candidates']) > 0:
            generated = data['candidates'][0]['content']['parts'][0]['text']
        else:
            generated = "Sorry, I couldn't generate a response at this time."
    except (ValueError, KeyError) as e:
        print(f"❌ Invalid Gemini response: {str(e)}")
        return jsonify({"error": "Invalid response from Gemini", "detail": str(e)}), 502

    # Update session history
    session['history'].append({'role': 'user', 'text': user_message})
    session['history'].append({'role': 'model', 'text': generated})
    
    print(f"✅ Response generated ({len(generated)} chars)")
    print("="*50 + "\n")

    return jsonify({"generated_text": generated}), 200


@app.route('/session/clear', methods=['POST'])
def clear_session():
    """Clear conversation history for a session"""
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    session_id = payload.get('session_id', '')
    
    if not session_id or session_id not in sessions:
        return jsonify({"error": "Invalid session"}), 404
    
    # Clear history but keep the session
    sessions[session_id]['history'] = []
    sessions[session_id]['last_active'] = datetime.now()
    
    print(f"🧹 Cleared history for session: {session_id[:8]}...")
    
    return jsonify({"status": "success", "message": "Conversation history cleared"}), 200


@app.route('/session/delete', methods=['POST'])
def delete_session():
    """Delete a session completely"""
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON payload"}), 400
    
    session_id = payload.get('session_id', '')
    
    if session_id in sessions:
        del sessions[session_id]
        print(f"🗑️ Deleted session: {session_id[:8]}...")
        return jsonify({"status": "success", "message": "Session deleted"}), 200
    
    return jsonify({"error": "Session not found"}), 404


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "active_sessions": len(sessions),
        "timestamp": datetime.now().isoformat()
    }), 200


if __name__ == '__main__':
    print("🚀 Starting Flask server...")
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
    app.run(debug=True, port=6969, host='0.0.0.0')