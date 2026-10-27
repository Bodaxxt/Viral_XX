/**
 * Viral-X Production AI Chat Client v3.0
 *
 * Features:
 * - Real server API integration (POST /api/chat)
 * - Multi-tenant workspace switching with session isolation
 * - Streaming-state UI with tool activity display
 * - Full draft order management with confirm/cancel
 * - WhatsApp handoff with encoded context
 * - Arabic/RTL detection and layout switching
 * - Retry logic, error boundaries, and accessibility
 * - Auto-sizing textarea, char counter, keyboard shortcuts
 */

(function () {
  'use strict';

  // ── Configuration ────────────────────────────────────────────────────────

  const TENANT_CONFIGS = {
    'al-noor-jewelry': {
      name: 'Al Noor High Jewelry',
      location: 'Place Vendôme, Doha',
      icon: '💎',
      status: 'AI Agent Online · Place Vendôme, Doha',
      color: '#D4AF37',
      prompts: [
        { icon: '💎', label: 'Check emerald collar availability', text: 'Check Doha boutique availability and verified price for the emerald collar necklace' },
        { icon: '💍', label: 'Solitaire ring specifications', text: 'What are the GIA certificate and carat specifications of the Solitaire Cushion Diamond Ring?' },
        { icon: '📦', label: 'Insured GCC delivery options', text: 'What are your delivery and private salon viewing options across the GCC?' },
        { icon: '👤', label: 'Request human jewelry concierge', text: 'I need to speak directly with an Al Noor jewelry specialist on WhatsApp.' }
      ],
      greeting: 'Welcome to **Al Noor High Jewelry** — your verified AI concierge for certified diamonds, precious gems, and bespoke luxury pieces from our Doha flagship. I can check live inventory, verify prices, prepare a reservation draft, or connect you directly with our specialist team.\n\nكيف يمكنني مساعدتك اليوم؟'
    },
    'saffron-table': {
      name: 'The Saffron Table',
      location: 'Zamalek, Cairo',
      icon: '🍽️',
      status: 'Reservation Matrix Active · Zamalek, Cairo',
      color: '#F59E0B',
      prompts: [
        { icon: '🍽️', label: 'Reserve Chef Tasting Menu for 2', text: 'What tasting menus are available for dinner tomorrow evening for 2 guests?' },
        { icon: '👥', label: 'Change party size to 3 guests', text: 'Actually, please make it 3 guests instead' },
        { icon: '🥗', label: 'Gluten & allergy policy', text: 'Can you accommodate gluten allergies and shellfish restrictions for our table?' },
        { icon: '👤', label: 'Speak with Maître d on WhatsApp', text: 'I would like to speak directly with the Maître d at The Saffron Table on WhatsApp.' }
      ],
      greeting: 'مرحباً بكم في **ذا زعفران تيبل** — تجربة المطبخ الشرقي الفاخر في قلب الزمالك. يمكنني مساعدتك في الاطلاع على قوائمنا، التحقق من مواعيد الحجز المتاحة، وتجهيز مسودة الطاولة.\n\nWelcome — I can check tonight\'s availability, prepare a table hold draft, or connect you with our team.'
    },
    'vitalis-health': {
      name: 'Vitalis Clinical Health',
      location: 'New Cairo Medical Park',
      icon: '🩺',
      status: 'EHR Scheduling Online · New Cairo Suite 402',
      color: '#10B981',
      prompts: [
        { icon: '🩺', label: 'Executive longevity screening info', text: 'What is included in the Executive Longevity & Metabolic Screening package in New Cairo?' },
        { icon: '🩸', label: 'Fasting and preparation requirements', text: 'What fasting and preparation is required before the executive screening blood panel?' },
        { icon: '📅', label: 'Book morning appointment slot', text: 'Can I book the executive longevity screening for tomorrow morning at New Cairo?' },
        { icon: '👤', label: 'Connect with clinical coordinator', text: 'I want to speak with a Vitalis patient coordinator via WhatsApp about my appointment.' }
      ],
      greeting: 'Welcome to **Vitalis Longevity & Clinical Center** — New Cairo Medical Park. I provide administrative information about our screening packages, appointment availability, fees, and preparation guidelines. For clinical questions, I will connect you with our medical coordinator.\n\n⚕️ Note: This assistant handles scheduling only and does not provide clinical diagnoses.'
    }
  };

  const TOOL_ICONS = {
    search_products: '🔍',
    get_product_details: '📋',
    check_inventory: '📦',
    calculate_price: '🧮',
    search_business_knowledge: '📚',
    check_booking_availability: '📅',
    create_order_draft: '📝',
    update_order_draft: '✏️',
    get_order_draft: '🗂️',
    request_human_handoff: '👤'
  };

  // ── DOM References ───────────────────────────────────────────────────────

  const els = {
    messages: document.getElementById('chatMessages'),
    textarea: document.getElementById('chatTextarea'),
    sendBtn: document.getElementById('chatSendBtn'),
    charCounter: document.getElementById('charCounter'),
    quickPrompts: document.getElementById('quickPromptsList'),
    workspaceTabs: document.getElementById('workspaceTabs'),
    headerAvatar: document.getElementById('chatHeaderAvatar'),
    headerName: document.getElementById('chatHeaderName'),
    headerStatus: document.getElementById('chatHeaderStatus'),
    modeLabel: document.getElementById('modeLabel'),
    modeIndicator: document.getElementById('modeIndicator'),
    draftPanel: document.getElementById('draftPanel'),
    draftContent: document.getElementById('draftContent'),
    draftStatusBadge: document.getElementById('draftStatusBadge'),
    toolFeed: document.getElementById('toolActivityFeed'),
    clearChat: document.getElementById('clearChatBtn'),
    clearActivity: document.getElementById('clearActivityBtn'),
    sidebarToggle: document.getElementById('sidebarToggleBtn'),
    sessionDisplay: document.getElementById('sessionIdDisplay'),
    llmStatusDot: document.getElementById('llmStatusDot'),
    llmStatusText: document.getElementById('llmStatusText'),
    integrationsList: document.getElementById('integrationsList'),
    whatsappPanel: document.getElementById('whatsappPanel'),
    whatsappContent: document.getElementById('whatsappContent'),
    leftSidebar: document.getElementById('chatLeftSidebar'),
    rightSidebar: document.getElementById('chatRightSidebar')
  };

  // ── State ────────────────────────────────────────────────────────────────

  let currentTenant = 'al-noor-jewelry';
  let sessionId = sessionStorage.getItem('vx_chat_session') || generateSessionId();
  let activeDraftId = null;
  let isLoading = false;
  let lastFailedMessage = null;
  let typingBubble = null;

  sessionStorage.setItem('vx_chat_session', sessionId);

  // ── Init ─────────────────────────────────────────────────────────────────

  function init() {
    updateSessionDisplay();
    bindEvents();
    renderWorkspaceTabs();
    switchTenant('al-noor-jewelry', true);
    loadIntegrationStatuses();
    checkServerHealth();
  }

  function generateSessionId() {
    return `SES-${Date.now()}-${Math.random().toString(36).substr(2, 7).toUpperCase()}`;
  }

  function updateSessionDisplay() {
    if (els.sessionDisplay) {
      els.sessionDisplay.textContent = `Session: ${sessionId.substring(0, 20)}`;
    }
  }

  // ── Events ───────────────────────────────────────────────────────────────

  function bindEvents() {
    // Send button
    els.sendBtn.addEventListener('click', handleSend);

    // Keyboard shortcut: Enter sends, Shift+Enter = newline
    els.textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    // Auto-resize textarea + char counter
    els.textarea.addEventListener('input', () => {
      autoResizeTextarea();
      updateCharCounter();
      updateSendButtonState();
    });

    // Clear chat
    if (els.clearChat) {
      els.clearChat.addEventListener('click', () => {
        clearChat();
      });
    }

    // Clear activity
    if (els.clearActivity) {
      els.clearActivity.addEventListener('click', () => {
        els.toolFeed.innerHTML = '<div class="tool-activity-empty">Agent tool activity will appear here during responses</div>';
      });
    }

    // Sidebar toggle (mobile)
    if (els.sidebarToggle) {
      els.sidebarToggle.addEventListener('click', () => {
        els.leftSidebar?.classList.toggle('open');
      });
    }

    // Workspace tab clicks (delegated)
    if (els.workspaceTabs) {
      els.workspaceTabs.addEventListener('click', (e) => {
        const tab = e.target.closest('.workspace-tab');
        if (tab && tab.dataset.tenant && tab.dataset.tenant !== currentTenant) {
          switchTenant(tab.dataset.tenant);
        }
      });
    }
  }

  function autoResizeTextarea() {
    const ta = els.textarea;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
  }

  function updateCharCounter() {
    const len = els.textarea.value.length;
    const max = 1000;
    els.charCounter.textContent = `${len} / ${max}`;
    els.charCounter.className = 'char-counter' +
      (len >= max ? ' at-limit' : len >= 850 ? ' near-limit' : '');
  }

  function updateSendButtonState() {
    const hasText = els.textarea.value.trim().length > 0;
    els.sendBtn.disabled = !hasText || isLoading;
  }

  // ── Workspace Switching ──────────────────────────────────────────────────

  function renderWorkspaceTabs() {
    if (!els.workspaceTabs) return;
    els.workspaceTabs.querySelectorAll('.workspace-tab').forEach(tab => {
      const tid = tab.dataset.tenant;
      tab.classList.toggle('active', tid === currentTenant);
    });
  }

  function switchTenant(tenantId, isInit = false) {
    currentTenant = tenantId;
    // New session per workspace
    if (!isInit) {
      sessionId = generateSessionId();
      sessionStorage.setItem('vx_chat_session', sessionId);
      updateSessionDisplay();
    }

    activeDraftId = null;

    const config = TENANT_CONFIGS[tenantId];
    if (!config) return;

    // Update header
    if (els.headerAvatar) els.headerAvatar.textContent = config.icon;
    if (els.headerName) els.headerName.textContent = config.name;
    if (els.headerStatus) els.headerStatus.textContent = config.status;

    // Update tab active states
    renderWorkspaceTabs();

    // Update quick prompts
    renderQuickPrompts(config.prompts);

    // Clear messages + show greeting
    clearChat(false);
    appendAIMessage(config.greeting, `Workspace: ${config.name} — Verified Data Sources Active`, []);

    // Reset draft + whatsapp panels
    resetDraftPanel();
    hideWhatsappPanel();
  }

  // ── Quick Prompts ────────────────────────────────────────────────────────

  function renderQuickPrompts(prompts) {
    if (!els.quickPrompts) return;
    els.quickPrompts.innerHTML = '';
    prompts.forEach(p => {
      const btn = document.createElement('button');
      btn.className = 'quick-prompt-btn';
      btn.innerHTML = `<span class="quick-prompt-icon">${p.icon}</span><span>${p.label}</span>`;
      btn.addEventListener('click', () => {
        if (isLoading) return;
        sendMessage(p.text);
      });
      els.quickPrompts.appendChild(btn);
    });
  }

  // ── Chat Management ──────────────────────────────────────────────────────

  function clearChat(showWelcome = true) {
    if (els.messages) els.messages.innerHTML = '';
    typingBubble = null;
    if (showWelcome) {
      const config = TENANT_CONFIGS[currentTenant];
      if (config) {
        appendAIMessage(config.greeting, `Workspace: ${config.name}`, []);
      }
    }
  }

  // ── Message Rendering ────────────────────────────────────────────────────

  function appendUserMessage(text) {
    const isAr = isArabic(text);
    const row = document.createElement('div');
    row.className = 'msg-row user-row';
    row.innerHTML = `
      <div class="msg-content-wrap" style="${isAr ? 'align-items:flex-start;' : ''}">
        <div class="msg-bubble user-bubble${isAr ? ' rtl-bubble' : ''}">${escapeHtml(text)}</div>
        <div class="msg-timestamp">${formatTime()}</div>
      </div>
      <div class="msg-avatar user-avatar">You</div>
    `;
    els.messages.appendChild(row);
    scrollToBottom();
  }

  function appendAIMessage(text, grounding = '', toolCalls = [], isHandoff = false, whatsappUrl = null) {
    const isAr = isArabic(text);
    const row = document.createElement('div');
    row.className = 'msg-row';

    let toolStepsHtml = '';
    if (toolCalls && toolCalls.length > 0) {
      toolStepsHtml = `<div class="msg-tool-steps">`;
      toolCalls.forEach(tc => {
        const icon = TOOL_ICONS[tc.tool] || '⚙️';
        const resultStatus = tc.result?.error ? '✗ Error' : '✓ Done';
        toolStepsHtml += `
          <div class="tool-step">
            <span class="tool-step-icon">${icon}</span>
            <span class="tool-step-name">${tc.tool}</span>
            <span class="tool-step-result">${resultStatus}</span>
          </div>`;
      });
      toolStepsHtml += `</div>`;
    }

    const formattedText = formatMessageText(text);

    let handoffCardHtml = '';
    if (isHandoff && whatsappUrl) {
      handoffCardHtml = `
        <div class="whatsapp-handoff-card">
          <div class="whatsapp-handoff-title">
            <span>💬</span> WhatsApp Specialist Ready
          </div>
          <div class="whatsapp-handoff-sub">
            Your conversation context and draft state have been compiled. Click to continue on WhatsApp — we will not claim it was delivered until you open the link.
          </div>
          <a href="${escapeAttr(whatsappUrl)}" target="_blank" rel="noopener noreferrer" class="whatsapp-open-btn">
            Open WhatsApp with Full Context →
          </a>
        </div>`;
    }

    row.innerHTML = `
      <div class="msg-avatar ai-avatar">🤖</div>
      <div class="msg-content-wrap">
        ${grounding ? `<div class="msg-grounding"><span class="msg-grounding-dot"></span>${escapeHtml(grounding)}</div>` : ''}
        <div class="msg-bubble ai-bubble${isAr ? ' rtl-bubble' : ''}">
          ${toolStepsHtml}
          ${formattedText}
          ${handoffCardHtml}
        </div>
        <div class="msg-timestamp">${formatTime()}</div>
      </div>
    `;
    els.messages.appendChild(row);
    scrollToBottom();
  }

  function appendErrorMessage(message, retryText = null) {
    const row = document.createElement('div');
    row.className = 'msg-row';
    row.innerHTML = `
      <div class="msg-avatar ai-avatar" style="background:rgba(244,63,94,0.3);">⚠️</div>
      <div class="msg-content-wrap">
        <div class="error-bubble">
          <div>
            <div>${escapeHtml(message)}</div>
            ${retryText ? `<button class="error-retry-btn" id="retryBtn">Retry</button>` : ''}
          </div>
        </div>
      </div>
    `;
    els.messages.appendChild(row);

    const retryBtn = row.querySelector('#retryBtn');
    if (retryBtn && retryText) {
      retryBtn.addEventListener('click', () => {
        row.remove();
        sendMessage(retryText);
      });
    }
    scrollToBottom();
  }

  function showTypingIndicator(state = 'Processing your request') {
    removeTypingIndicator();
    const row = document.createElement('div');
    row.className = 'msg-row';
    row.id = 'typingIndicatorRow';
    row.innerHTML = `
      <div class="msg-avatar ai-avatar">🤖</div>
      <div class="msg-content-wrap">
        <div class="typing-indicator-bubble">
          <div class="streaming-spinner"></div>
          <span class="typing-state-label">${escapeHtml(state)}</span>
          <div class="typing-dots">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>
      </div>
    `;
    els.messages.appendChild(row);
    typingBubble = row;
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const existing = document.getElementById('typingIndicatorRow');
    if (existing) existing.remove();
    typingBubble = null;
  }

  // ── Send Flow ────────────────────────────────────────────────────────────

  function handleSend() {
    const text = els.textarea.value.trim();
    if (!text || isLoading) return;
    els.textarea.value = '';
    autoResizeTextarea();
    updateCharCounter();
    sendMessage(text);
  }

  async function sendMessage(text) {
    if (isLoading) return;
    isLoading = true;
    lastFailedMessage = text;
    updateSendButtonState();

    appendUserMessage(text);
    showTypingIndicator('Agent reasoning — invoking verified tools');

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenantId: currentTenant,
          sessionId,
          message: text
        }),
        signal: AbortSignal.timeout(60000) // 60s timeout
      });

      removeTypingIndicator();

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
        throw new Error(errData.error || `Server error ${response.status}`);
      }

      const data = await response.json();

      // Render tool activity
      if (data.toolCalls && data.toolCalls.length > 0) {
        renderToolActivity(data.toolCalls);
      }

      // Render AI message
      appendAIMessage(
        data.reply,
        data.grounding,
        data.toolCalls || [],
        data.isHandoff || false,
        data.whatsappUrl || null
      );

      // Update draft panel
      if (data.hasDraftOrder) {
        renderDraftPanel(data.hasDraftOrder);
      }

      // Update WhatsApp panel in right sidebar
      if (data.isHandoff && data.whatsappUrl) {
        showWhatsappPanel(data.whatsappUrl);
      }

      // Update mode indicator based on grounding info
      updateModeIndicator(data.grounding);

    } catch (err) {
      removeTypingIndicator();
      const msg = err.name === 'TimeoutError'
        ? 'The request timed out. The AI agent may be processing a complex query.'
        : `Connection error: ${err.message}`;
      appendErrorMessage(msg, text);
    } finally {
      isLoading = false;
      updateSendButtonState();
      els.textarea.focus();
    }
  }

  // ── Draft Panel ──────────────────────────────────────────────────────────

  function renderDraftPanel(draft) {
    if (!els.draftContent || !draft) return;
    activeDraftId = draft.id;

    const isConfirmed = draft.status?.includes('Confirmed');
    const isCancelled = draft.status?.includes('cancelled');

    // Update header badge
    if (els.draftStatusBadge) {
      if (isConfirmed) {
        els.draftStatusBadge.textContent = 'Confirmed';
        els.draftStatusBadge.className = 'right-panel-badge confirmed';
      } else if (isCancelled) {
        els.draftStatusBadge.textContent = 'Cancelled';
        els.draftStatusBadge.className = 'right-panel-badge awaiting';
      } else {
        els.draftStatusBadge.textContent = 'Draft';
        els.draftStatusBadge.className = 'right-panel-badge draft';
      }
    }

    // Items
    let itemsHtml = '';
    if (draft.items && draft.items.length > 0) {
      itemsHtml = draft.items.map(item => `
        <div class="draft-item-row">
          <span class="draft-item-name">${escapeHtml(item.quantity + 'x ' + item.name)}</span>
          <span class="draft-item-price">${item.total?.toLocaleString() || ''} ${item.currency || draft.currency || ''}</span>
        </div>
      `).join('');
    } else {
      itemsHtml = `<div class="draft-item-row"><span class="draft-item-name">${escapeHtml(draft.title || 'Draft Order')}</span><span class="draft-item-price">${draft.price || ''}</span></div>`;
    }

    // Breakdown
    let breakdownHtml = `
      <div class="draft-breakdown">
        <div class="draft-breakdown-row"><span>Subtotal</span><span>${(draft.subtotal || 0).toLocaleString()} ${draft.currency}</span></div>
    `;
    if (draft.discount_amount > 0) {
      breakdownHtml += `<div class="draft-breakdown-row discount"><span>Discount</span><span>−${draft.discount_amount.toLocaleString()} ${draft.currency}</span></div>`;
    }
    if (draft.tax_amount > 0) {
      breakdownHtml += `<div class="draft-breakdown-row"><span>Tax / VAT</span><span>+${draft.tax_amount.toLocaleString()} ${draft.currency}</span></div>`;
    }
    if (draft.deposit_required && draft.deposit_required !== '0') {
      const dep = typeof draft.deposit_required === 'string' ? draft.deposit_required : `${(draft.deposit_required || 0).toLocaleString()} ${draft.currency}`;
      breakdownHtml += `<div class="draft-breakdown-row deposit"><span>Deposit Required</span><span>${dep}</span></div>`;
    }
    breakdownHtml += `
        <div class="draft-breakdown-row total">
          <span>Total</span>
          <span>${draft.price || ((draft.total_amount || 0).toLocaleString() + ' ' + draft.currency)}</span>
        </div>
      </div>
    `;

    // Action buttons
    let actionHtml = '';
    if (isConfirmed) {
      actionHtml = `<div class="draft-confirmed-btn">✓ Order Confirmed & Transmitted</div>`;
    } else if (!isCancelled) {
      actionHtml = `
        <button class="draft-confirm-btn" id="draftConfirmBtn">
          Confirm & Transmit to Merchant →
        </button>
        <button class="draft-cancel-btn" id="draftCancelBtn">Cancel Draft</button>
      `;
    }

    els.draftContent.className = 'draft-card';
    els.draftContent.innerHTML = `
      <div class="draft-card-id">
        <span>${escapeHtml(draft.id || 'DRAFT')}</span>
        <span class="draft-type-pill">Draft</span>
      </div>
      <div class="draft-items-list">${itemsHtml}</div>
      ${breakdownHtml}
      <div style="font-size:0.7rem;color:${isConfirmed ? '#10B981' : '#F59E0B'};line-height:1.4;margin-top:0.25rem;">
        ${escapeHtml(draft.status || 'Requires customer confirmation')}
      </div>
      ${actionHtml}
    `;

    // Bind action buttons
    const confirmBtn = document.getElementById('draftConfirmBtn');
    const cancelBtn = document.getElementById('draftCancelBtn');

    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => handleConfirmDraft(draft.id, confirmBtn));
    }
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => handleCancelDraft(draft.id));
    }
  }

  function resetDraftPanel() {
    activeDraftId = null;
    if (els.draftContent) {
      els.draftContent.className = 'draft-empty-state';
      els.draftContent.innerHTML = `
        <div class="draft-empty-icon">📋</div>
        <div class="draft-empty-text">No active draft</div>
        <div class="draft-empty-sub">Ask about a product or booking to create a verified draft order</div>
      `;
    }
    if (els.draftStatusBadge) {
      els.draftStatusBadge.textContent = 'Awaiting';
      els.draftStatusBadge.className = 'right-panel-badge awaiting';
    }
  }

  async function handleConfirmDraft(draftId, btn) {
    if (!draftId) return;
    const originalText = btn.textContent;
    btn.textContent = 'Verifying stock & confirming...';
    btn.disabled = true;

    try {
      const res = await fetch('/api/drafts/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          draftId,
          idempotencyKey: `IDEMP-${draftId}-${Date.now()}`
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Confirmation failed');

      const confirmRef = data.externalReference || 'CONF-OK';
      appendAIMessage(
        `Your draft order has been explicitly confirmed by you. **Confirmation Token: #${confirmRef}** has been generated and transmitted to the merchant fulfillment system.\n\nThis is the authoritative confirmation record. A receipt will follow from the business team.`,
        'Customer Explicit Confirmation Registered & Audited',
        []
      );

      if (data.draft) {
        data.draft.status = `✓ Confirmed by Customer (Transmitted) — Ref: #${confirmRef}`;
        renderDraftPanel(data.draft);
      }
    } catch (err) {
      appendErrorMessage(`Confirmation failed: ${err.message}. Your draft is preserved — please retry.`);
      btn.textContent = originalText;
      btn.disabled = false;
    }
  }

  async function handleCancelDraft(draftId) {
    if (!draftId || !confirm('Cancel this draft order? This cannot be undone.')) return;

    try {
      const res = await fetch('/api/drafts/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draftId })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Cancellation failed');

      appendAIMessage(
        'Your draft order has been cancelled. No charges have been made. You can start a new inquiry at any time.',
        'Draft Cancelled — No Action Taken',
        []
      );
      resetDraftPanel();
    } catch (err) {
      appendErrorMessage(`Cancellation error: ${err.message}`);
    }
  }

  // ── WhatsApp Panel ───────────────────────────────────────────────────────

  function showWhatsappPanel(url) {
    if (!els.whatsappPanel || !els.whatsappContent) return;
    els.whatsappPanel.style.display = 'block';
    els.whatsappContent.innerHTML = `
      <div class="whatsapp-handoff-sub">
        Conversation context and draft state compiled. Open WhatsApp to connect with the specialist team.
        <br><em style="font-size:0.65rem;color:#4B5563;">Note: we cannot confirm delivery until you open and send the message.</em>
      </div>
      <a href="${escapeAttr(url)}" target="_blank" rel="noopener noreferrer" class="whatsapp-open-btn" style="margin-top:0.625rem;">
        <span>💬</span> Open WhatsApp
      </a>
    `;
  }

  function hideWhatsappPanel() {
    if (els.whatsappPanel) els.whatsappPanel.style.display = 'none';
  }

  // ── Tool Activity Feed ───────────────────────────────────────────────────

  function renderToolActivity(toolCalls) {
    if (!els.toolFeed || !toolCalls.length) return;

    // Clear empty state on first entry
    const emptyEl = els.toolFeed.querySelector('.tool-activity-empty');
    if (emptyEl) emptyEl.remove();

    // Add timestamp separator
    const sep = document.createElement('div');
    sep.style.cssText = 'font-size:0.6rem;color:#2A2440;text-align:center;padding:0.25rem 0;';
    sep.textContent = formatTime();
    els.toolFeed.appendChild(sep);

    toolCalls.forEach(tc => {
      const icon = TOOL_ICONS[tc.tool] || '⚙️';
      const hasError = tc.result?.error;
      const item = document.createElement('div');
      item.className = 'activity-item';
      item.innerHTML = `
        <span class="activity-icon">${icon}</span>
        <div class="activity-body">
          <div class="activity-tool">${escapeHtml(tc.tool)}</div>
          <div class="activity-status ${hasError ? 'error' : 'success'}">
            ${hasError ? '✗ ' + escapeHtml(tc.result.error) : '✓ Executed successfully'}
          </div>
        </div>
      `;
      els.toolFeed.appendChild(item);
    });

    // Auto-scroll tool feed
    els.toolFeed.scrollTop = els.toolFeed.scrollHeight;
  }

  // ── Mode Indicator ───────────────────────────────────────────────────────

  function updateModeIndicator(grounding = '') {
    if (!els.modeLabel || !els.modeIndicator) return;

    const isGemini = grounding.includes('Gemini');
    const isAnthropic = grounding.includes('Anthropic') || grounding.includes('Claude');
    const isOpenAI = grounding.includes('OpenAI');
    const isDemo = grounding.includes('Demo Mode');

    if (isGemini) {
      els.modeLabel.textContent = 'Live Intelligence — Google Gemini';
      els.modeIndicator.className = 'mode-badge mode-live';
      updateLLMStatus('green', 'Google Gemini Active');
    } else if (isAnthropic) {
      els.modeLabel.textContent = 'Live Intelligence — Anthropic Claude';
      els.modeIndicator.className = 'mode-badge mode-live';
      updateLLMStatus('green', 'Anthropic Claude Active');
    } else if (isOpenAI) {
      els.modeLabel.textContent = 'Live Intelligence — OpenAI GPT';
      els.modeIndicator.className = 'mode-badge mode-live';
      updateLLMStatus('green', 'OpenAI GPT Active');
    } else if (isDemo) {
      els.modeLabel.textContent = 'Demo Mode — Local Orchestrator';
      els.modeIndicator.className = 'mode-badge mode-demo';
      updateLLMStatus('amber', 'No LLM key — Demo Mode');
    }
  }

  function updateLLMStatus(dotColor, text) {
    if (els.llmStatusDot) {
      els.llmStatusDot.className = `data-source-dot ${dotColor}`;
    }
    if (els.llmStatusText) els.llmStatusText.textContent = text;
  }

  // ── Server Health & Integration Status ───────────────────────────────────

  async function checkServerHealth() {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        // Server is up — mode indicator already set by first response
      }
    } catch {
      updateLLMStatus('red', 'Server offline');
    }
  }

  async function loadIntegrationStatuses() {
    if (!els.integrationsList) return;
    try {
      const res = await fetch('/api/integrations');
      if (!res.ok) return;
      const data = await res.json();
      const integrations = data.integrations || {};

      els.integrationsList.innerHTML = Object.entries(integrations).map(([key, val]) => `
        <div class="integration-item">
          <span>${escapeHtml(key)}</span>
          <span class="integration-badge ${val.configured ? 'live' : 'demo'}">${val.mode}</span>
        </div>
      `).join('');
    } catch {
      if (els.integrationsList) {
        els.integrationsList.innerHTML = '<div style="font-size:0.65rem;color:#3A3450;">Status unavailable</div>';
      }
    }
  }

  // ── Utilities ────────────────────────────────────────────────────────────

  function scrollToBottom() {
    if (els.messages) {
      requestAnimationFrame(() => {
        els.messages.scrollTop = els.messages.scrollHeight;
      });
    }
  }

  function isArabic(text) {
    return /[\u0600-\u06FF]/.test(text);
  }

  function formatMessageText(text) {
    // Convert **bold**, newlines, and preserve structure
    return text
      .replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function escapeAttr(str) {
    if (!str) return '';
    return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // ── Bootstrap ────────────────────────────────────────────────────────────

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
