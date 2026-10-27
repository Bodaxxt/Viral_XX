/**
 * Viral-X Server-Side Typed Tool Registry
 * Deterministic business logic, inventory verification, pricing engine, and draft lifecycle.
 */

const { dbManager } = require('../db/database');
const { integrationRegistry } = require('../adapters/externalIntegrations');
const { BI_EVENT_TYPES } = require('../analytics/telemetryService');

const TOOL_DEFINITIONS = [
  {
    name: 'search_products',
    description: 'Search products or service packages by keyword, category, or maximum budget within the current business tenant.',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search term (e.g. emerald, diamond, tasting menu, screening)' },
        category: { type: 'string', description: 'Product or service category' },
        max_budget: { type: 'number', description: 'Maximum price/budget filter' }
      }
    }
  },
  {
    name: 'get_product_details',
    description: 'Retrieve verified detailed product or service information, including metal specifications, carats, course lists, or fasting guidelines.',
    parameters: {
      type: 'object',
      properties: {
        product_id: { type: 'string', description: 'Product ID or SKU (e.g. J-101, R-201, H-301)' }
      },
      required: ['product_id']
    }
  },
  {
    name: 'check_inventory',
    description: 'Check verified live inventory, stock count, and location from the database or connected ERP/e-commerce system.',
    parameters: {
      type: 'object',
      properties: {
        product_id: { type: 'string', description: 'Product ID or SKU to check' }
      },
      required: ['product_id']
    }
  },
  {
    name: 'calculate_price',
    description: 'Deterministically calculate subtotal, discounts, taxes, deposits, and total amount using explicit business rules. Never calculate prices in prompt text.',
    parameters: {
      type: 'object',
      properties: {
        items: {
          type: 'array',
          description: 'List of items to price',
          items: {
            type: 'object',
            properties: {
              product_id: { type: 'string' },
              quantity: { type: 'integer', minimum: 1 }
            },
            required: ['product_id', 'quantity']
          }
        },
        discount_code: { type: 'string', description: 'Optional promo or discount code' },
        apply_shipping: { type: 'boolean', description: 'Whether GCC courier shipping applies (jewelry)' }
      },
      required: ['items']
    }
  },
  {
    name: 'search_business_knowledge',
    description: 'Search official business policies, FAQs, delivery terms, opening hours, allergy accommodation, and medical disclaimers.',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search term regarding policies, hours, delivery, allergies' },
        category: { type: 'string', description: 'Category: policy, delivery, hours, authenticity, allergies, preparation' }
      },
      required: ['query']
    }
  },
  {
    name: 'check_booking_availability',
    description: 'Query verified available booking and reservation time slots for dining or clinic appointments.',
    parameters: {
      type: 'object',
      properties: {
        date: { type: 'string', description: 'Date in YYYY-MM-DD format (e.g. 2026-10-26)' },
        service_type: { type: 'string', description: 'Service or menu type' }
      }
    }
  },
  {
    name: 'create_order_draft',
    description: 'Create a stateful, non-binding order draft or booking hold. Does NOT execute a live transaction or charge the customer.',
    parameters: {
      type: 'object',
      properties: {
        items: {
          type: 'array',
          description: 'Items or services to include',
          items: {
            type: 'object',
            properties: {
              product_id: { type: 'string' },
              quantity: { type: 'integer', minimum: 1 }
            },
            required: ['product_id', 'quantity']
          }
        },
        customer_notes: { type: 'string', description: 'Special customer requests, allergies, or ring size' },
        draft_type: { type: 'string', enum: ['product_order', 'table_booking', 'clinical_consultation'] }
      },
      required: ['items']
    }
  },
  {
    name: 'update_order_draft',
    description: 'Modify an existing order draft (adjust quantities, add/remove items, update customer notes) without losing context.',
    parameters: {
      type: 'object',
      properties: {
        draft_id: { type: 'string', description: 'ID of the existing draft to modify' },
        items: {
          type: 'array',
          description: 'Updated complete list of items',
          items: {
            type: 'object',
            properties: {
              product_id: { type: 'string' },
              quantity: { type: 'integer' }
            },
            required: ['product_id', 'quantity']
          }
        },
        customer_notes: { type: 'string' }
      },
      required: ['draft_id', 'items']
    }
  },
  {
    name: 'get_order_draft',
    description: 'Retrieve the verified status and breakdown of the current order draft.',
    parameters: {
      type: 'object',
      properties: {
        draft_id: { type: 'string', description: 'Draft ID to inspect' }
      },
      required: ['draft_id']
    }
  },
  {
    name: 'request_human_handoff',
    description: 'Escalate the conversation to a human specialist via WhatsApp with a structured conversation summary and draft state.',
    parameters: {
      type: 'object',
      properties: {
        reason: { type: 'string', description: 'Reason for handoff (e.g. bespoke customization, VIP concierge, medical triage)' },
        notes: { type: 'string', description: 'Relevant context from the conversation' }
      },
      required: ['reason']
    }
  }
];

