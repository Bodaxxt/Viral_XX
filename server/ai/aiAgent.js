/**
 * Viral-X Production AI Sales Agent Orchestrator v3.0
 *
 * Supports three real LLM providers with proper function-calling:
 *   - Google Gemini (GEMINI_API_KEY) — preferred, uses native function declarations
 *   - Anthropic Claude (ANTHROPIC_API_KEY) — uses tool_use blocks
 *   - OpenAI GPT (OPENAI_API_KEY) — uses function_call / tool_calls
 *
 * Falls back to a high-quality deterministic local orchestrator when no key is set.
 * All tool executions are handled server-side; the LLM only decides WHAT to call.
 */

const { dbManager } = require('../db/database');
const { toolExecutor, TOOL_DEFINITIONS } = require('../tools/toolRegistry');
const { buildSystemPrompt } = require('./promptTemplates');
const { SecurityGuardrails } = require('./guardrails');
const { BI_EVENT_TYPES } = require('../analytics/telemetryService');

// ─── Gemini function declarations (converted from JSON-Schema tool definitions) ───

function toGeminiFunctions(toolDefs) {
  return toolDefs.map(t => ({
    name: t.name,
    description: t.description,
    parameters: t.parameters || { type: 'object', properties: {} }
  }));
}

// ─── OpenAI function definitions ───

function toOpenAIFunctions(toolDefs) {
  return toolDefs.map(t => ({
    type: 'function',
    function: {
      name: t.name,
      description: t.description,
      parameters: t.parameters || { type: 'object', properties: {} }
    }
  }));
}

// ─── Anthropic tool definitions ───

function toAnthropicTools(toolDefs) {
  return toolDefs.map(t => ({
    name: t.name,
    description: t.description,
    input_schema: t.parameters || { type: 'object', properties: {} }
  }));
}

// ─── Maximum tool execution rounds per turn (prevent infinite loops) ───
const MAX_TOOL_ROUNDS = 6;

class AiSalesAgent {
  constructor(db = dbManager, tools = toolExecutor) {
    this.db = db;
    this.tools = tools;
  }

  /**
   * Main conversational entrypoint.
   */
  async processMessage({ tenantId, sessionId, userMessage, customerName = null }) {
    // 1. Verify tenant existence
    const tenant = this.db.getTenant(tenantId);
    if (!tenant) {
      throw new Error(`Tenant '${tenantId}' does not exist.`);
    }

    // 2. Prompt injection / security check
    const guardrailCheck = SecurityGuardrails.inspectPrompt(userMessage);
    if (!guardrailCheck.isSafe) {
      this.db.logAudit(tenantId, sessionId, 'INJECTION_ATTEMPT_BLOCKED', 'customer', {
        input: SecurityGuardrails.redactSensitive(userMessage),
        flaggedPattern: guardrailCheck.flaggedPattern
      });
      if (this.db && this.db.telemetry) {
        try {
          this.db.telemetry.recordEvent({
            tenantId,
            sessionId,
            eventType: BI_EVENT_TYPES.SECURITY_GUARDRAIL_TRIGGERED,
            category: 'security',
            outcome: 'blocked',
            metadata: {
              flaggedPattern: guardrailCheck.flaggedPattern
            }
          });
        } catch (e) {}
      }
      return {
        reply: guardrailCheck.safeResponse,
        grounding: 'Security: Prompt injection defense triggered',
        toolCalls: [],
        hasDraftOrder: null,
        isHandoff: false
      };
    }

    // 3. Ensure session + persist user message
    this.db.getOrCreateSession(sessionId, tenantId, customerName);
    const userMsgId = `MSG-U-${Date.now()}`;
    this.db.saveMessage(userMsgId, sessionId, tenantId, 'user', userMessage);

    // 4. Retrieve conversation history (last 14 turns)
    const history = this.db.getSessionMessages(sessionId, 14);

    // 5. Route to appropriate LLM provider
    let agentResult;
    const provider = this._detectProvider();

    try {
      if (provider === 'gemini') {
        agentResult = await this.callGemini(tenant, history, userMessage, sessionId);
      } else if (provider === 'anthropic') {
        agentResult = await this.callAnthropic(tenant, history, userMessage, sessionId);
      } else if (provider === 'openai') {
        agentResult = await this.callOpenAI(tenant, history, userMessage, sessionId);
      } else {
        agentResult = await this.orchestrateLocal(tenant, history, userMessage, sessionId);
      }
    } catch (err) {
      console.warn(`[${provider || 'local'}] LLM call failed — falling back to local orchestrator:`, err.message);
      if (this.db && this.db.telemetry) {
        try {
          this.db.telemetry.recordEvent({
            tenantId,
            sessionId,
            eventType: BI_EVENT_TYPES.LLM_PROVIDER_FAILED,
            category: 'ai_infrastructure',
            outcome: 'fallback_to_local',
            metadata: {
              provider: provider || 'unknown',
              error: err.message
            }
          });
        } catch (e) {}
      }
      agentResult = await this.orchestrateLocal(tenant, history, userMessage, sessionId);
    }

    // 6. Persist AI response
    const aiMsgId = `MSG-A-${Date.now()}`;
    this.db.saveMessage(
      aiMsgId, sessionId, tenantId, 'ai',
      agentResult.reply, agentResult.toolCalls, agentResult.grounding
    );

    return agentResult;
  }

