/**
 * PCAP Forensics - ChatGPT-Style Interface
 * =========================================
 * Modern conversational UI with markdown support and collapsible sidebar.
 */

// ============================================================================
// Configuration
// ============================================================================

// Configure marked for safe markdown rendering
marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    mangle: false,
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return hljs.highlight(code, { language: lang }).value;
            } catch (e) {}
        }
        return hljs.highlightAuto(code).value;
    }
});

// ============================================================================
// Application State
// ============================================================================

const state = {
    sessionId: null,
    eventSource: null,
    isConnected: false,
    mode: 'co-pilot',
    currentSources: [],
    currentMessageId: null,
    isThinking: false,
    sidebarOpen: true,
    availableModels: [],
    currentModel: '',
    currentTitle: null
};

// ============================================================================
// DOM Elements
// ============================================================================

const elements = {
    // Header
    sidebarToggle: document.getElementById('sidebarToggle'),
    sessionBadge: document.getElementById('sessionBadge'),
    contextMeter: document.getElementById('contextMeter'),
    contextFill: document.getElementById('contextFill'),
    contextValue: document.getElementById('contextValue'),
    modelSelector: document.getElementById('modelSelector'),
    modelBtn: document.getElementById('modelBtn'),
    modelDropdown: document.getElementById('modelDropdown'),
    currentModelName: document.getElementById('currentModelName'),

    // Layout
    mainContent: document.getElementById('mainContent'),
    sidebar: document.getElementById('sidebar'),

    // Welcome Screen
    welcomeScreen: document.getElementById('welcomeScreen'),
    uploadZone: document.getElementById('uploadZone'),
    fileInput: document.getElementById('fileInput'),
    uploadProgress: document.getElementById('uploadProgress'),

    // Chat
    chatMessages: document.getElementById('chatMessages'),
    thinkingIndicator: document.getElementById('thinkingIndicator'),
    thinkingText: document.getElementById('thinkingText'),

    // Sidebars
    newChatBtn: document.getElementById('newChatBtn'),
    casesList: document.getElementById('casesList'),

    // Input
    inputArea: document.getElementById('inputArea'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    autonomousBtn: document.getElementById('autonomousBtn'),

    // Modal
    reportModal: document.getElementById('reportModal'),
    reportContent: document.getElementById('reportContent'),
    closeReport: document.getElementById('closeReport'),
    copyReport: document.getElementById('copyReport'),
    downloadReport: document.getElementById('downloadReport')
};

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initNewChatButton();
    initModelSelector();
    initUploadZone();
    initInputHandlers();
    initModalHandlers();
    loadCases();
    loadModels();
});

// ============================================================================
// New Chat Button
// ============================================================================

function initNewChatButton() {
    elements.newChatBtn.addEventListener('click', startNewChat);
}

function startNewChat() {
    // Close any existing event source
    if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
    }
    
    // Reset state
    state.sessionId = null;
    state.isConnected = false;
    state.currentSources = [];
    state.currentTitle = null;
    
    // Reset UI
    elements.welcomeScreen.classList.remove('hidden');
    elements.chatMessages.classList.remove('visible');
    elements.chatMessages.innerHTML = '';
    elements.messageInput.disabled = true;
    elements.sendBtn.disabled = true;
    elements.messageInput.value = '';
    elements.uploadZone.classList.remove('uploading');
    
    // Reset header
    elements.sessionBadge.innerHTML = '<span class="badge-label">No Active Session</span>';
    elements.sessionBadge.classList.remove('active');
    elements.contextFill.style.width = '0%';
    elements.contextValue.textContent = '0%';
    
    // Deselect any active case
    document.querySelectorAll('.case-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Reload cases to get updated list
    loadCases();
}

// ============================================================================
// Sidebar
// ============================================================================

function initSidebar() {
    elements.sidebarToggle.addEventListener('click', toggleSidebar);
    
    // Check localStorage for saved preference
    const savedState = localStorage.getItem('sidebarOpen');
    if (savedState === 'false') {
        state.sidebarOpen = false;
        elements.sidebar.classList.add('collapsed');
    }
}

function toggleSidebar() {
    state.sidebarOpen = !state.sidebarOpen;
    elements.sidebar.classList.toggle('collapsed', !state.sidebarOpen);
    localStorage.setItem('sidebarOpen', state.sidebarOpen);
}

// ============================================================================
// Model Selector
// ============================================================================

function initModelSelector() {
    // Toggle dropdown
    elements.modelBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        elements.modelSelector.classList.toggle('open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', () => {
        elements.modelSelector.classList.remove('open');
    });

    // Prevent dropdown from closing when clicking inside
    elements.modelDropdown.addEventListener('click', (e) => {
        e.stopPropagation();
    });
}