class ToolExecutor {
  constructor(db = dbManager, integrations = integrationRegistry) {
    this.db = db;
    this.integrations = integrations;
  }

  getToolDefinitions() {
    return TOOL_DEFINITIONS;
  }

  async execute(toolName, args, context = {}) {
    const { tenantId, sessionId } = context;
    if (!tenantId) {
      throw new Error('Tenant context is required to execute tools.');
    }

    try {
      switch (toolName) {
        case 'search_products':
          return this.searchProducts(tenantId, args, context);

        case 'get_product_details':
          return this.getProductDetails(tenantId, args, context);

        case 'check_inventory':
          return this.checkInventory(tenantId, args, context);

        case 'calculate_price':
          return this.calculatePrice(tenantId, args, context);

        case 'search_business_knowledge':
          return this.searchKnowledge(tenantId, args, context);

        case 'check_booking_availability':
          return this.checkBookingAvailability(tenantId, args, context);

        case 'create_order_draft':
          return this.createOrderDraft(tenantId, sessionId, args, context);

        case 'update_order_draft':
          return this.updateOrderDraft(tenantId, args, context);

        case 'get_order_draft':
          return this.getOrderDraft(tenantId, args, context);

        case 'request_human_handoff':
          return this.requestHumanHandoff(tenantId, sessionId, args, context);

        default:
          throw new Error(`Unknown tool: ${toolName}`);
      }
    } catch (err) {
      if (this.db && this.db.telemetry) {
        try {
          this.db.telemetry.recordEvent({
            tenantId,
            sessionId: sessionId || null,
            eventType: BI_EVENT_TYPES.TOOL_EXECUTION_FAILED,
            category: 'tool_execution',
            outcome: 'failure',
            metadata: {
              tool: toolName,
              error: err.message
            }
          });
        } catch {
          // non-fatal telemetry failure
        }
      }
      throw err;
    }
  }

  // --- Tool Implementations ---

  searchProducts(tenantId, { query, category, max_budget }, context = {}) {
    const products = this.db.searchProducts(tenantId, query, category, max_budget);

    if (this.db && this.db.telemetry) {
      try {
        this.db.telemetry.recordEvent({
          tenantId,
          sessionId: context.sessionId || null,
          eventType: BI_EVENT_TYPES.PRODUCT_SEARCH,
          category: category || 'catalog_search',
          outcome: products.length > 0 ? 'success' : 'no_results',
          metadata: {
            query: query || '',
            category: category || null,
            max_budget: max_budget || null,
            results_count: products.length
          }
        });
      } catch (e) {
        // non-fatal telemetry error
      }

      if (products.length === 0 && (query || category)) {
        try {
          this.db.telemetry.recordEvent({
            tenantId,
            sessionId: context.sessionId || null,
            eventType: BI_EVENT_TYPES.UNFULFILLED_DEMAND,
            category: category || 'catalog_demand',
            outcome: 'unfulfilled',
            metadata: {
              query: query || '',
              category: category || null,
              reason: 'zero_matches'
            }
          });
        } catch (e) {
          // non-fatal
        }
      }
    }

    return {
      count: products.length,
      tenant_id: tenantId,
      results: products.map(p => ({
        id: p.id,
        sku: p.sku,
        name: p.name,
        name_ar: p.name_ar,
        category: p.category,
        price: p.base_price,
        currency: p.currency,
        in_stock: p.stock_count > 0,
        stock_available: p.stock_count,
        location: p.inventory_location
      }))
    };
  }

