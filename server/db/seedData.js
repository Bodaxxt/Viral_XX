/**
 * Seed data for the three sample business workspaces:
 * 1. Al Noor Jewelry (Doha, Qatar) - Luxury Jewelry
 * 2. The Saffron Table (Cairo, Egypt) - Fine Dining
 * 3. Vitalis Health (New Cairo, Egypt) - Clinical Wellness
 */

const tenants = [
  {
    id: 'al-noor-jewelry',
    name: 'Al Noor High Jewelry & Diamonds',
    category: 'jewelry',
    location: 'Place Vendôme & The Pearl, Doha, Qatar',
    currency: 'QAR',
    whatsapp_number: '+97444991200',
    operating_hours: 'Saturday to Thursday: 10:00 AM – 10:00 PM | Friday: 2:00 PM – 11:00 PM',
    policy_summary: 'All fine jewelry pieces are accompanied by international GIA / IGI certificates and Qatar National Gemology hallmarks. Custom sizing takes 3 business days. GCC secure courier shipping or private salon collection available. Returns accepted within 7 days in unworn condition with intact security tags.',
    integration_mode: 'demo'
  },
  {
    id: 'saffron-table',
    name: 'The Saffron Table Fine Dining',
    category: 'restaurant',
    location: 'Zamalek, Cairo, Egypt',
    currency: 'EGP',
    whatsapp_number: '+201098539907',
    operating_hours: 'Tuesday to Sunday: 6:00 PM – 12:00 AM (Closed Mondays). Dinner seatings at 7:30 PM & 9:30 PM.',
    policy_summary: 'Chef degustation experiences require advance reservation. A refundable deposit of 500 EGP per guest secures reservations up to 6 guests. Private dining salon accommodates up to 12 guests with custom menu curation. Dietary restrictions (gluten-free, shellfish, vegan) accommodated with 6 hours advance notice.',
    integration_mode: 'demo'
  },
  {
    id: 'vitalis-health',
    name: 'Vitalis Longevity & Clinical Center',
    category: 'healthcare',
    location: 'New Cairo Medical Park, Cairo, Egypt',
    currency: 'EGP',
    whatsapp_number: '+201200554488',
    operating_hours: 'Saturday to Thursday: 9:00 AM – 7:00 PM (Closed Fridays).',
    policy_summary: 'Vitalis provides preventive longevity, biomarker analysis, and administrative consultation scheduling. Medical guardrail: Our AI agent provides administrative, scheduling, and logistical guidance only. Diagnostic advice or prescription modifications must be conducted in person with a certified physician.',
    integration_mode: 'demo'
  }
];

