/**
 * VIRAL-X — Customer Intelligence Dashboard Demo
 * Demonstrates conversion funnels, purchase objection breakdowns,
 * inventory demand signals, and monthly AI-assisted reports.
 */

document.addEventListener('DOMContentLoaded', () => {
  const tabButtons = document.querySelectorAll('.dashboard-tab-btn');
  const panelViews = document.querySelectorAll('.dashboard-panel-view');
  const dateRangeSelect = document.getElementById('dashDateRange');

  // Stats Counters
  const valConversations = document.getElementById('metricConversations');
  const valFunnelRate = document.getElementById('metricFunnelRate');
  const valObjections = document.getElementById('metricObjections');
  const valDraftOrders = document.getElementById('metricDraftOrders');

  const dataset = {
    '30days': {
      conversations: '1,420',
      funnelRate: '28.4%',
      objections: '342 Resolved',
      draftOrders: '184 Completed',
      funnelData: [
        { stage: 'Inbound Customer Enquiries', count: 1420, pct: '100%' },
        { stage: 'Catalog & Inventory Engaged', count: 986, pct: '69.4%' },
        { stage: 'Grounded Product Recommendation', count: 614, pct: '43.2%' },
        { stage: 'Order or Booking Drafted', count: 248, pct: '17.5%' },
        { stage: 'Explicit Customer Confirmation', count: 184, pct: '13.0%' }
      ]
    },
    'quarter': {
      conversations: '4,650',
      funnelRate: '31.2%',
      objections: '1,080 Resolved',
      draftOrders: '612 Completed',
      funnelData: [
        { stage: 'Inbound Customer Enquiries', count: 4650, pct: '100%' },
        { stage: 'Catalog & Inventory Engaged', count: 3280, pct: '70.5%' },
        { stage: 'Grounded Product Recommendation', count: 2150, pct: '46.2%' },
        { stage: 'Order or Booking Drafted', count: 840, pct: '18.1%' },
        { stage: 'Explicit Customer Confirmation', count: 612, pct: '13.2%' }
      ]
    },
    'annual': {
      conversations: '18,920',
      funnelRate: '29.8%',
      objections: '4,290 Resolved',
      draftOrders: '2,480 Completed',
      funnelData: [
        { stage: 'Inbound Customer Enquiries', count: 18920, pct: '100%' },
        { stage: 'Catalog & Inventory Engaged', count: 13400, pct: '70.8%' },
        { stage: 'Grounded Product Recommendation', count: 8750, pct: '46.2%' },
        { stage: 'Order or Booking Drafted', count: 3410, pct: '18.0%' },
        { stage: 'Explicit Customer Confirmation', count: 2480, pct: '13.1%' }
      ]
    }
  };

  async function updateMetrics(rangeKey) {
    if (rangeKey === 'live') {
      try {
        const [sumRes, funRes] = await Promise.all([
          fetch('/api/analytics/summary?tenantId=al-noor-jewelry'),
          fetch('/api/analytics/funnel?tenantId=al-noor-jewelry')
        ]);
        const sumData = await sumRes.json();
        const funData = await funRes.json();

        if (sumData.success && funData.success) {
          const totalEvents = sumData.summary.total_events || 0;
          const funnel = sumData.summary.funnel || {};
          const rate = funData.funnel.overallConversionRate || '0%';

          if (valConversations) valConversations.innerText = totalEvents + ' Live Events';
          if (valFunnelRate) valFunnelRate.innerText = rate;
          if (valObjections) valObjections.innerText = (sumData.summary.by_event_type?.UNFULFILLED_DEMAND || 0) + ' Signals';
          if (valDraftOrders) valDraftOrders.innerText = (funnel.drafts_created || 0) + ' Drafted';

          const funnelContainer = document.getElementById('funnelBarsContainer');
          if (funnelContainer && funData.funnel.stages) {
            funnelContainer.innerHTML = funData.funnel.stages.map(item => `
              <div style="margin-bottom: 1.15rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.875rem; margin-bottom: 0.35rem; color: #100D17; font-weight: 500;">
                  <span>${item.stage}</span>
                  <span><strong>${item.count.toLocaleString()}</strong> (${item.conversionRate})</span>
                </div>
                <div style="background-color: #EAE6F2; height: 10px; border-radius: 999px; overflow: hidden;">
                  <div style="width: ${item.conversionRate}; height: 100%; background: linear-gradient(90deg, #10B981, #059669); border-radius: 999px; transition: width 0.4s ease;"></div>
                </div>
              </div>
            `).join('');
          }
          return;
        }
      } catch (err) {
        console.error('Failed to load live metrics:', err);
      }
    }

    const data = dataset[rangeKey] || dataset['30days'];
    if (valConversations) valConversations.innerText = data.conversations;
    if (valFunnelRate) valFunnelRate.innerText = data.funnelRate;
    if (valObjections) valObjections.innerText = data.objections;
    if (valDraftOrders) valDraftOrders.innerText = data.draftOrders;

    // Update Funnel Bars if present
    const funnelContainer = document.getElementById('funnelBarsContainer');
    if (funnelContainer) {
      funnelContainer.innerHTML = data.funnelData.map(item => `
        <div style="margin-bottom: 1.15rem;">
          <div style="display: flex; justify-content: space-between; font-size: 0.875rem; margin-bottom: 0.35rem; color: #100D17; font-weight: 500;">
            <span>${item.stage}</span>
            <span><strong>${item.count.toLocaleString()}</strong> (${item.pct})</span>
          </div>
          <div style="background-color: #EAE6F2; height: 10px; border-radius: 999px; overflow: hidden;">
            <div style="width: ${item.pct}; height: 100%; background: linear-gradient(90deg, #6C35D9, #8B5CF6); border-radius: 999px; transition: width 0.4s ease;"></div>
          </div>
        </div>
      `).join('');
    }
  }

  // Switch tabs
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      panelViews.forEach(p => p.style.display = 'none');

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-target');
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) {
        targetPanel.style.display = 'block';
      }
    });
  });

  // Switch date ranges
  if (dateRangeSelect) {
    dateRangeSelect.addEventListener('change', (e) => {
      updateMetrics(e.target.value);
    });
  }

  // Initial render
  updateMetrics('live');
});
