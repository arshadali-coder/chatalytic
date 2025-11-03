const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const fileName = document.getElementById('fileName');
const processBtn = document.getElementById('processBtn');
const loading = document.getElementById('loading');

let selectedFile = null;
let chatData = null;
let chatText = '';
let sessionId = null; // Store session ID from backend

// Backend API endpoints
const BACKEND_URL = 'http://127.0.0.1:6969/';
const UPLOAD_ENDPOINT = `${BACKEND_URL}/upload`;
const AI_ENDPOINT = `${BACKEND_URL}/ai`;

uploadArea.addEventListener('click', () => fileInput.click());

uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragging');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragging');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragging');
    const file = e.dataTransfer.files[0];
    handleFileSelect(file);
});

fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    handleFileSelect(file);
});

function handleFileSelect(file) {
    if (file && (file.name.endsWith('.zip') || file.name.endsWith('.txt'))) {
        selectedFile = file;
        const icon = file.name.endsWith('.zip') ? 'fa-file-archive' : 'fa-file-alt';
        fileName.innerHTML = `<i class="fas ${icon}" style="margin-right: 8px;"></i> ${file.name}`;
        fileName.style.display = 'block';
        processBtn.style.display = 'block';
        
        uploadArea.style.borderColor = '#667eea';
        uploadArea.style.background = 'rgba(102, 126, 234, 0.1)';
    } else {
        alert('Please select a valid ZIP or TXT file exported from WhatsApp');
        uploadArea.style.borderColor = '';
        uploadArea.style.background = '';
    }
}

// Auto-resize textarea
document.addEventListener('input', function(e) {
    if (e.target.classList.contains('chat-input')) {
        e.target.style.height = 'auto';
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
    }
});

// Send on Enter (Shift+Enter for new line)
document.addEventListener('keydown', function(e) {
    if (e.target.classList.contains('chat-input') && e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const isMobile = e.target.id === 'mobileUserInput';
        sendMessage(isMobile);
    }
});

