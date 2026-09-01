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

# Topics are the areas of decision-making a parent recognises, NOT the way the
# literature is filed. They were originally five - food, sleep, screens,
# activity, learning - which put twenty-six unrelated claims on one food screen:
# peanut allergy sat beside heavy metals in rice and breastfeeding duration, and
# the scatter was unreadable. Allergens, first foods, milk and food safety are
# separate decisions a parent makes at separate moments, so they get separate
# screens. Colours run in families so the split still reads as one subject.
TOPICS = {
    # Food & feeding
    "allergies": {
        "name": "Allergies",
        "colour": "#e8833a",
        "blurb": "Introducing peanut, egg and other allergens, and what prevents allergy",
    },
    "solids": {
        "name": "Starting Solids",
        "colour": "#f0a24b",
        "blurb": "When and how to begin solid food, textures and baby-led weaning",
    },
    "milk": {
        "name": "Milk & Drinks",
        "colour": "#d9694a",
        "blurb": "Breastfeeding, formula, cow's milk, plant milks and juice",
    },
    "nutrients": {
        "name": "Nutrients",
        "colour": "#c07a3c",
        "blurb": "Vitamin D, iron, omega-3 and vitamin K",
    },
    "food_safety": {
        "name": "Food Safety",
        "colour": "#b5562e",
        "blurb": "Honey, salt, sugar, heavy metals and ultra-processed food",
    },
    # Sleep
    "safe_sleep": {
        "name": "Safe Sleep",
        "colour": "#4a5fd0",
        "blurb": "Sleep position, bed and room sharing, bedding and SIDS risk",
    },
    "sleep_patterns": {
        "name": "Sleep Patterns",
        "colour": "#5b8ee1",
        "blurb": "How much infants sleep, night waking, and what is normal",
    },
    "settling": {
        "name": "Settling & Routines",
        "colour": "#7a6ee1",
        "blurb": "Sleep training, bedtime routines and self-settling",
    },
    # Screens
    "screen_time": {
        "name": "Screen Time",
        "colour": "#b5539c",
        "blurb": "Guidelines, background TV, co-viewing and video calls",
    },
    "screen_effects": {
        "name": "Screens & Development",
        "colour": "#8f3f7c",
        "blurb": "Effects on language, attention, sleep, feeding and weight",
    },
    # Movement
    "motor": {
        "name": "Movement & Motor Skills",
        "colour": "#d94f4f",
        "blurb": "Tummy time, crawling, walkers and how movement develops",
    },
    "active_play": {
        "name": "Active Play & Outdoors",
        "colour": "#e07a63",
        "blurb": "Activity guidelines, sedentary time, outdoors, swimming and massage",
    },
    # Learning
    "language": {
        "name": "Language & Reading",
        "colour": "#39a86b",
        "blurb": "Talking, reading aloud, bilingualism and baby sign",
    },
    "play": {
        "name": "Play & Care",
        "colour": "#4fb98a",
        "blurb": "Free play, pretend play, toys, music and childcare",
    },
}

# ── Claims ───────────────────────────────────────────────────────────────────