async function loadModels() {
    try {
        const response = await fetch('/api/models');
        const data = await response.json();

        state.availableModels = data.models || [];
        state.currentModel = data.current || '';

        elements.currentModelName.textContent = state.currentModel;
        renderModelDropdown();
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

function renderModelDropdown() {
    elements.modelDropdown.innerHTML = state.availableModels.map(model => `
        <div class="model-option ${model === state.currentModel ? 'active' : ''}" data-model="${model}">
            <span class="model-option-check">✓</span>
            <span>${model}</span>
        </div>
    `).join('');

    // Add click handlers
    elements.modelDropdown.querySelectorAll('.model-option').forEach(option => {
        option.addEventListener('click', () => selectModel(option.dataset.model));
    });
}

async function selectModel(modelName) {
    if (modelName === state.currentModel) {
        elements.modelSelector.classList.remove('open');
        return;
    }

    // Update UI immediately
    state.currentModel = modelName;
    elements.currentModelName.textContent = modelName;
    renderModelDropdown();
    elements.modelSelector.classList.remove('open');

    // If we have an active session, we could notify the backend
    // For now, model switch requires a page reload or new session
    showSystemMessage(`Switched to model: ${modelName}. New sessions will use this model.`, 'info');
}

// ============================================================================
// Upload Handling
// ============================================================================

function initUploadZone() {
    const zone = elements.uploadZone;
    const input = elements.fileInput;

    zone.addEventListener('click', () => input.click());

    input.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });
}

async function uploadFile(file) {
    const validExt = ['pcap', 'pcapng', 'cap'];
    const ext = file.name.split('.').pop().toLowerCase();

    if (!validExt.includes(ext)) {
        showSystemMessage('Invalid file type. Please upload a PCAP file.', 'error');
        return;
    }

    const modeRadio = document.querySelector('input[name="mode"]:checked');
    state.mode = modeRadio ? modeRadio.value : 'co-pilot';

    elements.uploadZone.classList.add('uploading');

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('mode', state.mode);

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Upload failed');
        }

        state.sessionId = data.session_id;
        startSession(data.session_info);

    } catch (error) {
        showSystemMessage(error.message, 'error');
        elements.uploadZone.classList.remove('uploading');
    }
}

// ============================================================================
// Session Management
// ============================================================================

function startSession(sessionInfo) {
    elements.welcomeScreen.classList.add('hidden');
    elements.chatMessages.classList.add('visible');
    elements.messageInput.disabled = false;
    elements.sendBtn.disabled = false;

    updateSessionBadge(sessionInfo.case_id);
    updateContextMeter(sessionInfo.context_usage);

    connectEventStream();

    showSystemMessage('Ready to analyze! Ask me anything about this PCAP file.');

    // Reload cases to show new case and mark as active
    loadCases();

    if (state.mode === 'autonomous') {
        startAutonomousAnalysis();
    }
}

function connectEventStream() {
    if (state.eventSource) {
        state.eventSource.close();
    }

    state.eventSource = new EventSource(`/api/sessions/${state.sessionId}/stream`);

    state.eventSource.onopen = () => {
        state.isConnected = true;
    };

    state.eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
    };

    state.eventSource.onerror = (error) => {
        console.error('SSE Error:', error);
        state.isConnected = false;
    };
}

function handleServerEvent(event) {
    switch (event.type) {
        case 'user_message':
            // Already added by UI
            break;

        case 'thinking':
            if (event.data.status === 'start') {
                showThinking(true, 'Thinking...');
                state.currentSources = [];
            } else {
                showThinking(false);
            }
            break;

        case 'searching':
            showThinking(true, event.data.message || 'Analyzing network traffic...');
            break;

        case 'tool_start':
            showThinking(true, `Analyzing: ${event.data.tool_name}...`);
            break;

        case 'tool_result':
            // Collect sources for the collapsible card
            state.currentSources.push({
                name: event.data.tool_name || 'analysis',
                summary: truncateText(event.data.output, 80)
            });
            break;

        case 'agent_thought':
            // Optionally show thought in sources
            break;

        case 'agent_analysis':
            showThinking(false);
            addAgentMessage(event.data.content, state.currentSources);
            state.currentSources = [];
            break;

        case 'finding':
            // Findings are now included in the response, no separate panel
            break;

        case 'context_update':
            updateContextMeter(event.data);
            break;

        case 'title_update':
            updateCaseTitle(event.data.case_id, event.data.title);
            break;

        case 'final_report':
            showThinking(false);
            showFinalReport(event.data.content);
            break;

        case 'system':
            showSystemMessage(event.data.message, event.data.style);
            break;

        case 'error':
            showThinking(false);
            showSystemMessage(event.data.message, 'error');
            break;

        case 'keepalive':
            break;
    }
}

