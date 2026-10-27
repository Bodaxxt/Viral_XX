/**
 * VIRAL-X — Bilingual Arabic (Qatari/Gulf Tone) & English Engine
 * Full site-wide coverage: index, services, portfolio, about, contact, case studies.
 */

(function () {
  'use strict';

  const translations = {
    en: {
      // ── Navigation ──────────────────────────────────────────────
      'nav.home': 'Home',
      'nav.services': 'Services',
      'nav.work': 'Work',
      'nav.studio': 'Studio',
      'nav.contact': 'Contact',
      'nav.startProject': 'Start a Project',
      'nav.tryDemo': 'Try the AI Demo',

      // ── Footer (shared) ─────────────────────────────────────────
      'footer.tagline': 'A premier creative digital studio delivering strategic design and engineering across Egypt and the Gulf.',
      'footer.rights': 'All rights reserved.',
      'footer.copy': '© 2026 Viral-X Digital Studio. All rights reserved.',
      'footer.col.services': 'Services',
      'footer.col.work': 'Selected Work',
      'footer.col.studio': 'Studio',
      'footer.link.web': 'Website Development',
      'footer.link.maps': 'Google Maps & Local Presence',
      'footer.link.ai': 'AI Sales Automation',
      'footer.link.intel': 'Customer Intelligence',
      'footer.link.about': 'About Viral-X',
      'footer.link.start': 'Start a Project',
      'footer.link.privacy': 'Privacy Policy',
      'footer.link.terms': 'Terms of Service',

      // ── INDEX: Hero ─────────────────────────────────────────────
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

      // ── INDEX: Portfolio Section ─────────────────────────────────
      'portfolio.eyebrow': 'Selected Work',
      'portfolio.title': 'Digital systems crafted for regional impact.',
      'portfolio.subtitle': 'A look into how we blend bespoke creative design with deep technical precision for brands across Qatar, the GCC, and Egypt.',
      'portfolio.viewCaseStudy': 'Explore Case Study →',
      'portfolio.viewAll': 'View Complete Portfolio →',

      // ── INDEX: Services Section ──────────────────────────────────
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

      // ── INDEX: Floating Button ───────────────────────────────────
      'floating.tryBtn': 'Try the AI Agent',

      // ── SERVICES PAGE ────────────────────────────────────────────
      'svcpage.eyebrow': 'Studio Capabilities',
      'svcpage.title': 'Strategic digital systems, meticulously engineered.',
      'svcpage.subtitle': 'Viral-X combines the aesthetic discernment of an award-winning creative agency with the rigor of enterprise software engineering. We offer four distinct service disciplines designed to work together seamlessly.',

      // ── PORTFOLIO PAGE ──────────────────────────────────────────
      'portfolio.page.eyebrow': 'Portfolio & Concept Work',
      'portfolio.page.title': 'Design direction tailored to category leaders.',
      'portfolio.page.subtitle': 'Each case study below is an original, self-initiated concept developed by the Viral-X creative and engineering team to demonstrate our art direction, UI/UX architecture, and technical capabilities across four major commercial sectors.',
      'portfolio.badge.concept': 'Concept Project',
      'portfolio.selfInitiated': 'Self-Initiated Concept',
      'portfolio.readCase': 'Read Full Case Study',
      'portfolio.disclaimer': 'All portfolio projects shown are self-initiated concepts developed by Viral-X to demonstrate our design direction and technical solutions. They are not implied to be commercial launched brands or paying clients.',
      'portfolio.cta.title': 'Ready to design your custom digital flagship?',
      'portfolio.cta.subtitle': "Let's discuss how we can create a distinctive digital presence for your brand in Egypt, Qatar, or across the Gulf.",
      'portfolio.cta.btn': 'Start Project Discovery →',

      'portfolio.p1.category': 'Luxury E-Commerce & Private Salon',
      'portfolio.p1.summary': "A digital boutique crafted for Qatar's elite fine jewelry market. Features an ivory, black, and gold design system, GIA-grounded gemstone documentation, private viewing requests, and secure courier dispatch logic.",
      'portfolio.p1.tag1': 'Ivory & Gold System',
      'portfolio.p1.tag2': 'Bespoke Diamond Zoom',
      'portfolio.p1.tag3': 'Private Salon Booking',

      'portfolio.p2.category': 'Fine Dining & Culinary Experience',
      'portfolio.p2.summary': 'An editorial food-focused digital experience highlighting modern Middle Eastern fine dining. Designed with warm photography, interactive chef tasting menus, dietary pre-consultation, and prominent reservation flows.',
      'portfolio.p2.tag1': 'Editorial Typography',
      'portfolio.p2.tag2': 'Tasting Menu Reservations',
      'portfolio.p2.tag3': 'Dietary Screening Flow',

      'portfolio.p3.category': 'Modern Healthcare & Medical Wellness',
      'portfolio.p3.summary': 'A serene, trustworthy medical web platform engineered for patient confidence. Includes physician credentials, screening pathway guides, multi-clinic GPS navigation, and friction-free consultation booking.',
      'portfolio.p3.tag1': 'Clean Architectural Aesthetic',
      'portfolio.p3.tag2': 'Screening Pathway Flow',
      'portfolio.p3.tag3': 'Multi-Branch GPS',

      'portfolio.p4.category': 'Enterprise Technology & API Platform',
      'portfolio.p4.summary': 'A dark-themed technical product website built for developers and engineering leaders. Showcases real-time telemetry visualizations, neural decision tree flows, latency metrics, and API documentation with zero marketing fluff.',
      'portfolio.p4.tag1': 'Dark Cybernetic UI',
      'portfolio.p4.tag2': 'Telemetry Visualizations',
      'portfolio.p4.tag3': 'Developer Documentation',

      // ── ABOUT PAGE ──────────────────────────────────────────────
      'about.eyebrow': 'Studio Manifesto',
      'about.title': 'Creative studio energy. Serious software engineering.',
      'about.subtitle': 'Viral-X was founded on a simple observation: most agencies are either design shops that cannot write scalable backend code, or software houses that lack aesthetic taste. We bridge that divide.',
      'about.roots.eyebrow': 'Our Roots & Corridor',
      'about.roots.title': 'Anchored in Egypt. Partnering across the Gulf.',
      'about.roots.p1': 'Egypt is a vibrant powerhouse of engineering and artistic talent. The Gulf—particularly Qatar, Saudi Arabia, and the UAE—is experiencing unprecedented commercial ambition, demanding digital flagships that rival London, Tokyo, or New York.',
      'about.roots.p2': 'Viral-X operates along this regional corridor. We understand local consumer behaviors: the reliance on WhatsApp for commercial transactions, the cultural importance of authentic Arabic typography, the need for precise physical location routing, and the desire for discreet, high-touch luxury service.',
      'about.p1.title': '01 / Art Direction Over Templates',
      'about.p1.desc': 'Every brand deserves an intentional visual identity. We reject repetitive website templates and cheap glassmorphic gimmicks in favor of thoughtful grids, tailored color harmonies, and responsive typography.',
      'about.p2.title': '02 / Practical Engineering, No AI Hype',
      'about.p2.desc': "We don't use AI as a buzzword to inflate invoices. We deploy AI strictly where it solves real business friction: grounding sales assistants in verified inventory databases, eliminating repetitive data entry, and uncovering customer purchase objections.",
      'about.p3.title': '03 / Direct Commercial Focus',
      'about.p3.desc': 'A beautiful website that fails to convert qualified inquiries is a failure. We measure every layout against real commercial objectives: inquiry rates, qualified leads, table reservations, and verified draft orders.',
      'about.p4.title': '04 / Transparent Data Ethics',
      'about.p4.desc': "We respect patient, diner, and shopper privacy. All data architectures strictly adhere to Egyptian Personal Data Protection regulations and Qatar's Personal Data Privacy Protection Law (PDPPL).",
      'about.standards.eyebrow': 'Studio Standards',
      'about.standards.title': 'What partnering with Viral-X looks like.',
      'about.std1.title': 'Direct Access to Senior Specialists',
      'about.std1.desc': 'You collaborate directly with our creative directors and full-stack software engineers. No junior account managers or game of telephone.',
      'about.std2.title': 'Milestone-Based Transparent Delivery',
      'about.std2.desc': 'Every engagement follows defined sprints: Discovery & Architecture → Design Approval → Production Engineering & Testing → Deployment & Intelligence Sync.',
      'about.std3.title': 'Full Intellectual Property Ownership',
      'about.std3.desc': 'Upon final milestone completion, you own 100% of your source code, design files, vector assets, and system configurations. No proprietary lock-in.',
      'about.cta': 'Discuss Your Project with Our Team →',

      // ── CONTACT PAGE ────────────────────────────────────────────
      'contact.eyebrow': 'Project Consultation',
      'contact.title': "Let's engineer something remarkable together.",
      'contact.subtitle': "Whether you need an authoritative corporate web flagship, a bespoke luxury e-commerce experience, Google Maps optimization, or a grounded AI sales agent, we're ready to review your goals.",
      'contact.form.title': 'Project Inquiry Planner',
      'contact.form.subtitle': 'Fill out your project specifications below. Our leadership reviews all inquiries within 24 business hours.',
      'contact.label.name': 'Full Name *',
      'contact.label.company': 'Company / Brand Name',
      'contact.label.email': 'Work Email *',
      'contact.label.phone': 'WhatsApp or Mobile',
      'contact.label.services': 'Services Required (Select all that apply)',
      'contact.svc.web': 'Premium Business Website',
      'contact.svc.maps': 'Google Maps & Local Presence',
      'contact.svc.ai': 'AI Sales Automation Agent',
      'contact.svc.intel': 'Monthly Customer Intelligence',
      'contact.label.budget': 'Estimated Budget Tier (USD)',
      'contact.label.timeline': 'Target Launch Target',
      'contact.label.brief': 'Project Brief & Objectives *',
      'contact.btn.submit': 'Submit Inquiry to Studio',
      'contact.btn.whatsapp': 'Dispatch via WhatsApp',
      'contact.privacy.note': 'No secrets or unconfigured external services are executed in the client browser. Submissions are transparently routed to our studio team.',
      'contact.wa.badge': 'Instant Priority Channel',
      'contact.wa.title': 'Prefer a direct conversation?',
      'contact.wa.desc': 'For confidential inquiries, NDA requests, or rapid project scoping, connect directly with our studio team on WhatsApp.',
      'contact.wa.btn': 'Open Studio WhatsApp Concierge',
      'contact.hours.title': 'Operating Corridor & Working Hours',
      'contact.hours.cairo.label': 'Cairo Operations',
      'contact.hours.cairo.hours': 'Sunday – Thursday: 09:00 – 18:00 (GMT+2) · Technical & Creative Engineering Center',
      'contact.hours.doha.label': 'Doha & GCC Client Corridor',
      'contact.hours.doha.hours': 'Sunday – Thursday: 10:00 – 19:00 (GMT+3) · Commercial Engagements & Private Consultations',
      'contact.hours.notice': 'Notice: Physical client meetings in Cairo or Doha are arranged by appointment following initial discovery review.',
      'contact.email.label': 'General Inquiries',
    },

    ar: {
      // ── Navigation (لهجة قطرية/خليجية راقية) ────────────────────
      'nav.home': 'الرئيسية',
      'nav.services': 'خدماتنا',
      'nav.work': 'أعمالنا',
      'nav.studio': 'عن الاستوديو',
      'nav.contact': 'تواصل معنا',
      'nav.startProject': 'ابدأ مشروعك',
      'nav.tryDemo': 'جرّب الذكاء الاصطناعي',

      // ── Footer (shared) ─────────────────────────────────────────
      'footer.tagline': 'استوديو تصميم وهندسة برمجيات احترافية — شريكك في الدوحة والقاهرة.',
      'footer.rights': 'جميع الحقوق محفوظة.',
      'footer.copy': '© 2026 Viral-X Digital Studio. جميع الحقوق محفوظة.',
      'footer.col.services': 'خدماتنا',
      'footer.col.work': 'أعمال مختارة',
      'footer.col.studio': 'الاستوديو',
      'footer.link.web': 'تطوير المواقع',
      'footer.link.maps': 'خرائط جوجل والحضور المحلي',
      'footer.link.ai': 'أتمتة المبيعات بالذكاء الاصطناعي',
      'footer.link.intel': 'ذكاء العملاء',
      'footer.link.about': 'عن Viral-X',
      'footer.link.start': 'ابدأ مشروعك',
      'footer.link.privacy': 'سياسة الخصوصية',
      'footer.link.terms': 'شروط الخدمة',

      // ── INDEX: Hero ─────────────────────────────────────────────
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

      // ── INDEX: Portfolio Section ─────────────────────────────────
      'portfolio.eyebrow': 'أعمال مختارة',
      'portfolio.title': 'أنظمة ومنصات صُممت لتصنع فارقاً حقيقياً في السوق.',
      'portfolio.subtitle': 'نظرة على كيفية دمجنا للتصميم العصري الفاخر مع الهندسة التقنية الدقيقة لعملائنا في قطر ودول الخليج ومصر.',
      'portfolio.viewCaseStudy': 'اطّلع على تفاصيل المشروع ←',
      'portfolio.viewAll': 'استعرض كامل أعمالنا ←',

      // ── INDEX: Services Section ──────────────────────────────────
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

      // ── INDEX: Floating Button ───────────────────────────────────
      'floating.tryBtn': 'جرّب وكيل المبيعات الذكي',

      // ── SERVICES PAGE ────────────────────────────────────────────
      'svcpage.eyebrow': 'إمكانياتنا في الاستوديو',
      'svcpage.title': 'أنظمة رقمية استراتيجية مهندسة بإتقان.',
      'svcpage.subtitle': 'يجمع Viral-X بين الذوق الإبداعي الرفيع لوكالة تصميم متميزة وصرامة هندسة البرمجيات المؤسسية — أربع خدمات متكاملة تعمل معاً بانسجام.',

      // ── PORTFOLIO PAGE ──────────────────────────────────────────
      'portfolio.page.eyebrow': 'ملف الأعمال والمشاريع التصورية',
      'portfolio.page.title': 'توجيه تصميمي يليق بأبرز العلامات التجارية.',
      'portfolio.page.subtitle': 'كل مشروع هنا هو فكرة مبتكرة ذاتية التطوير، أنجزها فريق Viral-X الإبداعي لإثبات قدراتنا في التوجيه الفني وهندسة واجهات المستخدم عبر أربعة قطاعات تجارية رئيسية.',
      'portfolio.badge.concept': 'مشروع تصوري',
      'portfolio.selfInitiated': 'مبادرة إبداعية خاصة',
      'portfolio.readCase': 'اطّلع على التفاصيل الكاملة',
      'portfolio.disclaimer': 'جميع المشاريع المعروضة هي أفكار تصورية ذاتية أعدّها فريق Viral-X لإبراز منهجيتنا التصميمية وحلولنا التقنية، وليست علامات تجارية تجارية مطلقة أو عملاء حاليين.',
      'portfolio.cta.title': 'هل أنت مستعد لبناء منصتك الرقمية الفاخرة؟',
      'portfolio.cta.subtitle': 'دعنا نبحث معاً كيف نصنع لك حضوراً رقمياً مميزاً في قطر أو الخليج أو مصر.',
      'portfolio.cta.btn': 'ابدأ رحلة مشروعك ←',

      'portfolio.p1.category': 'تجارة فاخرة وصالون خاص',
      'portfolio.p1.summary': 'بوتيك رقمي حصري صُمِّم لسوق المجوهرات الراقية في قطر، بنظام ألوان العاج والذهب والأسود، وتوثيق الأحجار الكريمة، وطلبات المعاينة الخاصة، وخدمة التوصيل الآمن.',
      'portfolio.p1.tag1': 'نظام العاج والذهب',
      'portfolio.p1.tag2': 'تكبير الماس الحصري',
      'portfolio.p1.tag3': 'حجز صالون خاص',

      'portfolio.p2.category': 'مطاعم راقية وتجربة ذواقة',
      'portfolio.p2.summary': 'تجربة رقمية افتخارية لمطعم شرق أوسطي راقي، بتصوير فوتوغرافي دافئ وقوائم طعام تفاعلية وحجوزات مخصصة واستشارات غذائية مسبقة.',
      'portfolio.p2.tag1': 'طباعة افتخارية',
      'portfolio.p2.tag2': 'حجوزات قائمة التذوق',
      'portfolio.p2.tag3': 'تدفق الفحص الغذائي',

      'portfolio.p3.category': 'رعاية صحية حديثة وطب متخصص',
      'portfolio.p3.summary': 'منصة طبية هادئة وموثوقة تُرسّخ ثقة المريض، تشمل ملفات الأطباء وإرشادات الفحص وملاحة GPS متعددة العيادات وحجز استشارات بلا عوائق.',
      'portfolio.p3.tag1': 'تصميم معماري نظيف',
      'portfolio.p3.tag2': 'تدفق مسار الفحص',
      'portfolio.p3.tag3': 'GPS متعدد الفروع',

      'portfolio.p4.category': 'تقنية مؤسسية ومنصة API',
      'portfolio.p4.summary': 'موقع منتج تقني داكن الطابع موجّه للمطورين وقادة الهندسة، يعرض مرئيات القياس الفوري وخرائط القرار العصبي ومقاييس الاستجابة وتوثيق API بلا مبالغة تسويقية.',
      'portfolio.p4.tag1': 'واجهة سيبرانية داكنة',
      'portfolio.p4.tag2': 'مرئيات القياس الفوري',
      'portfolio.p4.tag3': 'توثيق المطورين',

      // ── ABOUT PAGE ──────────────────────────────────────────────
      'about.eyebrow': 'رؤية الاستوديو',
      'about.title': 'طاقة استوديو إبداعي. دقة هندسة برمجية متقدمة.',
      'about.subtitle': 'تأسس Viral-X على ملاحظة بسيطة: معظم الوكالات إما استوديو تصميم يفتقر لهندسة برمجية قوية، أو شركة برمجيات تفتقر للذوق الجمالي. نحن نجمع الاثنين في مكان واحد.',
      'about.roots.eyebrow': 'جذورنا وامتدادنا',
      'about.roots.title': 'قاعدتنا في مصر. شراكاتنا في الخليج.',
      'about.roots.p1': 'مصر كنز حقيقي من المواهب الهندسية والفنية. والخليج — خاصة قطر والسعودية والإمارات — يشهد طموحاً تجارياً غير مسبوق يستدعي منصات رقمية تنافس لندن وطوكيو ونيويورك.',
      'about.roots.p2': 'نعمل على طول هذا الممر الإقليمي بفهم عميق للسلوك الاستهلاكي المحلي: الاعتماد على واتساب في المعاملات التجارية، وأهمية الخط العربي الأصيل، والحاجة لتحديد المواقع بدقة، والتوق لخدمة فاخرة راقية وسرية.',
      'about.p1.title': '٠١ / التوجيه الفني أولاً',
      'about.p1.desc': 'كل علامة تجارية تستحق هوية بصرية مقصودة. نرفض القوالب المكررة والتأثيرات الرخيصة لصالح شبكات تصميم مدروسة وتناسق ألوان مخصص وطباعة متجاوبة.',
      'about.p2.title': '٠٢ / هندسة عملية بلا مبالغة في الذكاء الاصطناعي',
      'about.p2.desc': 'لا نستخدم الذكاء الاصطناعي كلافتة تسويقية لرفع الأسعار. ندمجه فقط حيث يحل احتكاكاً تجارياً حقيقياً: ربط وكلاء البيع بقاعدة البيانات الفعلية، وإزالة الإدخال اليدوي المتكرر، وكشف نقاط تردد العملاء.',
      'about.p3.title': '٠٣ / التركيز التجاري المباشر',
      'about.p3.desc': 'الموقع الجميل الذي لا يحول الزوار لعملاء هو فشل. نقيس كل تصميم بمقاييس تجارية حقيقية: معدلات الاستفسار والعملاء المحتملين وحجوزات الطاولات ومسودات الطلبات.',
      'about.p4.title': '٠٤ / أخلاقيات البيانات والشفافية',
      'about.p4.desc': 'نحترم خصوصية المرضى والزبائن والمتسوقين. كل بنية بيانات لدينا تلتزم بلوائح حماية البيانات المصرية وقانون حماية خصوصية البيانات الشخصية القطري (PDPPL).',
      'about.standards.eyebrow': 'معايير الاستوديو',
      'about.standards.title': 'كيف تبدو الشراكة مع Viral-X.',
      'about.std1.title': 'تواصل مباشر مع المتخصصين الكبار',
      'about.std1.desc': 'ستتعامل مباشرة مع مدرائنا الإبداعيين ومهندسي البرمجيات. لا وسطاء، ولا تراسل عبر عدة أطراف.',
      'about.std2.title': 'تسليم شفاف قائم على المراحل',
      'about.std2.desc': 'كل مشروع يسير وفق مراحل واضحة: الاكتشاف والبنية ← اعتماد التصميم ← الهندسة والاختبار ← الإطلاق والمزامنة الذكية.',
      'about.std3.title': 'ملكية فكرية كاملة لك',
      'about.std3.desc': 'عند إتمام المشروع، تملك ١٠٠٪ من الكود والملفات التصميمية والأصول والإعدادات. لا قيود ولا احتجاز.',
      'about.cta': 'ناقش مشروعك مع فريقنا ←',

      // ── CONTACT PAGE ────────────────────────────────────────────
      'contact.eyebrow': 'استشارة مشروعك',
      'contact.title': 'لنبتكر معاً شيئاً يستحق أن يُحكى عنه.',
      'contact.subtitle': 'سواء كنت تحتاج موقعاً مؤسسياً فاخراً أو متجراً إلكترونياً راقياً أو تحسين خرائط جوجل أو وكيل مبيعات ذكي — نحن هنا لمراجعة أهدافك والبدء معك.',
      'contact.form.title': 'مخطط استفسار المشروع',
      'contact.form.subtitle': 'أدخل تفاصيل مشروعك أدناه. يراجع فريقنا القيادي جميع الاستفسارات خلال ٢٤ ساعة عمل.',
      'contact.label.name': 'الاسم الكامل *',
      'contact.label.company': 'اسم الشركة أو العلامة التجارية',
      'contact.label.email': 'البريد الإلكتروني للعمل *',
      'contact.label.phone': 'واتساب أو الجوال',
      'contact.label.services': 'الخدمات المطلوبة (اختر كل ما ينطبق)',
      'contact.svc.web': 'موقع تجاري احترافي',
      'contact.svc.maps': 'خرائط جوجل والحضور المحلي',
      'contact.svc.ai': 'وكيل مبيعات بالذكاء الاصطناعي',
      'contact.svc.intel': 'تقارير ذكاء العملاء الشهرية',
      'contact.label.budget': 'نطاق الميزانية التقديرية (بالدولار)',
      'contact.label.timeline': 'الجدول الزمني المستهدف للإطلاق',
      'contact.label.brief': 'موجز المشروع والأهداف *',
      'contact.btn.submit': 'إرسال الاستفسار للاستوديو',
      'contact.btn.whatsapp': 'إرسال عبر واتساب',
      'contact.privacy.note': 'لا تُنفَّذ أي خدمات خارجية في متصفحك. ترسل البيانات مباشرة لفريق الاستوديو بكل شفافية.',
      'contact.wa.badge': 'قناة الأولوية الفورية',
      'contact.wa.title': 'تفضّل التحدث مباشرة؟',
      'contact.wa.desc': 'للاستفسارات السرية أو طلبات اتفاقية عدم الإفصاح أو التحديد السريع لنطاق المشروع، تواصل مباشرة مع فريق الاستوديو عبر واتساب.',
      'contact.wa.btn': 'افتح واتساب الاستوديو الخاص',
      'contact.hours.title': 'ممر العمل وساعات الدوام',
      'contact.hours.cairo.label': 'عمليات القاهرة',
      'contact.hours.cairo.hours': 'الأحد – الخميس: ٩:٠٠ص – ٦:٠٠م (GMT+2) · مركز الهندسة الإبداعية والتقنية',
      'contact.hours.doha.label': 'الدوحة ومنطقة الخليج',
      'contact.hours.doha.hours': 'الأحد – الخميس: ١٠:٠٠ص – ٧:٠٠م (GMT+3) · الاستشارات التجارية والخاصة',
      'contact.hours.notice': 'تنبيه: تُرتَّب الاجتماعات الشخصية في القاهرة أو الدوحة بموعد مسبق بعد مراجعة الاستفسار الأولي.',
      'contact.email.label': 'استفسارات عامة',
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

    // Toggle Arabic font class on body
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