CLAIMS = {

    # ══ FOOD ═════════════════════════════════════════════════════════════════

    # -- Allergen introduction --
    "peanut_intro_early": {
        "topic": "allergies", "group": "Peanut",
        "claim": "Introducing peanut before 6 months of age reduces the risk of peanut allergy",
        "query": "early peanut introduction infant allergy prevention randomized",
        "age_range": "4-6 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "introducing peanut before 6 months",
        "claim_outcome": "peanut allergy",
        "keyword_hints": ["peanut", "early introduction", "allergy prevention", "tolerance", "LEAP", "sensitization"],
    },
    "peanut_intro_delay_risk": {
        "topic": "allergies", "group": "Peanut",
        "claim": "Introducing peanut before 12 months reduces the risk of peanut allergy",
        "query": "delayed peanut introduction infant allergy risk avoidance",
        "age_range": "12+ months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "introducing peanut before 12 months",
        "claim_outcome": "peanut allergy",
        "keyword_hints": ["peanut", "delay", "avoidance", "later introduction", "allergy risk", "prevalence"],
    },
    "egg_intro_early": {
        "topic": "allergies", "group": "Egg",
        "claim": "Introducing egg between 4 and 6 months reduces the risk of egg allergy",
        "query": "early egg introduction infant allergy prevention trial",
        "age_range": "4-6 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "introducing egg between 4 and 6 months",
        "claim_outcome": "egg allergy",
        "keyword_hints": ["egg", "early introduction", "allergy", "prevention", "tolerance"],
    },
    "egg_cooked_safer": {
        "topic": "allergies", "group": "Egg",
        "claim": "Eggs should be prepared well cooked to prevent illness until 12 months of age",
        "query": "cooked versus raw egg infant allergenicity introduction",
        "tested_as": "Consumption of raw or lightly cooked egg before 12 months increases the risk of illness",
        "age_range": "4-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "raw or lightly cooked egg before 12 months",
        "claim_outcome": "illness",
        "keyword_hints": ["egg", "cooked", "raw", "baked", "heated", "allergenicity"],
    },
    "allergen_variety_early": {
        "topic": "allergies", "group": "Other allergens",
        "claim": "Introducing multiple allergenic foods early reduces overall food allergy risk",
        "query": "early introduction multiple allergenic foods infant allergy prevention",
        "age_range": "4-12 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "introducing multiple allergenic foods early",
        "claim_outcome": "overall food allergy risk",
        "keyword_hints": ["multiple allergen", "diverse diet", "food diversity", "allergy prevention", "EAT study"],
    },
    "hydrolysed_formula_allergy": {
        "topic": "allergies", "group": "Other allergens",
        "claim": "Hydrolysed formula prevents allergic disease in high-risk infants",
        "query": "hydrolysed formula infant allergy prevention high risk atopy",
        "age_range": "0-6 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "hydrolysed formula",
        "claim_outcome": "allergic disease in high-risk infants",
        "keyword_hints": ["hydrolysed", "hydrolyzed", "partially hydrolysed", "formula", "atopy", "allergy prevention"],
    },

    # -- Starting solids --
    "weaning_6m": {
        "topic": "solids", "group": "Timing",
        "claim": "Complementary feeding should begin at around 6 months of age",
        "tested_as": "Introducing complementary foods at around 6 months is associated with better outcomes than introducing them earlier or later",
        "query": "complementary feeding introduction 6 months infant timing",
        "age_range": "6 months",
        "claim_type": "comparative",
        "claim_sign": 1,
        "claim_exposure": "introducing complementary foods around 6 months (vs earlier/later)",
        "claim_outcome": "better outcomes",
        "keyword_hints": ["complementary feeding", "weaning", "6 months", "solid food", "introduction", "timing"],
    },
    "weaning_before_4m_risk": {
        "topic": "solids", "group": "Timing",
        "claim": "Introducing solid foods before 4 months increases health risks",
        "query": "early introduction solid foods before 4 months infant risk",
        "age_range": "0-4 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "introducing solid foods before 4 months",
        "claim_outcome": "health risks",
        "keyword_hints": ["before 4 months", "early solid", "premature introduction", "risk", "obesity", "infection"],
    },
    "baby_led_weaning": {
        "topic": "solids", "group": "Method",
        "claim": "Baby-led weaning supports healthy appetite self-regulation",
        "query": "baby led weaning infant self regulation appetite growth",
        "age_range": "6-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "baby-led weaning",
        "claim_outcome": "healthy appetite self-regulation",
        "keyword_hints": ["baby-led", "baby led weaning", "blw", "self-feeding", "satiety", "appetite", "self-regulation"],
    },
    "blw_choking": {
        "topic": "solids", "group": "Method",
        "claim": "Baby-led weaning increases the risk of choking",
        "query": "baby led weaning choking gagging risk infant safety",
        "age_range": "6-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "baby-led weaning",
        "claim_outcome": "choking",
        "keyword_hints": ["choking", "gagging", "baby-led", "blw", "airway", "safety"],
    },
    "texture_window": {
        "topic": "solids", "group": "Textures & tastes",
        "claim": "Delaying lumpy textures beyond 9 months increases later feeding difficulties",
        "query": "delayed lumpy texture introduction infant feeding difficulties later",
        "age_range": "6-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "delaying lumpy textures beyond 9 months",
        "claim_outcome": "later feeding difficulties",
        "keyword_hints": ["texture", "lumpy", "critical window", "feeding difficulties", "fussy", "chewing"],
    },
    "repeated_exposure_veg": {
        "topic": "solids", "group": "Textures & tastes",
        "claim": "Repeated exposure increases an infant's acceptance of vegetables",
        "query": "repeated exposure vegetable acceptance infant taste learning",
        "age_range": "6-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "repeated exposure to vegetables",
        "claim_outcome": "acceptance of vegetables",
        "keyword_hints": ["repeated exposure", "vegetable", "acceptance", "taste", "familiarisation", "liking"],
    },

    # -- Milk & drinks --
    "breastfeeding_6m": {
        "topic": "milk", "group": "Breastfeeding",
        "claim": "Exclusive breastfeeding for the first 6 months gives the best health outcomes",
        "query": "exclusive breastfeeding six months infant health outcomes",
        "tested_as": "Exclusive breastfeeding for the first 6 months leads to better health outcomes",
        "age_range": "0-6 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "exclusive breastfeeding for the first 6 months",
        "claim_outcome": "better health outcomes",
        "keyword_hints": ["exclusive breastfeeding", "6 months", "infection", "growth", "outcomes"],
    },
    "cow_milk_12m": {
        "topic": "milk", "group": "Cow's milk",
        "claim": "Cow's milk should not be given as a main drink before 12 months",
        "tested_as": "Cow's milk as the main drink before 12 months is associated with worse outcomes such as iron deficiency",
        "query": "cow milk introduction before 12 months infant main drink",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "cow's milk as main drink before 12 months",
        "claim_outcome": "worse outcomes such as iron deficiency",
        "keyword_hints": ["cow milk", "cows milk", "main drink", "12 months", "introduction"],
    },
    "cow_milk_anaemia": {
        "topic": "milk", "group": "Cow's milk",
        "claim": "Early cow's milk introduction increases the risk of iron deficiency anaemia",
        "query": "cow milk infant iron deficiency anaemia gastrointestinal blood loss",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "early cow's milk introduction",
        "claim_outcome": "iron deficiency anaemia",
        "keyword_hints": ["cow milk", "iron deficiency", "anaemia", "anemia", "ferritin", "blood loss"],
    },
    "juice_limit": {
        "topic": "milk", "group": "Other drinks",
        "claim": "Fruit juice should be avoided before 12 months",
        "tested_as": "Fruit juice consumption before 12 months is associated with worse health outcomes",
        "query": "fruit juice infant intake dental caries weight guidelines",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "fruit juice consumption before 12 months",
        "claim_outcome": "worse health outcomes",
        "keyword_hints": ["fruit juice", "juice", "caries", "sugar", "guideline", "intake"],
    },
    "plant_milk_inadequate": {
        "topic": "milk", "group": "Other drinks",
        "claim": "Plant-based milks are nutritionally inadequate as a main drink for infants",
        "query": "plant based milk alternative infant nutrition adequacy rice soy almond",
        "tested_as": "Plant-based milks as a main drink lead to poor health outcomes",
        "age_range": "0-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "plant-based milk as main drink",
        "claim_outcome": "poor health outcomes",
        "keyword_hints": ["plant-based", "rice milk", "almond milk", "soy milk", "inadequate", "protein", "nutrient"],
    },

    # -- Nutrients --
    "vit_d_supplement": {
        "topic": "nutrients", "group": "Supplements",
        "claim": "Breastfed infants require vitamin D supplementation",
        "query": "vitamin D supplementation breastfed infant deficiency",
        "tested_as": "Vitamin D supplementation in breastfed infants reduces vitamin D deficiency and rickets",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "vitamin D supplementation in breastfed infants",
        "claim_outcome": "vitamin D deficiency and rickets",
        "keyword_hints": ["vitamin d", "supplement", "breastfed", "deficiency", "rickets"],
    },
    "iron_rich_6m": {
        "topic": "nutrients", "group": "From the diet",
        "claim": "Iron-rich complementary foods are needed from 6 months",
        "query": "iron rich complementary food infant 6 months stores depletion",
        "tested_as": "Iron-rich complementary foods from 6 months lead to better health outcomes",
        "age_range": "6-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "iron-rich complementary foods from 6 months",
        "claim_outcome": "better health outcomes",
        "keyword_hints": ["iron", "complementary food", "ferritin", "stores", "fortified", "meat", "deficiency"],
    },
    "dha_brain": {
        "topic": "nutrients", "group": "From the diet",
        "claim": "Omega-3 DHA intake in infancy supports brain and visual development",
        "query": "DHA omega 3 infant brain visual development supplementation",
        "age_range": "0-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "omega-3 DHA intake in infancy",
        "claim_outcome": "brain and visual development",
        "keyword_hints": ["dha", "omega-3", "docosahexaenoic", "visual acuity", "cognitive", "neurodevelopment"],
    },
    "vitamin_k_birth": {
        "topic": "nutrients", "group": "Supplements",
        "claim": "Vitamin K at birth prevents haemorrhagic disease of the newborn",
        "query": "vitamin K prophylaxis newborn haemorrhagic disease bleeding",
        "age_range": "0-6 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "vitamin K at birth",
        "claim_outcome": "haemorrhagic disease of the newborn",
        "keyword_hints": ["vitamin k", "prophylaxis", "haemorrhagic", "hemorrhagic", "bleeding", "newborn"],
    },

    # -- Safety --
    "honey_avoid_12m": {
        "topic": "food_safety", "group": "Avoid entirely",
        "claim": "Honey should be avoided before 12 months because of infant botulism risk",
        "tested_as": "Honey consumption before 12 months is associated with infant botulism",
        "query": "honey infant botulism Clostridium botulinum spores risk",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "honey consumption before 12 months",
        "claim_outcome": "infant botulism",
        "keyword_hints": ["honey", "botulism", "clostridium", "spore", "infant"],
    },
    "salt_limit": {
        "topic": "food_safety", "group": "Limit",
        "claim": "Added salt should be avoided in the infant diet",
        "tested_as": "Higher sodium intake in infancy is associated with worse health outcomes",
        "query": "sodium salt intake infant blood pressure renal load",
        "age_range": "0-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "higher sodium intake in infancy",
        "claim_outcome": "worse health outcomes",
        "keyword_hints": ["salt", "sodium", "blood pressure", "renal", "intake"],
    },
    "sugar_limit": {
        "topic": "food_safety", "group": "Limit",
        "claim": "Free sugars should be avoided before 24 months",
        "tested_as": "Free sugar intake before 24 months is associated with worse health outcomes",
        "query": "free sugar intake infant toddler dental caries taste preference",
        "age_range": "0-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "free sugar intake before 24 months",
        "claim_outcome": "worse health outcomes",
        "keyword_hints": ["sugar", "sweet", "caries", "taste preference", "free sugars"],
    },
    "heavy_metals_rice": {
        "topic": "food_safety", "group": "Contaminants",
        "claim": "Rice-based infant foods should be avoided because they contain inorganic arsenic and will lead to poor health",
        "query": "inorganic arsenic rice infant cereal heavy metals exposure",
        "tested_as": "Rice-based infant foods lead to poor health",
        "age_range": "0-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "rice-based infant foods",
        "claim_outcome": "poor health",
        "keyword_hints": ["arsenic", "heavy metal", "rice cereal", "cadmium", "lead", "contamination"],
    },
    "upf_infant": {
        "topic": "food_safety", "group": "Limit",
        "claim": "Ultra-processed foods in infancy are associated with poorer diet quality",
        "query": "ultra processed food infant toddler diet quality commercial baby food",
        "age_range": "6-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "ultra-processed food intake in infancy",
        "claim_outcome": "poorer diet quality",
        "keyword_hints": ["ultra-processed", "ultraprocessed", "commercial baby food", "diet quality", "nutrient density"],
    },

    # ══ SLEEP ════════════════════════════════════════════════════════════════

    # -- Safe sleep --
    "back_to_sleep": {
        "topic": "safe_sleep", "group": "Position",
        "claim": "Placing infants on their back to sleep reduces the risk of SIDS",
        "query": "supine sleep position sudden infant death syndrome risk reduction",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "placing infants on their back to sleep",
        "claim_outcome": "SIDS",
        "keyword_hints": ["supine", "prone", "sleep position", "sids", "sudden infant death", "back to sleep"],
    },
    "room_sharing": {
        "topic": "safe_sleep", "group": "Where baby sleeps",
        "claim": "Room-sharing without bed-sharing reduces the risk of SIDS",
        "query": "room sharing infant sleep location sudden infant death risk",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "room-sharing without bed-sharing",
        "claim_outcome": "SIDS",
        "keyword_hints": ["room sharing", "room-sharing", "sleep location", "sids", "separate surface"],
    },
    "bed_sharing_risk": {
        "topic": "safe_sleep", "group": "Where baby sleeps",
        "claim": "Bed-sharing increases the risk of sudden unexpected infant death",
        "query": "bed sharing co-sleeping sudden unexpected infant death risk",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "bed-sharing",
        "claim_outcome": "sudden unexpected infant death",
        "keyword_hints": ["bed sharing", "bed-sharing", "co-sleeping", "cosleeping", "suid", "sids", "sofa"],
    },
    "soft_bedding_risk": {
        "topic": "safe_sleep", "group": "Bedding & temperature",
        "claim": "Soft bedding and pillows in the sleep space increase the risk of SIDS",
        "query": "soft bedding pillows infant sleep surface suffocation SIDS risk",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "soft bedding and pillows in sleep space",
        "claim_outcome": "SIDS",
        "keyword_hints": ["soft bedding", "pillow", "duvet", "bumper", "suffocation", "sleep surface"],
    },
    "pacifier_sids": {
        "topic": "safe_sleep", "group": "Other SIDS factors",
        "claim": "Pacifier use at sleep onset reduces the risk of SIDS",
        "query": "pacifier dummy use sleep sudden infant death syndrome protective",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "pacifier use at sleep onset",
        "claim_outcome": "SIDS",
        "keyword_hints": ["pacifier", "dummy", "soother", "sids", "protective", "arousal"],
    },
    "overheating_sids": {
        "topic": "safe_sleep", "group": "Bedding & temperature",
        "claim": "Overheating during sleep increases the risk of SIDS",
        "query": "overheating thermal stress infant sleep sudden infant death risk",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "overheating during sleep",
        "claim_outcome": "SIDS",
        "keyword_hints": ["overheating", "thermal", "temperature", "sids", "wrapping", "tog"],
    },
    "swaddle_rolling_risk": {
        "topic": "safe_sleep", "group": "Position",
        "claim": "Swaddling becomes unsafe once an infant can roll over",
        "query": "swaddling infant rolling prone sudden infant death risk",
        "tested_as": "Swaddling after an infant can roll over increases the risk of sudden unexpected infant death",
        "age_range": "0-6 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "swaddling after the infant can roll over",
        "claim_outcome": "sudden unexpected infant death",
        "keyword_hints": ["swaddle", "swaddling", "rolling", "prone", "sids", "hip dysplasia"],
    },

    # -- Sleep patterns --
    "sleep_hours_infant": {
        "topic": "sleep_patterns", "group": "How much sleep",
        "claim": "Infants aged 4-12 months need 12-16 hours of sleep per 24 hours",
        "query": "infant sleep duration normative hours reference 24 hour",
        "age_range": "4-12 months",
        "claim_type": "threshold",
        "claim_sign": 0,
        "claim_exposure": "infants aged 4-12 months",
        "claim_outcome": "sleep duration per 24 hours",
        "keyword_hints": ["sleep duration", "hours of sleep", "total sleep time", "normative", "reference values"],
    },
    "night_waking_normal": {
        "topic": "sleep_patterns", "group": "Night waking",
        "claim": "Frequent night waking is developmentally normal in the first year",
        "query": "infant night waking normal developmental prevalence first year",
        "age_range": "0-12 months",
        "claim_type": "threshold",
        "claim_sign": 0,
        "claim_exposure": "infants in the first year",
        "claim_outcome": "frequency of night waking",
        "keyword_hints": ["night waking", "night-waking", "normative", "prevalence", "developmental", "signalling"],
    },
    "sleep_consolidation_6m": {
        "topic": "sleep_patterns", "group": "How much sleep",
        "claim": "Most infants sleep through the night by 6 months of age",
        "query": "sleeping through the night infant 6 months consolidation prevalence",
        "age_range": "0-12 months",
        "claim_type": "threshold",
        "claim_sign": 0,
        "claim_exposure": "infant age (months)",
        "claim_outcome": "proportion sleeping through the night",
        "keyword_hints": ["sleeping through", "consolidation", "6 months", "uninterrupted", "prevalence"],
    },
    "short_sleep_obesity": {
        "topic": "sleep_patterns", "group": "Consequences",
        "claim": "Short sleep duration in infancy is associated with later obesity",
        "query": "short sleep duration infancy childhood obesity adiposity risk",
        "age_range": "0-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "short sleep duration in infancy",
        "claim_outcome": "later obesity",
        "keyword_hints": ["short sleep", "sleep duration", "obesity", "adiposity", "bmi", "weight gain"],
    },
    "nap_memory": {
        "topic": "sleep_patterns", "group": "Naps",
        "claim": "Daytime naps support memory consolidation and learning in infants",
        "query": "infant nap daytime sleep memory consolidation learning",
        "age_range": "6-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "daytime naps",
        "claim_outcome": "memory consolidation and learning",
        "keyword_hints": ["nap", "daytime sleep", "memory consolidation", "learning", "retention"],
    },

    # -- Settling & environment --
    "sleep_training_effective": {
        "topic": "settling", "group": "Sleep training",
        "claim": "Behavioural sleep interventions improve infant sleep and maternal wellbeing",
        "query": "behavioural sleep intervention infant randomized controlled trial outcomes",
        "age_range": "6-18 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "behavioural sleep interventions",
        "claim_outcome": "infant sleep and maternal wellbeing",
        "keyword_hints": ["sleep intervention", "extinction", "graduated", "controlled comforting", "sleep training", "maternal mood"],
    },
    "sleep_training_harm": {
        "topic": "settling", "group": "Sleep training",
        "claim": "Behavioural sleep training causes lasting harm to infant attachment or stress regulation",
        "query": "sleep training infant cortisol attachment long term emotional outcomes",
        "age_range": "6-18 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "behavioural sleep training",
        "claim_outcome": "harm to attachment or stress regulation",
        "keyword_hints": ["cortisol", "attachment", "stress response", "sleep training", "long-term", "emotional development"],
    },
    "bedtime_routine": {
        "topic": "settling", "group": "Routines & environment",
        "claim": "A consistent bedtime routine improves infant sleep",
        "query": "consistent bedtime routine infant sleep outcomes randomized",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "consistent bedtime routine",
        "claim_outcome": "infant sleep",
        "keyword_hints": ["bedtime routine", "consistent routine", "sleep onset", "sleep quality", "nightly"],
    },
    "self_settling": {
        "topic": "settling", "group": "Sleep training",
        "claim": "Teaching infants to self-settle leads to less waking at night",
        "query": "self soothing settling infant night waking sleep onset association",
        "age_range": "3-18 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "teaching infants to self-settle",
        "claim_outcome": "night waking",
        "keyword_hints": ["self-settling", "self-soothing", "sleep onset association", "night waking", "independent"],
    },
    "screen_before_bed_sleep": {
        "topic": "settling", "group": "Routines & environment",
        "claim": "Screen exposure before bedtime worsens infant sleep",
        "query": "screen media use before bedtime infant toddler sleep quality duration",
        "age_range": "6-36 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "screen exposure before bedtime",
        "claim_outcome": "infant sleep",
        "keyword_hints": ["screen", "bedtime", "sleep onset", "sleep duration", "media use", "evening"],
    },

    # ══ SCREENS ══════════════════════════════════════════════════════════════

    "no_screens_under_2": {
        "topic": "screen_time", "group": "Guidelines",
        "claim": "Screen media should be avoided before 18-24 months",
        "tested_as": "Screen media exposure before 18-24 months is associated with worse developmental outcomes",
        "query": "screen media exposure under 2 years infant guidelines outcomes",
        "age_range": "0-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "screen media exposure before 18-24 months",
        "claim_outcome": "worse developmental outcomes",
        "keyword_hints": ["screen time", "screen media", "under 2", "guideline", "media exposure", "television"],
    },
    "background_tv": {
        "topic": "screen_time", "group": "How screens are used",
        "claim": "Background television reduces the quantity and quality of parent-child interaction",
        "query": "background television parent child interaction infant play quality",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "background television",
        "claim_outcome": "quantity and quality of parent-child interaction",
        "keyword_hints": ["background television", "background tv", "parent-child interaction", "play quality", "distraction"],
    },
    "video_chat_exception": {
        "topic": "screen_time", "group": "How screens are used",
        "claim": "Video chatting is an acceptable exception to infant screen-time limits",
        "tested_as": "Video chatting with a live partner is associated with better outcomes than pre-recorded screen content in infancy",
        "query": "video chat infant social contingency learning screen exception",
        "age_range": "6-24 months",
        "claim_type": "comparative",
        "claim_sign": 1,
        "claim_exposure": "video chatting with live partner (vs pre-recorded content)",
        "claim_outcome": "better developmental outcomes",
        "keyword_hints": ["video chat", "videochat", "skype", "facetime", "social contingency", "video deficit"],
    },
    "coviewing_benefit": {
        "topic": "screen_time", "group": "How screens are used",
        "claim": "Adult co-viewing reduces the negative effects of screen time",
        "query": "parent co-viewing joint media engagement infant toddler learning outcomes",
        "age_range": "12-36 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "adult co-viewing",
        "claim_outcome": "negative effects of screen time",
        "keyword_hints": ["co-viewing", "coviewing", "joint media engagement", "scaffolding", "parent mediation"],
    },
    "screen_language_delay": {
        "topic": "screen_effects", "group": "Language & learning",
        "claim": "Higher screen time in infancy is associated with language delay",
        "query": "screen time infant toddler language delay expressive vocabulary",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "higher screen time in infancy",
        "claim_outcome": "language delay",
        "keyword_hints": ["screen time", "language delay", "expressive language", "vocabulary", "communication"],
    },
    "video_deficit": {
        "topic": "screen_effects", "group": "Language & learning",
        "claim": "Infants learn less from video than from equivalent live interaction",
        "query": "video deficit effect infant learning transfer live demonstration",
        "age_range": "6-36 months",
        "claim_type": "comparative",
        "claim_sign": -1,
        "claim_exposure": "video presentation (vs live interaction)",
        "claim_outcome": "infant learning",
        "keyword_hints": ["video deficit", "transfer deficit", "imitation", "live demonstration", "learning"],
    },
    "screen_attention": {
        "topic": "screen_effects", "group": "Attention",
        "claim": "Early screen exposure is associated with later attention problems",
        "query": "early television screen exposure infant later attention problems ADHD",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "early screen exposure",
        "claim_outcome": "later attention problems",
        "keyword_hints": ["attention", "adhd", "executive function", "screen exposure", "inattention"],
    },
    "educational_apps": {
        "topic": "screen_effects", "group": "Language & learning",
        "claim": "Educational apps improve learning outcomes in toddlers",
        "query": "educational app touchscreen toddler learning outcomes evaluation",
        "age_range": "18-48 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "educational apps",
        "claim_outcome": "learning outcomes in toddlers",
        "keyword_hints": ["educational app", "touchscreen", "tablet", "learning outcome", "vocabulary", "numeracy"],
    },
    "screen_sleep": {
        "topic": "screen_effects", "group": "Sleep & body",
        "claim": "Higher screen time is associated with shorter sleep in young children",
        "query": "screen time young children sleep duration association",
        "age_range": "0-60 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "higher screen time",
        "claim_outcome": "shorter sleep in young children",
        "keyword_hints": ["screen time", "sleep duration", "sleep quality", "bedtime", "association"],
    },
    "screen_obesity": {
        "topic": "screen_effects", "group": "Sleep & body",
        "claim": "Higher screen time is associated with higher BMI in early childhood",
        "query": "screen time early childhood body mass index obesity association",
        "age_range": "12-60 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "higher screen time",
        "claim_outcome": "higher BMI in early childhood",
        "keyword_hints": ["screen time", "bmi", "obesity", "adiposity", "sedentary"],
    },
    "screen_feeding": {
        "topic": "screen_effects", "group": "Sleep & body",
        "claim": "Screen use during meals is associated with poorer eating behaviour",
        "query": "screen use during mealtime infant toddler eating behaviour intake",
        "age_range": "6-60 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "screen use during meals",
        "claim_outcome": "poorer eating behaviour",
        "keyword_hints": ["mealtime", "distracted eating", "screen", "food intake", "responsive feeding"],
    },

    # ══ ACTIVITY & MOTOR ═════════════════════════════════════════════════════

    "tummy_time_motor": {
        "topic": "motor", "group": "Tummy time & positioning",
        "claim": "Tummy time supports gross motor development",
        "query": "tummy time prone positioning infant gross motor development",
        "age_range": "0-6 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "tummy time",
        "claim_outcome": "gross motor development",
        "keyword_hints": ["tummy time", "prone position", "motor development", "milestones", "gross motor"],
    },
    "tummy_time_plagiocephaly": {
        "topic": "motor", "group": "Tummy time & positioning",
        "claim": "Tummy time reduces positional plagiocephaly",
        "query": "tummy time prone positioning positional plagiocephaly head shape prevention",
        "age_range": "0-6 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "tummy time",
        "claim_outcome": "positional plagiocephaly",
        "keyword_hints": ["plagiocephaly", "head shape", "flat head", "positional", "tummy time", "repositioning"],
    },
    "restrictive_devices": {
        "topic": "motor", "group": "Equipment",
        "claim": "Prolonged time in walkers or containers delays motor development",
        "query": "infant walker container restrictive device motor development delay",
        "age_range": "0-18 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "prolonged time in walkers or containers",
        "claim_outcome": "motor development",
        "keyword_hints": ["baby walker", "container", "bouncer", "restrictive", "motor delay", "sitting device"],
    },
    "walkers_injury": {
        "topic": "motor", "group": "Equipment",
        "claim": "Baby walkers increase the risk of injury",
        "query": "baby walker infant injury falls stairs emergency department",
        "age_range": "6-18 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "baby walkers",
        "claim_outcome": "injury",
        "keyword_hints": ["baby walker", "injury", "falls", "stairs", "emergency", "burns"],
    },
    "barefoot_walking": {
        "topic": "motor", "group": "Equipment",
        "claim": "Barefoot walking supports healthy foot development in early childhood",
        "query": "barefoot versus shod walking children foot development gait",
        "age_range": "12-60 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "barefoot walking",
        "claim_outcome": "healthy foot development",
        "keyword_hints": ["barefoot", "shod", "footwear", "foot development", "arch", "gait"],
    },
    "crawling_not_required": {
        "topic": "motor", "group": "Milestones",
        "claim": "Crawling is a required precursor to walking",
        "query": "crawling stage skipping infant locomotor development walking onset",
        "tested_as": "Crawling is positively associated with the later onset of independent walking",
        "age_range": "6-18 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "crawling",
        "claim_outcome": "onset of independent walking",
        "keyword_hints": ["crawling", "creeping", "locomotor", "walking onset", "skip", "developmental sequence"],
    },
    "physical_activity_guideline": {
        "topic": "active_play", "group": "How much activity",
        "claim": "Infants should have at least 30 minutes of tummy time or active play daily",
        "tested_as": "Greater daily tummy time or active play in infancy is associated with better motor development",
        "query": "infant physical activity guideline 30 minutes tummy time daily recommendation",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "daily tummy time or active play",
        "claim_outcome": "better motor development",
        "keyword_hints": ["physical activity", "guideline", "30 minutes", "recommendation", "active play", "adherence"],
    },
    "sedentary_time_development": {
        "topic": "active_play", "group": "How much activity",
        "claim": "Prolonged sedentary or restrained time is associated with poorer development",
        "query": "sedentary behaviour restraint infant toddler developmental outcomes",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "prolonged sedentary or restrained time",
        "claim_outcome": "poorer development",
        "keyword_hints": ["sedentary", "restrained", "stroller", "high chair", "developmental outcome", "screen"],
    },
    "outdoor_time_myopia": {
        "topic": "active_play", "group": "Outdoors",
        "claim": "More outdoor time in early childhood reduces the risk of myopia",
        "query": "outdoor time children myopia incidence prevention light exposure",
        "age_range": "12-72 months",
        "claim_type": "association",
        "claim_sign": -1,
        "claim_exposure": "outdoor time in early childhood",
        "claim_outcome": "myopia",
        "keyword_hints": ["outdoor", "myopia", "near work", "light exposure", "refractive error"],
    },
    "infant_swimming": {
        "topic": "active_play", "group": "Classes & touch",
        "claim": "Infant swimming programmes improve motor skill development",
        "query": "infant swimming aquatic programme motor skill development outcomes",
        "age_range": "0-48 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "infant swimming programmes",
        "claim_outcome": "motor skill development",
        "keyword_hints": ["swimming", "aquatic", "water", "motor skill", "programme", "balance"],
    },
    "infant_massage": {
        "topic": "active_play", "group": "Classes & touch",
        "claim": "Infant massage supports growth and development",
        "query": "infant massage therapy growth weight gain development preterm",
        "age_range": "0-12 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "infant massage",
        "claim_outcome": "growth and development",
        "keyword_hints": ["massage", "tactile stimulation", "weight gain", "preterm", "development", "kangaroo"],
    },

    # ══ LEARNING & PLAY ══════════════════════════════════════════════════════

    "reading_language": {
        "topic": "language", "group": "Reading",
        "claim": "Reading aloud to infants improves later language development",
        "query": "shared book reading infant language development vocabulary outcomes",
        "age_range": "0-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "reading aloud to infants",
        "claim_outcome": "later language development",
        "keyword_hints": ["shared reading", "book reading", "read aloud", "vocabulary", "language development", "literacy"],
    },
    "shared_reading_early": {
        "topic": "language", "group": "Reading",
        "claim": "Shared reading beginning in infancy improves later literacy outcomes",
        "query": "early shared reading infancy later literacy school readiness longitudinal",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "shared reading beginning in infancy",
        "claim_outcome": "later literacy outcomes",
        "keyword_hints": ["shared reading", "literacy", "school readiness", "print exposure", "longitudinal"],
    },
    "print_books_vs_ebooks": {
        "topic": "language", "group": "Reading",
        "claim": "Print books produce richer parent-child interaction than electronic books",
        "query": "print versus electronic book shared reading toddler parent interaction",
        "age_range": "12-48 months",
        "claim_type": "comparative",
        "claim_sign": 1,
        "claim_exposure": "print books (vs electronic books)",
        "claim_outcome": "quality of parent-child interaction",
        "keyword_hints": ["print book", "electronic book", "ebook", "tablet", "interaction quality", "dialogic"],
    },
    "talk_volume": {
        "topic": "language", "group": "Talking",
        "claim": "The amount of adult speech directed at an infant predicts vocabulary growth",
        "query": "child directed speech quantity infant vocabulary growth language input",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "amount of adult speech directed at infant",
        "claim_outcome": "vocabulary growth",
        "keyword_hints": ["child-directed speech", "language input", "word count", "vocabulary", "lena"],
    },
    "conversational_turns": {
        "topic": "language", "group": "Talking",
        "claim": "Conversational turn-taking predicts language outcomes better than word count alone",
        "query": "conversational turns versus adult word count child language brain outcomes",
        "age_range": "0-48 months",
        "claim_type": "comparative",
        "claim_sign": 1,
        "claim_exposure": "conversational turn-taking (vs adult word count)",
        "claim_outcome": "language outcomes",
        "keyword_hints": ["conversational turn", "turn-taking", "adult word count", "lena", "language outcome", "brain"],
    },
    "bilingual_no_delay": {
        "topic": "language", "group": "Two languages",
        "claim": "Bilingual exposure in infancy delays language development",
        "query": "bilingual infant language development delay milestones monolingual comparison",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "bilingual exposure in infancy",
        "claim_outcome": "language delay",
        "keyword_hints": ["bilingual", "dual language", "monolingual", "delay", "vocabulary size", "milestones"],
    },
    "baby_sign": {
        "topic": "language", "group": "Signing",
        "claim": "Teaching baby sign language accelerates spoken language development",
        "query": "baby sign language gesture training infant spoken language development",
        "age_range": "6-24 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "teaching baby sign language",
        "claim_outcome": "speech",
        "keyword_hints": ["baby sign", "signing", "gesture", "symbolic gesture", "spoken language", "vocabulary"],
    },
    "free_play": {
        "topic": "play", "group": "Play",
        "claim": "Unstructured play supports cognitive and social development",
        "query": "unstructured free play infant toddler cognitive social development",
        "age_range": "6-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "unstructured play",
        "claim_outcome": "cognitive and social development",
        "keyword_hints": ["free play", "unstructured", "exploratory play", "cognitive development", "social development"],
    },
    "pretend_play": {
        "topic": "play", "group": "Play",
        "claim": "Pretend play supports social cognition and theory of mind",
        "query": "pretend play symbolic play toddler theory of mind social cognition",
        "age_range": "18-60 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "pretend play",
        "claim_outcome": "social cognition and theory of mind",
        "keyword_hints": ["pretend play", "symbolic play", "theory of mind", "social cognition", "imagination"],
    },
    "fewer_toys": {
        "topic": "play", "group": "Toys & music",
        "claim": "Fewer toys in the environment leads to better learning retention and motor skill development",
        "query": "number of toys toddler play quality sustained attention environment",
        "age_range": "12-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "fewer toys in the play environment",
        "claim_outcome": "learning retention and motor skill development",
        "keyword_hints": ["number of toys", "toy quantity", "play quality", "sustained attention", "distraction"],
    },
    "music_exposure": {
        "topic": "play", "group": "Toys & music",
        "claim": "Musical activity in infancy supports language and auditory development",
        "query": "infant music training exposure auditory language development outcomes",
        "age_range": "0-36 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "musical activity in infancy",
        "claim_outcome": "language and auditory development",
        "keyword_hints": ["music", "musical training", "rhythm", "auditory", "language development", "singing"],
    },
    "childcare_quality": {
        "topic": "play", "group": "Care & schooling",
        "claim": "High-quality group childcare improves cognitive outcomes",
        "query": "childcare quality early education cognitive outcomes children longitudinal",
        "age_range": "6-60 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "high-quality group childcare",
        "claim_outcome": "cognitive outcomes",
        "keyword_hints": ["childcare", "day care", "quality", "cognitive outcome", "early education", "longitudinal"],
    },
    "early_academics": {
        "topic": "play", "group": "Care & schooling",
        "claim": "Early formal academic instruction improves later school achievement",
        "query": "early formal academic instruction preschool later achievement fade out",
        "age_range": "36-72 months",
        "claim_type": "association",
        "claim_sign": 1,
        "claim_exposure": "early formal academic instruction",
        "claim_outcome": "later school achievement",
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

# `claim_type` says what SHAPE of question a claim asks, which decides how a
# paper's finding is turned into a verdict:
#
#   association   one exposure, one outcome, a direction between them. The
#                 verdict is a polarity comparison (BACKLOG 1c): a paper
#                 reporting the complement exposure ("prone increases risk")
#                 supports a claim asserting the converse ("supine reduces it").
#   comparative   two exposures contrasted ("print books produce richer
#                 interaction than electronic"). Polarity applies, but the
#                 exposure is a contrast rather than a single thing.
#   threshold     a quantity, range or prevalence ("infants aged 4-12 months
#                 need 12-16 hours of sleep"). There is NO direction to agree
#                 with. A paper reports a value that falls inside the stated
#                 range or outside it, so the verdict is containment, not
#                 polarity. Scoring these as associations is what puts a
#                 confident-looking number on a question that was never asked.
#
# It is also the field the age timeline will branch on (BACKLOG 8): a threshold
# claim plots as a band, an association as a point.
CLAIM_TYPES = ("association", "comparative", "threshold")


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
