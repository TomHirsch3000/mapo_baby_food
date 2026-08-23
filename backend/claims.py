#!/usr/bin/env python3
"""
claims.py — The claim registry. Single source of truth for the whole app.

Two levels, matching the two screens above the evidence view:

    TOPIC      →  CLAIM
    "sleep"       "Placing infants on their back to sleep reduces the risk of SIDS"
    (landing)     (claim node)  → evidence view

A CLAIM is one falsifiable statement. Papers are sorted into supports /
refutes / neutral by the evaluator, so claims are never stored as for/against
pairs.

`group` is a display sub-heading inside a topic (e.g. "Safe sleep"), not a
navigation level — you go straight from topic to claims.

Sizing note: every claim carries an OpenAlex match count fetched by
`import_claims.py --counts-only`, and node size is derived from that count
rather than from how many papers we have collected. A claim can therefore look
large while holding no evidence at all — that is deliberate, and is how the map
distinguishes "well studied" from "lots of adjacent literature, little on this
specific question".
"""

# ── Topics — the nodes on the landing page ───────────────────────────────────
#
# Topic size is the sum of its claims' OpenAlex counts. A single umbrella query
# per topic was tried and abandoned: OpenAlex `search` ANDs terms, so a phrase
# like "infant sleep safe sleep SIDS night waking" returned 50 works while its
# individual claims return thousands.

TOPICS = {
    "food": {
        "name": "Food & Nutrition",
        "colour": "#e8833a",
        "blurb": "Allergens, first foods, milk, nutrients and food safety",
    },
    "sleep": {
        "name": "Sleep",
        "colour": "#5b6ee1",
        "blurb": "Safe sleep, sleep patterns, settling and environment",
    },
    "screens": {
        "name": "Screens & Media",
        "colour": "#b5539c",
        "blurb": "Screen exposure, media content and its effects",
    },
    "activity": {
        "name": "Activity & Motor",
        "colour": "#d94f4f",
        "blurb": "Tummy time, movement, milestones and physical development",
    },
    "learning": {
        "name": "Learning & Play",
        "colour": "#39a86b",
        "blurb": "Language, reading, play and early cognitive development",
    },
}

# ── Claims ───────────────────────────────────────────────────────────────────

