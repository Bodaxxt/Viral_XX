/**
 * VIRAL-X Production AI Sales Agent Simulator Client
 * Communicates with the real server-side REST API, tracks multi-turn session state,
 * manages workspace context switching, renders tool execution pipelines,
 * and handles explicit order confirmation gates.
 */

document.addEventListener('DOMContentLoaded', () => {
  const chatMessages = document.getElementById('demoChatMessages');
  const chatInput = document.getElementById('demoChatInput');
  const sendBtn = document.getElementById('demoSendBtn');
  const samplePromptsContainer = document.querySelector('.sample-prompts-list');
  const handoffBtn = document.getElementById('demoHandoffBtn');
  const orderPreview = document.getElementById('demoOrderPreview');
  const catalogStatus = document.getElementById('demoCatalogStatus');

  if (!chatMessages || !chatInput || !sendBtn) return;

  // Active Session and Workspace State
  let currentTenant = 'al-noor-jewelry';
  let sessionId = sessionStorage.getItem('viral_x_session_id') || `SES-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
  sessionStorage.setItem('viral_x_session_id', sessionId);
  let activeDraft = null;

  // Dynamic Workspace Prompts
  const TENANT_CONFIGS = {
    'al-noor-jewelry': {
      name: '💎 Al Noor High Jewelry (Doha)',
      location: 'Place Vendôme, Doha',
      statusText: '● Al Noor High Jewelry Catalog v4.2 Synced (Doha Place Vendôme Flagship)',
      prompts: [
        { label: '💎 Inquire emerald collar stock & price', text: 'Check Doha boutique availability and verified price for the emerald collar' },
        { label: '💍 Details on Solitaire Cushion Ring', text: 'What are the certificate and carat specifications of the Solitaire Cushion Ring?' },
        { label: '📦 Ask about insured GCC delivery', text: 'What are your delivery and viewing options across the GCC?' },
        { label: '👤 Request WhatsApp human concierge', text: 'I need to speak directly with an Al Noor jewelry specialist on WhatsApp.' }
      ]
    },
    'saffron-table': {
      name: '🍽️ The Saffron Table (Cairo)',
      location: 'Zamalek, Cairo',
      statusText: '● The Saffron Table Reservation Matrix Active (Zamalek Suite)',
      prompts: [
        { label: '🍽️ Reserve Chef Tasting Menu for 2', text: 'What tasting menus are available for dinner tomorrow evening for 2 guests?' },
        { label: '👥 Update party size to 3 guests', text: 'Actually, please make it 3 guests instead' },
        { label: '🥗 Inquire about gluten & allergy policy', text: 'Can you accommodate gluten allergies and shellfish restrictions?' },
        { label: '👤 Speak with restaurant concierge', text: 'I would like to speak directly with the Maître d on WhatsApp.' }
      ]
    },
    'vitalis-health': {
      name: '🩺 Vitalis Health (New Cairo)',
      location: 'New Cairo Medical Park',
      statusText: '● Vitalis EHR Clinic Appointments Online (New Cairo Suite 402)',
      prompts: [
        { label: '🩺 Executive longevity screening info', text: 'What is included in the Executive Longevity & Metabolic Screening in New Cairo?' },
        { label: '🩸 Fasting and preparation rules', text: 'What preparation and fasting is required before the screening?' },
        { label: '📅 Hold a morning appointment slot', text: 'Can I book the executive screening for tomorrow morning?' },
        { label: '👤 Connect with clinical coordinator', text: 'I want to speak with a Vitalis patient coordinator via WhatsApp.' }
      ]
    }
  };

  // Inject Tenant Switcher Bar above chat
  const demoContainer = document.querySelector('.interactive-demo-container');
  if (demoContainer && !document.getElementById('tenantSelectorBar')) {
    const selectorBar = document.createElement('div');
    selectorBar.id = 'tenantSelectorBar';
    selectorBar.className = 'tenant-selector-bar';
    selectorBar.innerHTML = `
      <span style="font-size: 0.75rem; color: #8A8494; font-weight: 600; text-transform: uppercase;">Workspace:</span>
      <button class="tenant-tab active" data-tenant="al-noor-jewelry">💎 Doha Jewelry</button>
      <button class="tenant-tab" data-tenant="saffron-table">🍽️ Cairo Fine Dining</button>
      <button class="tenant-tab" data-tenant="vitalis-health">🩺 Vitalis Health</button>
      <span style="margin-left: auto; font-size: 0.72rem; color: #10B981; font-weight: 500; display: flex; align-items: center; gap: 4px;">
        <span class="status-dot"></span> Production API Connected
      </span>
    `;

    const headerBar = demoContainer.querySelector('.demo-header-bar');
    if (headerBar) {
      headerBar.insertAdjacentElement('afterend', selectorBar);
    }

    // Attach switcher event listeners
    selectorBar.querySelectorAll('.tenant-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const selected = tab.getAttribute('data-tenant');
        if (selected === currentTenant) return;

        selectorBar.querySelectorAll('.tenant-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');

        switchTenant(selected);
      });
    });
  }

  function switchTenant(tenantId) {
    currentTenant = tenantId;
    sessionId = `SES-${tenantId}-${Date.now()}`;
    sessionStorage.setItem('viral_x_session_id', sessionId);
    activeDraft = null;

    const config = TENANT_CONFIGS[tenantId];
    if (catalogStatus) {
      catalogStatus.innerHTML = `<span style="color: #10B981;">${config.statusText}</span>`;
    }

    // Clear and show workspace welcome
    chatMessages.innerHTML = '';
    appendMessage('ai', `Switched workspace to **${config.name}** (${config.location}). Verified server catalog and deterministic business tools connected. How may I assist you?`, 'System Grounding Active & Verified');

    // Update Prompts
    renderSamplePrompts(config.prompts);

    // Reset draft panel
    renderDraftPreview(null);
  }

  function renderSamplePrompts(prompts) {
    if (!samplePromptsContainer) return;
    samplePromptsContainer.innerHTML = '';
    prompts.forEach(p => {
      const btn = document.createElement('button');
      btn.className = 'sample-prompt-btn';
      btn.setAttribute('data-prompt', p.text);
      btn.innerText = p.label;
      btn.addEventListener('click', () => handleSend(p.text));
      samplePromptsContainer.appendChild(btn);
    });
  }

  function appendMessage(sender, text, meta, toolCalls = [], isArabic = false) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender === 'user' ? 'bubble-user' : 'bubble-ai'}`;

    if (isArabic) {
      bubble.classList.add('rtl-bubble');
    }

    if (sender === 'ai' && meta) {
      const metaEl = document.createElement('div');
      metaEl.className = 'bubble-ai-meta';
      metaEl.innerHTML = `<span class="status-dot"></span> <span>${meta}</span>`;
      bubble.appendChild(metaEl);
    }

    // Render tool activity steps if present
    if (toolCalls && toolCalls.length > 0) {
      const toolsBox = document.createElement('div');
      toolsBox.className = 'tool-steps-container';

      toolCalls.forEach(tc => {
        const item = document.createElement('div');
        item.className = 'tool-step-item';
        let icon = '⚙️';
        if (tc.tool.includes('search')) icon = '🔍';
        if (tc.tool.includes('inventory')) icon = '📦';
        if (tc.tool.includes('price')) icon = '🧮';
        if (tc.tool.includes('draft')) icon = '📝';
        if (tc.tool.includes('handoff')) icon = '👤';

        item.innerHTML = `
          <span>${icon}</span>
          <span class="tool-step-badge">${tc.tool}</span>
          <span>Verified server execution</span>
        `;
        toolsBox.appendChild(item);
      });

      bubble.appendChild(toolsBox);
    }

    const content = document.createElement('div');
    content.innerHTML = text
      .replace(/\n/g, '<br/>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    bubble.appendChild(content);

    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function showLoadingIndicator() {
    const bubble = document.createElement('div');
    bubble.id = 'demoTypingIndicator';
    bubble.className = 'chat-bubble bubble-ai';
    bubble.innerHTML = `
      <div class="bubble-ai-meta">
        <span class="status-dot" style="background:#8B5CF6;"></span>
        <span>Verified AI Engine Reasoning...</span>
      </div>
      <div class="typing-dots">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>
    `;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return bubble;
  }

  function removeLoadingIndicator() {
    const el = document.getElementById('demoTypingIndicator');
    if (el) el.remove();
  }

  function renderDraftPreview(draft) {
    if (!orderPreview) return;

    if (!draft) {
      orderPreview.innerHTML = `
        <div class="sidebar-panel-title">
          <span>Draft Order State</span>
          <span style="font-size: 0.7rem; color: #8A8494;">Awaiting Action</span>
        </div>
        <p style="font-size: 0.8125rem; color: #8A8494; margin: 0;">
          No active draft order. Inquire about a product or booking above to view safe price calculation and confirmation gates.
        </p>
      `;
      return;
    }

    activeDraft = draft;
    const isConfirmed = draft.status && draft.status.includes('Confirmed');

    let itemsHtml = '';
    if (draft.items && draft.items.length > 0) {
      itemsHtml = draft.items.map(it => `
        <div class="draft-item-row">
          <span>${it.quantity}x ${it.name}</span>
          <span style="font-weight: 600;">${it.total.toLocaleString()} ${it.currency || draft.currency}</span>
        </div>
      `).join('');
    } else {
      itemsHtml = `
        <div class="draft-item-row">
          <span>${draft.title || 'Selected Item'}</span>
          <span style="font-weight: 600;">${draft.price || ''}</span>
        </div>
      `;
    }

    orderPreview.innerHTML = `
      <div class="draft-card-wrapper">
        <div class="draft-header">
          <span style="font-size: 0.72rem; text-transform: uppercase; color: #C8B8F0; font-weight: 700; letter-spacing: 0.05em;">
            Verified Draft Cart / Booking
          </span>
          <span class="status-pill ${isConfirmed ? 'status-pill-confirmed' : 'status-pill-draft'}">
            ${isConfirmed ? 'Confirmed' : 'Draft Prepared'}
          </span>
        </div>

        <div style="font-size: 0.875rem; font-weight: 700; color: #FFFFFF; margin-bottom: 0.5rem;">
          ${draft.id || 'Active Hold'} &bull; ${draft.sku || ''}
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.25rem;">
          ${itemsHtml}
        </div>

        <div class="draft-summary-breakdown">
          ${draft.deposit_required ? `<div>Deposit Required: <strong style="color: #F59E0B;">${draft.deposit_required}</strong></div>` : ''}
          ${draft.discount_amount ? `<div>Promotional Discount: <strong style="color: #10B981;">-${draft.discount_amount.toLocaleString()} ${draft.currency}</strong></div>` : ''}
          <div class="draft-total-highlight">
            <span>Verified Total:</span>
            <span>${draft.price || `${draft.total_amount.toLocaleString()} ${draft.currency}`}</span>
          </div>
        </div>

        <div style="font-size: 0.72rem; color: ${isConfirmed ? '#10B981' : '#F59E0B'}; margin: 0.75rem 0 0.5rem 0; line-height: 1.3;">
          ${draft.status || 'Requires explicit customer confirmation'}
        </div>

        ${!isConfirmed ? `
          <button id="confirmOrderBtn" class="btn btn-primary btn-sm" style="width: 100%; font-size: 0.8125rem; margin-top: 0.35rem;">
            Confirm & Transmit to Verified Merchant
          </button>
        ` : `
          <button class="btn btn-secondary btn-sm" style="width: 100%; font-size: 0.8125rem; background: rgba(16, 185, 129, 0.2); border-color: #10B981; color: #10B981;" disabled>
            ✓ Transmission Verified (#${draft.externalReference || 'CONF-OK'})
          </button>
        `}
      </div>
    `;

    const confirmBtn = document.getElementById('confirmOrderBtn');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', () => handleConfirmDraft(draft.id));
    }
  }

  async function handleConfirmDraft(draftId) {
    const confirmBtn = document.getElementById('confirmOrderBtn');
    if (confirmBtn) {
      confirmBtn.innerText = 'Verifying Stock & Confirming...';
      confirmBtn.disabled = true;
    }

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
      if (!res.ok) {
        throw new Error(data.error || 'Failed to confirm draft.');
      }

      appendMessage('ai', `Thank you! Your draft order has been safely confirmed by customer intent. A confirmation receipt has been transmitted with verified transaction token **#${data.externalReference}**.`, 'Security: Customer Explicit Confirmation Registered');

      if (data.draft) {
        data.draft.status = '✓ Confirmed by Customer (Transmitted)';
        data.draft.externalReference = data.externalReference;
        renderDraftPreview(data.draft);
      }
    } catch (err) {
      appendMessage('ai', `Confirmation Alert: ${err.message}`, 'Verification Warning');
      if (confirmBtn) {
        confirmBtn.innerText = 'Confirm & Transmit to Verified Merchant';
        confirmBtn.disabled = false;
      }
    }
  }

  async function handleSend(userText) {
    const text = userText || chatInput.value.trim();
    if (!text) return;

    const isArabic = /[\u0600-\u06FF]/.test(text);
    appendMessage('user', text, null, [], isArabic);
    chatInput.value = '';

    const loader = showLoadingIndicator();

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenantId: currentTenant,
          sessionId,
          message: text
        })
      });

      removeLoadingIndicator();

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      appendMessage('ai', data.reply, data.grounding, data.toolCalls, /[\u0600-\u06FF]/.test(data.reply));

      if (data.hasDraftOrder) {
        renderDraftPreview(data.hasDraftOrder);
      }

      if (data.isHandoff && data.whatsappUrl) {
        // Render immediate WhatsApp launch action in chat
        const handoffCard = document.createElement('div');
        handoffCard.className = 'chat-bubble bubble-ai';
        handoffCard.innerHTML = `
          <div style="background: rgba(37, 211, 102, 0.1); border: 1px solid rgba(37, 211, 102, 0.35); border-radius: 8px; padding: 0.85rem; margin-top: 4px;">
            <div style="font-size: 0.8125rem; font-weight: 700; color: #25D366; margin-bottom: 4px;">
              WhatsApp Specialist Handoff Ready
            </div>
            <p style="font-size: 0.78125rem; color: #D1CCDB; margin: 0 0 8px 0;">
              Your conversation context and draft cart have been compiled. Click below to continue directly on WhatsApp.
            </p>
            <a href="${data.whatsappUrl}" target="_blank" class="btn btn-primary btn-sm" style="background: #25D366; border-color: #25D366; width: 100%; text-align: center; font-size: 0.8125rem;">
              Open WhatsApp with Full Context &rarr;
            </a>
          </div>
        `;
        chatMessages.appendChild(handoffCard);
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    } catch (err) {
      removeLoadingIndicator();
      console.error('Chat error:', err);
      appendMessage('ai', `An error occurred while contacting the Viral-X agent service: ${err.message}. Please retry in a moment.`, 'System Exception: Network/Server');
    }
  }

  sendBtn.addEventListener('click', () => handleSend());
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleSend();
  });

  // Initial Sample Prompts for Al Noor Jewelry
  renderSamplePrompts(TENANT_CONFIGS['al-noor-jewelry'].prompts);

  if (handoffBtn) {
    handoffBtn.addEventListener('click', () => {
      handleSend('I need to speak directly with a human specialist via WhatsApp.');
    });
  }
});
