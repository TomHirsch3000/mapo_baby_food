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
        "guidance": {
            "nhs": {"says": "Introduce peanut from around 6 months, when you start solids. Delaying it past 6 to 12 months may raise your baby's chance of peanut allergy.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/food-allergies-in-babies-and-young-children/"},
            "aap": {"says": "Babies at high risk of peanut allergy (severe eczema or egg allergy) should try peanut foods as early as 4 to 6 months, after other solids.", "url": "https://www.healthychildren.org/English/healthy-living/nutrition/Pages/when-to-introduce-egg-peanut-butter-and-other-common-food-allergens-to-your-baby-food-allergy-prevention-tips.aspx"},
            "agreement": "differ",
            "note": "The AAP recommends peanut as early as 4 to 6 months for high-risk babies, while the NHS says around 6 months for all babies and does not recommend solids before then; both pages are current post-LEAP guidance, and neither says introducing peanut before 6 months benefits low-risk babies.",
        },
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
        "guidance": {
            "nhs": {"says": "Leaving peanut and egg out of your baby's diet past 6 to 12 months may make an allergy to them more likely.", "url": "https://www.nhs.uk/best-start-in-life/baby/weaning/safe-weaning/food-allergies/"},
            "aap": {"says": "Holding peanut back does not protect against allergy; offer it once your baby is ready for solids, usually about 6 months.", "url": "https://www.healthychildren.org/English/healthy-living/nutrition/Pages/when-to-introduce-egg-peanut-butter-and-other-common-food-allergens-to-your-baby-food-allergy-prevention-tips.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Introduce egg from around 6 months; delaying it past 6 to 12 months may raise the risk of egg allergy.", "url": "https://www.nhs.uk/best-start-in-life/baby/weaning/safe-weaning/food-allergies/"},
            "aap": {"says": "Introducing egg early appears to protect against egg allergy.", "url": "https://www.healthychildren.org/English/healthy-living/nutrition/Pages/when-to-introduce-egg-peanut-butter-and-other-common-food-allergens-to-your-baby-food-allergy-prevention-tips.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Eggs without the British Lion mark must be cooked solid for babies; Lion-marked hens' eggs may be raw or lightly cooked.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/foods-to-avoid-giving-babies-and-young-children/"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Introduce allergenic foods one at a time from around 6 months and keep them in the diet to lower allergy risk.", "url": "https://www.nhs.uk/best-start-in-life/baby/weaning/safe-weaning/food-allergies/"},
            "aap": {"says": "Waiting past 4 to 6 months to offer allergenic foods such as egg, dairy, soy, peanut or fish does not prevent food allergy.", "url": "https://www.healthychildren.org/English/ages-stages/baby/feeding-nutrition/Pages/Starting-Solid-Foods.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "Hydrolysed formula does not prevent allergies, even in babies at high risk.", "url": "https://www.healthychildren.org/English/news/Pages/Early-Introduction-of-Peanut-based-Foods-to-Prevent-Allergies.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Start solid foods when your baby is around 6 months old. Before that, breast milk or first infant formula gives them everything they need.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/babys-first-solid-foods/"},
            "aap": {"says": "Give only breast milk for about the first 6 months, then start solid foods once your baby shows they are developmentally ready.", "url": "https://www.healthychildren.org/English/ages-stages/baby/feeding-nutrition/Pages/starting-solid-foods.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Wait until around 6 months before starting solids, even if food labels say from 4 months.", "url": "https://www.nhs.uk/best-start-in-life/baby/weaning/how-to-start-weaning-your-baby/"},
            "aap": {"says": "Give only breast milk for about the first 6 months, though babies may show readiness for solids from about 4 months.", "url": "https://www.healthychildren.org/English/ages-stages/baby/feeding-nutrition/Pages/Starting-Solid-Foods.aspx"},
            "agreement": "differ",
            "note": "Neither body states a risk threshold at 4 months specifically: the NHS tells parents to wait until around 6 months even where labels say 4 months, whereas the AAP recommends about 6 months but also says babies who have doubled their birth weight, typically at about 4 months, may be ready for solids.",
        },
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
        "guidance": {
            "aap": {"says": "Listed as a possible benefit of baby-led weaning: babies stop when full, which may help prevent obesity.", "url": "https://www.healthychildren.org/English/ages-stages/baby/feeding-nutrition/Pages/baby-led-weaning-is-it-safe.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Self-feeding does not carry a higher choking risk than spoon-feeding.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/babys-first-solid-foods/"},
            "aap": {"says": "Some studies suggest baby-led weaning does not raise choking risk compared with traditional feeding.", "url": "https://www.healthychildren.org/English/ages-stages/baby/feeding-nutrition/Pages/baby-led-weaning-is-it-safe.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Babies often need 10 or more tries of a new food, so keep offering it.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/help-your-baby-enjoy-new-foods/"},
            "aap": {"says": "A baby may need 10 to 15 tries of a new food over several months before accepting it.", "url": "https://www.healthychildren.org/English/healthy-living/growing-healthy/Pages/baby-food-and-feeding.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Breast milk alone is recommended for about the first 6 months.", "url": "https://www.nhs.uk/conditions/baby/breastfeeding-and-bottle-feeding/breastfeeding/benefits/"},
            "aap": {"says": "Exclusive breastfeeding is recommended for about the first six months where possible.", "url": "https://www.healthychildren.org/English/ages-stages/baby/breastfeeding/Pages/Where-We-Stand-Breastfeeding.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Do not give cow's milk as your baby's main drink until 12 months. It does not have the right balance of nutrients for them before then.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/drinks-and-cups-for-babies-and-young-children/"},
            "aap": {"says": "Do not give cow's milk before about 12 months. It can irritate the gut, cause blood loss and lead to iron-deficiency anaemia.", "url": "https://www.healthychildren.org/English/ages-stages/baby/formula-feeding/Pages/Why-Formula-Instead-of-Cows-Milk.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "Cow's milk before 1 year can cause iron-deficiency anaemia by irritating the gut lining and causing blood loss.", "url": "https://www.healthychildren.org/English/ages-stages/baby/formula-feeding/Pages/Why-Formula-Instead-of-Cows-Milk.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Babies under 1 do not need juice or smoothies; if given, dilute them heavily and only at mealtimes.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/drinks-and-cups-for-babies-and-young-children/"},
            "aap": {"says": "No juice before 12 months; it displaces more nutritious milk and food.", "url": "https://www.healthychildren.org/English/ages-stages/baby/feeding-nutrition/Pages/Starting-Solid-Foods.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Soya, oat and almond drinks should be avoided before 12 months; they can be given from age 1 as part of a balanced diet.", "url": "https://www.nhs.uk/best-start-in-life/baby/weaning/safe-weaning/food-and-drinks-to-avoid/"},
            "aap": {"says": "No cow's milk or milk substitute, including plant milks, before about 12 months.", "url": "https://www.healthychildren.org/English/ages-stages/baby/formula-feeding/Pages/Why-Formula-Instead-of-Cows-Milk.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Give breastfed babies a daily vitamin D supplement of 8.5 to 10 micrograms from birth to age 1. Formula-fed babies on 500ml a day do not need one.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/vitamins-for-children/"},
            "aap": {"says": "Give breastfed and partly breastfed babies 400 IU of vitamin D a day, starting in the first few days of life.", "url": "https://www.healthychildren.org/English/healthy-living/nutrition/Pages/vitamin-d-on-the-double.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Once solids start at around 6 months, include iron-containing foods such as meat, fish, fortified cereals, beans and greens.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/babys-first-solid-foods/"},
            "aap": {"says": "Iron-rich foods from about 6 months supply the extra iron babies need for growth.", "url": "https://www.healthychildren.org/English/health-issues/conditions/chronic/Pages/Anemia-and-Your-Child.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "DHA and ARA, added to most formulas, are believed to matter for a baby's brain and eye development.", "url": "https://www.healthychildren.org/English/ages-stages/baby/formula-feeding/Pages/choosing-an-infant-formula.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Your baby will be offered a vitamin K injection after birth. It prevents haemorrhagic disease of the newborn, a rare bleeding disorder.", "url": "https://www.nhs.uk/pregnancy/labour-and-birth/what-happens-straight-after/"},
            "aap": {"says": "Every newborn should get a vitamin K shot at birth. One injection protects your baby from vitamin K deficiency bleeding.", "url": "https://www.healthychildren.org/English/ages-stages/prenatal/delivery-beyond/Pages/Where-We-Stand-Administration-of-Vitamin-K.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Do not give honey until your child is over 1 year old. Honey can contain bacteria that cause infant botulism, a very serious illness.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/foods-to-avoid-giving-babies-and-young-children/"},
            "aap": {"says": "Do not give honey to a baby under 12 months. Honey carries botulism spores. It is safe from age 1 onwards.", "url": "https://www.healthychildren.org/English/health-issues/conditions/infections/Pages/Botulism.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Do not add salt to a baby's food or cooking water, and skip stock cubes and gravy; salt is bad for their kidneys.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/foods-to-avoid-giving-babies-and-young-children/"},
            "aap": {"says": "Moderate added salt is acceptable but excess should be discouraged, since taste preferences form early and high sodium may raise blood pressure later.", "url": "https://www.healthychildren.org/English/healthy-living/nutrition/Pages/We-Dont-Need-to-Add-Salt-to-Food.aspx"},
            "agreement": "differ",
            "note": "The NHS tells parents not to add any salt to a baby's food, while the AAP page found (which addresses children's diets generally rather than infants specifically) says moderate added salt is acceptable and only excessive amounts should be discouraged.",
        },
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
        "guidance": {
            "nhs": {"says": "Do not add sugar to a baby's food or drink under 1. From age 1, cap free sugars at 10g a day.", "url": "https://www.nhs.uk/live-well/eat-well/food-types/how-does-sugar-in-our-diet-affect-our-health/"},
            "aap": {"says": "Give no foods or drinks with added sugar at all until your child is 2 years old.", "url": "https://www.healthychildren.org/English/healthy-living/nutrition/Pages/How-to-Reduce-Added-Sugar-in-Your-Childs-Diet.aspx"},
            "agreement": "differ",
            "note": "AAP says avoid added sugar entirely until age 2, while the NHS sets a no-added-sugar rule only under age 1 and then allows up to 10g of free sugars a day from age 1.",
        },
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
        "guidance": {
            "nhs": {"says": "Rice does absorb more arsenic than other grains, but UK limits mean babies can still eat rice; avoid rice drinks under 5.", "url": "https://www.nhs.uk/baby/weaning-and-feeding/foods-to-avoid-giving-babies-and-young-children/"},
            "aap": {"says": "Rice absorbs more arsenic than other crops, so rice cereal should not be your baby's only or first cereal.", "url": "https://www.healthychildren.org/English/ages-stages/baby/feeding-nutrition/Pages/reduce-arsenic.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Always put your baby down to sleep on their back, feet at the end of the cot. This is listed as a way to reduce the risk of SIDS.", "url": "https://www.nhs.uk/baby/caring-for-a-newborn/reduce-the-risk-of-sudden-infant-death-syndrome/"},
            "aap": {"says": "Put your baby on their back for every nap and every night until age 1. Back sleepers are far less likely to die suddenly.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/Preventing-SIDS.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Sleep your baby in their own cot in your room for every sleep for at least the first 6 months to lower SIDS risk.", "url": "https://www.nhs.uk/baby/caring-for-a-newborn/sudden-infant-death-syndrome-sids/"},
            "aap": {"says": "Share a room, not a bed. Room-sharing can cut SIDS risk by up to half and is far safer than bed-sharing.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/a-parents-guide-to-safe-sleep.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "A separate cot in your room is safest, but if you do share a bed, do it safely. Never co-sleep after alcohol, drugs, smoking, or if very tired.", "url": "https://www.nhs.uk/best-start-in-life/baby/baby-basics/newborn-and-baby-sleeping-advice-for-parents/safe-sleep-advice-for-babies/"},
            "aap": {"says": "Do not share a bed with your baby. Sleep in the same room but on separate surfaces; room-sharing without bed-sharing protects against SIDS.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/Preventing-SIDS.aspx"},
            "agreement": "differ",
            "note": "The AAP tells parents not to bed-share at all and to room-share on a separate surface, whereas the NHS accepts that some parents will bed-share and gives conditions for doing it more safely alongside a list of circumstances in which it is never safe.",
        },
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
        "guidance": {
            "nhs": {"says": "Nothing soft near your baby in the cot: soft items can cause overheating and raise the risk of SIDS.", "url": "https://beststartinlife.gov.uk/safer-sleep/"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Consider a dummy at sleep time; some research suggests it can help lower the risk of SIDS.", "url": "https://www.nhs.uk/baby/caring-for-a-newborn/sudden-infant-death-syndrome-sids/"},
            "aap": {"says": "Offer a pacifier at naps and bedtime; it lowers SIDS risk even if it falls out once your baby is asleep.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/a-parents-guide-to-safe-sleep.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Overheating raises SIDS risk. Keep the room at 16C to 20C and avoid too much bedding or clothing.", "url": "https://www.nhs.uk/baby/caring-for-a-newborn/sudden-infant-death-syndrome-sids/"},
            "aap": {"says": "Overheating raises SIDS risk. Dress your baby in only one more layer than you are wearing.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/a-parents-guide-to-safe-sleep.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "Stop swaddling as soon as your baby looks like they are trying to roll; rolling while swaddled raises suffocation risk.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/a-parents-guide-to-safe-sleep.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Repeated night waking is expected in the first few months, though the NHS frames this for newborns rather than the whole first year.", "url": "https://www.nhs.uk/baby/caring-for-a-newborn/helping-your-baby-to-sleep/"},
            "aap": {"says": "Frequent night waking is developmentally normal in babies and is protective, letting them rouse if breathing is disturbed.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/Sleeping-Through-the-Night.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Some babies sleep long stretches at night by around 6 months, but many do not; it is not something to expect.", "url": "https://www.nhs.uk/best-start-in-life/baby/baby-basics/newborn-and-baby-sleeping-advice-for-parents/your-babys-sleep-patterns/"},
            "aap": {"says": "A good infant sleeper wakes often and resettles; long unbroken sleep at this age is not the healthy goal.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/Sleeping-Through-the-Night.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Respond to your baby's cries. A baby left to cry it out may go quiet but can still be distressed when no one comes.", "url": "https://www.nhs.uk/start-for-life/baby/baby-basics/baby-myths-and-facts/"},
            "aap": {"says": "Put your baby down drowsy and give them a chance to resettle themselves rather than rushing in. Learning to self-soothe is a normal skill.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/getting-your-baby-to-sleep.aspx"},
            "agreement": "differ",
            "note": "The AAP actively advises giving a baby time to resettle without rushing in, while the NHS warns that a baby left to 'cry it out' may still be distressed and urges responding to cries; neither page states a position on the claim's specific question of lasting harm to attachment or stress regulation.",
        },
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
        "guidance": {
            "nhs": {"says": "A simple, soothing bedtime routine may help your baby settle, and gives you one-to-one time together.", "url": "https://www.nhs.uk/baby/caring-for-a-newborn/helping-your-baby-to-sleep/"},
            "aap": {"says": "Start a bedtime routine early with young children, such as brush teeth, read a book, then bed.", "url": "https://www.healthychildren.org/English/healthy-living/sleep/Pages/healthy-sleep-habits-how-many-hours-does-your-child-need.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "Put your baby down drowsy but awake; babies rocked to sleep may struggle to resettle themselves after night wakings.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/getting-your-baby-to-sleep.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Avoid screens in the hour before bed, as screen use before bedtime could affect a young child's sleep.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "Turn all screens off at least an hour before bedtime and keep them out of bedrooms to prevent sleep disruption.", "url": "https://www.healthychildren.org/English/healthy-living/sleep/Pages/healthy-sleep-habits-how-many-hours-does-your-child-need.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Avoid screens for babies and toddlers. If you do use one, watch together and talk about it so it becomes a shared, interactive activity.", "url": "https://www.nhs.uk/best-start-in-life/baby/learning-to-talk/listening-and-learning-6-to-12-months/"},
            "aap": {"says": "Avoid TV and apps before 18 months, apart from video chat with family. Babies learn from real interaction, not from screens.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Why-to-Avoid-TV-Before-Age-2.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Keep screens off in the background. They pull attention away from social interaction and play with your child.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "A TV on in the background cuts how much a parent talks to a toddler by hundreds of words an hour and delays language.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Why-to-Avoid-TV-Before-Age-2.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Under 2s should avoid screens except for shared family activities, and video calling relatives is given as an acceptable example.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "Video chatting with a relative is fine. Sit with your child and keep everyone talking to each other.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Food-and-TV-Not-a-Healthy-Mix.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Watch and talk about content with your child rather than leaving them alone with a screen. It supports development.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "Children get more out of TV or apps when a parent is watching and using it alongside them.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Why-to-Avoid-TV-Before-Age-2.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "A lot of screen time is linked to poorer development, including language.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "Screen viewing before 18 months has lasting negative effects on language, reading and short-term memory.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Why-to-Avoid-TV-Before-Age-2.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Young children learn best from back-and-forth interaction with people, not from a screen.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "For the same amount of time, a toddler learns far more from real play with you than from watching a screen.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Why-to-Avoid-TV-Before-Age-2.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Fast-paced, over-stimulating video may affect how young children learn to concentrate, so avoid it. NHS frames this by content type, not total exposure.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "Toddlers who watch more TV are more likely to have trouble paying attention by age 7.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Why-to-Avoid-TV-Before-Age-2.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "App skills do not transfer to real-world learning for toddlers, though after age 2 some children do learn from well-designed educational programmes.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Why-to-Avoid-TV-Before-Age-2.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "A lot of screen time is linked to poorer sleep, among other effects on health and development.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "Children with a lot of media exposure fall asleep later and sleep less; even babies can be overstimulated and lose sleep.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/adverse-effects-of-television-commercials.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "A lot of screen time is linked to effects on healthy weight, among other health and development outcomes.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "Watching a lot of TV is associated with overweight and obesity in children.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Food-and-TV-Not-a-Healthy-Mix.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Keep mealtimes screen-free. NHS gives the reason as protecting family time and interaction, not eating behaviour specifically.", "url": "https://beststartinlife.gov.uk/screen-time-under-5s/"},
            "aap": {"says": "Eating in front of a screen distracts children so they keep eating past fullness, which can lead to weight gain.", "url": "https://www.healthychildren.org/English/family-life/Media/Pages/Food-and-TV-Not-a-Healthy-Mix.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Tummy time builds the muscles a baby needs for sitting and crawling.", "url": "https://www.nhs.uk/baby/babys-development/play-and-learning/keep-baby-or-toddler-active/"},
            "aap": {"says": "Supervised tummy time while awake is what a baby needs to build strong muscles and prepare for crawling.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/back-to-sleep-tummy-to-play.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Plenty of supervised awake tummy time is listed as a way to prevent flat head syndrome or stop it getting worse.", "url": "https://www.nhs.uk/conditions/plagiocephaly-brachycephaly/"},
            "aap": {"says": "Too little tummy time is named as a cause of flat head, and increasing tummy time is the recommended prevention.", "url": "https://www.healthychildren.org/English/health-issues/conditions/Cleft-Craniofacial/Pages/Positional-Skull-Deformities-and-Torticollis.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Heavy use of walkers or bouncers can delay walking, and long periods in carriers or propped seats can delay sitting up. Cap use at 20 minutes.", "url": "https://www.nhs.uk/baby/babys-development/play-and-learning/keep-baby-or-toddler-active/"},
            "aap": {"says": "Walkers do not help a baby learn to walk and can actually delay when walking starts.", "url": "https://www.healthychildren.org/English/safety-prevention/at-home/Pages/baby-walkers-a-dangerous-choice.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "Baby walkers cause thousands of hospital visits a year, mostly falls down stairs. AAP says throw them out.", "url": "https://www.healthychildren.org/English/safety-prevention/at-home/Pages/baby-walkers-a-dangerous-choice.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "No shoes are needed until a child walks, and then only outdoors. Toe bones cramped by tight shoes or socks cannot grow properly.", "url": "https://www.nhs.uk/baby/health/leg-and-foot-problems-in-children/"},
            "aap": {"says": "Babies' feet develop best unshod; socks are enough indoors, with shoes only once they walk outdoors, for protection.", "url": "https://www.healthychildren.org/English/ages-stages/toddler/Pages/Shoes-for-Active-Toddlers.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Not all babies crawl. Some shuffle on their bottoms instead, and that is normal.", "url": "https://www.nhs.uk/best-start-in-life/baby/baby-moves/"},
            "aap": {"says": "Some children never crawl and scoot or slither instead. That is no cause for concern as long as both sides are used equally.", "url": "https://www.healthychildren.org/English/ages-stages/baby/Pages/Movement-8-to-12-Months.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Babies under 1 should get at least 30 minutes of tummy time a day, spread across the day while awake.", "url": "https://www.nhs.uk/live-well/exercise/physical-activity-guidelines-children-under-five-years/"},
            "aap": {"says": "Start with 2 to 3 short sessions a day from birth and build up to 15 to 30 minutes a day by about 7 weeks, more as babies grow.", "url": "https://www.healthychildren.org/English/ages-stages/baby/sleep/Pages/back-to-sleep-tummy-to-play.aspx"},
            "agreement": "differ",
            "note": "The NHS sets a floor of at least 30 minutes of tummy time a day across the first year, while the AAP frames it as gradually building up to 15 to 30 minutes a day by around 7 weeks, with more as the baby gets stronger.",
        },
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
        "guidance": {
            "nhs": {"says": "Long stretches of sitting still or being strapped into a buggy or car seat are not good for an under-5's health and development.", "url": "https://www.nhs.uk/live-well/exercise/physical-activity-guidelines-children-under-five-years/"},
            "aap": {"says": "Babies who spend too long in car seats, swings, bouncy seats or strollers may be slower to reach motor milestones.", "url": "https://www.aap.org/en/patient-care/healthy-active-living-for-families/infant-physical-activity/"},
            "agreement": "agree",
        },
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
        "guidance": {
            "nhs": {"says": "Spending more time outdoors, especially for children, can help stop short-sightedness getting worse. NHS frames this as slowing progression, not preventing onset.", "url": "https://www.nhs.uk/conditions/short-sightedness/"},
            "aap": {"says": "Balancing screen time with time outside may help limit your child's short-sightedness and protect their vision as they grow.", "url": "https://www.healthychildren.org/English/health-issues/conditions/eyes/Pages/Myopia-Nearsightedness.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "Baby massage supports your baby's physical wellness and their emotional and psychological development.", "url": "https://www.healthychildren.org/English/ages-stages/baby/Pages/the-benefits-of-baby-massage.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Looking at books and singing with your child helps them develop language and communication skills.", "url": "https://www.nhs.uk/baby/babys-development/play-and-learning/baby-and-toddler-play-ideas/"},
            "aap": {"says": "Reading together builds the foundation for healthy social-emotional, cognitive, language and literacy development.", "url": "https://www.healthychildren.org/English/news/Pages/beyond-literacy-shared-reading-starting-in-infancy-offers-lifelong-benefits.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "AAP tells doctors to encourage shared reading from birth through kindergarten, saying it builds the foundation for language and literacy development.", "url": "https://www.healthychildren.org/English/news/Pages/beyond-literacy-shared-reading-starting-in-infancy-offers-lifelong-benefits.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "aap": {"says": "AAP puts the emphasis on print books for young children, saying digital books do not produce the same parent-child interaction.", "url": "https://www.healthychildren.org/English/news/Pages/beyond-literacy-shared-reading-starting-in-infancy-offers-lifelong-benefits.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Growing up with more than one language is an advantage for learning, and knowing another language helps a child's English develop.", "url": "https://www.nhs.uk/baby/babys-development/play-and-learning/help-your-baby-learn-to-talk/"},
            "aap": {"says": "Learning more than one language does not cause speech or language problems or delay communication in babies and toddlers.", "url": "https://www.healthychildren.org/English/ages-stages/gradeschool/school/Pages/7-Myths-Facts-Bilingual-Children-Learning-Language.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "AAP says signing won't hinder learning to talk provided you keep speaking too. It claims better communication, not faster speech.", "url": "https://www.healthychildren.org/English/ages-stages/baby/Pages/These-Hands-Were-Made-for-Talking.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Playtime activities matter for a toddler's development; the NHS lists language, cognitive growth, motor skills and social interaction among what play helps.", "url": "https://www.nhs.uk/best-start-in-life/toddler/activities-for-toddlers/"},
            "aap": {"says": "Play helps children learn language, maths and social skills; AAP urges families and schools to protect unstructured play.", "url": "https://www.healthychildren.org/English/news/Pages/healthier-children-play-according-to-the-AAP.aspx"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "Playing different characters teaches children other people's mindsets, motivations and perspectives, and builds social and emotional skills.", "url": "https://www.healthychildren.org/English/family-life/power-of-play/Pages/pretend-play-ways-children-can-exercise-their-imagination.aspx"},
            "agreement": "one_only",
        },
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
        "guidance": {
            "nhs": {"says": "Singing to your baby helps them tune in to the rhythm of language.", "url": "https://www.nhs.uk/baby/babys-development/play-and-learning/help-your-baby-learn-to-talk/"},
            "aap": {"says": "Music early in infancy helps babies learn the sounds and meanings of words and supports language and literacy.", "url": "https://www.aap.org/en/patient-care/media-and-children/center-of-excellence-on-social-media-and-youth-mental-health/qa-portal/qa-portal-library/qa-portal-library-questions/infants-and-music-media/"},
            "agreement": "agree",
        },
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
        "guidance": {
            "aap": {"says": "High-quality early child care and education has lasting positive effects on children's thinking, social skills, maths and language; quality matters more than the setting type.", "url": "https://www.healthychildren.org/English/family-life/work-and-child-care/Pages/why-quality-matters-in-early-child-care-aap-policy-explained.aspx"},
            "agreement": "one_only",
        },
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