CLAIMS = {

    # ══ FOOD ═════════════════════════════════════════════════════════════════

    # -- Allergen introduction --
    "peanut_intro_early": {
        "topic": "food", "group": "Allergen introduction",
        "claim": "Introducing peanut before 6 months of age reduces the risk of peanut allergy",
        "query": "early peanut introduction infant allergy prevention randomized",
        "age_range": "4-6 months",
        "keyword_hints": ["peanut", "early introduction", "allergy prevention", "tolerance", "LEAP", "sensitization"],
    },
    "peanut_intro_delay_risk": {
        "topic": "food", "group": "Allergen introduction",
        "claim": "Delaying peanut introduction beyond 12 months increases the risk of peanut allergy",
        "query": "delayed peanut introduction infant allergy risk avoidance",
        "age_range": "12+ months",
        "keyword_hints": ["peanut", "delay", "avoidance", "later introduction", "allergy risk", "prevalence"],
    },
    "egg_intro_early": {
        "topic": "food", "group": "Allergen introduction",
        "claim": "Introducing egg between 4 and 6 months reduces the risk of egg allergy",
        "query": "early egg introduction infant allergy prevention trial",
        "age_range": "4-6 months",
        "keyword_hints": ["egg", "early introduction", "allergy", "prevention", "tolerance"],
    },
    "egg_cooked_safer": {
        "topic": "food", "group": "Allergen introduction",
        "claim": "Well-cooked egg is safer than raw or lightly cooked egg for first introduction",
        "query": "cooked versus raw egg infant allergenicity introduction",
        "age_range": "4-12 months",
        "keyword_hints": ["egg", "cooked", "raw", "baked", "heated", "allergenicity"],
    },
    "allergen_variety_early": {
        "topic": "food", "group": "Allergen introduction",
        "claim": "Introducing multiple allergenic foods early reduces overall food allergy risk",
        "query": "early introduction multiple allergenic foods infant allergy prevention",
        "age_range": "4-12 months",
        "keyword_hints": ["multiple allergen", "diverse diet", "food diversity", "allergy prevention", "EAT study"],
    },
    "hydrolysed_formula_allergy": {
        "topic": "food", "group": "Allergen introduction",
        "claim": "Hydrolysed formula prevents allergic disease in high-risk infants",
        "query": "hydrolysed formula infant allergy prevention high risk atopy",
        "age_range": "0-6 months",
        "keyword_hints": ["hydrolysed", "hydrolyzed", "partially hydrolysed", "formula", "atopy", "allergy prevention"],
    },

    # -- Starting solids --
    "weaning_6m": {
        "topic": "food", "group": "Starting solids",
        "claim": "Complementary feeding should begin at around 6 months of age",
        "tested_as": "Introducing complementary foods at around 6 months is associated with better outcomes than introducing them earlier or later",
        "query": "complementary feeding introduction 6 months infant timing",
        "age_range": "6 months",
        "keyword_hints": ["complementary feeding", "weaning", "6 months", "solid food", "introduction", "timing"],
    },
    "weaning_before_4m_risk": {
        "topic": "food", "group": "Starting solids",
        "claim": "Introducing solid foods before 4 months increases health risks",
        "query": "early introduction solid foods before 4 months infant risk",
        "age_range": "0-4 months",
        "keyword_hints": ["before 4 months", "early solid", "premature introduction", "risk", "obesity", "infection"],
    },
    "baby_led_weaning": {
        "topic": "food", "group": "Starting solids",
        "claim": "Baby-led weaning supports healthy appetite self-regulation",
        "query": "baby led weaning infant self regulation appetite growth",
        "age_range": "6-12 months",
        "keyword_hints": ["baby-led", "baby led weaning", "blw", "self-feeding", "satiety", "appetite", "self-regulation"],
    },
    "blw_choking": {
        "topic": "food", "group": "Starting solids",
        "claim": "Baby-led weaning increases the risk of choking",
        "query": "baby led weaning choking gagging risk infant safety",
        "age_range": "6-12 months",
        "keyword_hints": ["choking", "gagging", "baby-led", "blw", "airway", "safety"],
    },
    "texture_window": {
        "topic": "food", "group": "Starting solids",
        "claim": "Delaying lumpy textures beyond 9 months increases later feeding difficulties",
        "query": "delayed lumpy texture introduction infant feeding difficulties later",
        "age_range": "6-12 months",
        "keyword_hints": ["texture", "lumpy", "critical window", "feeding difficulties", "fussy", "chewing"],
    },
    "repeated_exposure_veg": {
        "topic": "food", "group": "Starting solids",
        "claim": "Repeated exposure increases an infant's acceptance of vegetables",
        "query": "repeated exposure vegetable acceptance infant taste learning",
        "age_range": "6-24 months",
        "keyword_hints": ["repeated exposure", "vegetable", "acceptance", "taste", "familiarisation", "liking"],
    },

    # -- Milk & drinks --
    "breastfeeding_6m": {
        "topic": "food", "group": "Milk & drinks",
        "claim": "Exclusive breastfeeding for the first 6 months gives the best health outcomes",
        "query": "exclusive breastfeeding six months infant health outcomes",
        "age_range": "0-6 months",
        "keyword_hints": ["exclusive breastfeeding", "6 months", "infection", "growth", "outcomes"],
    },
    "cow_milk_12m": {
        "topic": "food", "group": "Milk & drinks",
        "claim": "Cow's milk should not be given as a main drink before 12 months",
        "tested_as": "Cow's milk as the main drink before 12 months is associated with worse outcomes such as iron deficiency",
        "query": "cow milk introduction before 12 months infant main drink",
        "age_range": "0-12 months",
        "keyword_hints": ["cow milk", "cows milk", "main drink", "12 months", "introduction"],
    },
    "cow_milk_anaemia": {
        "topic": "food", "group": "Milk & drinks",
        "claim": "Early cow's milk introduction increases the risk of iron deficiency anaemia",
        "query": "cow milk infant iron deficiency anaemia gastrointestinal blood loss",
        "age_range": "0-12 months",
        "keyword_hints": ["cow milk", "iron deficiency", "anaemia", "anemia", "ferritin", "blood loss"],
    },
    "juice_limit": {
        "topic": "food", "group": "Milk & drinks",
        "claim": "Fruit juice should be avoided before 12 months",
        "tested_as": "Fruit juice consumption before 12 months is associated with worse health outcomes",
        "query": "fruit juice infant intake dental caries weight guidelines",
        "age_range": "0-12 months",
        "keyword_hints": ["fruit juice", "juice", "caries", "sugar", "guideline", "intake"],
    },
    "plant_milk_inadequate": {
        "topic": "food", "group": "Milk & drinks",
        "claim": "Plant-based milks are nutritionally inadequate as a main drink for infants",
        "query": "plant based milk alternative infant nutrition adequacy rice soy almond",
        "age_range": "0-24 months",
        "keyword_hints": ["plant-based", "rice milk", "almond milk", "soy milk", "inadequate", "protein", "nutrient"],
    },

    # -- Nutrients --
    "vit_d_supplement": {
        "topic": "food", "group": "Nutrients",
        "claim": "Breastfed infants require vitamin D supplementation",
        "query": "vitamin D supplementation breastfed infant deficiency",
        "age_range": "0-12 months",
        "keyword_hints": ["vitamin d", "supplement", "breastfed", "deficiency", "rickets"],
    },
    "iron_rich_6m": {
        "topic": "food", "group": "Nutrients",
        "claim": "Iron-rich complementary foods are needed from 6 months",
        "query": "iron rich complementary food infant 6 months stores depletion",
        "age_range": "6-12 months",
        "keyword_hints": ["iron", "complementary food", "ferritin", "stores", "fortified", "meat", "deficiency"],
    },
    "dha_brain": {
        "topic": "food", "group": "Nutrients",
        "claim": "Omega-3 DHA intake in infancy supports brain and visual development",
        "query": "DHA omega 3 infant brain visual development supplementation",
        "age_range": "0-24 months",
        "keyword_hints": ["dha", "omega-3", "docosahexaenoic", "visual acuity", "cognitive", "neurodevelopment"],
    },
    "vitamin_k_birth": {
        "topic": "food", "group": "Nutrients",
        "claim": "Vitamin K at birth prevents haemorrhagic disease of the newborn",
        "query": "vitamin K prophylaxis newborn haemorrhagic disease bleeding",
        "age_range": "0-6 months",
        "keyword_hints": ["vitamin k", "prophylaxis", "haemorrhagic", "hemorrhagic", "bleeding", "newborn"],
    },

    # -- Safety --
    "honey_avoid_12m": {
        "topic": "food", "group": "Food safety",
        "claim": "Honey should be avoided before 12 months because of infant botulism risk",
        "tested_as": "Honey consumption before 12 months is associated with infant botulism",
        "query": "honey infant botulism Clostridium botulinum spores risk",
        "age_range": "0-12 months",
        "keyword_hints": ["honey", "botulism", "clostridium", "spore", "infant"],
    },
    "salt_limit": {
        "topic": "food", "group": "Food safety",
        "claim": "Added salt should be avoided in the infant diet",
        "tested_as": "Higher sodium intake in infancy is associated with worse health outcomes",
        "query": "sodium salt intake infant blood pressure renal load",
        "age_range": "0-24 months",
        "keyword_hints": ["salt", "sodium", "blood pressure", "renal", "intake"],
    },
    "sugar_limit": {
        "topic": "food", "group": "Food safety",
        "claim": "Free sugars should be avoided before 24 months",
        "tested_as": "Free sugar intake before 24 months is associated with worse health outcomes",
        "query": "free sugar intake infant toddler dental caries taste preference",
        "age_range": "0-24 months",
        "keyword_hints": ["sugar", "sweet", "caries", "taste preference", "free sugars"],
    },
    "heavy_metals_rice": {
        "topic": "food", "group": "Food safety",
        "claim": "Rice-based infant foods contain concerning levels of inorganic arsenic",
        "query": "inorganic arsenic rice infant cereal heavy metals exposure",
        "age_range": "0-24 months",
        "keyword_hints": ["arsenic", "heavy metal", "rice cereal", "cadmium", "lead", "contamination"],
    },
    "upf_infant": {
        "topic": "food", "group": "Food safety",
        "claim": "Ultra-processed foods in infancy are associated with poorer diet quality",
        "query": "ultra processed food infant toddler diet quality commercial baby food",
        "age_range": "6-36 months",
        "keyword_hints": ["ultra-processed", "ultraprocessed", "commercial baby food", "diet quality", "nutrient density"],
    },

    # ══ SLEEP ════════════════════════════════════════════════════════════════

    # -- Safe sleep --
    "back_to_sleep": {
        "topic": "sleep", "group": "Safe sleep",
        "claim": "Placing infants on their back to sleep reduces the risk of SIDS",
        "query": "supine sleep position sudden infant death syndrome risk reduction",
        "age_range": "0-12 months",
        "keyword_hints": ["supine", "prone", "sleep position", "sids", "sudden infant death", "back to sleep"],
    },
    "room_sharing": {
        "topic": "sleep", "group": "Safe sleep",
        "claim": "Room-sharing without bed-sharing reduces the risk of SIDS",
        "query": "room sharing infant sleep location sudden infant death risk",
        "age_range": "0-12 months",
        "keyword_hints": ["room sharing", "room-sharing", "sleep location", "sids", "separate surface"],
    },
    "bed_sharing_risk": {
        "topic": "sleep", "group": "Safe sleep",
        "claim": "Bed-sharing increases the risk of sudden unexpected infant death",
        "query": "bed sharing co-sleeping sudden unexpected infant death risk",
        "age_range": "0-12 months",
        "keyword_hints": ["bed sharing", "bed-sharing", "co-sleeping", "cosleeping", "suid", "sids", "sofa"],
    },
    "soft_bedding_risk": {
        "topic": "sleep", "group": "Safe sleep",
        "claim": "Soft bedding and pillows in the sleep space increase the risk of SIDS",
        "query": "soft bedding pillows infant sleep surface suffocation SIDS risk",
        "age_range": "0-12 months",
        "keyword_hints": ["soft bedding", "pillow", "duvet", "bumper", "suffocation", "sleep surface"],
    },
    "pacifier_sids": {
        "topic": "sleep", "group": "Safe sleep",
        "claim": "Pacifier use at sleep onset reduces the risk of SIDS",
        "query": "pacifier dummy use sleep sudden infant death syndrome protective",
        "age_range": "0-12 months",
        "keyword_hints": ["pacifier", "dummy", "soother", "sids", "protective", "arousal"],
    },
    "overheating_sids": {
        "topic": "sleep", "group": "Safe sleep",
        "claim": "Overheating during sleep increases the risk of SIDS",
        "query": "overheating thermal stress infant sleep sudden infant death risk",
        "age_range": "0-12 months",
        "keyword_hints": ["overheating", "thermal", "temperature", "sids", "wrapping", "tog"],
    },
    "swaddle_rolling_risk": {
        "topic": "sleep", "group": "Safe sleep",
        "claim": "Swaddling becomes unsafe once an infant can roll over",
        "query": "swaddling infant rolling prone sudden infant death risk",
        "age_range": "0-6 months",
        "keyword_hints": ["swaddle", "swaddling", "rolling", "prone", "sids", "hip dysplasia"],
    },

    # -- Sleep patterns --
    "sleep_hours_infant": {
        "topic": "sleep", "group": "Sleep patterns",
        "claim": "Infants aged 4-12 months need 12-16 hours of sleep per 24 hours",
        "query": "infant sleep duration normative hours reference 24 hour",
        "age_range": "4-12 months",
        "keyword_hints": ["sleep duration", "hours of sleep", "total sleep time", "normative", "reference values"],
    },
    "night_waking_normal": {
        "topic": "sleep", "group": "Sleep patterns",
        "claim": "Frequent night waking is developmentally normal in the first year",
        "query": "infant night waking normal developmental prevalence first year",
        "age_range": "0-12 months",
        "keyword_hints": ["night waking", "night-waking", "normative", "prevalence", "developmental", "signalling"],
    },
    "sleep_consolidation_6m": {
        "topic": "sleep", "group": "Sleep patterns",
        "claim": "Most infants sleep through the night by 6 months of age",
        "query": "sleeping through the night infant 6 months consolidation prevalence",
        "age_range": "0-12 months",
        "keyword_hints": ["sleeping through", "consolidation", "6 months", "uninterrupted", "prevalence"],
    },
    "short_sleep_obesity": {
        "topic": "sleep", "group": "Sleep patterns",
        "claim": "Short sleep duration in infancy is associated with later obesity",
        "query": "short sleep duration infancy childhood obesity adiposity risk",
        "age_range": "0-24 months",
        "keyword_hints": ["short sleep", "sleep duration", "obesity", "adiposity", "bmi", "weight gain"],
    },
    "nap_memory": {
        "topic": "sleep", "group": "Sleep patterns",
        "claim": "Daytime naps support memory consolidation and learning in infants",
        "query": "infant nap daytime sleep memory consolidation learning",
        "age_range": "6-24 months",
        "keyword_hints": ["nap", "daytime sleep", "memory consolidation", "learning", "retention"],
    },

    # -- Settling & environment --
    "sleep_training_effective": {
        "topic": "sleep", "group": "Settling & environment",
        "claim": "Behavioural sleep interventions improve infant sleep and maternal wellbeing",
        "query": "behavioural sleep intervention infant randomized controlled trial outcomes",
        "age_range": "6-18 months",
        "keyword_hints": ["sleep intervention", "extinction", "graduated", "controlled comforting", "sleep training", "maternal mood"],
    },
    "sleep_training_harm": {
        "topic": "sleep", "group": "Settling & environment",
        "claim": "Behavioural sleep training causes lasting harm to infant attachment or stress regulation",
        "query": "sleep training infant cortisol attachment long term emotional outcomes",
        "age_range": "6-18 months",
        "keyword_hints": ["cortisol", "attachment", "stress response", "sleep training", "long-term", "emotional development"],
    },
    "bedtime_routine": {
        "topic": "sleep", "group": "Settling & environment",
        "claim": "A consistent bedtime routine improves infant sleep",
        "query": "consistent bedtime routine infant sleep outcomes randomized",
        "age_range": "0-36 months",
        "keyword_hints": ["bedtime routine", "consistent routine", "sleep onset", "sleep quality", "nightly"],
    },
    "self_settling": {
        "topic": "sleep", "group": "Settling & environment",
        "claim": "Infants who can self-settle at bedtime wake less during the night",
        "query": "self soothing settling infant night waking sleep onset association",
        "age_range": "3-18 months",
        "keyword_hints": ["self-settling", "self-soothing", "sleep onset association", "night waking", "independent"],
    },
    "screen_before_bed_sleep": {
        "topic": "sleep", "group": "Settling & environment",
        "claim": "Screen exposure before bedtime worsens infant sleep",
        "query": "screen media use before bedtime infant toddler sleep quality duration",
        "age_range": "6-36 months",
        "keyword_hints": ["screen", "bedtime", "sleep onset", "sleep duration", "media use", "evening"],
    },

    # ══ SCREENS ══════════════════════════════════════════════════════════════

    "no_screens_under_2": {
        "topic": "screens", "group": "Exposure & guidelines",
        "claim": "Screen media should be avoided before 18-24 months",
        "tested_as": "Screen media exposure before 18-24 months is associated with worse developmental outcomes",
        "query": "screen media exposure under 2 years infant guidelines outcomes",
        "age_range": "0-24 months",
        "keyword_hints": ["screen time", "screen media", "under 2", "guideline", "media exposure", "television"],
    },
    "background_tv": {
        "topic": "screens", "group": "Exposure & guidelines",
        "claim": "Background television reduces the quantity and quality of parent-child interaction",
        "query": "background television parent child interaction infant play quality",
        "age_range": "0-36 months",
        "keyword_hints": ["background television", "background tv", "parent-child interaction", "play quality", "distraction"],
    },
    "video_chat_exception": {
        "topic": "screens", "group": "Exposure & guidelines",
        "claim": "Video chatting is an acceptable exception to infant screen-time limits",
        "tested_as": "Video chatting with a live partner is associated with better outcomes than pre-recorded screen content in infancy",
        "query": "video chat infant social contingency learning screen exception",
        "age_range": "6-24 months",
        "keyword_hints": ["video chat", "videochat", "skype", "facetime", "social contingency", "video deficit"],
    },
    "coviewing_benefit": {
        "topic": "screens", "group": "Exposure & guidelines",
        "claim": "Adult co-viewing reduces the negative effects of screen time",
        "query": "parent co-viewing joint media engagement infant toddler learning outcomes",
        "age_range": "12-36 months",
        "keyword_hints": ["co-viewing", "coviewing", "joint media engagement", "scaffolding", "parent mediation"],
    },
    "screen_language_delay": {
        "topic": "screens", "group": "Development effects",
        "claim": "Higher screen time in infancy is associated with language delay",
        "query": "screen time infant toddler language delay expressive vocabulary",
        "age_range": "0-36 months",
        "keyword_hints": ["screen time", "language delay", "expressive language", "vocabulary", "communication"],
    },
    "video_deficit": {
        "topic": "screens", "group": "Development effects",
        "claim": "Infants learn less from video than from equivalent live interaction",
        "query": "video deficit effect infant learning transfer live demonstration",
        "age_range": "6-36 months",
        "keyword_hints": ["video deficit", "transfer deficit", "imitation", "live demonstration", "learning"],
    },
    "screen_attention": {
        "topic": "screens", "group": "Development effects",
        "claim": "Early screen exposure is associated with later attention problems",
        "query": "early television screen exposure infant later attention problems ADHD",
        "age_range": "0-36 months",
        "keyword_hints": ["attention", "adhd", "executive function", "screen exposure", "inattention"],
    },
    "educational_apps": {
        "topic": "screens", "group": "Development effects",
        "claim": "Educational apps improve learning outcomes in toddlers",
        "query": "educational app touchscreen toddler learning outcomes evaluation",
        "age_range": "18-48 months",
        "keyword_hints": ["educational app", "touchscreen", "tablet", "learning outcome", "vocabulary", "numeracy"],
    },
    "screen_sleep": {
        "topic": "screens", "group": "Development effects",
        "claim": "Higher screen time is associated with shorter sleep in young children",
        "query": "screen time young children sleep duration association",
        "age_range": "0-60 months",
        "keyword_hints": ["screen time", "sleep duration", "sleep quality", "bedtime", "association"],
    },
    "screen_obesity": {
        "topic": "screens", "group": "Development effects",
        "claim": "Higher screen time is associated with higher BMI in early childhood",
        "query": "screen time early childhood body mass index obesity association",
        "age_range": "12-60 months",
        "keyword_hints": ["screen time", "bmi", "obesity", "adiposity", "sedentary"],
    },
    "screen_feeding": {
        "topic": "screens", "group": "Development effects",
        "claim": "Screen use during meals is associated with poorer eating behaviour",
        "query": "screen use during mealtime infant toddler eating behaviour intake",
        "age_range": "6-60 months",
        "keyword_hints": ["mealtime", "distracted eating", "screen", "food intake", "responsive feeding"],
    },

    # ══ ACTIVITY & MOTOR ═════════════════════════════════════════════════════

    "tummy_time_motor": {
        "topic": "activity", "group": "Tummy time & positioning",
        "claim": "Tummy time supports gross motor development",
        "query": "tummy time prone positioning infant gross motor development",
        "age_range": "0-6 months",
        "keyword_hints": ["tummy time", "prone position", "motor development", "milestones", "gross motor"],
    },
    "tummy_time_plagiocephaly": {
        "topic": "activity", "group": "Tummy time & positioning",
        "claim": "Tummy time reduces positional plagiocephaly",
        "query": "tummy time prone positioning positional plagiocephaly head shape prevention",
        "age_range": "0-6 months",
        "keyword_hints": ["plagiocephaly", "head shape", "flat head", "positional", "tummy time", "repositioning"],
    },
    "restrictive_devices": {
        "topic": "activity", "group": "Equipment & environment",
        "claim": "Prolonged time in walkers or containers delays motor development",
        "query": "infant walker container restrictive device motor development delay",
        "age_range": "0-18 months",
        "keyword_hints": ["baby walker", "container", "bouncer", "restrictive", "motor delay", "sitting device"],
    },
    "walkers_injury": {
        "topic": "activity", "group": "Equipment & environment",
        "claim": "Baby walkers increase the risk of injury",
        "query": "baby walker infant injury falls stairs emergency department",
        "age_range": "6-18 months",
        "keyword_hints": ["baby walker", "injury", "falls", "stairs", "emergency", "burns"],
    },
    "barefoot_walking": {
        "topic": "activity", "group": "Equipment & environment",
        "claim": "Barefoot walking supports healthy foot development in early childhood",
        "query": "barefoot versus shod walking children foot development gait",
        "age_range": "12-60 months",
        "keyword_hints": ["barefoot", "shod", "footwear", "foot development", "arch", "gait"],
    },
    "crawling_not_required": {
        "topic": "activity", "group": "Milestones",
        "claim": "Crawling is not a required precursor to walking",
        "query": "crawling stage skipping infant locomotor development walking onset",
        "age_range": "6-18 months",
        "keyword_hints": ["crawling", "creeping", "locomotor", "walking onset", "skip", "developmental sequence"],
    },
    "motor_cognitive_link": {
        "topic": "activity", "group": "Milestones",
        "claim": "Early motor development predicts later cognitive outcomes",
        "query": "early motor development later cognitive language outcomes longitudinal",
        "age_range": "0-36 months",
        "keyword_hints": ["motor development", "cognitive outcome", "longitudinal", "predict", "milestone", "language"],
    },
    "physical_activity_guideline": {
        "topic": "activity", "group": "Activity levels",
        "claim": "Infants should have at least 30 minutes of tummy time or active play daily",
        "tested_as": "Greater daily tummy time or active play in infancy is associated with better motor development",
        "query": "infant physical activity guideline 30 minutes tummy time daily recommendation",
        "age_range": "0-12 months",
        "keyword_hints": ["physical activity", "guideline", "30 minutes", "recommendation", "active play", "adherence"],
    },
    "sedentary_time_development": {
        "topic": "activity", "group": "Activity levels",
        "claim": "Prolonged sedentary or restrained time is associated with poorer development",
        "query": "sedentary behaviour restraint infant toddler developmental outcomes",
        "age_range": "0-36 months",
        "keyword_hints": ["sedentary", "restrained", "stroller", "high chair", "developmental outcome", "screen"],
    },
    "outdoor_time_myopia": {
        "topic": "activity", "group": "Activity levels",
        "claim": "More outdoor time in early childhood reduces the risk of myopia",
        "query": "outdoor time children myopia incidence prevention light exposure",
        "age_range": "12-72 months",
        "keyword_hints": ["outdoor", "myopia", "near work", "light exposure", "refractive error"],
    },
    "infant_swimming": {
        "topic": "activity", "group": "Activity levels",
        "claim": "Infant swimming programmes improve motor skill development",
        "query": "infant swimming aquatic programme motor skill development outcomes",
        "age_range": "0-48 months",
        "keyword_hints": ["swimming", "aquatic", "water", "motor skill", "programme", "balance"],
    },
    "infant_massage": {
        "topic": "activity", "group": "Activity levels",
        "claim": "Infant massage supports growth and development",
        "query": "infant massage therapy growth weight gain development preterm",
        "age_range": "0-12 months",
        "keyword_hints": ["massage", "tactile stimulation", "weight gain", "preterm", "development", "kangaroo"],
    },

    # ══ LEARNING & PLAY ══════════════════════════════════════════════════════

    "reading_language": {
        "topic": "learning", "group": "Reading & literacy",
        "claim": "Reading aloud to infants improves later language development",
        "query": "shared book reading infant language development vocabulary outcomes",
        "age_range": "0-24 months",
        "keyword_hints": ["shared reading", "book reading", "read aloud", "vocabulary", "language development", "literacy"],
    },
    "shared_reading_early": {
        "topic": "learning", "group": "Reading & literacy",
        "claim": "Shared reading beginning in infancy improves later literacy outcomes",
        "query": "early shared reading infancy later literacy school readiness longitudinal",
        "age_range": "0-36 months",
        "keyword_hints": ["shared reading", "literacy", "school readiness", "print exposure", "longitudinal"],
    },
    "print_books_vs_ebooks": {
        "topic": "learning", "group": "Reading & literacy",
        "claim": "Print books produce richer parent-child interaction than electronic books",
        "query": "print versus electronic book shared reading toddler parent interaction",
        "age_range": "12-48 months",
        "keyword_hints": ["print book", "electronic book", "ebook", "tablet", "interaction quality", "dialogic"],
    },
    "talk_volume": {
        "topic": "learning", "group": "Language input",
        "claim": "The amount of adult speech directed at an infant predicts vocabulary growth",
        "query": "child directed speech quantity infant vocabulary growth language input",
        "age_range": "0-36 months",
        "keyword_hints": ["child-directed speech", "language input", "word count", "vocabulary", "lena"],
    },
    "conversational_turns": {
        "topic": "learning", "group": "Language input",
        "claim": "Conversational turn-taking predicts language outcomes better than word count alone",
        "query": "conversational turns versus adult word count child language brain outcomes",
        "age_range": "0-48 months",
        "keyword_hints": ["conversational turn", "turn-taking", "adult word count", "lena", "language outcome", "brain"],
    },
    "bilingual_no_delay": {
        "topic": "learning", "group": "Language input",
        "claim": "Bilingual exposure in infancy does not delay language development",
        "query": "bilingual infant language development delay milestones monolingual comparison",
        "age_range": "0-36 months",
        "keyword_hints": ["bilingual", "dual language", "monolingual", "delay", "vocabulary size", "milestones"],
    },
    "baby_sign": {
        "topic": "learning", "group": "Language input",
        "claim": "Teaching baby sign language accelerates spoken language development",
        "query": "baby sign language gesture training infant spoken language development",
        "age_range": "6-24 months",
        "keyword_hints": ["baby sign", "signing", "gesture", "symbolic gesture", "spoken language", "vocabulary"],
    },
    "responsive_interaction": {
        "topic": "learning", "group": "Play & interaction",
        "claim": "Responsive serve-and-return interaction supports infant brain development",
        "query": "responsive caregiving contingent interaction infant brain development",
        "age_range": "0-24 months",
        "keyword_hints": ["responsive", "contingent", "serve and return", "caregiver interaction", "synchrony"],
    },
    "free_play": {
        "topic": "learning", "group": "Play & interaction",
        "claim": "Unstructured play supports cognitive and social development",
        "query": "unstructured free play infant toddler cognitive social development",
        "age_range": "6-36 months",
        "keyword_hints": ["free play", "unstructured", "exploratory play", "cognitive development", "social development"],
    },
    "pretend_play": {
        "topic": "learning", "group": "Play & interaction",
        "claim": "Pretend play supports social cognition and theory of mind",
        "query": "pretend play symbolic play toddler theory of mind social cognition",
        "age_range": "18-60 months",
        "keyword_hints": ["pretend play", "symbolic play", "theory of mind", "social cognition", "imagination"],
    },
    "fewer_toys": {
        "topic": "learning", "group": "Play & interaction",
        "claim": "Fewer toys in the environment leads to higher quality play",
        "query": "number of toys toddler play quality sustained attention environment",
        "age_range": "12-36 months",
        "keyword_hints": ["number of toys", "toy quantity", "play quality", "sustained attention", "distraction"],
    },
    "music_exposure": {
        "topic": "learning", "group": "Play & interaction",
        "claim": "Musical activity in infancy supports language and auditory development",
        "query": "infant music training exposure auditory language development outcomes",
        "age_range": "0-36 months",
        "keyword_hints": ["music", "musical training", "rhythm", "auditory", "language development", "singing"],
    },
    "childcare_quality": {
        "topic": "learning", "group": "Care & environment",
        "claim": "High-quality group childcare improves cognitive outcomes",
        "query": "childcare quality early education cognitive outcomes children longitudinal",
        "age_range": "6-60 months",
        "keyword_hints": ["childcare", "day care", "quality", "cognitive outcome", "early education", "longitudinal"],
    },
    "early_academics": {
        "topic": "learning", "group": "Care & environment",
        "claim": "Early formal academic instruction improves later school achievement",
        "query": "early formal academic instruction preschool later achievement fade out",
        "age_range": "36-72 months",
        "keyword_hints": ["academic instruction", "direct instruction", "preschool", "fade out", "achievement", "play-based"],
    },
}