const products = [
  // --- 1. Al Noor Jewelry (Doha) ---
  {
    id: 'J-101',
    tenant_id: 'al-noor-jewelry',
    sku: 'SKU-EM-101',
    name: 'Al-Thuraya Diamond & Emerald Collar',
    name_ar: 'طوق الثريا من الألماس والزمرد الكولومبي',
    category: 'Necklaces & Collars',
    base_price: 42000,
    currency: 'QAR',
    description: 'Handcrafted collar necklace set in 18K white gold with 4.5 carats of Zambian/Colombian vivid green emeralds and 6.2 carats of brilliant-cut diamonds (F/VS1).',
    description_ar: 'عقد طوق مصنوع يدويًا من الذهب الأبيض عيار 18 قيراط مرصع بـ 4.5 قيراط زمرد أخضر نضر و6.2 قيراط ألماس براق (F/VS1).',
    attributes: {
      metal: '18K White Gold',
      metal_weight_grams: 38.5,
      gemstones: 'Vivid Green Emeralds (4.5 ct) & Round Diamonds (6.2 ct)',
      clarity: 'F / VS1',
      certificate: 'GIA & Qatar Hallmarked',
      bespoke_customizable: true,
      customization_time_days: 7
    }
  },
  {
    id: 'J-102',
    tenant_id: 'al-noor-jewelry',
    sku: 'SKU-SAP-102',
    name: 'Noor Pavé Sapphire Bangle (18K White Gold)',
    name_ar: 'سوار نور المرصع بياقوت السفير الأزرق والذهب الأبيض',
    category: 'Bracelets & Bangles',
    base_price: 14500,
    currency: 'QAR',
    description: 'Slim hinged oval bangle in 18K white gold adorned with 2.8 carats of royal blue Ceylon sapphires and pavé micro-diamonds.',
    description_ar: 'سوار بيضاوي أنيق عيار 18 قيراط ذهب أبيض مرصع بـ 2.8 قيراط من ياقوت سيلان الأزرق الملكي وألماس بافيه دقيق.',
    attributes: {
      metal: '18K White Gold',
      metal_weight_grams: 19.2,
      gemstones: 'Royal Blue Ceylon Sapphires (2.8 ct) & Diamonds (0.9 ct)',
      clarity: 'G / VS2',
      certificate: 'IGI Certified',
      bespoke_customizable: false
    }
  },
  {
    id: 'J-103',
    tenant_id: 'al-noor-jewelry',
    sku: 'SKU-SOL-103',
    name: 'Solitaire Cushion Diamond Ring (3.2ct D/VVS1)',
    name_ar: 'خاتم سوليتير ماسي قصة وسادة (3.2 قيراط D/VVS1)',
    category: 'Rings & Bridal',
    base_price: 68000,
    currency: 'QAR',
    description: 'Exceptional 3.20 carat cushion brilliant diamond set on a platinum four-prong solitaire band with hidden diamond halo.',
    description_ar: 'ألماسة وسادة استثنائية بوزن 3.20 قيراط مثبتة على خاتم بلاتين بأربعة مخالب مع هالة ماسية خفية.',
    attributes: {
      metal: 'Platinum 950',
      metal_weight_grams: 6.8,
      diamond_weight_carat: 3.2,
      color: 'D (Colorless)',
      clarity: 'VVS1',
      certificate: 'GIA Dossier Report #648190',
      bespoke_customizable: true,
      ring_sizing_available: true
    }
  },
  {
    id: 'J-104',
    tenant_id: 'al-noor-jewelry',
    sku: 'SKU-GLD-104',
    name: 'Heritage Royal 21K Gold Filigree Cuff',
    name_ar: 'إسوارة التراث الملكي عيار 21 قيراط نقش يدوي',
    category: 'Heritage Gold',
    base_price: 9800,
    currency: 'QAR',
    description: 'Traditional Gulf filigree cuff crafted in solid 21K yellow gold with intricate hand-engraved Arabesque motifs.',
    description_ar: 'سوار تراثي خليجي صلب عيار 21 قيراط مزين بزخارف أرابيسك دقيقة منقوشة يدويًا.',
    attributes: {
      metal: '21K Yellow Gold',
      metal_weight_grams: 32.0,
      gemstones: 'None (Pure 21K Gold)',
      certificate: 'Qatar Central Assay Hallmarked',
      bespoke_customizable: false
    }
  },

  // --- 2. The Saffron Table (Cairo) ---
  {
    id: 'R-201',
    tenant_id: 'saffron-table',
    sku: 'RES-DEG-201',
    name: 'Chef Tasting Degustation (7 Courses)',
    name_ar: 'قائمة تذوق الشيف المميزة (7 أطباق)',
    category: 'Tasting Menus',
    base_price: 1850,
    currency: 'EGP',
    description: 'Award-winning 7-course seasonal modern Egyptian journey crafted by Chef Tarek. Includes amuse-bouche, dry-aged local squab, and artisanal sea-salt halawa dessert.',
    description_ar: 'رحلة طهي مصرية عصرية حائزة على جوائز من 7 أطباق موسمية يقدمها الشيف طارق، تشمل مقبلات خاصة وحمام مسكوف وحلاوة طحينية بالملح البحري.',
    attributes: {
      courses: 7,
      seatings: ['19:30', '21:30'],
      deposit_per_guest: 500,
      dietary_support: ['Gluten-Free', 'Shellfish Allergy', 'Vegetarian (with notice)'],
      duration_hours: 2.5
    }
  },
  {
    id: 'R-202',
    tenant_id: 'saffron-table',
    sku: 'RES-PDR-202',
    name: 'Private Dining Salon (Up to 12 Guests)',
    name_ar: 'صالون العشاء الخاص (حتى 12 ضيفًا)',
    category: 'Private Events',
    base_price: 14000,
    currency: 'EGP',
    description: 'Exclusive private Nile-view salon with dedicated butler service, custom 5-course bespoke menu, and personalized table styling.',
    description_ar: 'صالون خاص بإطلالة راقية على النيل مع خدمة ساقي خاصة، وقائمة طعام مخصصة من 5 أطباق وتنسيق طاولات فاخر.',
    attributes: {
      max_guests: 12,
      deposit_required: 4000,
      min_spend_required: true,
      requires_staff_confirmation: true
    }
  },
  {
    id: 'R-203',
    tenant_id: 'saffron-table',
    sku: 'RES-BRN-203',
    name: 'Weekend Artisanal Brunch Experience',
    name_ar: 'تجربة برانش نهاية الأسبوع الحرفية',
    category: 'Weekend Specials',
    base_price: 1100,
    currency: 'EGP',
    description: 'Curated 4-course Friday & Saturday late brunch featuring farm-to-table Baladi pastries, truffled foul medames, and specialty hibiscus infusions.',
    description_ar: 'برانش فاخر ليومي الجمعة والسبت من 4 أطباق بمكونات طازجة ومخبوزات بلدية وفول بالترافل ومشروبات كركديه مميزة.',
    attributes: {
      days: ['Friday', 'Saturday'],
      time: '12:00 PM – 4:30 PM',
      deposit_per_guest: 300
    }
  },

  // --- 3. Vitalis Clinical Health (New Cairo) ---
  {
    id: 'H-301',
    tenant_id: 'vitalis-health',
    sku: 'MED-LON-301',
    name: 'Executive Longevity & Metabolic Screening',
    name_ar: 'الفحص التنفيذي الشامل للصحة الأيضية وطول العمر',
    category: 'Longevity Checkups',
    base_price: 4500,
    currency: 'EGP',
    description: 'Comprehensive 65-biomarker panel including advanced lipid subfractions, fasting insulin sensitivity, hs-CRP inflammation, liver/kidney profiles, and 45-minute physician consultation.',
    description_ar: 'فحص مخبري متقدم يشمل 65 مؤشرًا حيويًا لتحليل الدهون المفصلة، ومقاومة الإنسولين، والالتهاب الدقيق، ووظائف الكبد والكلى، مع جلسة استشارة طبية 45 دقيقة.',
    attributes: {
      fasting_required: '10 to 12 hours fasting required (water permitted)',
      duration_minutes: 60,
      results_turnaround: '24 hours in Vitalis Patient Portal',
      administrative_only: true,
      clinic_suite: 'New Cairo Suite 402'
    }
  },
  {
    id: 'H-302',
    tenant_id: 'vitalis-health',
    sku: 'MED-CRD-302',
    name: 'Cardio-Vascular & Endurance Assessment',
    name_ar: 'تقييم كفاءة القلب والأوعية الدموية واللياقة',
    category: 'Cardio Wellness',
    base_price: 3200,
    currency: 'EGP',
    description: 'Resting 12-lead ECG, Carotid intima-media ultrasound thickness test, and VO2 cardiovascular endurance analysis supervised by our cardiology consultant.',
    description_ar: 'رسم قلب متقدم 12 قناة، سونار الشريان السباتي، وقياس كفاءة استهلاك الأكسجين ولياقة القلب بإشراف استشاري قلب وأوعية.',
    attributes: {
      fasting_required: '2 hours light fasting, comfortable athletic footwear',
      duration_minutes: 45,
      clinic_suite: 'New Cairo Suite 405'
    }
  }
];