// ============================================================================
// Input Handling
// ============================================================================

function initInputHandlers() {
    elements.sendBtn.addEventListener('click', sendMessage);

    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    elements.messageInput.addEventListener('input', () => {
        elements.messageInput.style.height = 'auto';
        elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 200) + 'px';
    });

    elements.autonomousBtn.addEventListener('click', startAutonomousAnalysis);
}

async function sendMessage() {
    const message = elements.messageInput.value.trim();
    if (!message || !state.sessionId) return;

    addUserMessage(message);
    elements.messageInput.value = '';
    elements.messageInput.style.height = 'auto';

    try {
        const response = await fetch(`/api/sessions/${state.sessionId}/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to send message');
        }
    } catch (error) {
        showSystemMessage(error.message, 'error');
    }
}

async function startAutonomousAnalysis() {
    if (!state.sessionId) return;

    try {
        const response = await fetch(`/api/sessions/${state.sessionId}/autonomous`, {
            method: 'POST'
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to start analysis');
        }
    } catch (error) {
        showSystemMessage(error.message, 'error');
    }
}

// ============================================================================
// Message Rendering
// ============================================================================

function addUserMessage(content) {
    const container = elements.chatMessages;
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const message = document.createElement('div');
    message.className = 'message user';
    message.innerHTML = `
        <div class="message-avatar">👤</div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-role">You</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-body">${escapeHtml(content)}</div>
        </div>
    `;

    container.appendChild(message);
    scrollToBottom();
}

function addAgentMessage(content, sources = []) {
    const container = elements.chatMessages;
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const message = document.createElement('div');
    message.className = 'message agent';

    // Build sources card HTML if there are sources
    let sourcesHtml = '';
    if (sources.length > 0) {
        const sourceItems = sources.map(s => `
            <div class="source-item">
                <span class="source-name">${escapeHtml(s.name)}</span>
                <span class="source-summary">${escapeHtml(s.summary)}</span>
            </div>
        `).join('');

        sourcesHtml = `
            <div class="sources-card complete" onclick="toggleSourcesCard(this)">
                <div class="sources-header">
                    <span class="sources-icon">🔍</span>
                    <span class="sources-label">Analyzed ${sources.length} source${sources.length > 1 ? 's' : ''}</span>
                    <span class="sources-chevron">▼</span>
                </div>
                <div class="sources-list">${sourceItems}</div>
            </div>
        `;
    }

    // Render markdown content
    const renderedContent = renderMarkdown(content);

    message.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-role">Agent</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-body">
                ${sourcesHtml}
                <div class="markdown-body">${renderedContent}</div>
            </div>
        </div>
    `;

    container.appendChild(message);
    scrollToBottom();

    // Apply syntax highlighting to code blocks
    message.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
}

function showSystemMessage(content, style = 'info') {
    const container = elements.chatMessages;
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const icons = {
        info: '💡',
        success: '✅',
        warning: '⚠️',
        error: '❌'
    };

    const message = document.createElement('div');
    message.className = 'message system';
    message.innerHTML = `
        <div class="message-avatar">${icons[style] || '💡'}</div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-role">System</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-body">${escapeHtml(content)}</div>
        </div>
    `;

    container.appendChild(message);
    scrollToBottom();
}

// Toggle sources card expansion
window.toggleSourcesCard = function(card) {
    card.classList.toggle('expanded');
};

// ============================================================================
// Markdown Rendering
// ============================================================================

function renderMarkdown(content) {
    if (!content) return '';
    
    // Parse markdown
    let html = marked.parse(content);
    
    // Apply network syntax highlighting
    html = highlightNetworkData(html);
    
    return html;
}

function highlightNetworkData(text) {
    // IP addresses
    text = text.replace(/\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b/g, '<span class="hl-ip">$1</span>');

    // Ports (after colon)
    text = text.replace(/:(\d{2,5})\b/g, ':<span class="hl-port">$1</span>');

    // Protocols
    const protocols = ['TCP', 'UDP', 'HTTP', 'HTTPS', 'FTP', 'DNS', 'TLS', 'SSL', 'SMTP', 'SSH', 'ICMP'];
    protocols.forEach(proto => {
        const regex = new RegExp(`\\b(${proto})\\b`, 'gi');
        text = text.replace(regex, '<span class="hl-protocol">$1</span>');
    });

    return text;
}

// ============================================================================
// Header Updates
// ============================================================================

function updateSessionBadge(caseId) {
    const badge = elements.sessionBadge;
    badge.innerHTML = `<span class="badge-label">${caseId}</span>`;
    badge.classList.add('active');
}

function updateContextMeter(usage) {
    if (!usage || !usage.used_tokens || !usage.max_tokens) return;

    const percent = Math.round((usage.used_tokens / usage.max_tokens) * 100);
    elements.contextFill.style.width = `${percent}%`;
    elements.contextValue.textContent = `${percent}%`;

    elements.contextFill.classList.remove('warning', 'danger');
    if (percent > 80) {
        elements.contextFill.classList.add('danger');
    } else if (percent > 60) {
        elements.contextFill.classList.add('warning');
    }
}

// ============================================================================
// Cases Panel
// ============================================================================

async function loadCases() {
    try {
        const response = await fetch('/api/cases');
        const data = await response.json();

        if (data.cases && data.cases.length > 0) {
            renderCases(data.cases);
        }
    } catch (error) {
        console.error('Failed to load cases:', error);
    }
}

function renderCases(cases) {
    const container = elements.casesList;
    container.innerHTML = '';

    // Sort by start_time descending (newest first)
    cases.sort((a, b) => new Date(b.start_time) - new Date(a.start_time));

    cases.forEach(caseInfo => {
        const item = document.createElement('div');
        item.className = 'case-item';
        item.dataset.caseId = caseInfo.case_id;

        const filename = caseInfo.pcap_file.split(/[\\/]/).pop();
        const title = caseInfo.title || filename;
        const isActive = state.sessionId === caseInfo.case_id;
        
        if (isActive) {
            item.classList.add('active');
        }

        item.innerHTML = `
            <div class="case-title">${escapeHtml(title)}</div>
            <div class="case-meta">
                <span class="case-file">${escapeHtml(filename)}</span>
            </div>
        `;

        item.addEventListener('click', () => resumeCase(caseInfo.case_id));
        container.appendChild(item);
    });
}

function updateCaseTitle(caseId, title) {
    state.currentTitle = title;
    
    // Update the case item in the sidebar
    const caseItem = document.querySelector(`.case-item[data-case-id="${caseId}"]`);
    if (caseItem) {
        const titleEl = caseItem.querySelector('.case-title');
        if (titleEl) {
            titleEl.textContent = title;
        }
    }
    
    // Reload cases to ensure ordering is correct
    loadCases();
}

async function resumeCase(caseId) {
    try {
        const response = await fetch(`/api/cases/${caseId}/resume`, {
            method: 'POST'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to resume case');
        }

        state.sessionId = data.session_id;
        startSession(data.session_info);

        document.querySelectorAll('.case-item').forEach(item => {
            item.classList.toggle('active', item.dataset.caseId === caseId);
        });

    } catch (error) {
        showSystemMessage(error.message, 'error');
    }
}

// ============================================================================
// Final Report Modal
// ============================================================================

function initModalHandlers() {
    elements.closeReport.addEventListener('click', () => {
        elements.reportModal.classList.remove('visible');
    });

    elements.reportModal.querySelector('.modal-backdrop').addEventListener('click', () => {
        elements.reportModal.classList.remove('visible');
    });

    elements.copyReport.addEventListener('click', () => {
        const content = elements.reportContent.innerText;
        navigator.clipboard.writeText(content);
        elements.copyReport.textContent = '✓ Copied!';
        setTimeout(() => {
            elements.copyReport.textContent = '📋 Copy Report';
        }, 2000);
    });

    elements.downloadReport.addEventListener('click', () => {
        const content = elements.reportContent.innerText;
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `forensic_report_${state.sessionId}.md`;
        a.click();
        URL.revokeObjectURL(url);
    });
}

function showFinalReport(content) {
    let reportHtml;
    if (typeof content === 'object' && content !== null) {
        reportHtml = marked.parse('```json\n' + JSON.stringify(content, null, 2) + '\n```');
    } else {
        reportHtml = renderMarkdown(String(content || 'No report content available.'));
    }

    elements.reportContent.innerHTML = reportHtml;
    elements.reportModal.classList.add('visible');

    // Also add as agent message
    addAgentMessage(String(content), [{ name: 'Final Report', summary: 'Investigation complete' }]);
}

// ============================================================================
// UI Helpers
// ============================================================================

function showThinking(show, text = 'Thinking...') {
    state.isThinking = show;
    elements.thinkingIndicator.classList.toggle('visible', show);
    elements.thinkingText.textContent = text;
    if (show) scrollToBottom();
}

function scrollToBottom() {
    const container = elements.chatMessages;
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}