  getProductDetails(tenantId, { product_id }) {
    const product = this.db.getProductById(tenantId, product_id);
    if (!product) {
      return { found: false, error: `Product or service '${product_id}' was not found in ${tenantId} catalog.` };
    }
    return {
      found: true,
      product: {
        id: product.id,
        sku: product.sku,
        name: product.name,
        name_ar: product.name_ar,
        category: product.category,
        base_price: product.base_price,
        currency: product.currency,
        description: product.description,
        description_ar: product.description_ar,
        attributes: product.attributes || {},
        stock_count: product.stock_count,
        location: product.inventory_location
      }
    };
  }

  checkInventory(tenantId, { product_id }, context = {}) {
    const inv = this.db.getInventory(tenantId, product_id);
    if (!inv) {
      if (this.db && this.db.telemetry) {
        try {
          this.db.telemetry.recordEvent({
            tenantId,
            sessionId: context.sessionId || null,
            eventType: BI_EVENT_TYPES.UNFULFILLED_DEMAND,
            category: 'inventory',
            productId: product_id,
            outcome: 'not_found',
            metadata: { product_id, reason: 'missing_inventory_record' }
          });
        } catch (e) {}
      }
      return { found: false, error: `No inventory record for '${product_id}' in tenant ${tenantId}.` };
    }

    const tenant = this.db.getTenant(tenantId);
    const availableToSell = Math.max(0, inv.stock_count - inv.reserved_count);
    const isAvailable = availableToSell > 0;

    if (!isAvailable && this.db && this.db.telemetry) {
      try {
        this.db.telemetry.recordEvent({
          tenantId,
          sessionId: context.sessionId || null,
          eventType: BI_EVENT_TYPES.OUT_OF_STOCK_DETECTED,
          category: 'inventory',
          productId: inv.product_id,
          sku: inv.sku,
          outcome: 'out_of_stock',
          metadata: {
            name: inv.name,
            stock_count: inv.stock_count,
            reserved_count: inv.reserved_count,
            location: inv.location
          }
        });
      } catch (e) {}
    }

    return {
      found: true,
      product_id: inv.product_id,
      name: inv.name,
      sku: inv.sku,
      stock_count: inv.stock_count,
      reserved_count: inv.reserved_count,
      available_to_sell: availableToSell,
      is_available: isAvailable,
      location: inv.location,
      tenant_mode: tenant.integration_mode,
      verified_source: tenant.integration_mode === 'live' ? 'Live ERP Sync' : 'Verified Local Catalog Database'
    };
  }