# Small cross-topic set used to prove the pipeline end-to-end before a full run.
SEED_CLAIMS = [
    "peanut_intro_early",
    "peanut_intro_delay_risk",
    "back_to_sleep",
    "bed_sharing_risk",
    "no_screens_under_2",
    "screen_language_delay",
]


# ── Lookup helpers ───────────────────────────────────────────────────────────

# A claim carries the wording people actually use ("claim") and, where those
# differ, the wording a study can actually test ("tested_as").
#
# They diverge because a prescriptive claim - "screen media should be avoided
# before 18-24 months" - is not something any paper tests. Asked to judge one,
# mistral extracts the right finding and then inverts the verdict: the identical
# abstract scored "refutes" against that wording and "supports" against
# "...exposure before 18-24 months is associated with worse developmental
# outcomes". Nine of the eighty claims were phrased prescriptively, covering a
# fifth of all judgements.
#
# So the evaluator reads tested_as and the reader sees claim. tested_as is
# surfaced in the UI too - a reader is entitled to know what was actually
# measured on their behalf.
def tested_text(claim_key):
    """What the evaluator should judge against: the empirical wording if the
    claim has one, otherwise the claim itself."""
    cfg = CLAIMS[claim_key]
    return cfg.get("tested_as") or cfg["claim"]