const inventory = [
  // Jewelry live stock
  { product_id: 'J-101', tenant_id: 'al-noor-jewelry', stock_count: 2, reserved_count: 0, location: 'Doha Place Vendôme Flagship' },
  { product_id: 'J-102', tenant_id: 'al-noor-jewelry', stock_count: 5, reserved_count: 1, location: 'Doha Place Vendôme Flagship' },
  { product_id: 'J-103', tenant_id: 'al-noor-jewelry', stock_count: 1, reserved_count: 0, location: 'The Pearl Private Salon Vault' },
  { product_id: 'J-104', tenant_id: 'al-noor-jewelry', stock_count: 0, reserved_count: 0, location: 'Out of Stock - Custom Order Only (10 days)' },

  // Restaurant capacities
  { product_id: 'R-201', tenant_id: 'saffron-table', stock_count: 18, reserved_count: 6, location: 'Main Dining Room' },
  { product_id: 'R-202', tenant_id: 'saffron-table', stock_count: 1, reserved_count: 0, location: 'Zamalek Salon Privé' },
  { product_id: 'R-203', tenant_id: 'saffron-table', stock_count: 24, reserved_count: 8, location: 'Garden Terrace' },

  // Clinical slots
  { product_id: 'H-301', tenant_id: 'vitalis-health', stock_count: 6, reserved_count: 2, location: 'New Cairo Suite 402' },
  { product_id: 'H-302', tenant_id: 'vitalis-health', stock_count: 4, reserved_count: 1, location: 'New Cairo Suite 405' }
];