  calculatePrice(tenantId, { items, discount_code, apply_shipping }) {
    if (!items || !items.length) {
      throw new Error('Items array is required for price calculation.');
    }

    const tenant = this.db.getTenant(tenantId);
    let subtotal = 0;
    const validatedItems = [];

    for (const item of items) {
      if (!item.quantity || item.quantity <= 0) continue;
      const product = this.db.getProductById(tenantId, item.product_id);
      if (!product) {
        throw new Error(`Invalid item: '${item.product_id}' does not exist.`);
      }

      const itemSubtotal = product.base_price * item.quantity;
      subtotal += itemSubtotal;
      validatedItems.push({
        product_id: product.id,
        sku: product.sku,
        name: product.name,
        name_ar: product.name_ar,
        unit_price: product.base_price,
        quantity: item.quantity,
        total: itemSubtotal,
        currency: product.currency
      });
    }

    // Explicit business rules per tenant
    let discountAmount = 0;
    if (discount_code && discount_code.trim().toUpperCase() === 'VIRALX10') {
      discountAmount = Math.round(subtotal * 0.10); // 10% promotional discount
    }

    let taxAmount = 0;
    let depositRequired = 0;
    let shippingFee = 0;

    if (tenant.category === 'jewelry') {
      // In Doha jewelry: 0% sales tax, insured courier free over 20,000 QAR or 250 QAR
      if (apply_shipping && subtotal < 20000) {
        shippingFee = 250;
      }
      taxAmount = 0;
    } else if (tenant.category === 'restaurant') {
      // Cairo Fine Dining: 14% VAT + 12% Service fee for seated dining
      // Deposit required: 500 EGP per guest for tasting menus
      const totalGuests = validatedItems.reduce((acc, it) => acc + it.quantity, 0);
      depositRequired = totalGuests * 500;
      taxAmount = Math.round(subtotal * 0.14);
    } else if (tenant.category === 'healthcare') {
      // Healthcare: 14% Clinical administration VAT
      taxAmount = Math.round(subtotal * 0.14);
    }

    const totalAmount = subtotal - discountAmount + taxAmount + shippingFee;

    return {
      subtotal,
      discount_code: discount_code || null,
      discount_amount: discountAmount,
      tax_amount: taxAmount,
      deposit_required: depositRequired,
      shipping_fee: shippingFee,
      total_amount: totalAmount,
      currency: tenant.currency,
      items: validatedItems,
      breakdown_summary: `Subtotal: ${subtotal.toLocaleString()} ${tenant.currency}` +
        (discountAmount > 0 ? ` | Discount (-10%): -${discountAmount.toLocaleString()} ${tenant.currency}` : '') +
        (taxAmount > 0 ? ` | Tax/VAT: +${taxAmount.toLocaleString()} ${tenant.currency}` : '') +
        (depositRequired > 0 ? ` | Deposit Required: ${depositRequired.toLocaleString()} ${tenant.currency}` : '') +
        (shippingFee > 0 ? ` | Insured Courier: +${shippingFee} ${tenant.currency}` : '') +
        ` | Final Total: ${totalAmount.toLocaleString()} ${tenant.currency}`
    };
  }

  searchKnowledge(tenantId, { query, category }, context = {}) {
    const records = this.db.searchKnowledge(tenantId, query, category);

    if (records.length === 0 && query && this.db && this.db.telemetry) {
      try {
        this.db.telemetry.recordEvent({
          tenantId,
          sessionId: context.sessionId || null,
          eventType: BI_EVENT_TYPES.UNANSWERED_QUESTION,
          category: category || 'knowledge_base',
          outcome: 'unanswered',
          metadata: {
            query: String(query).substring(0, 300),
            category: category || null
          }
        });
      } catch (e) {}
    }

    return {
      count: records.length,
      tenant_id: tenantId,
      results: records.map(r => ({
        id: r.id,
        category: r.category,
        question: r.question,
        question_ar: r.question_ar,
        answer: r.answer,
        answer_ar: r.answer_ar
      }))
    };
  }

  checkBookingAvailability(tenantId, { date, service_type }) {
    const slots = this.db.getBookingSlots(tenantId, date, service_type);
    return {
      tenant_id: tenantId,
      date_queried: date || 'all_upcoming',
      available_slots: slots.filter(s => s.status === 'available').map(s => ({
        slot_id: s.id,
        date: s.slot_date,
        time: s.slot_time,
        service: s.service_type,
        remaining_capacity: s.capacity - s.booked_count
      })),
      total_found: slots.length
    };
  }