def claims_for_topic(topic_key):
    return {k: v for k, v in CLAIMS.items() if v["topic"] == topic_key}


def groups_for_topic(topic_key):
    """Ordered list of the display sub-headings used inside a topic."""
    seen = []
    for cfg in claims_for_topic(topic_key).values():
        if cfg["group"] not in seen:
            seen.append(cfg["group"])
    return seen


def resolve_claim_keys(selection=None, seed=False):
    """Turn a CLI selection into a list of claim keys.

    selection may name claims or topics; None means everything.
    """
    if seed:
        return list(SEED_CLAIMS)
    if not selection:
        return list(CLAIMS)

    keys = []
    for token in selection:
        if token in CLAIMS:
            keys.append(token)
        elif token in TOPICS:
            keys.extend(claims_for_topic(token))
        else:
            raise KeyError(f"Unknown claim/topic: {token}")
    return list(dict.fromkeys(keys))


def validate():
    """Fail loudly on registry typos."""
    problems = []
    for ck, cfg in CLAIMS.items():
        if cfg.get("topic") not in TOPICS:
            problems.append(f"claim '{ck}' references unknown topic '{cfg.get('topic')}'")
        for field in ("claim", "query", "keyword_hints", "group"):
            if not cfg.get(field):
                problems.append(f"claim '{ck}' is missing '{field}'")
    for tk, cfg in TOPICS.items():
        if not claims_for_topic(tk):
            problems.append(f"topic '{tk}' has no claims")
    for key in SEED_CLAIMS:
        if key not in CLAIMS:
            problems.append(f"SEED_CLAIMS references unknown claim '{key}'")
    return problems


if __name__ == "__main__":
    issues = validate()
    if issues:
        print("Registry problems:")
        for issue in issues:
            print(f"  - {issue}")
        raise SystemExit(1)
    print(f"{len(TOPICS)} topics, {len(CLAIMS)} claims - registry OK")
    for tk, tcfg in TOPICS.items():
        claims = claims_for_topic(tk)
        groups = groups_for_topic(tk)
        print(f"  {tcfg['name']:20s} {len(claims):2d} claims in {len(groups)} groups")
        for g in groups:
            n = sum(1 for c in claims.values() if c["group"] == g)
            print(f"      {g:28s} {n}")