const knowledge_base = [
  // --- Al Noor Jewelry Policies ---
  {
    id: 'K-J01',
    tenant_id: 'al-noor-jewelry',
    category: 'authenticity',
    question: 'How do I know the diamonds and emeralds are authentic?',
    question_ar: 'كيف أضمن أصالة الألماس والأحجار الكريمة؟',
    answer: 'Every piece at Al Noor High Jewelry is hallmarked by the Qatar Ministry of Commerce & Industry Assay Office and accompanied by certified GIA (Gemological Institute of America) or IGI dossiers detailing cut, clarity, color, and carat weight.',
    answer_ar: 'جميع قطع مجوهرات النور مدموغة رسميًا من إدارة المعايرة والمقاييس القطرية ومصحوبة بشهادات دولية معتمدة من معهد GIA الأمريكي أو IGI تثبت تفاصيل القيراط واللون والنقاء.',
    tags: 'authenticity, certificate, gia, hallmark, trust'
  },
  {
    id: 'K-J02',
    tenant_id: 'al-noor-jewelry',
    category: 'delivery',
    question: 'What are your delivery and viewing options across the GCC?',
    question_ar: 'ما هي خيارات التوصيل والمعاينة في قطر ودول الخليج؟',
    answer: 'We offer complimentary private salon viewings at Place Vendôme or The Pearl, as well as insured armored courier delivery across Qatar, UAE, Saudi Arabia, and Kuwait within 48 to 72 hours.',
    answer_ar: 'نوفر خدمة المعاينة الخاصة في صالوناتنا بقطر (بلاس فاندوم أو اللؤلؤة)، بالإضافة إلى شحن آمن وسريع عبر ناقل مصفح ومؤمن لكافة دول الخليج خلال 48 إلى 72 ساعة.',
    tags: 'delivery, shipping, gcc, courier, salon, viewing'
  },
  {
    id: 'K-J03',
    tenant_id: 'al-noor-jewelry',
    category: 'policy',
    question: 'What is your ring resizing and customization policy?',
    question_ar: 'ما هي سياسة تعديل المقاس والطلب الخاص؟',
    answer: 'Complimentary ring resizing is included with every purchase and completed within 3 business days by our master in-house jewelers. Bespoke engravings and custom settings require 7-10 business days.',
    answer_ar: 'تعديل مقاس الخاتم خدمة مجانية مقدمة مع كل عملية شراء ويتم إنجازها خلال 3 أيام عمل بواسطة أمهر صائغينا. النقش والطلبات الخاصة تستغرق 7-10 أيام عمل.',
    tags: 'sizing, resizing, custom, bespoke, policy'
  },

  // --- Saffron Table Policies ---
  {
    id: 'K-R01',
    tenant_id: 'saffron-table',
    category: 'policy',
    question: 'What is your cancellation and deposit policy?',
    question_ar: 'ما هي سياسة الإلغاء وتأكيد الحجز؟',
    answer: 'Reservations for our tasting degustation require a deposit of 500 EGP per guest. Deposits are fully refundable if cancelled at least 24 hours prior to your seating time. Changes to party size can be made up to 6 hours before arrival.',
    answer_ar: 'تتطلب حجوزات قائمة التذوق عربون تأكيد بقيمة 500 جنيه للشخص، وهو مسترد بالكامل في حال الإلغاء قبل 24 ساعة من موعد الحجز. يمكن تعديل عدد الضيوف حتى 6 ساعات قبل الموعد.',
    tags: 'deposit, cancellation, refund, table, policy'
  },
  {
    id: 'K-R02',
    tenant_id: 'saffron-table',
    category: 'allergies',
    question: 'Can you accommodate allergies and dietary restrictions?',
    question_ar: 'هل يمكنكم تلبية الحساسية والأنظمة الغذائية الخاصة؟',
    answer: 'Yes. Our culinary team accommodates vegetarian, gluten-free, dairy-free, and shellfish restrictions. Please inform us when drafting your reservation so Chef Tarek can prepare tailored course substitutions.',
    answer_ar: 'نعم، يمكننا تلبية متطلبات الأنظمة النباتية، وحساسية الجلوتين، ومنتجات الألبان، والمأكولات البحرية. يُرجى توضيح ذلك أثناء الحجز ليقوم الشيف طارق بإعداد البدائل المناسبة.',
    tags: 'allergies, gluten-free, dietary, vegetarian'
  },
  {
    id: 'K-R03',
    tenant_id: 'saffron-table',
    category: 'hours',
    question: 'What are the dining hours and dress code?',
    question_ar: 'ما هي مواعيد العمل وقواعد الزي؟',
    answer: 'We welcome guests Tuesday through Sunday from 6:00 PM to midnight. Tasting seatings begin promptly at 7:30 PM and 9:30 PM. The dress code is Smart Casual / Elegant Evening attire.',
    answer_ar: 'نستقبل ضيوفنا الكرام من الثلاثاء إلى الأحد من 6:00 مساءً حتى منتصف الليل. تبدأ جلسات التذوق في تمام 7:30 و9:30 مساءً. الزي المطلوب: أنيق ومرتب (Smart Casual).',
    tags: 'hours, dress code, schedule'
  },

  // --- Vitalis Health Policies ---
  {
    id: 'K-H01',
    tenant_id: 'vitalis-health',
    category: 'preparation',
    question: 'What preparation is required before the Executive Longevity Screening?',
    question_ar: 'ما هي التعليمات والتحضيرات المطلوبة قبل الفحص الشامل؟',
    answer: 'A fasting period of 10 to 12 hours prior to your morning appointment is required for accurate biomarker analysis. Plain water is encouraged. Avoid intense workouts and heavy alcohol 24 hours prior.',
    answer_ar: 'يُشترط الصيام لمدة 10 إلى 12 ساعة قبل موعد الفحص الصباحي لضمان دقة التحاليل. شرب الماء مسموح وموصى به. يُرجى تجنب التمارين الشاقة أو الوجبات الدسمة قبل 24 ساعة.',
    tags: 'fasting, prep, screening, blood, test'
  },
  {
    id: 'K-H02',
    tenant_id: 'vitalis-health',
    category: 'policy',
    question: 'What is the role of this digital assistant regarding medical advice?',
    question_ar: 'ما هي حدود المساعد الرقمي في النصائح الطبية؟',
    answer: 'Vitalis AI Agent assists with clinic schedules, test package explanations, pricing, and administrative booking holds. It cannot provide clinical diagnoses, triage acute emergencies, or prescribe medications. In case of acute medical symptoms, please visit an emergency department immediately.',
    answer_ar: 'مساعد فايتاليس مخصص للمساعدة الإدارية في مواعيد العيادة وشرح باقات الفحص والأسعار وحجز المواعيد. لا يقدم المساعد أي تشخيص طبي أو وصفات علاجية. في الحالات الطارئة يُرجى التوجه فورًا إلى قسم الطوارئ.',
    tags: 'medical guardrail, policy, disclaimer, safety'
  }
];