  createOrderDraft(tenantId, sessionId, { items, customer_notes, draft_type }) {
    const tenant = this.db.getTenant(tenantId);
    const pricing = this.calculatePrice(tenantId, { items });

    // Validate inventory availability
    for (const item of pricing.items) {
      const inv = this.db.getInventory(tenantId, item.product_id);
      if (inv && inv.stock_count < item.quantity) {
        if (this.db && this.db.telemetry) {
          try {
            this.db.telemetry.recordEvent({
              tenantId,
              sessionId,
              eventType: BI_EVENT_TYPES.OUT_OF_STOCK_DETECTED,
              category: 'drafting',
              productId: item.product_id,
              sku: item.sku,
              outcome: 'insufficient_stock',
              metadata: {
                requested_quantity: item.quantity,
                available_stock: inv.stock_count
              }
            });
          } catch (e) {}
        }
        return {
          success: false,
          error: `Item '${item.name}' cannot be drafted. Insufficient stock (Requested: ${item.quantity}, In stock: ${inv.stock_count}).`,
          available_stock: inv.stock_count
        };
      }
    }

    const draftId = `DRF-${tenant.category.substring(0, 3).toUpperCase()}-${Date.now().toString(36).toUpperCase()}`;
    // Ensure session exists to satisfy foreign key constraints
    if (sessionId) {
      this.db.getOrCreateSession(sessionId, tenantId);
    }
    const draft = {
      id: draftId,
      session_id: sessionId,
      tenant_id: tenantId,
      status: 'draft',
      draft_type: draft_type || (tenant.category === 'restaurant' ? 'table_booking' : 'product_order'),
      items: pricing.items,
      subtotal: pricing.subtotal,
      discount_amount: pricing.discount_amount,
      tax_amount: pricing.tax_amount,
      deposit_required: pricing.deposit_required,
      total_amount: pricing.total_amount,
      currency: tenant.currency,
      customer_notes: customer_notes || '',
      idempotency_key: `IDEMP-${draftId}`
    };

    const saved = this.db.saveDraft(draft);
    this.db.logAudit(tenantId, sessionId, 'DRAFT_CREATED', 'ai_agent', {
      draft_id: draftId,
      total_amount: draft.total_amount,
      currency: draft.currency
    });

    if (this.db && this.db.telemetry) {
      try {
        this.db.telemetry.recordEvent({
          tenantId,
          sessionId,
          eventType: BI_EVENT_TYPES.DRAFT_CREATED,
          category: draft.draft_type,
          draftId: draftId,
          outcome: 'draft_prepared',
          metadata: {
            total_amount: draft.total_amount,
            currency: draft.currency,
            items_count: draft.items.length,
            deposit_required: draft.deposit_required
          }
        });
      } catch (e) {}
    }

    return {
      success: true,
      draft_id: draftId,
      status: 'draft_prepared',
      total_amount: draft.total_amount,
      currency: draft.currency,
      deposit_required: draft.deposit_required,
      items: draft.items,
      customer_notes: draft.customer_notes,
      confirmation_prompt: 'Draft cart created and verified against catalog & inventory. Requires explicit customer confirmation to proceed.'
    };
  }

  updateOrderDraft(tenantId, { draft_id, items, customer_notes }, context = {}) {
    const existing = this.db.getDraft(draft_id);
    if (!existing) {
      return { success: false, error: `Draft ${draft_id} not found.` };
    }
    if (existing.tenant_id !== tenantId) {
      return { success: false, error: 'Unauthorized: draft belongs to another workspace.' };
    }
    if (existing.status !== 'draft') {
      return { success: false, error: `Cannot modify draft in status: ${existing.status}.` };
    }

    const pricing = this.calculatePrice(tenantId, { items });

    // Validate inventory for updated items
    for (const item of pricing.items) {
      const inv = this.db.getInventory(tenantId, item.product_id);
      if (inv && inv.stock_count < item.quantity) {
        if (this.db && this.db.telemetry) {
          try {
            this.db.telemetry.recordEvent({
              tenantId,
              sessionId: existing.session_id,
              eventType: BI_EVENT_TYPES.OUT_OF_STOCK_DETECTED,
              category: 'draft_update',
              productId: item.product_id,
              sku: item.sku,
              outcome: 'insufficient_stock',
              metadata: {
                requested_quantity: item.quantity,
                available_stock: inv.stock_count
              }
            });
          } catch (e) {}
        }
        return {
          success: false,
          error: `Item '${item.name}' insufficient stock (Requested: ${item.quantity}, Available: ${inv.stock_count}).`
        };
      }
    }

    existing.items = pricing.items;
    existing.subtotal = pricing.subtotal;
    existing.discount_amount = pricing.discount_amount;
    existing.tax_amount = pricing.tax_amount;
    existing.deposit_required = pricing.deposit_required;
    existing.total_amount = pricing.total_amount;
    if (customer_notes !== undefined) existing.customer_notes = customer_notes;

    const updated = this.db.saveDraft(existing);

    if (this.db && this.db.telemetry) {
      try {
        this.db.telemetry.recordEvent({
          tenantId,
          sessionId: existing.session_id,
          eventType: BI_EVENT_TYPES.DRAFT_UPDATED,
          category: existing.draft_type,
          draftId: updated.id,
          outcome: 'draft_updated',
          metadata: {
            total_amount: updated.total_amount,
            currency: updated.currency,
            items_count: updated.items.length
          }
        });
      } catch (e) {}
    }

    return {
      success: true,
      draft_id: updated.id,
      status: updated.status,
      total_amount: updated.total_amount,
      currency: updated.currency,
      items: updated.items,
      customer_notes: updated.customer_notes
    };
  }

