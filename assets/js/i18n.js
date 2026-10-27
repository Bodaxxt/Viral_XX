/**
 * VIRAL-X — Bilingual Arabic (Qatari/Gulf Tone) & English Engine
 * Provides seamless toggle, persistent preferences, and authentic business phrasing.
 */

(function () {
  'use strict';

  const translations = {
    en: {
      // Navigation
      'nav.home': 'Home',
      'nav.services': 'Services',
      'nav.work': 'Work',
      'nav.studio': 'Studio',
      'nav.contact': 'Contact',
      'nav.startProject': 'Start a Project',
      'nav.tryDemo': 'Try the AI Demo',

      // Hero Section
      'hero.eyebrow': 'Creative Studio & Serious Software Engineering',
      'hero.title': 'We build digital experiences that move brands forward.',
      'hero.subtitle': 'Viral-X partners with businesses in Egypt and the Gulf—especially Qatar—to build high-performance bespoke websites, optimize Google Maps local presence, engineer safe catalog-grounded AI sales systems, and extract actionable monthly customer intelligence.',
      'hero.ctaAi': 'Try the AI Agent →',
      'hero.ctaProject': 'Start a Project →',
      'hero.metric1Val': '4 Core',
      'hero.metric1Label': 'Integrated Capabilities',
      'hero.metric2Val': 'Cairo & Doha',
      'hero.metric2Label': 'Regional Corridor',
      'hero.metric3Val': '100% Bespoke',
      'hero.metric3Label': 'Engineered Codebase',

      // Portfolio Section
      'portfolio.eyebrow': 'Selected Work',
      'portfolio.title': 'Digital systems crafted for regional impact.',
      'portfolio.subtitle': 'A look into how we blend bespoke creative design with deep technical precision for brands across Qatar, the GCC, and Egypt.',
      'portfolio.viewCaseStudy': 'Explore Case Study →',
      'portfolio.viewAll': 'View Complete Portfolio →',

      // Services Section
      'services.eyebrow': 'Our Disciplines',
      'services.title': 'Engineering, Intelligence & Market Positioning',
      'services.subtitle': 'Four specialized, deeply integrated services engineered to transform your commercial presence.',
      'services.s1Title': 'Bespoke High-Performance Websites',
      'services.s1Desc': 'Fast, distinctive, hand-crafted digital flagships built without templates or bloat.',
      'services.s2Title': 'Google Maps Local Domination',
      'services.s2Desc': 'Rank in the local top-three pack in Doha and Cairo to capture high-intent foot and delivery traffic.',
      'services.s3Title': 'Catalog-Grounded AI Sales Agents',
      'services.s3Desc': 'Multi-tenant autonomous sales and booking agents that converse naturally in Gulf Arabic and English.',
      'services.s4Title': 'Monthly Customer Intelligence',
      'services.s4Desc': 'Strategic actionable executive briefings distilled from customer conversations and buying intent.',

      // Floating Button
      'floating.tryBtn': 'Try the AI Agent',

      // Footer
      'footer.tagline': 'Creative Studio & Serious Software Engineering across Cairo and Doha.',
      'footer.rights': 'All rights reserved.'
    },

    ar: {
      // Navigation (لهجة قطرية/خليجية بيزنس راقية)
      'nav.home': 'الرئيسية',
      'nav.services': 'خدماتنا',
      'nav.work': 'أعمالنا',
      'nav.studio': 'عن الاستوديو',
      'nav.contact': 'تواصل معنا',
      'nav.startProject': 'ابدأ مشروعك',
      'nav.tryDemo': 'جرّب الذكاء الاصطناعي',

      // Hero Section
      'hero.eyebrow': 'استوديو إبداعي وهندسة برمجية متقدمة بين الدوحة والقاهرة',
      'hero.title': 'نبتكر تجارب رقمية تليق بأكبر العلامات التجارية.',
      'hero.subtitle': 'شريكك التقني الموثوق في قطر والخليج ومصر — نصمم ونطوّر مواقع إلكترونية سريعة وفخمة، وأنظمة بيع ذكية تفهم لهجة العميل الخليجي واحتياجه بدقة، مع إدارة وتصدّر حضورك التجاري على خرائط جوجل.',
      'hero.ctaAi': 'جرّب وكيل المبيعات الذكي ←',
      'hero.ctaProject': 'ابدأ مشروعك معنا ←',
      'hero.metric1Val': '٤ ركائز',
      'hero.metric1Label': 'حلول تقنية متكاملة',
      'hero.metric2Val': 'الدوحة والقاهرة',
      'hero.metric2Label': 'تواجد إقليمي مباشر',
      'hero.metric3Val': '١٠٠٪ مخصص',
      'hero.metric3Label': 'برمجة خاصة بدون قوالب',

      // Portfolio Section
      'portfolio.eyebrow': 'أعمال مختارة',
      'portfolio.title': 'أنظمة ومنصات صُممت لتصنع فارقاً حقيقياً في السوق.',
      'portfolio.subtitle': 'نظرة على كيفية دمجنا للتصميم العصري الفاخر مع الهندسة التقنية الدقيقة لعملائنا في قطر ودول الخليج ومصر.',
      'portfolio.viewCaseStudy': 'اطّلع على تفاصيل المشروع ←',
      'portfolio.viewAll': 'استعرض كامل أعمالنا ←',

      // Services Section
      'services.eyebrow': 'مجالات اختصاصنا',
      'services.title': 'هندسة تقنية، ذكاء اصطناعي، وتصدّر في السوق',
      'services.subtitle': 'أربع خدمات متخصصة ومتكاملة طُوّرت لترتقي بنشاطك التجاري ونتائجه.',
      'services.s1Title': 'مواقع ومنصات رقمية متطورة وفائقة السرعة',
      'services.s1Desc': 'واجهات وتطبيقات حصرية مبرمجة خصيصاً لهوية علامتك التجارية وبأعلى معايير الأمان.',
      'services.s2Title': 'إدارة وتصدّر خرائط جوجل محلياً',
      'services.s2Desc': 'نضمن ظهور نشاطك في المراتب الثلاث الأولى بالدوحة ومصر لجذب العملاء الأكثر جدية.',
      'services.s3Title': 'وكيل مبيعات ذكي (AI Sales Agent)',
      'services.s3Desc': 'نظام ذكاء اصطناعي يتحاور بلهجة قطرية وخليجية طبيعية، يستعرض الكتالوج ويجهز مسودات الطلبات فوراً.',
      'services.s4Title': 'تقارير ذكاء وسلوك العملاء الشهرية',
      'services.s4Desc': 'ملخصات تنفيذية ترصد بدقة أكثر ما يطلبه عملاؤك ونقاط التردد لتطوير مبيعاتك شهراً بعد شهر.',

      // Floating Button
      'floating.tryBtn': 'جرّب وكيل المبيعات الذكي',

      // Footer
      'footer.tagline': 'استوديو تصميم وهندسة برمجيات احترافية تخدم مشاريع الدوحة والقاهرة.',
      'footer.rights': 'جميع الحقوق محفوظة.'
    }
  };

  let currentLang = localStorage.getItem('viral_lang') || 'en';

  function applyLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('viral_lang', lang);

    const isAr = lang === 'ar';
    document.documentElement.lang = lang;
    document.documentElement.dir = isAr ? 'rtl' : 'ltr';

    // Update all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (translations[lang] && translations[lang][key]) {
        el.textContent = translations[lang][key];
      }
    });

    // Update toggle button states
    const toggleBtn = document.getElementById('langToggleBtn');
    if (toggleBtn) {
      toggleBtn.querySelectorAll('.lang-opt').forEach(opt => {
        if (opt.classList.contains(`lang-${lang}`)) {
          opt.classList.add('active');
        } else {
          opt.classList.remove('active');
        }
      });
    }

    // Toggle specific Arabic font class on body
    if (isAr) {
      document.body.classList.add('ar-active');
    } else {
      document.body.classList.remove('ar-active');
    }
  }

  function injectLanguageSwitcher() {
    const navActions = document.querySelector('.nav-actions');
    if (!navActions || document.getElementById('langToggleBtn')) return;

    const switcher = document.createElement('button');
    switcher.id = 'langToggleBtn';
    switcher.className = 'lang-toggle-btn';
    switcher.setAttribute('type', 'button');
    switcher.setAttribute('aria-label', 'Toggle Arabic / English');
    switcher.innerHTML = `
      <span class="lang-opt lang-en ${currentLang === 'en' ? 'active' : ''}">EN</span>
      <span class="lang-divider">/</span>
      <span class="lang-opt lang-ar ${currentLang === 'ar' ? 'active' : ''}">عربي</span>
    `;

    switcher.addEventListener('click', (e) => {
      e.preventDefault();
      const nextLang = currentLang === 'en' ? 'ar' : 'en';
      applyLanguage(nextLang);
    });

    // Insert as first item in nav-actions
    navActions.insertBefore(switcher, navActions.firstChild);
  }

  // Initialize
  document.addEventListener('DOMContentLoaded', () => {
    injectLanguageSwitcher();
    applyLanguage(currentLang);
  });

  // Expose globally
  window.ViralX_i18n = {
    setLang: applyLanguage,
    getLang: () => currentLang,
    translations
  };
})();