const booking_slots = [
  // Saffron Table slots
  { id: 'SLOT-R01', tenant_id: 'saffron-table', slot_date: '2026-10-26', slot_time: '19:30', service_type: 'Chef Tasting Degustation', capacity: 10, booked_count: 4, status: 'available' },
  { id: 'SLOT-R02', tenant_id: 'saffron-table', slot_date: '2026-10-26', slot_time: '21:30', service_type: 'Chef Tasting Degustation', capacity: 10, booked_count: 2, status: 'available' },
  { id: 'SLOT-R03', tenant_id: 'saffron-table', slot_date: '2026-10-27', slot_time: '19:30', service_type: 'Chef Tasting Degustation', capacity: 10, booked_count: 8, status: 'available' },
  { id: 'SLOT-R04', tenant_id: 'saffron-table', slot_date: '2026-10-27', slot_time: '21:30', service_type: 'Chef Tasting Degustation', capacity: 10, booked_count: 10, status: 'booked' },

  // Vitalis Health slots
  { id: 'SLOT-H01', tenant_id: 'vitalis-health', slot_date: '2026-10-26', slot_time: '09:30', service_type: 'Executive Longevity Screening', capacity: 2, booked_count: 0, status: 'available' },
  { id: 'SLOT-H02', tenant_id: 'vitalis-health', slot_date: '2026-10-26', slot_time: '11:00', service_type: 'Executive Longevity Screening', capacity: 2, booked_count: 1, status: 'available' },
  { id: 'SLOT-H03', tenant_id: 'vitalis-health', slot_date: '2026-10-27', slot_time: '10:00', service_type: 'Cardio-Vascular Assessment', capacity: 2, booked_count: 0, status: 'available' }
];

module.exports = {
  tenants,
  products,
  inventory,
  knowledge_base,
  booking_slots
};