  getOrderDraft(tenantId, { draft_id }) {
    const draft = this.db.getDraft(draft_id);
    if (!draft || draft.tenant_id !== tenantId) {
      return { found: false, error: 'Draft not found in workspace.' };
    }
    return { found: true, draft };
  }

  requestHumanHandoff(tenantId, sessionId, { reason, notes }) {
    const tenant = this.db.getTenant(tenantId);
    const draft = this.db.getLatestDraftForSession(sessionId);

    // Build structured WhatsApp escalation text
    let messageBody = `Hello ${tenant.name} Team,\n\nCustomer Inquiry Escalation:\nReason: ${reason}\n`;
    if (notes) messageBody += `Notes: ${notes}\n`;
    if (draft) {
      messageBody += `\nAssociated Draft: ${draft.id}\nItems: ${draft.items.map(i => `${i.quantity}x ${i.name}`).join(', ')}\nTotal: ${draft.total_amount.toLocaleString()} ${draft.currency}\nStatus: ${draft.status}\n`;
    }
    messageBody += `\nSession Token: ${sessionId}\nEscalated via Viral-X Safe Sales Agent.`;

    const encodedText = encodeURIComponent(messageBody);
    const cleanPhone = tenant.whatsapp_number.replace(/[^0-9]/g, '');
    const whatsappUrl = `https://wa.me/${cleanPhone}?text=${encodedText}`;

    this.db.logAudit(tenantId, sessionId, 'HANDOFF_TRIGGERED', 'customer', {
      reason,
      draft_id: draft ? draft.id : null,
      whatsapp_number: tenant.whatsapp_number
    });

    if (this.db && this.db.telemetry) {
      try {
        this.db.telemetry.recordEvent({
          tenantId,
          sessionId,
          eventType: BI_EVENT_TYPES.HUMAN_HANDOFF_REQUESTED,
          category: 'escalation',
          draftId: draft ? draft.id : null,
          outcome: 'escalated',
          metadata: {
            reason,
            whatsapp_number: tenant.whatsapp_number,
            has_draft: Boolean(draft)
          }
        });
      } catch (e) {}
    }

    return {
      handoff_prepared: true,
      whatsapp_number: tenant.whatsapp_number,
      whatsapp_url: whatsappUrl,
      summary: {
        business: tenant.name,
        reason,
        draft_id: draft ? draft.id : null,
        notes: notes || 'Direct customer request for human assistance.'
      },
      user_message: `I have prepared a direct escalation to our specialist team at ${tenant.name}. Click the WhatsApp button to continue your conversation with full context preserved.`
    };
  }
}

const toolExecutor = new ToolExecutor();

module.exports = {
  toolExecutor,
  ToolExecutor,
  TOOL_DEFINITIONS
};