function processFile() {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append("myFile", selectedFile);
    formData.append("username", "User"); // Add username if needed

    processBtn.style.display = 'none';
    loading.style.display = 'flex';

    setTimeout(() => {
        fetch(UPLOAD_ENDPOINT, {
            method: "POST",
            body: formData
        })
        .then(res => {
            if (!res.ok) {
                throw new Error(`Server returned ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            console.log("Full Server Response:", data);
            
            if (data.status === 'error') {
                throw new Error(data.message || 'Upload failed');
            }
            
            chatData = data.parsed_data;
            sessionId = data.session_id; // Store session ID
            
            console.log("✅ Chat Data Length:", chatData ? chatData.length : 0);
            console.log("✅ Session ID:", sessionId);
            console.log("✅ Session ID Type:", typeof sessionId);
            
            if (!sessionId) {
                console.error("❌ Session ID is missing from backend response!");
                alert("Warning: Session ID not received from server. AI features may not work.");
            }
            
            // Extract all chat text for AI context
            chatText = extractChatText(chatData);
            
            renderChat(chatData);
            loading.style.display = 'none';
            showAnalysisScreen();
        })
        .catch(error => {
            console.error("Error:", error);
            loading.style.display = 'none';
            processBtn.style.display = 'block';
            alert(`Error processing file: ${error.message}. Please make sure the file is a valid WhatsApp export and try again.`);
        });
    }, 100);
}

function extractChatText(data) {
    let text = '';
    for (const entry of data) {
        text += `Date: ${entry.date}\n`;
        for (const content of entry.content) {
            if (content.type === "message") {
                text += `${content.sender}: ${content.message}\n`;
            }
        }
    }
    return text;
}

function showWelcome() {
    document.getElementById('welcomeState').style.display = 'flex';
    document.getElementById('analysisScreen').style.display = 'none';
    document.getElementById('chatMessages').innerHTML = '';
    document.getElementById('aiMessages').innerHTML = `
        <div class="ai-welcome">
            <div class="ai-welcome-icon">
                <i class="fas fa-sparkles"></i>
            </div>
            <h3>Ready to Analyze!</h3>
            <p>I've loaded your chat data. Ask me anything about your conversations!</p>
            <div class="suggestion-chips">
                <div class="suggestion-chip" onclick="askSuggestion('Summarize this chat')">
                    <i class="fas fa-file-alt"></i> Summarize
                </div>
                <div class="suggestion-chip" onclick="askSuggestion('What are the most discussed topics?')">
                    <i class="fas fa-hashtag"></i> Topics
                </div>
                <div class="suggestion-chip" onclick="askSuggestion('Show conversation statistics')">
                    <i class="fas fa-chart-bar"></i> Stats
                </div>
            </div>
        </div>
    `;
    selectedFile = null; 
    fileName.style.display = 'none';
    processBtn.style.display = 'none';            
    fileInput.value = '';
    chatData = null;
    chatText = '';
    sessionId = null; // Clear session ID
    
    uploadArea.style.borderColor = '';
    uploadArea.style.background = '';
}

function showAnalysisScreen() {
    document.getElementById('welcomeState').style.display = 'none';
    document.getElementById('analysisScreen').style.display = 'block';
}

function renderChat(data) {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '';

    for (const entry of data) {
        const dateDiv = document.createElement('div');
        dateDiv.textContent = entry.date;
        dateDiv.className = 'date-header';
        chatMessages.appendChild(dateDiv);

        for (const content of entry.content) {
            if (content.type === "message") {
                const messageElement = document.createElement('div');
                messageElement.className = `chat-message ${content.isCurrentUser ? 'sent' : 'received'}`;
                
                messageElement.innerHTML = `
                    ${!content.isCurrentUser ? `<div class="sender-name">${content.sender}</div>` : ''}
                    <div class="message-bubble">
                        <div class="message-text">${content.message}</div>
                        <div class="message-time">${content.timestamp}</div>
                    </div>
                `;
                chatMessages.appendChild(messageElement);
            } else {
                const notificationElement = document.createElement('div');
                notificationElement.className = `system-notification notification-${content.type}`;
                notificationElement.innerHTML = `<div>${content.message}</div>`;
                chatMessages.appendChild(notificationElement);
            }
        }
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function askSuggestion(question) {
    const isMobile = window.innerWidth < 1024;
    const input = isMobile ? document.getElementById('mobileUserInput') : document.getElementById('desktopUserInput');
    input.value = question;
    sendMessage(isMobile);
}

async function sendMessage(isMobile) {
    const inputId = isMobile ? 'mobileUserInput' : 'desktopUserInput';
    const sendBtnId = isMobile ? 'mobileSendBtn' : 'desktopSendBtn';
    const messagesId = isMobile ? 'chatMessages' : 'aiMessages';
    
    const userInput = document.getElementById(inputId);
    const sendBtn = document.getElementById(sendBtnId);
    const messagesContainer = document.getElementById(messagesId);
    
    const message = userInput.value.trim();
    if (!message) return;

    // Check if session exists with detailed logging
    console.log("🔍 Checking session before sending message...");
    console.log("Session ID:", sessionId);
    console.log("Session ID Type:", typeof sessionId);
    console.log("Session ID is null/undefined:", sessionId == null);
    
    if (!sessionId || sessionId === 'undefined') {
        alert('No active session. Please upload a chat file first.');
        console.error("❌ Cannot send message: No valid session ID");
        return;
    }

    // Clear input and disable send button
    userInput.value = '';
    userInput.style.height = 'auto';
    sendBtn.disabled = true;

    // For mobile, add message to chat messages area
    if (isMobile) {
        // Add user message as system notification
        const userMsgElement = document.createElement('div');
        userMsgElement.className = 'system-notification';
        userMsgElement.style.background = 'rgba(102, 126, 234, 0.2)';
        userMsgElement.style.color = 'var(--text-primary)';
        userMsgElement.innerHTML = `<div><strong>You asked:</strong> ${message}</div>`;
        messagesContainer.appendChild(userMsgElement);
    } else {
        // Remove welcome message if exists
        const welcome = messagesContainer.querySelector('.ai-welcome');
        if (welcome) welcome.remove();

        // Add user message
        const userMsgElement = document.createElement('div');
        userMsgElement.className = 'ai-message user';
        userMsgElement.innerHTML = `<div class="ai-message-bubble">${message}</div>`;
        messagesContainer.appendChild(userMsgElement);
    }

    // Show typing indicator
    const typingIndicator = document.createElement('div');
    typingIndicator.className = isMobile ? 'system-notification' : 'typing-indicator';
    typingIndicator.style.display = isMobile ? 'block' : 'flex';
    if (isMobile) {
        typingIndicator.innerHTML = '<div><i class="fas fa-robot"></i> AI is thinking...</div>';
    } else {
        typingIndicator.innerHTML = `
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
    }
    messagesContainer.appendChild(typingIndicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    try {
        // Call Gemini API via backend
        const response = await callGeminiAPI(message);
        
        // Remove typing indicator
        typingIndicator.remove();

        // Add AI response
        const aiMsgElement = document.createElement('div');
        if (isMobile) {
            aiMsgElement.className = 'system-notification';
            aiMsgElement.style.background = 'rgba(240, 147, 251, 0.15)';
            aiMsgElement.style.maxWidth = '90%';
            aiMsgElement.innerHTML = `<div style="white-space: pre-wrap; text-align: left;">${formatMarkdown(response)}</div>`;
        } else {
            aiMsgElement.className = 'ai-message assistant';
            aiMsgElement.innerHTML = `<div class="ai-message-bubble">${formatMarkdown(response)}</div>`;
        }
        messagesContainer.appendChild(aiMsgElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

    } catch (error) {
        console.error('Error:', error);
        typingIndicator.remove();
        
        const errorMsgElement = document.createElement('div');
        if (isMobile) {
            errorMsgElement.className = 'system-notification';
            errorMsgElement.style.background = 'rgba(255, 82, 82, 0.15)';
            errorMsgElement.innerHTML = `<div>Error: ${error.message}</div>`;
        } else {
            errorMsgElement.className = 'ai-message assistant';
            errorMsgElement.innerHTML = `<div class="ai-message-bubble">Sorry, I encountered an error: ${error.message}</div>`;
        }
        messagesContainer.appendChild(errorMsgElement);
    }

    // Re-enable send button
    sendBtn.disabled = false;
}

async function callGeminiAPI(userMessage) {
    console.log("📤 Calling Gemini API...");
    console.log("Session ID being sent:", sessionId);
    console.log("User message:", userMessage);
    
    if (!sessionId || sessionId === 'undefined') {
        throw new Error('No active session. Please upload a chat file first.');
    }

    try {
        const requestBody = { 
            message: userMessage, 
            session_id: sessionId 
        };
        
        console.log("Request body:", JSON.stringify(requestBody));
        
        const response = await fetch(AI_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        console.log("Response status:", response.status);

        if (!response.ok) {
            if (response.status === 404) {
                // Session expired
                sessionId = null;
                throw new Error('Session expired. Please upload your chat file again.');
            }
            const errorText = await response.text();
            console.error("Error response:", errorText);
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        console.log("✅ AI Response received:", data);
        
        if (data.error) {
            throw new Error(data.error);
        }

        if (data.generated_text) {
            return data.generated_text;
        }

        // Fallback to local analysis if API returns no text
        return getLocalAnalysis(userMessage);

    } catch (error) {
        console.error('❌ Error contacting AI:', error);
        // Try local fallback
        if (chatData && chatData.length > 0) {
            console.log("Using local analysis fallback");
            return getLocalAnalysis(userMessage);
        }
        throw error;
    }
}

// Simple markdown formatter
function formatMarkdown(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

// Local fallback analysis when API is not available
function getLocalAnalysis(question) {
    const lowerQuestion = question.toLowerCase();
    
    if (!chatData || chatData.length === 0) {
        return "No chat data available to analyze.";
    }

    // Count messages
    let totalMessages = 0;
    let userMessages = {};
    let allMessages = [];
    
    for (const entry of chatData) {
        for (const content of entry.content) {
            if (content.type === "message") {
                totalMessages++;
                allMessages.push(content.message);
                if (!userMessages[content.sender]) {
                    userMessages[content.sender] = 0;
                }
                userMessages[content.sender]++;
            }
        }
    }

    // Summarize
    if (lowerQuestion.includes('summar')) {
        const users = Object.keys(userMessages);
        const dateRange = chatData.length > 0 ? 
            `from ${chatData[0].date} to ${chatData[chatData.length - 1].date}` : '';
        
        let summary = `📊 <strong>Chat Summary:</strong><br><br>`;
        summary += `📅 <strong>Period:</strong> ${dateRange}<br>`;
        summary += `💬 <strong>Total messages:</strong> ${totalMessages}<br>`;
        summary += `👥 <strong>Participants:</strong> ${users.join(', ')}<br><br>`;
        summary += `<strong>Message breakdown:</strong><br>`;
        for (const [user, count] of Object.entries(userMessages)) {
            const percentage = ((count / totalMessages) * 100).toFixed(1);
            summary += `• ${user}: ${count} messages (${percentage}%)<br>`;
        }
        
        return summary;
    }

    // Statistics
    if (lowerQuestion.includes('stat') || lowerQuestion.includes('number')) {
        let stats = `📈 <strong>Conversation Statistics:</strong><br><br>`;
        stats += `<strong>Total Messages:</strong> ${totalMessages}<br>`;
        stats += `<strong>Total Days:</strong> ${chatData.length}<br>`;
        stats += `<strong>Average Messages/Day:</strong> ${(totalMessages / chatData.length).toFixed(1)}<br><br>`;
        stats += `👥 <strong>Participants:</strong><br>`;
        
        const sorted = Object.entries(userMessages).sort((a, b) => b[1] - a[1]);
        for (const [user, count] of sorted) {
            stats += `• ${user}: ${count} messages<br>`;
        }
        
        return stats;
    }

    // Topics
    if (lowerQuestion.includes('topic') || lowerQuestion.includes('discuss')) {
        const commonWords = findCommonWords(allMessages);
        let topics = `🔍 <strong>Most Discussed Topics:</strong><br><br>`;
        topics += `Based on frequently used words:<br>`;
        commonWords.slice(0, 10).forEach((word, i) => {
            topics += `${i + 1}. "${word.word}" - used ${word.count} times<br>`;
        });
        
        return topics;
    }

    // Most active
    if (lowerQuestion.includes('active') || lowerQuestion.includes('most')) {
        const sorted = Object.entries(userMessages).sort((a, b) => b[1] - a[1]);
        let active = `⭐ <strong>Most Active Participants:</strong><br><br>`;
        sorted.forEach(([user, count], i) => {
            const percentage = ((count / totalMessages) * 100).toFixed(1);
            active += `${i + 1}. ${user}<br>   ${count} messages (${percentage}% of total)<br><br>`;
        });
        
        return active;
    }

    // Default response
    return `I can help you analyze this chat! Try asking me:<br><br>` +
           `• "Summarize this chat"<br>` +
           `• "Show conversation statistics"<br>` +
           `• "What are the most discussed topics?"<br>` +
           `• "Who is most active?"<br><br>` +
           `<em>Note: Using local analysis. For AI-powered insights, the backend will use Gemini API.</em>`;
}

function findCommonWords(messages) {
    const stopWords = ['the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'but', 'in', 'with', 'to', 'for', 'of', 'as', 'by', 'that', 'this', 'it', 'from', 'i', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her', 'us', 'them'];
    const wordCount = {};
    
    messages.forEach(msg => {
        const words = msg.toLowerCase()
            .replace(/[^\w\s]/g, '')
            .split(/\s+/)
            .filter(w => w.length > 3 && !stopWords.includes(w));
        
        words.forEach(word => {
            wordCount[word] = (wordCount[word] || 0) + 1;
        });
    });
    
    return Object.entries(wordCount)
        .map(([word, count]) => ({ word, count }))
        .sort((a, b) => b.count - a.count);
}