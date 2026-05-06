#!/usr/bin/env python3
"""
import_openalex.py — Fetches papers from the OpenAlex API for baby food topics
and stores them in per-topic SQLite databases.

Usage:
    python import_openalex.py --topic peanut_allergy --max 500
    python import_openalex.py --topic infant_nutrition --query "infant complementary feeding" --max 300
    python import_openalex.py --list-topics
"""

import argparse
import os
import sqlite3
import time
import json
import re
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data'))

OPENALEX_BASE = "https://api.openalex.org"
EMAIL = os.environ.get("OPENALEX_EMAIL", "research@example.com")

# Pre-defined baby food topics with curated search queries
PREDEFINED_TOPICS = {

    # ── ALLERGENS (14) ──────────────────────────────────────────────────────
    "peanut_allergy": {
        "name": "Peanut Allergy",
        "query": "peanut allergy infant introduction early prevention sensitisation",
        "concepts": ["C2776082936"],
        "food_type_hint": "peanuts",
        "age_hint": "infant",
    },
    "egg_allergy": {
        "name": "Egg Allergy",
        "query": "egg allergy infant introduction prevention sensitisation",
        "food_type_hint": "eggs",
        "age_hint": "infant",
    },
    "cow_milk_allergy": {
        "name": "Cow Milk Allergy",
        "query": "cow milk protein allergy infant formula sensitisation",
        "food_type_hint": "cow-milk",
        "age_hint": "infant",
    },
    "tree_nut_allergy": {
        "name": "Tree Nut Allergy",
        "query": "tree nut allergy children walnut cashew almond introduction",
        "food_type_hint": "tree-nuts",
        "age_hint": "infant",
    },
    "wheat_gluten_allergy": {
        "name": "Wheat & Gluten Allergy",
        "query": "wheat gluten allergy infant introduction sensitisation celiac",
        "food_type_hint": "wheat-gluten",
        "age_hint": "infant",
    },
    "soy_allergy": {
        "name": "Soy Allergy",
        "query": "soy allergy infant soy protein formula sensitisation",
        "food_type_hint": "soy",
        "age_hint": "infant",
    },
    "sesame_allergy": {
        "name": "Sesame Allergy",
        "query": "sesame allergy infant children sensitisation introduction",
        "food_type_hint": "sesame",
        "age_hint": "infant",
    },
    "fish_shellfish_allergy": {
        "name": "Fish & Shellfish Allergy",
        "query": "fish shellfish allergy infant children introduction prevention",
        "food_type_hint": "fish",
        "age_hint": "infant",
    },
    "multiple_food_allergy": {
        "name": "Multiple Food Allergies",
        "query": "multiple food allergy infant polysensitisation management diet",
        "food_type_hint": "general",
        "age_hint": "infant",
    },
    "oral_immunotherapy_allergy": {
        "name": "Oral Immunotherapy for Food Allergy",
        "query": "oral immunotherapy food allergy desensitisation children peanut egg milk",
        "food_type_hint": "general",
        "age_hint": "infant",
    },
    "early_allergen_introduction": {
        "name": "Early Allergen Introduction",
        "query": "early introduction allergenic foods infant prevention tolerance LEAP PETIT",
        "food_type_hint": "general",
        "age_hint": "4-6 months",
    },
    "allergy_prevention_diet": {
        "name": "Dietary Allergy Prevention",
        "query": "food allergy prevention infant dietary strategy maternal breastfeeding",
        "food_type_hint": "general",
        "age_hint": "infant",
    },
    "eczema_food_allergy": {
        "name": "Eczema & Food Allergy",
        "query": "eczema atopic dermatitis food allergy infant skin barrier sensitisation",
        "food_type_hint": "general",
        "age_hint": "infant",
    },
    "food_allergy_anaphylaxis": {
        "name": "Anaphylaxis in Infants",
        "query": "anaphylaxis food allergy infant children emergency epinephrine management",
        "food_type_hint": "general",
        "age_hint": "infant",
    },

    # ── FEEDING METHODS (11) ─────────────────────────────────────────────────
    "complementary_feeding": {
        "name": "Complementary Feeding",
        "query": "complementary feeding infant solid foods introduction weaning",
        "food_type_hint": "solid-food",
        "age_hint": "6-12 months",
    },
    "breastfeeding": {
        "name": "Breastfeeding",
        "query": "breastfeeding infant nutrition benefits outcomes health",
        "food_type_hint": "breast-milk",
        "age_hint": "0-6 months",
    },
    "infant_formula": {
        "name": "Infant Formula",
        "query": "infant formula nutrition comparison breastfeeding outcomes",
        "food_type_hint": "formula",
        "age_hint": "0-12 months",
    },
    "baby_led_weaning": {
        "name": "Baby-Led Weaning",
        "query": "baby-led weaning self-feeding solid foods infant",
        "food_type_hint": "solid-food",
        "age_hint": "6-12 months",
    },
    "responsive_feeding": {
        "name": "Responsive Feeding",
        "query": "responsive feeding infant cue-based hunger satiety parental feeding style",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "donor_breast_milk": {
        "name": "Donor Breast Milk",
        "query": "donor human milk bank pasteurisation preterm infant formula alternative",
        "food_type_hint": "breast-milk",
        "age_hint": "0-6 months",
    },
    "mixed_feeding": {
        "name": "Mixed Breast & Formula Feeding",
        "query": "mixed feeding breastfeeding formula supplementation infant outcomes",
        "food_type_hint": "breast-milk",
        "age_hint": "0-6 months",
    },
    "formula_preparation_safety": {
        "name": "Formula Preparation Safety",
        "query": "infant formula preparation safety contamination water sterilisation bacterial",
        "food_type_hint": "formula",
        "age_hint": "0-12 months",
    },
    "extended_breastfeeding": {
        "name": "Extended Breastfeeding",
        "query": "extended breastfeeding beyond 12 months toddler outcomes benefits",
        "food_type_hint": "breast-milk",
        "age_hint": "12-24 months",
    },
    "breastfeeding_difficulties": {
        "name": "Breastfeeding Difficulties",
        "query": "breastfeeding difficulties latching low milk supply mastitis support intervention",
        "food_type_hint": "breast-milk",
        "age_hint": "0-6 months",
    },
    "preterm_infant_nutrition": {
        "name": "Preterm Infant Nutrition",
        "query": "preterm infant nutrition fortification necrotising enterocolitis NICU growth",
        "food_type_hint": "formula",
        "age_hint": "preterm",
    },

    # ── NUTRIENTS & SUPPLEMENTS (13) ─────────────────────────────────────────
    "iron_deficiency": {
        "name": "Iron Deficiency",
        "query": "iron deficiency anaemia infant toddler supplementation complementary food",
        "food_type_hint": "iron",
        "age_hint": "6-24 months",
    },
    "vitamin_d": {
        "name": "Vitamin D",
        "query": "vitamin D deficiency infant supplementation rickets sun exposure",
        "food_type_hint": "vitamin-d",
        "age_hint": "0-12 months",
    },
    "omega3_dha": {
        "name": "Omega-3 / DHA",
        "query": "omega-3 DHA ARA infant brain development fish oil supplementation",
        "food_type_hint": "omega3",
        "age_hint": "0-12 months",
    },
    "zinc_infant": {
        "name": "Zinc in Infant Nutrition",
        "query": "zinc deficiency infant supplementation growth immunity complementary food",
        "food_type_hint": "general",
        "age_hint": "6-24 months",
    },
    "calcium_bone_infant": {
        "name": "Calcium & Bone Development",
        "query": "calcium intake infant bone development density dairy supplementation",
        "food_type_hint": "dairy",
        "age_hint": "0-24 months",
    },
    "iodine_infant": {
        "name": "Iodine & Thyroid in Infants",
        "query": "iodine deficiency infant thyroid development breast milk formula",
        "food_type_hint": "general",
        "age_hint": "0-12 months",
    },
    "folate_infant": {
        "name": "Folate & Neural Development",
        "query": "folate folic acid infant neural development supplementation brain",
        "food_type_hint": "general",
        "age_hint": "0-12 months",
    },
    "vitamin_a_infant": {
        "name": "Vitamin A Deficiency",
        "query": "vitamin A deficiency infant supplementation infection mortality vision",
        "food_type_hint": "general",
        "age_hint": "6-24 months",
    },
    "vitamin_b12_infant": {
        "name": "Vitamin B12 in Infant Nutrition",
        "query": "vitamin B12 deficiency infant vegan vegetarian breastfeeding supplementation",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "vitamin_k_infant": {
        "name": "Vitamin K in Newborns",
        "query": "vitamin K newborn haemorrhagic disease supplementation prophylaxis",
        "food_type_hint": "general",
        "age_hint": "0-6 months",
    },
    "choline_infant": {
        "name": "Choline & Brain Development",
        "query": "choline infant brain development cognitive supplementation breast milk egg",
        "food_type_hint": "eggs",
        "age_hint": "0-24 months",
    },
    "probiotics_infant": {
        "name": "Probiotics in Infant Nutrition",
        "query": "probiotics infant colic eczema allergy gut lactobacillus bifidobacterium",
        "food_type_hint": "probiotics",
        "age_hint": "0-12 months",
    },
    "prebiotics_infant": {
        "name": "Prebiotics & Infant Gut",
        "query": "prebiotics infant gut microbiome human milk oligosaccharides HMO formula",
        "food_type_hint": "probiotics",
        "age_hint": "0-12 months",
    },

    # ── SPECIFIC FOODS (12) ──────────────────────────────────────────────────
    "vegetable_introduction": {
        "name": "Vegetable Introduction",
        "query": "vegetable acceptance infant repeated exposure food neophobia taste",
        "food_type_hint": "vegetables",
        "age_hint": "4-12 months",
    },
    "fruit_introduction": {
        "name": "Fruit Introduction",
        "query": "fruit introduction infant diet sweetness preference early exposure",
        "food_type_hint": "fruits",
        "age_hint": "4-12 months",
    },
    "meat_introduction": {
        "name": "Meat Introduction",
        "query": "meat introduction infant iron zinc complementary food protein haem",
        "food_type_hint": "meat",
        "age_hint": "6-12 months",
    },
    "fish_introduction": {
        "name": "Fish Introduction",
        "query": "fish introduction infant omega-3 DHA mercury allergy complementary",
        "food_type_hint": "fish",
        "age_hint": "6-12 months",
    },
    "dairy_introduction": {
        "name": "Cow's Milk Introduction",
        "query": "cow milk introduction toddler dairy transition infant formula 12 months",
        "food_type_hint": "cow-milk",
        "age_hint": "12-24 months",
    },
    "legume_introduction": {
        "name": "Legumes & Pulses",
        "query": "legume bean lentil infant introduction protein complementary feeding",
        "food_type_hint": "legumes",
        "age_hint": "6-12 months",
    },
    "whole_grain_infant": {
        "name": "Whole Grains & Infant Cereals",
        "query": "whole grain cereal infant porridge oat rice complementary feeding fibre",
        "food_type_hint": "grains",
        "age_hint": "6-12 months",
    },
    "organic_baby_food": {
        "name": "Organic Baby Food",
        "query": "organic baby food infant pesticide nutrient content commercial puree",
        "food_type_hint": "baby-food",
        "age_hint": "6-12 months",
    },
    "sugar_salt_babies": {
        "name": "Sugar & Salt in Infant Diet",
        "query": "added sugar salt sodium intake infant toddler processed food diet",
        "food_type_hint": "general",
        "age_hint": "6-36 months",
    },
    "ultra_processed_infant": {
        "name": "Ultra-Processed Foods in Infant Diet",
        "query": "ultra-processed food toddler infant diet health obesity early childhood",
        "food_type_hint": "general",
        "age_hint": "12-36 months",
    },
    "commercial_baby_food": {
        "name": "Commercial Baby Food Pouches",
        "query": "commercial baby food pouch jar puree nutrition labelling composition quality",
        "food_type_hint": "baby-food",
        "age_hint": "6-12 months",
    },
    "plant_based_infant": {
        "name": "Plant-Based Infant Diets",
        "query": "plant-based vegan vegetarian infant toddler diet nutrition deficiency risk",
        "food_type_hint": "legumes",
        "age_hint": "0-24 months",
    },

    # ── GUT HEALTH (6) ──────────────────────────────────────────────────────
    "gut_microbiome": {
        "name": "Gut Microbiome",
        "query": "infant gut microbiome diet colonisation early life diversity",
        "food_type_hint": "probiotics",
        "age_hint": "0-24 months",
    },
    "infant_colic": {
        "name": "Infant Colic & Diet",
        "query": "infant colic excessive crying probiotic maternal diet elimination",
        "food_type_hint": "general",
        "age_hint": "0-6 months",
    },
    "infant_constipation": {
        "name": "Infant Constipation & Diet",
        "query": "infant constipation diet fibre prune juice complementary feeding",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "infant_reflux": {
        "name": "Infant Reflux & GERD",
        "query": "gastroesophageal reflux infant GERD diet thickening formula positioning",
        "food_type_hint": "general",
        "age_hint": "0-12 months",
    },
    "gut_dysbiosis_infant": {
        "name": "Gut Dysbiosis in Infants",
        "query": "gut dysbiosis infant antibiotic microbiome disruption diet restoration",
        "food_type_hint": "probiotics",
        "age_hint": "0-24 months",
    },
    "food_texture_progression": {
        "name": "Food Texture Progression",
        "query": "food texture lumpy pureed infant feeding development swallowing",
        "food_type_hint": "solid-food",
        "age_hint": "6-18 months",
    },

    # ── GROWTH & DEVELOPMENT (7) ─────────────────────────────────────────────
    "infant_growth_faltering": {
        "name": "Infant Growth Faltering",
        "query": "infant growth faltering failure to thrive undernutrition feeding intervention",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "childhood_obesity_diet": {
        "name": "Childhood Obesity & Early Diet",
        "query": "childhood obesity early diet infant overweight prevention risk factor",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "stunting_wasting": {
        "name": "Stunting & Wasting",
        "query": "stunting wasting infant malnutrition complementary food therapeutic nutrition",
        "food_type_hint": "general",
        "age_hint": "6-24 months",
    },
    "brain_development_nutrition": {
        "name": "Brain & Cognitive Development",
        "query": "brain development infant nutrition cognitive outcomes DHA iron choline iodine",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "catch_up_growth": {
        "name": "Catch-Up Growth",
        "query": "catch up growth preterm low birth weight infant nutrition formula enriched",
        "food_type_hint": "formula",
        "age_hint": "preterm",
    },
    "dental_health_infant": {
        "name": "Dental Health & Early Diet",
        "query": "early childhood caries dental health sugar infant bottle feeding fluoride",
        "food_type_hint": "general",
        "age_hint": "12-36 months",
    },
    "toddler_milk_drinks": {
        "name": "Toddler Milk & Growing-Up Drinks",
        "query": "toddler milk growing up formula drink nutrition marketing necessity",
        "food_type_hint": "formula",
        "age_hint": "12-36 months",
    },

    # ── FEEDING BEHAVIOUR (7) ────────────────────────────────────────────────
    "food_neophobia": {
        "name": "Food Neophobia in Toddlers",
        "query": "food neophobia toddler new food refusal exposure intervention variety",
        "food_type_hint": "general",
        "age_hint": "12-36 months",
    },
    "picky_eating": {
        "name": "Picky Eating",
        "query": "picky eating toddler selective eating diet variety intervention outcomes",
        "food_type_hint": "general",
        "age_hint": "12-36 months",
    },
    "feeding_difficulties": {
        "name": "Paediatric Feeding Difficulties",
        "query": "feeding difficulties infant ARFID avoidant restrictive food intake disorder paediatric",
        "food_type_hint": "general",
        "age_hint": "0-36 months",
    },
    "appetite_regulation": {
        "name": "Appetite Regulation in Infants",
        "query": "appetite regulation infant satiety hunger cues overfeeding parental feeding style",
        "food_type_hint": "general",
        "age_hint": "0-12 months",
    },
    "flavor_learning": {
        "name": "Flavour Learning & Taste Exposure",
        "query": "flavour flavor learning infant taste exposure amniotic fluid breast milk preference",
        "food_type_hint": "general",
        "age_hint": "0-12 months",
    },
    "mealtime_behaviour": {
        "name": "Mealtime Behaviour & Family",
        "query": "mealtime behaviour family infant toddler feeding practices parenting shared meals",
        "food_type_hint": "general",
        "age_hint": "12-36 months",
    },
    "division_of_responsibility": {
        "name": "Division of Responsibility in Feeding",
        "query": "division of responsibility feeding toddler parental role child autonomy Satter",
        "food_type_hint": "general",
        "age_hint": "12-36 months",
    },

    # ── MATERNAL NUTRITION (8) ───────────────────────────────────────────────
    "maternal_diet_breastmilk": {
        "name": "Maternal Diet & Breast Milk Composition",
        "query": "maternal diet breast milk composition fatty acids nutrients infant",
        "food_type_hint": "breast-milk",
        "age_hint": "0-6 months",
    },
    "maternal_nutrition_pregnancy": {
        "name": "Maternal Nutrition in Pregnancy",
        "query": "maternal nutrition pregnancy diet birth outcome infant health",
        "food_type_hint": "general",
        "age_hint": "prenatal",
    },
    "prenatal_allergy_prevention": {
        "name": "Prenatal Diet & Allergy Prevention",
        "query": "prenatal maternal diet allergy prevention infant sensitisation fish peanut probiotic",
        "food_type_hint": "general",
        "age_hint": "prenatal",
    },
    "gestational_diabetes_feeding": {
        "name": "Gestational Diabetes & Infant Feeding",
        "query": "gestational diabetes infant feeding breastfeeding glucose neonatal hypoglycaemia",
        "food_type_hint": "general",
        "age_hint": "0-6 months",
    },
    "maternal_microbiome": {
        "name": "Maternal Microbiome & Infant Colonisation",
        "query": "maternal gut microbiome pregnancy infant colonisation birth mode caesarean",
        "food_type_hint": "probiotics",
        "age_hint": "0-6 months",
    },
    "prenatal_omega3": {
        "name": "Prenatal Omega-3 Supplementation",
        "query": "prenatal omega-3 fish oil supplementation infant brain development allergy asthma",
        "food_type_hint": "omega3",
        "age_hint": "prenatal",
    },
    "maternal_iodine_pregnancy": {
        "name": "Maternal Iodine & Infant Thyroid",
        "query": "maternal iodine pregnancy supplementation infant thyroid cognitive development",
        "food_type_hint": "general",
        "age_hint": "prenatal",
    },
    "maternal_anaemia_infant": {
        "name": "Maternal Anaemia & Infant Iron",
        "query": "maternal anaemia iron deficiency pregnancy infant iron stores birth outcome",
        "food_type_hint": "iron",
        "age_hint": "prenatal",
    },

    # ── SPECIAL POPULATIONS (8) ──────────────────────────────────────────────
    "low_birth_weight_feeding": {
        "name": "Low Birth Weight Infant Feeding",
        "query": "low birth weight infant feeding nutrition kangaroo mother care growth",
        "food_type_hint": "formula",
        "age_hint": "preterm",
    },
    "celiac_disease_infant": {
        "name": "Coeliac Disease & Gluten Introduction",
        "query": "celiac coeliac disease infant gluten introduction timing prevention risk",
        "food_type_hint": "wheat-gluten",
        "age_hint": "4-12 months",
    },
    "fpies": {
        "name": "FPIES",
        "query": "food protein induced enterocolitis syndrome FPIES infant vomiting management trigger",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "eosinophilic_esophagitis": {
        "name": "Eosinophilic Oesophagitis",
        "query": "eosinophilic esophagitis oesophagitis child diet elimination feeding dysphagia",
        "food_type_hint": "general",
        "age_hint": "0-36 months",
    },
    "cleft_palate_feeding": {
        "name": "Cleft Palate & Feeding",
        "query": "cleft palate lip infant feeding breast bottle specialist support nutrition",
        "food_type_hint": "general",
        "age_hint": "0-12 months",
    },
    "downs_syndrome_feeding": {
        "name": "Down Syndrome & Feeding",
        "query": "Down syndrome trisomy 21 infant feeding difficulties breastfeeding nutrition",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "immune_development_diet": {
        "name": "Immune System Development & Diet",
        "query": "immune system development infant diet nutrition immunity infection susceptibility",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "fortified_complementary_foods": {
        "name": "Fortified Complementary Foods",
        "query": "fortified complementary food infant micronutrient powder sprinkles anaemia",
        "food_type_hint": "general",
        "age_hint": "6-24 months",
    },

    # ── FOOD SAFETY & CONTAMINANTS (6) ──────────────────────────────────────
    "heavy_metals_baby_food": {
        "name": "Heavy Metals in Baby Food",
        "query": "heavy metals arsenic lead cadmium mercury infant baby food rice exposure",
        "food_type_hint": "baby-food",
        "age_hint": "6-24 months",
    },
    "pesticides_infant_food": {
        "name": "Pesticides in Infant Food",
        "query": "pesticide residues organophosphate infant food fruit vegetable exposure risk",
        "food_type_hint": "baby-food",
        "age_hint": "6-24 months",
    },
    "nitrates_baby_food": {
        "name": "Nitrates in Baby Food",
        "query": "nitrate nitrite infant food spinach carrot vegetable methemoglobinaemia",
        "food_type_hint": "vegetables",
        "age_hint": "4-12 months",
    },
    "microplastics_formula": {
        "name": "Microplastics in Infant Formula",
        "query": "microplastics nanoplastics infant formula bottle sterilisation polypropylene exposure",
        "food_type_hint": "formula",
        "age_hint": "0-12 months",
    },
    "bpa_packaging_infant": {
        "name": "BPA & Food Packaging",
        "query": "BPA bisphenol food packaging infant formula can leaching endocrine disruption",
        "food_type_hint": "formula",
        "age_hint": "0-12 months",
    },
    "food_safety_preparation": {
        "name": "Baby Food Preparation Hygiene",
        "query": "baby food preparation hygiene safety bacterial contamination infant home",
        "food_type_hint": "baby-food",
        "age_hint": "6-12 months",
    },

    # ── SOCIOECONOMIC, CULTURAL & GLOBAL (8) ────────────────────────────────
    "food_insecurity_infant": {
        "name": "Food Insecurity & Infant Feeding",
        "query": "food insecurity infant feeding poverty breastfeeding formula access hunger",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "cultural_complementary_feeding": {
        "name": "Cultural Practices in Complementary Feeding",
        "query": "cultural practices complementary feeding tradition immigrant diversity infant",
        "food_type_hint": "solid-food",
        "age_hint": "6-12 months",
    },
    "global_malnutrition_infant": {
        "name": "Global Infant Malnutrition",
        "query": "global infant malnutrition developing countries complementary feeding intervention",
        "food_type_hint": "general",
        "age_hint": "6-24 months",
    },
    "baby_food_marketing": {
        "name": "Baby Food Marketing & Industry",
        "query": "infant formula marketing WHO code breastfeeding promotion industry influence",
        "food_type_hint": "formula",
        "age_hint": "0-12 months",
    },
    "baby_food_labelling": {
        "name": "Baby Food Labelling & Regulation",
        "query": "baby food labelling regulation nutrition claims infant toddler commercial standards",
        "food_type_hint": "baby-food",
        "age_hint": "6-24 months",
    },
    "socioeconomic_infant_diet": {
        "name": "Socioeconomic Factors in Infant Diet",
        "query": "socioeconomic status infant feeding diet inequality maternal education",
        "food_type_hint": "general",
        "age_hint": "0-24 months",
    },
    "sleep_feeding_infant": {
        "name": "Infant Sleep & Feeding",
        "query": "infant sleep feeding night waking breastfeeding formula solid food association",
        "food_type_hint": "general",
        "age_hint": "0-12 months",
    },
    "screen_time_feeding": {
        "name": "Screen Time & Feeding Behaviour",
        "query": "screen time television infant toddler feeding distracted eating diet quality",
        "food_type_hint": "general",
        "age_hint": "12-36 months",
    },
}


def create_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            paperId TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            year INTEGER,
            publicationDate TEXT,
            cited_by_count INTEGER,
            all_author_names TEXT,
            first_author_name TEXT,
            all_institution_names TEXT,
            AI_primary_field TEXT,
            AI_summary TEXT,
            paper_nature TEXT,
            food_type TEXT,
            age_group TEXT,
            recommendation_summary TEXT,
            evidence_strength TEXT,
            likelihood_score REAL,
            seriousness_score REAL,
            participant_count INTEGER,
            study_type TEXT,
            doi TEXT,
            url TEXT,
            raw_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS citations (
            source TEXT,
            target TEXT,
            PRIMARY KEY (source, target)
        )
    """)
    conn.commit()
    return conn


def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""
    positions = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(positions[k] for k in sorted(positions.keys()))


def fetch_topic_count(query, concepts=None):
    """Return the total number of works in OpenAlex matching this topic query."""
    headers = {"User-Agent": f"mapo-baby-food/1.0 (mailto:{EMAIL})"}
    filters = ["type:article", "has_abstract:true"]
    if concepts:
        filters.append(f"concepts.id:{'|'.join(concepts)}")
    params = {
        "search": query,
        "filter": ",".join(filters),
        "per-page": 1,
        "select": "id",
    }
    try:
        resp = requests.get(f"{OPENALEX_BASE}/works", params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get("meta", {}).get("count", 0)
    except Exception as e:
        print(f"  [warn] count fetch failed: {e}")
        return 0


def fetch_all_topic_counts(out_path=None):
    """Fetch total OpenAlex paper counts for all predefined topics and save to JSON."""
    if out_path is None:
        out_path = os.path.join(DATA_DIR, "topic_counts.json")
    existing = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)

    counts = dict(existing)
    total = len(PREDEFINED_TOPICS)
    for i, (key, cfg) in enumerate(PREDEFINED_TOPICS.items(), 1):
        count = fetch_topic_count(cfg["query"], cfg.get("concepts"))
        counts[key] = count
        print(f"  [{i:3d}/{total}] {key:45s} {count:>8,d}")
        time.sleep(0.15)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(counts, f, indent=2)
    print(f"\nSaved topic counts → {out_path}")
    return counts


def fetch_works(query, concepts=None, max_results=200, filter_str=None):
    """Cursor-based pagination from OpenAlex /works."""
    headers = {"User-Agent": f"mapo-baby-food/1.0 (mailto:{EMAIL})"}
    filters = [
        "type:article",
        "has_abstract:true",
    ]
    if filter_str:
        filters.append(filter_str)
    if concepts:
        filters.append(f"concepts.id:{'|'.join(concepts)}")

    params = {
        "search": query,
        "filter": ",".join(filters),
        "per-page": 200,
        "cursor": "*",
        "select": (
            "id,title,abstract_inverted_index,publication_year,publication_date,"
            "cited_by_count,authorships,primary_location,referenced_works,"
            "topics,concepts,type"
        ),
    }

    fetched = []
    while len(fetched) < max_results:
        resp = requests.get(f"{OPENALEX_BASE}/works", params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        fetched.extend(results)
        print(f"  Fetched {len(fetched)} papers...", end="\r")
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        params["cursor"] = cursor
        time.sleep(0.1)

    print(f"  Fetched {len(fetched)} papers total.   ")
    return fetched[:max_results]


def parse_paper(work, food_type_hint="general", age_hint=None):
    paper_id = work["id"].replace("https://openalex.org/", "")
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    authors = work.get("authorships", [])
    author_names = [
        a["author"]["display_name"] for a in authors
        if a.get("author") and a["author"].get("display_name")
    ]
    institutions = []
    for a in authors:
        for inst in a.get("institutions", []):
            if inst.get("display_name"):
                institutions.append(inst["display_name"])

    first_author = author_names[0] if author_names else "Unknown"

    # Determine study type from type field and topics
    work_type = work.get("type", "")
    topics = work.get("topics", []) or []
    topic_names = [t.get("display_name", "") for t in topics]

    study_type = "review" if "review" in work_type.lower() else "article"
    paper_nature = "review"
    if any(k in " ".join(topic_names).lower() for k in ["trial", "rct", "randomized"]):
        paper_nature = "clinical_trial"
        study_type = "clinical_trial"
    elif any(k in " ".join(topic_names).lower() for k in ["cohort", "longitudinal", "prospective"]):
        paper_nature = "experimental"
        study_type = "cohort"
    elif "meta-analysis" in " ".join(topic_names).lower():
        paper_nature = "meta_analysis"
        study_type = "meta_analysis"
    elif abstract and any(k in abstract.lower() for k in ["randomized", "randomised", "placebo"]):
        paper_nature = "clinical_trial"
        study_type = "clinical_trial"

    doi = ""
    url = ""
    primary_loc = work.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    if primary_loc.get("doi"):
        doi = primary_loc["doi"]
        url = f"https://doi.org/{doi.replace('https://doi.org/', '')}"

    return {
        "paperId": paper_id,
        "title": work.get("title", ""),
        "abstract": abstract,
        "year": work.get("publication_year"),
        "publicationDate": work.get("publication_date", ""),
        "cited_by_count": work.get("cited_by_count", 0),
        "all_author_names": "; ".join(author_names),
        "first_author_name": first_author,
        "all_institution_names": "; ".join(dict.fromkeys(institutions)),
        "food_type": food_type_hint,
        "age_group": age_hint or "",
        "doi": doi,
        "url": url,
        "paper_nature": paper_nature,
        "study_type": study_type,
        "raw_json": json.dumps(work),
        # Fields to be filled by process_ai.py
        "AI_primary_field": None,
        "AI_summary": None,
        "recommendation_summary": None,
        "evidence_strength": None,
        "likelihood_score": None,
        "seriousness_score": None,
        "participant_count": None,
    }, [r.replace("https://openalex.org/", "") for r in work.get("referenced_works", [])]


def import_topic(topic_key, query=None, max_results=200, min_citations=0):
    if topic_key in PREDEFINED_TOPICS:
        cfg = PREDEFINED_TOPICS[topic_key]
        query = query or cfg["query"]
        food_type_hint = cfg.get("food_type_hint", "general")
        age_hint = cfg.get("age_hint")
        concepts = cfg.get("concepts")
    else:
        food_type_hint = "general"
        age_hint = None
        concepts = None
        if not query:
            query = topic_key.replace("_", " ")

    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, f"papers_{topic_key}.db")
    print(f"[import] Topic: {topic_key}")
    print(f"[import] Query: {query}")
    print(f"[import] DB: {db_path}")

    conn = create_db(db_path)
    existing = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    print(f"[import] Existing papers: {len(existing)}")

    total_count = fetch_topic_count(query, concepts)
    print(f"[import] Total in OpenAlex: {total_count:,}")

    counts_path = os.path.join(DATA_DIR, "topic_counts.json")
    counts = {}
    if os.path.exists(counts_path):
        with open(counts_path) as f:
            counts = json.load(f)
    counts[topic_key] = total_count
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(counts_path, "w") as f:
        json.dump(counts, f, indent=2)

    works = fetch_works(query, concepts=concepts, max_results=max_results)

    inserted, skipped, citation_pairs = 0, 0, []
    for work in works:
        paper, ref_ids = parse_paper(work, food_type_hint, age_hint)
        if work.get("cited_by_count", 0) < min_citations:
            skipped += 1
            continue
        if paper["paperId"] in existing:
            skipped += 1
            continue
        conn.execute("""
            INSERT OR IGNORE INTO papers
            (paperId, title, abstract, year, publicationDate, cited_by_count,
             all_author_names, first_author_name, all_institution_names,
             food_type, age_group, doi, url, paper_nature, study_type,
             AI_primary_field, AI_summary, recommendation_summary,
             evidence_strength, likelihood_score, seriousness_score,
             participant_count, raw_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            paper["paperId"], paper["title"], paper["abstract"], paper["year"],
            paper["publicationDate"], paper["cited_by_count"],
            paper["all_author_names"], paper["first_author_name"],
            paper["all_institution_names"], paper["food_type"], paper["age_group"],
            paper["doi"], paper["url"], paper["paper_nature"], paper["study_type"],
            paper["AI_primary_field"], paper["AI_summary"],
            paper["recommendation_summary"], paper["evidence_strength"],
            paper["likelihood_score"], paper["seriousness_score"],
            paper["participant_count"], paper["raw_json"]
        ))
        citation_pairs.extend(
            (paper["paperId"], ref_id) for ref_id in ref_ids
        )
        inserted += 1

    # Insert citations between papers in this DB
    existing_ids = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    citation_count = 0
    for source, target in citation_pairs:
        if source in existing_ids and target in existing_ids:
            conn.execute("INSERT OR IGNORE INTO citations (source, target) VALUES (?,?)", (source, target))
            citation_count += 1

    conn.commit()
    conn.close()
    print(f"[import] Done. Inserted: {inserted}, Skipped: {skipped}, Citations: {citation_count}")
    return db_path


def main():
    parser = argparse.ArgumentParser(description="Import baby food papers from OpenAlex")
    parser.add_argument("--topic", help="Topic key (use --list-topics to see options)")
    parser.add_argument("--query", help="Custom search query (overrides default for topic)")
    parser.add_argument("--max", type=int, default=200, help="Max papers to fetch (default: 200)")
    parser.add_argument("--min-citations", type=int, default=0, help="Min citations filter")
    parser.add_argument("--list-topics", action="store_true", help="List predefined topics")
    parser.add_argument("--all", action="store_true", help="Import all predefined topics")
    args = parser.parse_args()

    if args.list_topics:
        print("\nPredefined topics:")
        for key, cfg in PREDEFINED_TOPICS.items():
            print(f"  {key:30s} — {cfg['name']}")
        return

    if args.all:
        for key in PREDEFINED_TOPICS:
            print(f"\n{'='*60}")
            import_topic(key, max_results=args.max, min_citations=args.min_citations)
        return

    if not args.topic:
        parser.print_help()
        return

    import_topic(args.topic, query=args.query, max_results=args.max, min_citations=args.min_citations)


if __name__ == "__main__":
    main()