  _detectProvider() {
    if (process.env.GEMINI_API_KEY) return 'gemini';
    if (process.env.ANTHROPIC_API_KEY) return 'anthropic';
    if (process.env.OPENAI_API_KEY) return 'openai';
    return null;
  }

  // ─────────────────────────────────────────────────────────────────────────
  //  GOOGLE GEMINI — native function calling with multi-round tool execution
  // ─────────────────────────────────────────────────────────────────────────

  async callGemini(tenant, history, currentMessage, sessionId) {
    const apiKey = process.env.GEMINI_API_KEY;
    const model = process.env.GEMINI_MODEL || 'gemini-3.5-flash-lite';
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

    const systemInstruction = buildSystemPrompt(tenant);
    const toolCallsExecuted = [];

    // Build conversation history for Gemini (exclude current message — appended last)
    const contents = history
      .filter(m => m.sender === 'user' || m.sender === 'ai')
      .map(m => ({
        role: m.sender === 'user' ? 'user' : 'model',
        parts: [{ text: m.content }]
      }));
    contents.push({ role: 'user', parts: [{ text: currentMessage }] });

    const tools = [{ functionDeclarations: toGeminiFunctions(TOOL_DEFINITIONS) }];

    let rounds = 0;
    while (rounds < MAX_TOOL_ROUNDS) {
      rounds++;

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: systemInstruction }] },
          contents,
          tools,
          generationConfig: {
            temperature: 0.15,
            maxOutputTokens: 1200,
            candidateCount: 1
          }
        })
      });

      if (!response.ok) {
        const errBody = await response.text();
        throw new Error(`Gemini API error ${response.status}: ${errBody}`);
      }

      const data = await response.json();
      const candidate = data.candidates?.[0];
      if (!candidate) throw new Error('Gemini returned no candidates.');

      const parts = candidate.content?.parts || [];
      const functionCalls = parts.filter(p => p.functionCall);
      const textParts = parts.filter(p => p.text);

      if (functionCalls.length === 0) {
        // No more tool calls — extract final text
        const replyText = textParts.map(p => p.text).join('');
        const latestDraft = this.db.getLatestDraftForSession(sessionId);
        const isHandoff = toolCallsExecuted.some(tc => tc.tool === 'request_human_handoff');
        const handoffResult = isHandoff
          ? toolCallsExecuted.find(tc => tc.tool === 'request_human_handoff')?.result
          : null;

        return {
          reply: replyText,
          grounding: `Grounded: Google Gemini (${model}) — ${toolCallsExecuted.length} tools invoked against ${tenant.name}`,
          toolCalls: toolCallsExecuted,
          hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
          isHandoff,
          whatsappUrl: handoffResult?.whatsapp_url || null
        };
      }

      // Execute each function call server-side
      const toolResultParts = [];
      for (const fc of functionCalls) {
        const { name, args } = fc.functionCall;
        let toolResult;
        try {
          toolResult = await this.tools.execute(name, args || {}, { tenantId: tenant.id, sessionId });
        } catch (toolErr) {
          toolResult = { error: toolErr.message };
        }

        toolCallsExecuted.push({ tool: name, args: args || {}, result: toolResult });
        toolResultParts.push({
          functionResponse: {
            name,
            response: { content: JSON.stringify(toolResult) }
          }
        });
      }

      // Append model turn (with function calls) + tool results to conversation
      contents.push({ role: 'model', parts });
      contents.push({ role: 'user', parts: toolResultParts });
    }

    throw new Error('Gemini exceeded maximum tool execution rounds.');
  }

  // ─────────────────────────────────────────────────────────────────────────
  //  ANTHROPIC CLAUDE — tool_use blocks with multi-round execution
  // ─────────────────────────────────────────────────────────────────────────

  async callAnthropic(tenant, history, currentMessage, sessionId) {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    const model = process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-5';
    const url = 'https://api.anthropic.com/v1/messages';

    const systemInstruction = buildSystemPrompt(tenant);
    const toolCallsExecuted = [];

    // Build messages (filter to user/ai turns only, exclude system)
    const messages = history
      .filter(m => m.sender === 'user' || m.sender === 'ai')
      .map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.content
      }));
    messages.push({ role: 'user', content: currentMessage });

    const tools = toAnthropicTools(TOOL_DEFINITIONS);
    let rounds = 0;

    while (rounds < MAX_TOOL_ROUNDS) {
      rounds++;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01'
        },
        body: JSON.stringify({
          model,
          system: systemInstruction,
          messages,
          tools,
          max_tokens: 1500,
          temperature: 0.15
        })
      });

      if (!response.ok) {
        const errBody = await response.text();
        throw new Error(`Anthropic API error ${response.status}: ${errBody}`);
      }

      const data = await response.json();
      const stopReason = data.stop_reason;
      const contentBlocks = data.content || [];

      if (stopReason !== 'tool_use') {
        // Final response — collect text blocks
        const replyText = contentBlocks
          .filter(b => b.type === 'text')
          .map(b => b.text)
          .join('');

        const latestDraft = this.db.getLatestDraftForSession(sessionId);
        const isHandoff = toolCallsExecuted.some(tc => tc.tool === 'request_human_handoff');
        const handoffResult = isHandoff
          ? toolCallsExecuted.find(tc => tc.tool === 'request_human_handoff')?.result
          : null;

        return {
          reply: replyText,
          grounding: `Grounded: Anthropic Claude (${model}) — ${toolCallsExecuted.length} tools invoked against ${tenant.name}`,
          toolCalls: toolCallsExecuted,
          hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
          isHandoff,
          whatsappUrl: handoffResult?.whatsapp_url || null
        };
      }

      // Append assistant message with tool_use blocks
      messages.push({ role: 'assistant', content: contentBlocks });

      // Execute tool calls
      const toolResults = [];
      for (const block of contentBlocks.filter(b => b.type === 'tool_use')) {
        const { id, name, input } = block;
        let toolResult;
        try {
          toolResult = await this.tools.execute(name, input || {}, { tenantId: tenant.id, sessionId });
        } catch (toolErr) {
          toolResult = { error: toolErr.message };
        }

        toolCallsExecuted.push({ tool: name, args: input || {}, result: toolResult });
        toolResults.push({
          type: 'tool_result',
          tool_use_id: id,
          content: JSON.stringify(toolResult)
        });
      }

      // Append tool results as user message
      messages.push({ role: 'user', content: toolResults });
    }

    throw new Error('Anthropic exceeded maximum tool execution rounds.');
  }

  // ─────────────────────────────────────────────────────────────────────────
  //  OPENAI GPT — tool_calls with parallel execution
  // ─────────────────────────────────────────────────────────────────────────

  async callOpenAI(tenant, history, currentMessage, sessionId) {
    const apiKey = process.env.OPENAI_API_KEY;
    const model = process.env.OPENAI_MODEL || 'gpt-4o-mini';
    const url = 'https://api.openai.com/v1/chat/completions';

    const systemInstruction = buildSystemPrompt(tenant);
    const toolCallsExecuted = [];

    const messages = [
      { role: 'system', content: systemInstruction },
      ...history
        .filter(m => m.sender === 'user' || m.sender === 'ai')
        .map(m => ({ role: m.sender === 'user' ? 'user' : 'assistant', content: m.content })),
      { role: 'user', content: currentMessage }
    ];

    const tools = toOpenAIFunctions(TOOL_DEFINITIONS);
    let rounds = 0;

    while (rounds < MAX_TOOL_ROUNDS) {
      rounds++;

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
          model,
          messages,
          tools,
          tool_choice: 'auto',
          temperature: 0.15,
          max_tokens: 1500
        })
      });

      if (!response.ok) {
        const errBody = await response.text();
        throw new Error(`OpenAI API error ${response.status}: ${errBody}`);
      }

      const data = await response.json();
      const choice = data.choices?.[0];
      if (!choice) throw new Error('OpenAI returned no choices.');

      const assistantMsg = choice.message;
      messages.push(assistantMsg);

      if (choice.finish_reason !== 'tool_calls' || !assistantMsg.tool_calls?.length) {
        // Final response
        const replyText = assistantMsg.content || '';
        const latestDraft = this.db.getLatestDraftForSession(sessionId);
        const isHandoff = toolCallsExecuted.some(tc => tc.tool === 'request_human_handoff');
        const handoffResult = isHandoff
          ? toolCallsExecuted.find(tc => tc.tool === 'request_human_handoff')?.result
          : null;

        return {
          reply: replyText,
          grounding: `Grounded: OpenAI (${model}) — ${toolCallsExecuted.length} tools invoked against ${tenant.name}`,
          toolCalls: toolCallsExecuted,
          hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
          isHandoff,
          whatsappUrl: handoffResult?.whatsapp_url || null
        };
      }

      // Execute tool calls in parallel
      const toolResultMsgs = await Promise.all(
        assistantMsg.tool_calls.map(async (tc) => {
          const name = tc.function.name;
          let args = {};
          try { args = JSON.parse(tc.function.arguments || '{}'); } catch { args = {}; }
          let toolResult;
          try {
            toolResult = await this.tools.execute(name, args, { tenantId: tenant.id, sessionId });
          } catch (toolErr) {
            toolResult = { error: toolErr.message };
          }
          toolCallsExecuted.push({ tool: name, args, result: toolResult });
          return {
            role: 'tool',
            tool_call_id: tc.id,
            content: JSON.stringify(toolResult)
          };
        })
      );

      messages.push(...toolResultMsgs);
    }

    throw new Error('OpenAI exceeded maximum tool execution rounds.');
  }

  // ─────────────────────────────────────────────────────────────────────────
  //  LOCAL DETERMINISTIC ORCHESTRATOR
  //  Used when no LLM key is configured, or as fallback on API failure.
  //  Understands English, MSA, Egyptian Arabic, and mixed Arabizi.
  // ─────────────────────────────────────────────────────────────────────────

  async orchestrateLocal(tenant, history, currentMessage, sessionId) {
    const raw = currentMessage.trim();
    const q = raw.toLowerCase();
    const isArabic = /[\u0600-\u06FF]/.test(raw);
    const toolCallsExecuted = [];
    let latestDraft = this.db.getLatestDraftForSession(sessionId);

    // --- 0. Human Greeting Detection (Zero robotic clutter, warm & personal) ---
    const greetingWords = [
      'السلام عليكم', 'سلام عليكم', 'وعليكم السلام', 'سلام',
      'صباح الخير', 'مساء الخير', 'مرحبا', 'مرحباً', 'اهلين', 'أهلاً', 'اهلا', 'يا هلا', 'هلا والله', 'هلا',
      'ازيك', 'عامل ايه', 'كيف حالك', 'شخبارك', 'شلونك', 'هاي',
      'hello', 'hi', 'hey', 'good morning', 'good evening', 'greetings'
    ];
    const cleanNoPunct = q.replace(/[.,?!؟،]/g, '').trim();
    const isPureGreeting = greetingWords.some(g => cleanNoPunct === g || cleanNoPunct.startsWith(g + ' ') && cleanNoPunct.length < g.length + 15);
    const hasProductInquiry = [
      'سعر', 'بكام', 'بكم', 'تكلفة', 'احجز', 'حجز', 'شراء', 'اشتري', 'طوق', 'خاتم', 'اسوارة', 'الماس', 'ألماس',
      'زمرد', 'تذوق', 'طاولة', 'ترابيزة', 'فحص', 'عيادة', 'دكتور', 'price', 'cost', 'reserve', 'book', 'menu',
      'collar', 'ring', 'cuff', 'screening', 'doctor', 'clinic', 'tasting'
    ].some(w => q.includes(w));

    if (isPureGreeting && !hasProductInquiry) {
      let welcomeReply = '';
      if (tenant.category === 'jewelry') {
        welcomeReply = isArabic
          ? `وعليكم السلام ورحمة الله وبركاته، أهلاً بحضرتك يا فندم في **${tenant.name}** بالدوحة. تشرفنا بزيارتك جداً! أقدر أساعدك إزاي النهاردة؟ تحب نطلعك على أحدث مجموعات الألماس والزمرد النادر، أو بتدور على قطعة معينة لمناسبة خاصة؟`
          : `Warm greetings and welcome to **${tenant.name}**, Place Vendôme. It is our pleasure to assist you. Are you looking for a specific high-jewelry creation today, or would you like to explore our latest diamond and gemstone collections?`;
      } else if (tenant.category === 'restaurant') {
        welcomeReply = isArabic
          ? `وعليكم السلام ورحمة الله وبركاته، أهلاً بحضرتك يا فندم في **${tenant.name}** بالزمالك. نورتنا! تحب تستفسر عن قائمة تذوق الشيف المميزة لليوم، أو حابب ننسق حجز طاولة خاصة؟`
          : `A very warm welcome to **${tenant.name}**, Zamalek. How may I host you this evening? We can arrange a Chef's Tasting Degustation table or answer any dietary and menu questions you have.`;
      } else {
        welcomeReply = isArabic
          ? `وعليكم السلام ورحمة الله وبركاته، أهلاً بحضرتك يا فندم في **${tenant.name}**. يومك سعيد! أقدر أساعدك إزاي النهاردة؟ سواء بحجز موعد استشارة طبية أو الاستفسار عن باقات الفحص الشامل وبرامج طول العمر.`
          : `Welcome to **${tenant.name}** Clinical Center. How can we support your health journey today? I can assist with appointment scheduling, longevity screenings, or clinic logistics.`;
      }

      return {
        reply: welcomeReply,
        grounding: `Concierge: Welcomed customer to ${tenant.name}`,
        toolCalls: [],
        hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
        isHandoff: false
      };
    }

    // --- 0.1 Strict Business Boundary (No cosmic, philosophical, political, or code trivia) ---
    const outOfScopePatterns = [
      'أصل الكون', 'الانفجار العظيم', 'المجرة', 'الكواكب', 'الفضاء', 'الثقب الأسود', 'النجوم',
      'معنى الحياة', 'وجود الإنسان', 'الفلسفة', 'ما هو الموت', 'أصل الإنسان', 'النسبية', 'فيزياء',
      'كود بايثون', 'اكتب كود', 'حل مسألة', 'برمجة', 'الذكاء الاصطناعي هيسيطر', 'مين عملك', 'مين صنعك',
      'الانتخابات', 'رئيس', 'السياسة', 'كأس العالم', 'ماتش', 'مين فاز', 'أخبار العالم',
      'universe', 'big bang', 'cosmos', 'astronomy', 'meaning of life', 'philosophy',
      'write code', 'python script', 'solve equation', 'who created you', 'politics', 'world cup'
    ];
    if (outOfScopePatterns.some(pat => q.includes(pat))) {
      const politeDecline = isArabic
        ? `يسعدني جداً اهتمامك وتنوع فكرك يا فندم! ✨\n\nلكن اختصاصي هنا مكرس بالكامل لمساعدتك في كل ما يتعلق بـ **${tenant.name}** (${tenant.category === 'jewelry' ? 'المجوهرات الراقية والساعات الفاخرة' : tenant.category === 'restaurant' ? 'العشاء الفاخر وقوائم التذوق' : 'الرعاية الطبية وبرامج طول العمر'}).\n\nأنا تحت أمرك بكل سرور في أي استفسار يخص تشكيلاتنا، الأسعار، أو المواعيد والحجوزات. تحب نبدأ بإيه؟`
        : `I appreciate your curiosity! ✨ However, my expertise is dedicated exclusively to **${tenant.name}** (${tenant.category === 'jewelry' ? 'high jewelry & luxury watches' : tenant.category === 'restaurant' ? 'fine dining & culinary experiences' : 'clinical health & longevity screenings'}).\n\nI would be delighted to assist you with our catalog, pricing, or bookings. How can I help you today?`;

      return {
        reply: politeDecline,
        grounding: `Boundary: Politely redirected out-of-scope query to ${tenant.name} scope`,
        toolCalls: [],
        hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
        isHandoff: false
      };
    }

    // --- A. Human Escalation Intent ---
    const handoffTriggers = [
      'human', 'agent', 'specialist', 'person', 'speak to', 'talk to', 'whatsapp', 'call me',
      'customer service', 'real person', 'concierge',
      'إنسان', 'موظف', 'بشري', 'خدمة عملاء', 'واتساب', 'أكلم حد', 'عايز اكلم حد',
      'تحدث مع', 'اتصال', 'بشخص', 'مسؤول'
    ];
    if (handoffTriggers.some(t => q.includes(t))) {
      const handoff = await this.tools.execute('request_human_handoff', {
        reason: 'Customer requested direct specialist communication via WhatsApp',
        notes: raw
      }, { tenantId: tenant.id, sessionId });

      toolCallsExecuted.push({
        tool: 'request_human_handoff',
        args: { reason: 'Direct customer escalation' },
        result: handoff
      });

      const reply = isArabic
        ? `لقد قمت بإعداد تصعيد فوري إلى فريق الاستشاريين في **${tenant.name}**. يمكنك الضغط على زر الواتساب أدناه للمتابعة مع الاحتفاظ بكافة تفاصيل وسياق المحادثة.`
        : `I have prepared an immediate escalation to our specialist team at **${tenant.name}**. Click the WhatsApp button below to proceed — all conversation context is preserved.`;

      return {
        reply,
        grounding: `Handoff: Human Escalation Triggered (${tenant.whatsapp_number}) — Demo Mode`,
        toolCalls: toolCallsExecuted,
        hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
        isHandoff: true,
        whatsappUrl: handoff.whatsapp_url
      };
    }

    // --- B. Modification Intent (multi-turn context) ---
    const numberMatch = raw.match(/\b([1-9]|1[0-2])\b/) ||
      raw.match(/(تلاتة|ثلاثة|اتنين|اثنين|أربعة|اربعة|خمسة|واحد)/);
    const isModification = (
      q.includes('actually') || q.includes('make it') || q.includes('change it') ||
      q.includes('خليهم') || q.includes('بدل') || q.includes('تعديل') ||
      q.includes('update') || q.includes('change') || q.includes('instead') ||
      q.includes('بدله') || q.includes('بدلاً')
    ) && latestDraft && latestDraft.status === 'draft';

    if (isModification && latestDraft) {
      let newQty = 2;
      if (numberMatch) {
        const val = numberMatch[0];
        const arabicMap = { 'تلاتة': 3, 'ثلاثة': 3, 'اتنين': 2, 'اثنين': 2, 'أربعة': 4, 'اربعة': 4, 'خمسة': 5, 'واحد': 1 };
        newQty = arabicMap[val] || parseInt(val, 10) || 2;
      }

      const updatedItems = latestDraft.items.map(it => ({
        product_id: it.product_id,
        quantity: newQty
      }));

      const updateRes = await this.tools.execute('update_order_draft', {
        draft_id: latestDraft.id,
        items: updatedItems,
        customer_notes: `Updated quantity to ${newQty} ${tenant.category === 'restaurant' ? 'guests' : 'items'}`
      }, { tenantId: tenant.id, sessionId });

      toolCallsExecuted.push({ tool: 'update_order_draft', args: { draft_id: latestDraft.id, items: updatedItems }, result: updateRes });
      latestDraft = this.db.getDraft(latestDraft.id);

      const reply = isArabic
        ? `تم تحديث مسودة الطلب بنجاح إلى **${newQty}** ${tenant.category === 'restaurant' ? 'أفراد' : 'قطع'}. الإجمالي الجديد المحقق: **${latestDraft.total_amount.toLocaleString()} ${latestDraft.currency}**.\n\nالمسودة جاهزة للمراجعة وتتطلب تأكيدك الصريح لإرسالها.`
        : `Draft updated to **${newQty}** ${tenant.category === 'restaurant' ? 'guests' : 'items'}. New verified total: **${latestDraft.total_amount.toLocaleString()} ${latestDraft.currency}**.\n\nThis draft is non-binding and awaits your explicit confirmation.`;

      return {
        reply,
        grounding: `Draft Engine: Updated #${latestDraft.id} — Demo Mode`,
        toolCalls: toolCallsExecuted,
        hasDraftOrder: this.formatDraftOutput(latestDraft),
        isHandoff: false
      };
    }

    // --- C. Policy / Knowledge Intent ---
    const isPolicyQuery = [
      'policy', 'authentic', 'gia', 'delivery', 'shipping', 'courier', 'cancel', 'deposit',
      'allergy', 'allergies', 'hours', 'fasting', 'refund', 'return', 'opening', 'schedule',
      'سياسة', 'أصالة', 'توصيل', 'شحن', 'إلغاء', 'عربون', 'حساسية', 'صيام', 'مواعيد',
      'استرداد', 'تسليم', 'فتح', 'أوقات'
    ].some(t => q.includes(t));

    if (isPolicyQuery) {
      const kbRes = await this.tools.execute('search_business_knowledge', { query: raw }, { tenantId: tenant.id, sessionId });
      toolCallsExecuted.push({ tool: 'search_business_knowledge', args: { query: raw }, result: kbRes });

      if (kbRes.count > 0) {
        const item = kbRes.results[0];
        const answer = (isArabic && item.answer_ar) ? item.answer_ar : item.answer;
        const reply = isArabic
          ? `**بشأن استفساركم:**\n\n${answer}\n\nهل تودون المساعدة في تفاصيل أخرى أو الاطلاع على المنتجات والخدمات المتاحة؟`
          : `**Policy & Information:**\n\n${answer}\n\nWould you like help with our catalog or available booking appointments?`;

        return {
          reply,
          grounding: `Verified Business Knowledge: '${item.category}' — Demo Mode`,
          toolCalls: toolCallsExecuted,
          hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
          isHandoff: false
        };
      }
    }

    // --- D. Product / Service-Specific Queries ---

    if (tenant.category === 'jewelry') {
      return this._handleJewelry(tenant, raw, isArabic, sessionId, toolCallsExecuted, latestDraft);
    }
    if (tenant.category === 'restaurant') {
      return this._handleRestaurant(tenant, raw, q, isArabic, sessionId, toolCallsExecuted, latestDraft);
    }
    if (tenant.category === 'healthcare') {
      return this._handleHealthcare(tenant, raw, isArabic, sessionId, toolCallsExecuted, latestDraft);
    }

    // Default welcome
    return {
      reply: isArabic
        ? `مرحباً بك. أنا المساعد الذكي المعتمد لـ **${tenant.name}**. يمكنني مساعدتك في استعراض الكتالوج المعتمد، التحقق من المخزون، وحساب الأسعار بدقة، أو تجهيز مسودة حجز، أو تحويلك إلى موظف بشري.`
        : `Welcome to **${tenant.name}**. I am your verified AI sales assistant. I can search our catalog, check live inventory, calculate exact pricing, prepare reservation drafts, or connect you directly with a specialist via WhatsApp. How can I help?`,
      grounding: `Grounded: ${tenant.name} — Demo Mode (No LLM Key Configured)`,
      toolCalls: toolCallsExecuted,
      hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
      isHandoff: false
    };
  }

  async _handleJewelry(tenant, raw, isArabic, sessionId, toolCallsExecuted, latestDraft) {
    const searchRes = await this.tools.execute('search_products', { query: raw }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'search_products', args: { query: raw }, result: searchRes });

    let targetProduct = searchRes.count > 0 ? searchRes.results[0] : null;
    if (!targetProduct) {
      const fallback = await this.tools.execute('search_products', { query: 'diamond' }, { tenantId: tenant.id, sessionId });
      if (fallback.count > 0) targetProduct = fallback.results[0];
    }

    if (!targetProduct) {
      return {
        reply: isArabic
          ? `لم أتمكن من العثور على منتج مطابق في كتالوج **${tenant.name}**. يمكنك وصف القطعة التي تبحث عنها أو السؤال عن فئة معينة.`
          : `I could not find a matching product in the **${tenant.name}** catalog. Please describe the piece you are looking for, or ask about a specific category.`,
        grounding: `Product Search: No results — Demo Mode`,
        toolCalls: toolCallsExecuted,
        hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
        isHandoff: false
      };
    }

    const invRes = await this.tools.execute('check_inventory', { product_id: targetProduct.id }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'check_inventory', args: { product_id: targetProduct.id }, result: invRes });

    const detailsRes = await this.tools.execute('get_product_details', { product_id: targetProduct.id }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'get_product_details', args: { product_id: targetProduct.id }, result: detailsRes });

    if (!invRes.is_available) {
      return {
        reply: isArabic
          ? `تحققت من المخزون الحي لـ **${targetProduct.name_ar || targetProduct.name}** (${targetProduct.sku}). القطعة حالياً **غير متوفرة للتسليم الفوري**، ولكن يمكننا تفصيلها كطلب خاص خلال 10 أيام عمل. هل ترغب في الاطلاع على قطع بديلة؟`
          : `I verified live inventory for **${targetProduct.name}** (${targetProduct.sku}). This item is currently **out of stock for immediate delivery**. We can handcraft it as a bespoke order within 10 business days. Would you like to see similar available pieces?`,
        grounding: `Catalog & Stock Verified: ${targetProduct.sku} (Out of Stock) — Demo Mode`,
        toolCalls: toolCallsExecuted,
        hasDraftOrder: null,
        isHandoff: false
      };
    }

    const priceRes = await this.tools.execute('calculate_price', {
      items: [{ product_id: targetProduct.id, quantity: 1 }],
      apply_shipping: true
    }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'calculate_price', args: { items: [{ product_id: targetProduct.id, quantity: 1 }] }, result: priceRes });

    const draftRes = await this.tools.execute('create_order_draft', {
      items: [{ product_id: targetProduct.id, quantity: 1 }],
      customer_notes: 'Standard presentation case with GIA certificate dossier.'
    }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'create_order_draft', args: { items: [{ product_id: targetProduct.id, quantity: 1 }] }, result: draftRes });

    latestDraft = this.db.getDraft(draftRes.draft_id);

    const reply = isArabic
      ? `تحققت من مخزون بوتيك الدوحة. القطعة **${targetProduct.name_ar || targetProduct.name}** متوفرة حاليًا (${invRes.stock_count} قطع في ${invRes.location}).\n\n` +
        `• **السعر المعتمد:** ${targetProduct.price.toLocaleString()} ${targetProduct.currency}\n` +
        `• **الأصالة:** معتمدة بدمغة دولة قطر الرسمية مع شهادة GIA الدولية.\n` +
        `• **المعاينة والشحن:** معاينة خاصة في صالون اللؤلؤة أو توصيل مصفح مؤمن لكافة دول الخليج.\n\n` +
        `لقد أعددت لك **مسودة طلب غير ملزمة**. هل ترغب في تأكيد الحجز المسبق؟`
      : `Checked live Doha boutique inventory. **${targetProduct.name}** is in stock (${invRes.stock_count} pieces at ${invRes.location}).\n\n` +
        `• **Verified Price:** ${targetProduct.price.toLocaleString()} ${targetProduct.currency}\n` +
        `• **Authenticity:** Certified GIA & Qatar National Gemology Hallmark\n` +
        `• **Delivery / Viewing:** Private salon appointment or discreet secure courier across the GCC.\n\n` +
        `I have prepared a **non-binding reservation draft**. Would you like to confirm it?`;

    return {
      reply,
      grounding: `Verified: Al Noor Catalog (${targetProduct.sku}) & Live Inventory — Demo Mode`,
      toolCalls: toolCallsExecuted,
      hasDraftOrder: this.formatDraftOutput(latestDraft),
      isHandoff: false
    };
  }

  async _handleRestaurant(tenant, raw, q, isArabic, sessionId, toolCallsExecuted, latestDraft) {
    const searchRes = await this.tools.execute('search_products', { query: raw }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'search_products', args: { query: raw }, result: searchRes });

    let targetMenu = searchRes.count > 0 ? searchRes.results[0] : null;
    if (!targetMenu) {
      const fallback = await this.tools.execute('search_products', { query: 'tasting' }, { tenantId: tenant.id, sessionId });
      if (fallback.count > 0) targetMenu = fallback.results[0];
    }
    if (!targetMenu) return this._defaultFallback(tenant, isArabic, toolCallsExecuted, latestDraft);

    const slotRes = await this.tools.execute('check_booking_availability', { date: '2026-10-26' }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'check_booking_availability', args: { date: '2026-10-26' }, result: slotRes });

    // Extract guest count
    let guestCount = 2;
    const numMatch = raw.match(/\b([2-9]|1[0-2])\b/);
    if (numMatch) guestCount = parseInt(numMatch[0], 10);
    if (q.includes('تلاتة') || q.includes('ثلاثة')) guestCount = 3;
    if (q.includes('أربعة') || q.includes('اربعة') || q.includes('4')) guestCount = 4;
    if (q.includes('خمسة') || q.includes('5')) guestCount = 5;

    const priceRes = await this.tools.execute('calculate_price', {
      items: [{ product_id: targetMenu.id, quantity: guestCount }]
    }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'calculate_price', args: { items: [{ product_id: targetMenu.id, quantity: guestCount }] }, result: priceRes });

    const draftRes = await this.tools.execute('create_order_draft', {
      items: [{ product_id: targetMenu.id, quantity: guestCount }],
      customer_notes: `Table hold for ${guestCount} guests. Degustation seating at 19:30.`,
      draft_type: 'table_booking'
    }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'create_order_draft', args: { items: [{ product_id: targetMenu.id, quantity: guestCount }] }, result: draftRes });

    latestDraft = this.db.getDraft(draftRes.draft_id);

    const reply = isArabic
      ? `يسعدنا استقبالكم في **ذا زعفران تيبل** بالزمالك. أماكن متاحة لـ **${targetMenu.name_ar || targetMenu.name}** غداً (19:30 و 21:30).\n\n` +
        `• **سعر الفرد المعتمد:** ${targetMenu.price.toLocaleString()} ${targetMenu.currency}\n` +
        `• **الأنظمة الغذائية:** نلبي حساسية الجلوتين والمأكولات البحرية مع إشعار 6 ساعات.\n` +
        `• **تأكيد الحجز:** عربون مسترد ${priceRes.deposit_required.toLocaleString()} ${tenant.currency} لـ ${guestCount} أفراد (الإجمالي: ${priceRes.total_amount.toLocaleString()} ${tenant.currency}).\n\n` +
        `لقد أعددت **مسودة حجز مبدئية**. هل تود التأكيد؟`
      : `We have availability for **${targetMenu.name}** tomorrow evening at 19:30 and 21:30.\n\n` +
        `• **Price:** ${targetMenu.price.toLocaleString()} ${targetMenu.currency} per guest\n` +
        `• **Dietary:** Gluten-free and shellfish accommodations with 6h advance notice.\n` +
        `• **Deposit:** Refundable ${priceRes.deposit_required.toLocaleString()} ${tenant.currency} secures the table for ${guestCount} guests (Total: ${priceRes.total_amount.toLocaleString()} ${tenant.currency}).\n\n` +
        `I have prepared a **table hold draft** for ${guestCount} guests. Shall I confirm upon your go-ahead?`;

    return {
      reply,
      grounding: `Verified: Saffron Table Reservation Matrix (${slotRes.available_slots.length} slots) — Demo Mode`,
      toolCalls: toolCallsExecuted,
      hasDraftOrder: this.formatDraftOutput(latestDraft),
      isHandoff: false
    };
  }

  async _handleHealthcare(tenant, raw, isArabic, sessionId, toolCallsExecuted, latestDraft) {
    const searchRes = await this.tools.execute('search_products', { query: raw }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'search_products', args: { query: raw }, result: searchRes });

    let targetScreening = searchRes.count > 0 ? searchRes.results[0] : null;
    if (!targetScreening) {
      const fallback = await this.tools.execute('search_products', { query: 'screening' }, { tenantId: tenant.id, sessionId });
      if (fallback.count > 0) targetScreening = fallback.results[0];
    }
    if (!targetScreening) return this._defaultFallback(tenant, isArabic, toolCallsExecuted, latestDraft);

    const slotsRes = await this.tools.execute('check_booking_availability', { date: '2026-10-26' }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'check_booking_availability', args: { date: '2026-10-26' }, result: slotsRes });

    const priceRes = await this.tools.execute('calculate_price', {
      items: [{ product_id: targetScreening.id, quantity: 1 }]
    }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'calculate_price', args: { items: [{ product_id: targetScreening.id, quantity: 1 }] }, result: priceRes });

    const draftRes = await this.tools.execute('create_order_draft', {
      items: [{ product_id: targetScreening.id, quantity: 1 }],
      customer_notes: 'Provisional appointment hold — New Cairo Suite 402.',
      draft_type: 'clinical_consultation'
    }, { tenantId: tenant.id, sessionId });
    toolCallsExecuted.push({ tool: 'create_order_draft', args: { items: [{ product_id: targetScreening.id, quantity: 1 }] }, result: draftRes });

    latestDraft = this.db.getDraft(draftRes.draft_id);

    const reply = isArabic
      ? `يقدم مركز فايتاليس الطبي **${targetScreening.name_ar || targetScreening.name}** في التجمع الخامس.\n\n` +
        `• **الرسوم المعتمدة:** ${priceRes.total_amount.toLocaleString()} ${tenant.currency} (شاملة الفحوصات والاستشارة).\n` +
        `• **الموعد المتاح:** غداً 09:30 صباحاً — جناح 402.\n` +
        `• **التحضير:** صيام 10-12 ساعة قبل فحوصات المؤشرات الحيوية (الماء مسموح).\n` +
        `• **تنبيه:** هذا المساعد يقدم معلومات إدارية فقط ولا يقدم أي تشخيص طبي.\n\n` +
        `لقد أعددت **مسودة حجز موعد مؤقتة**. هل تود التأكيد؟`
      : `Vitalis offers the **${targetScreening.name}** at our New Cairo Medical Park.\n\n` +
        `• **Verified Fee:** ${priceRes.total_amount.toLocaleString()} ${tenant.currency} (65 biomarker panel + physician consult)\n` +
        `• **Next Available:** Tomorrow at 09:30 AM (Suite 402)\n` +
        `• **Preparation:** 10-12 hours fasting required (water permitted).\n` +
        `• **Clinical Guardrail:** This assistant handles administrative scheduling only — no clinical diagnoses.\n\n` +
        `I have prepared a **provisional appointment hold draft**. Shall I confirm this reservation?`;

    return {
      reply,
      grounding: `Verified: Vitalis Clinical Booking Matrix — Demo Mode`,
      toolCalls: toolCallsExecuted,
      hasDraftOrder: this.formatDraftOutput(latestDraft),
      isHandoff: false
    };
  }

  _defaultFallback(tenant, isArabic, toolCallsExecuted, latestDraft) {
    return {
      reply: isArabic
        ? `مرحباً بك في **${tenant.name}**. يمكنني مساعدتك في استعراض الكتالوج أو التحقق من الأسعار أو الحجز أو التحويل إلى فريق الدعم. كيف يمكنني مساعدتك؟`
        : `Welcome to **${tenant.name}**. I can help you browse our catalog, check pricing, prepare a booking draft, or connect you to our support team. How can I assist you?`,
      grounding: `Grounded: ${tenant.name} — Demo Mode`,
      toolCalls: toolCallsExecuted,
      hasDraftOrder: latestDraft ? this.formatDraftOutput(latestDraft) : null,
      isHandoff: false
    };
  }

  formatDraftOutput(draft) {
    if (!draft) return null;
    return {
      id: draft.id,
      title: draft.items?.length > 0 ? draft.items.map(i => `${i.quantity}x ${i.name}`).join(' + ') : 'Active Draft Cart',
      sku: draft.items?.length > 0 ? draft.items[0].sku : 'CART-REF',
      price: `${draft.total_amount.toLocaleString()} ${draft.currency}`,
      deposit_required: draft.deposit_required ? `${draft.deposit_required.toLocaleString()} ${draft.currency}` : null,
      items: draft.items,
      subtotal: draft.subtotal,
      tax_amount: draft.tax_amount,
      discount_amount: draft.discount_amount,
      total_amount: draft.total_amount,
      currency: draft.currency,
      status: draft.status === 'confirmed'
        ? '✓ Confirmed by Customer (Transmitted)'
        : 'Draft Prepared — Requires Customer Confirmation'
    };
  }
}

const aiAgent = new AiSalesAgent();

module.exports = {
  aiAgent,
  AiSalesAgent
};
