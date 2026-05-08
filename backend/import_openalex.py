#!/usr/bin/env python3
"""
import_openalex.py — Fetches papers from the OpenAlex API for curated baby food
recommendation topics and stores them in per-topic SQLite databases.

Architecture:
  1. FETCH   — broad minimal query per topic pulls all relevant papers into one DB
               (e.g. papers_peanut_allergy.db)
  2. PREPASS — fast keyword scan assigns each paper to zero or more claims
  3. EVALUATE — local Ollama/Mistral LLM evaluates each paper against each matched claim

Usage:
    python import_openalex.py --topic peanut_allergy --max 500
    python import_openalex.py --list-topics
    python import_openalex.py --all
    python import_openalex.py --topic peanut_allergy --prepass
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
EMAIL = os.environ.get("OPENALEX_EMAIL", "tom.hirsch3000@gmail.com")


# ── Retry / rate-limit helpers ────────────────────────────────────────────────

class BudgetExhaustedError(Exception):
    def __init__(self, retry_after_secs):
        self.retry_after_secs = retry_after_secs
        hrs = retry_after_secs / 3600
        super().__init__(
            f"OpenAlex daily budget exhausted. Resets in {retry_after_secs}s ({hrs:.1f}h)."
        )


def _headers():
    return {"User-Agent": f"mapo-baby-food/1.0 (mailto:{EMAIL})"}


def _params_with_email(params: dict) -> dict:
    p = dict(params)
    p.setdefault("mailto", EMAIL)
    return p


def _parse_429(response):
    """Return (is_budget_exhausted, wait_seconds)."""
    try:
        body = response.json()
        if "dailyRemainingUsd" in body or "creditsRemaining" in body:
            return True, int(body.get("retryAfter", 3600))
        body_wait = body.get("retryAfter")
        if body_wait:
            return False, int(body_wait)
    except Exception:
        pass
    header = response.headers.get("Retry-After")
    if header:
        try:
            value = int(header)
            if value > 1_000_000_000:  # epoch timestamp, not duration
                wait = max(1, value - int(time.time()))
            else:
                wait = value
            return False, min(wait, 120)
        except ValueError:
            pass
    return False, 0


HARD_PAUSE_AFTER = 4   # switch to hard pause after this many retries
HARD_PAUSE_SECS  = 180  # 3 minutes


def _get_with_retry(url, params, max_retries=8, base_delay=5):
    for attempt in range(max_retries):
        r = requests.get(
            url, params=_params_with_email(params),
            headers=_headers(), timeout=30
        )
        if r.status_code == 429:
            is_budget, wait_secs = _parse_429(r)
            if is_budget:
                raise BudgetExhaustedError(wait_secs)
            if attempt < HARD_PAUSE_AFTER:
                backoff = base_delay * (2 ** attempt)
                wait = max(wait_secs, backoff)
            else:
                wait = HARD_PAUSE_SECS
            print(f"  [rate-limit] 429 — waiting {wait}s (attempt {attempt+1}/{max_retries})...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r
    raise RuntimeError(f"Max retries exceeded for {url}")


# ── Active topic queries (broad, minimal) ─────────────────────────────────────
#
# Each topic has ONE shared DB. Pull widely — claims are evaluated locally.

TOPIC_QUERIES = {
    "peanut_allergy": {
        "name": "Peanut Allergy",
        "query": "peanut allergy infant child",
        "food_type_hint": "peanuts",
        "age_hint": "infant",
    },
    "vitamin_d": {
        "name": "Vitamin D",
        "query": "vitamin D infant child",
        "food_type_hint": "vitamin-d",
        "age_hint": "0-12 months",
    },
    "cow_milk": {
        "name": "Cow's Milk Introduction",
        "query": "cow milk infant child",
        "food_type_hint": "cow-milk",
        "age_hint": "12-24 months",
    },
    "yoghurt": {
        "name": "Yoghurt Introduction",
        "query": "yoghurt yogurt infant baby introduction",
        "food_type_hint": "yoghurt",
        "age_hint": "6-12 months",
    },
    "weaning": {
        "name": "Weaning & Complementary Feeding",
        "query": "weaning complementary feeding infant solid food introduction",
        "food_type_hint": "solid-food",
        "age_hint": "4-6 months",
    },
    "honey": {
        "name": "Honey Safety",
        "query": "honey infant botulism child safety",
        "food_type_hint": "honey",
        "age_hint": "0-12 months",
    },
    "salt_sugar": {
        "name": "Salt & Sugar in Baby Food",
        "query": "salt sugar sodium infant baby food intake",
        "food_type_hint": "salt-sugar",
        "age_hint": "0-24 months",
    },
    "egg_introduction": {
        "name": "Egg Introduction",
        "query": "egg allergy infant introduction prevention",
        "food_type_hint": "eggs",
        "age_hint": "4-6 months",
    },
    "iron_foods": {
        "name": "Iron-Rich Foods for Infants",
        "query": "iron deficiency infant complementary food fortification",
        "food_type_hint": "iron-rich",
        "age_hint": "6-12 months",
    },
}

# Alias for backwards-compatible --list-topics and --all
PREDEFINED_TOPICS = TOPIC_QUERIES


# ── Claims — specific recommendations to evaluate papers against ──────────────
#
# Each claim belongs to a topic (shares the topic's DB).
# keyword_hints: any of these words/phrases in title+abstract triggers a prepass match.
# direction: "for" = paper likely supports the claim, "against" = likely contradicts it.

CLAIMS = {

    # ── Peanut allergy: introduction timing ──────────────────────────────────
    "peanut_intro_4m_for": {
        "topic": "peanut_allergy",
        "claim": "Introducing peanuts at around 4 months of age reduces the risk of peanut allergy",
        "direction": "for",
        "keyword_hints": [
            "4 month", "4-month", "four month", "early introduction",
            "early exposure", "prevention", "tolerance induction",
        ],
    },
    "peanut_intro_4m_against": {
        "topic": "peanut_allergy",
        "claim": "Introducing peanuts at 4 months is not recommended or may increase allergy risk",
        "direction": "against",
        "keyword_hints": [
            "4 month", "4-month", "four month", "risk", "sensitization",
            "sensitisation", "not recommended", "too early",
        ],
    },
    "peanut_intro_6m_for": {
        "topic": "peanut_allergy",
        "claim": "Introducing peanuts at around 6 months of age reduces the risk of peanut allergy",
        "direction": "for",
        "keyword_hints": [
            "6 month", "6-month", "six month", "early introduction",
            "prevention", "tolerance", "LEAP", "PETIT",
        ],
    },
    "peanut_intro_6m_against": {
        "topic": "peanut_allergy",
        "claim": "Introducing peanuts at 6 months is not sufficient to prevent allergy",
        "direction": "against",
        "keyword_hints": [
            "6 month", "6-month", "six month", "insufficient",
            "still at risk", "allergy despite", "sensitization",
        ],
    },
    "peanut_intro_later_for": {
        "topic": "peanut_allergy",
        "claim": "Delaying peanut introduction beyond 6 months is safe and acceptable for low-risk infants",
        "direction": "for",
        "keyword_hints": [
            "delay", "delayed introduction", "later introduction",
            "12 month", "after 6", "low risk", "standard guideline",
        ],
    },
    "peanut_intro_later_against": {
        "topic": "peanut_allergy",
        "claim": "Delaying peanut introduction beyond 6 months increases the risk of peanut allergy",
        "direction": "against",
        "keyword_hints": [
            "delay", "delayed", "late introduction", "later introduction",
            "avoidance", "increased risk", "window of opportunity",
        ],
    },

    # ── Vitamin D ─────────────────────────────────────────────────────────────
    "vitamin_d_supplement_for": {
        "topic": "vitamin_d",
        "claim": "Vitamin D supplementation is recommended for breastfed infants to prevent deficiency",
        "direction": "for",
        "keyword_hints": [
            "supplement", "deficiency", "breastfed", "breastfeeding",
            "rickets", "recommendation", "400 IU",
        ],
    },
    "vitamin_d_sun_sufficient": {
        "topic": "vitamin_d",
        "claim": "Adequate sun exposure can provide sufficient vitamin D for infants without supplementation",
        "direction": "for",
        "keyword_hints": [
            "sun exposure", "sunlight", "sufficient", "adequate",
            "outdoor", "UV", "synthesis",
        ],
    },

    # ── Cow's milk ────────────────────────────────────────────────────────────
    "cow_milk_12m_for": {
        "topic": "cow_milk",
        "claim": "Cow's milk as a main drink should not be introduced before 12 months",
        "direction": "for",
        "keyword_hints": [
            "12 month", "one year", "main drink", "not before",
            "avoid before", "transition", "iron deficiency",
        ],
    },
    "cow_milk_early_against": {
        "topic": "cow_milk",
        "claim": "Introducing cow's milk before 12 months as a main drink is associated with iron deficiency anaemia",
        "direction": "against",
        "keyword_hints": [
            "iron deficiency", "anaemia", "anemia", "before 12",
            "early introduction", "under 12 months", "gut bleeding",
        ],
    },

    # ── Yoghurt ──────────────────────────────────────────────────────────────
    "yoghurt_6m_for": {
        "topic": "yoghurt",
        "claim": "Plain whole-milk yoghurt can be safely introduced from around 6 months of age",
        "direction": "for",
        "keyword_hints": [
            "yoghurt", "yogurt", "6 month", "complementary",
            "dairy", "introduction", "safe", "fermented",
        ],
    },
    "yoghurt_6m_against": {
        "topic": "yoghurt",
        "claim": "Yoghurt should be delayed beyond 6 months due to dairy protein sensitivity concerns",
        "direction": "against",
        "keyword_hints": [
            "yoghurt", "yogurt", "delay", "allergy", "dairy protein",
            "sensitivity", "intolerance", "not recommended",
        ],
    },
    "yoghurt_probiotic_for": {
        "topic": "yoghurt",
        "claim": "Probiotic-containing yoghurt provides gut health benefits for infants",
        "direction": "for",
        "keyword_hints": [
            "probiotic", "yoghurt", "yogurt", "gut health", "microbiome",
            "lactobacillus", "bifidobacterium", "fermented milk",
        ],
    },

    # ── Weaning ──────────────────────────────────────────────────────────────
    "weaning_6m_for": {
        "topic": "weaning",
        "claim": "Complementary foods should be introduced at around 6 months of age",
        "direction": "for",
        "keyword_hints": [
            "6 month", "six month", "WHO", "complementary feeding",
            "solid food", "weaning", "introduction", "readiness",
        ],
    },
    "weaning_4m_for": {
        "topic": "weaning",
        "claim": "Introducing complementary foods between 4 and 6 months may be beneficial for some infants",
        "direction": "for",
        "keyword_hints": [
            "4 month", "four month", "4-6 month", "early weaning",
            "developmental readiness", "earlier introduction",
        ],
    },
    "weaning_blw_for": {
        "topic": "weaning",
        "claim": "Baby-led weaning is a safe and effective approach to introducing solid foods",
        "direction": "for",
        "keyword_hints": [
            "baby-led", "baby led weaning", "BLW", "self-feeding",
            "finger food", "autonomy", "responsive feeding",
        ],
    },
    "weaning_blw_against": {
        "topic": "weaning",
        "claim": "Baby-led weaning may increase choking risk or lead to inadequate nutrient intake",
        "direction": "against",
        "keyword_hints": [
            "baby-led", "baby led weaning", "BLW", "choking",
            "gagging", "inadequate intake", "iron deficiency", "energy intake",
        ],
    },

    # ── Honey ────────────────────────────────────────────────────────────────
    "honey_avoid_12m_for": {
        "topic": "honey",
        "claim": "Honey must not be given to infants under 12 months due to infant botulism risk",
        "direction": "for",
        "keyword_hints": [
            "honey", "botulism", "clostridium botulinum", "under 12",
            "under 1 year", "avoid", "infant botulism", "spores",
        ],
    },
    "honey_after_12m_safe": {
        "topic": "honey",
        "claim": "Honey is safe to introduce after 12 months of age when the gut is mature enough",
        "direction": "for",
        "keyword_hints": [
            "honey", "after 12", "over 1 year", "safe", "gut maturity",
            "toddler", "older infant",
        ],
    },

    # ── Salt & Sugar ─────────────────────────────────────────────────────────
    "salt_avoid_for": {
        "topic": "salt_sugar",
        "claim": "Added salt should be avoided in food for infants under 12 months as their kidneys cannot process excess sodium",
        "direction": "for",
        "keyword_hints": [
            "salt", "sodium", "kidney", "renal", "avoid",
            "under 12 months", "no added salt", "infant food",
        ],
    },
    "sugar_avoid_for": {
        "topic": "salt_sugar",
        "claim": "Added sugars should be avoided in infant and toddler food to prevent obesity and dental caries",
        "direction": "for",
        "keyword_hints": [
            "sugar", "added sugar", "free sugar", "dental caries",
            "obesity", "tooth decay", "sweet", "infant food",
        ],
    },
    "sugar_fruit_ok": {
        "topic": "salt_sugar",
        "claim": "Natural sugars from whole fruits are acceptable and nutritious for infants from 6 months",
        "direction": "for",
        "keyword_hints": [
            "fruit", "natural sugar", "whole fruit", "puree",
            "complementary food", "acceptable", "nutritious",
        ],
    },

    # ── Egg introduction ─────────────────────────────────────────────────────
    "egg_early_for": {
        "topic": "egg_introduction",
        "claim": "Early egg introduction from around 4-6 months reduces the risk of egg allergy",
        "direction": "for",
        "keyword_hints": [
            "egg", "early introduction", "4 month", "6 month",
            "allergy prevention", "tolerance", "PETIT", "HEAP",
            "BEAT", "STEP", "EAT",
        ],
    },
    "egg_early_against": {
        "topic": "egg_introduction",
        "claim": "Early egg introduction may trigger allergic reactions in sensitised infants",
        "direction": "against",
        "keyword_hints": [
            "egg", "allergic reaction", "sensitised", "sensitized",
            "eczema", "IgE", "skin prick", "risk factor",
        ],
    },
    "egg_cooked_vs_raw": {
        "topic": "egg_introduction",
        "claim": "Well-cooked egg is safer for first introduction than raw or lightly cooked egg",
        "direction": "for",
        "keyword_hints": [
            "cooked egg", "baked egg", "heated egg", "raw egg",
            "ovomucoid", "ovalbumin", "cooking", "heat treatment",
        ],
    },

    # ── Iron-rich foods ──────────────────────────────────────────────────────
    "iron_6m_for": {
        "topic": "iron_foods",
        "claim": "Iron-rich complementary foods should be prioritised from 6 months as breastmilk iron stores deplete",
        "direction": "for",
        "keyword_hints": [
            "iron", "iron-rich", "complementary food", "6 month",
            "iron stores", "depletion", "meat", "fortified cereal",
        ],
    },
    "iron_meat_for": {
        "topic": "iron_foods",
        "claim": "Red meat is the most bioavailable source of iron for infants starting solids",
        "direction": "for",
        "keyword_hints": [
            "red meat", "heme iron", "bioavailable", "beef",
            "lamb", "absorption", "complementary", "first food",
        ],
    },
    "iron_fortified_for": {
        "topic": "iron_foods",
        "claim": "Iron-fortified cereals are an effective way to meet infant iron requirements",
        "direction": "for",
        "keyword_hints": [
            "fortified cereal", "iron-fortified", "infant cereal",
            "rice cereal", "iron requirement", "supplementation",
        ],
    },
}


# ── OLD topics (commented out — kept for reference) ──────────────────────────
# fmt: off
# _OLD_PREDEFINED_TOPICS = {
#
#     # ── ALLERGENS (14) ───────────────────────────────────────────────────────
#     # "peanut_allergy": {
#     #     "name": "Peanut Allergy",
#     #     "query": "peanut allergy infant introduction early prevention sensitisation",
#     #     "concepts": ["C2776082936"],
#     #     "food_type_hint": "peanuts",
#     #     "age_hint": "infant",
#     # },
#     # "egg_allergy": {
#     #     "name": "Egg Allergy",
#     #     "query": "egg allergy infant introduction prevention sensitisation",
#     #     "food_type_hint": "eggs",
#     #     "age_hint": "infant",
#     # },
#     # "cow_milk_allergy": {
#     #     "name": "Cow Milk Allergy",
#     #     "query": "cow milk protein allergy infant formula sensitisation",
#     #     "food_type_hint": "cow-milk",
#     #     "age_hint": "infant",
#     # },
#     # "tree_nut_allergy": {
#     #     "name": "Tree Nut Allergy",
#     #     "query": "tree nut allergy children walnut cashew almond introduction",
#     #     "food_type_hint": "tree-nuts",
#     #     "age_hint": "infant",
#     # },
#     # "wheat_gluten_allergy": {
#     #     "name": "Wheat & Gluten Allergy",
#     #     "query": "wheat gluten allergy infant introduction sensitisation celiac",
#     #     "food_type_hint": "wheat-gluten",
#     #     "age_hint": "infant",
#     # },
#     # "soy_allergy": {
#     #     "name": "Soy Allergy",
#     #     "query": "soy allergy infant soy protein formula sensitisation",
#     #     "food_type_hint": "soy",
#     #     "age_hint": "infant",
#     # },
#     # "sesame_allergy": {
#     #     "name": "Sesame Allergy",
#     #     "query": "sesame allergy infant children sensitisation introduction",
#     #     "food_type_hint": "sesame",
#     #     "age_hint": "infant",
#     # },
#     # "fish_shellfish_allergy": {
#     #     "name": "Fish & Shellfish Allergy",
#     #     "query": "fish shellfish allergy infant children introduction prevention",
#     #     "food_type_hint": "fish",
#     #     "age_hint": "infant",
#     # },
#     # "multiple_food_allergy": {
#     #     "name": "Multiple Food Allergies",
#     #     "query": "multiple food allergy infant polysensitisation management diet",
#     #     "food_type_hint": "general",
#     #     "age_hint": "infant",
#     # },
#     # "oral_immunotherapy_allergy": {
#     #     "name": "Oral Immunotherapy for Food Allergy",
#     #     "query": "oral immunotherapy food allergy desensitisation children peanut egg milk",
#     #     "food_type_hint": "general",
#     #     "age_hint": "infant",
#     # },
#     # "early_allergen_introduction": {
#     #     "name": "Early Allergen Introduction",
#     #     "query": "early introduction allergenic foods infant prevention tolerance LEAP PETIT",
#     #     "food_type_hint": "general",
#     #     "age_hint": "4-6 months",
#     # },
#     # "allergy_prevention_diet": {
#     #     "name": "Dietary Allergy Prevention",
#     #     "query": "food allergy prevention infant dietary strategy maternal breastfeeding",
#     #     "food_type_hint": "general",
#     #     "age_hint": "infant",
#     # },
#     # "eczema_food_allergy": {
#     #     "name": "Eczema & Food Allergy",
#     #     "query": "eczema atopic dermatitis food allergy infant skin barrier sensitisation",
#     #     "food_type_hint": "general",
#     #     "age_hint": "infant",
#     # },
#     # "food_allergy_anaphylaxis": {
#     #     "name": "Anaphylaxis in Infants",
#     #     "query": "anaphylaxis food allergy infant children emergency epinephrine management",
#     #     "food_type_hint": "general",
#     #     "age_hint": "infant",
#     # },
#
#     # ── FEEDING METHODS (11) ─────────────────────────────────────────────────
#     # "complementary_feeding": {
#     #     "name": "Complementary Feeding",
#     #     "query": "complementary feeding infant solid foods introduction weaning",
#     #     "food_type_hint": "solid-food",
#     #     "age_hint": "6-12 months",
#     # },
#     # "breastfeeding": {
#     #     "name": "Breastfeeding",
#     #     "query": "breastfeeding infant nutrition benefits outcomes health",
#     #     "food_type_hint": "breast-milk",
#     #     "age_hint": "0-6 months",
#     # },
#     # "infant_formula": {
#     #     "name": "Infant Formula",
#     #     "query": "infant formula nutrition comparison breastfeeding outcomes",
#     #     "food_type_hint": "formula",
#     #     "age_hint": "0-12 months",
#     # },
#     # "baby_led_weaning": {
#     #     "name": "Baby-Led Weaning",
#     #     "query": "baby-led weaning self-feeding solid foods infant",
#     #     "food_type_hint": "solid-food",
#     #     "age_hint": "6-12 months",
#     # },
#     # "responsive_feeding": {
#     #     "name": "Responsive Feeding",
#     #     "query": "responsive feeding infant cue-based hunger satiety parental feeding style",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-24 months",
#     # },
#     # "donor_breast_milk": {
#     #     "name": "Donor Breast Milk",
#     #     "query": "donor human milk bank pasteurisation preterm infant formula alternative",
#     #     "food_type_hint": "breast-milk",
#     #     "age_hint": "0-6 months",
#     # },
#     # "mixed_feeding": {
#     #     "name": "Mixed Breast & Formula Feeding",
#     #     "query": "mixed feeding breastfeeding formula supplementation infant outcomes",
#     #     "food_type_hint": "breast-milk",
#     #     "age_hint": "0-6 months",
#     # },
#     # "formula_preparation_safety": {
#     #     "name": "Formula Preparation Safety",
#     #     "query": "infant formula preparation safety contamination water sterilisation bacterial",
#     #     "food_type_hint": "formula",
#     #     "age_hint": "0-12 months",
#     # },
#     # "extended_breastfeeding": {
#     #     "name": "Extended Breastfeeding",
#     #     "query": "extended breastfeeding beyond 12 months toddler outcomes benefits",
#     #     "food_type_hint": "breast-milk",
#     #     "age_hint": "12-24 months",
#     # },
#     # "breastfeeding_difficulties": {
#     #     "name": "Breastfeeding Difficulties",
#     #     "query": "breastfeeding difficulties latching low milk supply mastitis support intervention",
#     #     "food_type_hint": "breast-milk",
#     #     "age_hint": "0-6 months",
#     # },
#     # "preterm_infant_nutrition": {
#     #     "name": "Preterm Infant Nutrition",
#     #     "query": "preterm infant nutrition fortification necrotising enterocolitis NICU growth",
#     #     "food_type_hint": "formula",
#     #     "age_hint": "preterm",
#     # },
#
#     # ── NUTRIENTS & SUPPLEMENTS (13) ─────────────────────────────────────────
#     # "iron_deficiency": {
#     #     "name": "Iron Deficiency",
#     #     "query": "iron deficiency anaemia infant toddler supplementation complementary food",
#     #     "food_type_hint": "iron",
#     #     "age_hint": "6-24 months",
#     # },
#     # "vitamin_d": {
#     #     "name": "Vitamin D",
#     #     "query": "vitamin D deficiency infant supplementation rickets sun exposure",
#     #     "food_type_hint": "vitamin-d",
#     #     "age_hint": "0-12 months",
#     # },
#     # "omega3_dha": {
#     #     "name": "Omega-3 / DHA",
#     #     "query": "omega-3 DHA ARA infant brain development fish oil supplementation",
#     #     "food_type_hint": "omega3",
#     #     "age_hint": "0-12 months",
#     # },
#     # "zinc_infant": {
#     #     "name": "Zinc in Infant Nutrition",
#     #     "query": "zinc deficiency infant supplementation growth immunity complementary food",
#     #     "food_type_hint": "general",
#     #     "age_hint": "6-24 months",
#     # },
#     # "calcium_bone_infant": {
#     #     "name": "Calcium & Bone Development",
#     #     "query": "calcium intake infant bone development density dairy supplementation",
#     #     "food_type_hint": "dairy",
#     #     "age_hint": "0-24 months",
#     # },
#     # "iodine_infant": {
#     #     "name": "Iodine & Thyroid in Infants",
#     #     "query": "iodine deficiency infant thyroid development breast milk formula",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-12 months",
#     # },
#     # "folate_infant": {
#     #     "name": "Folate & Neural Development",
#     #     "query": "folate folic acid infant neural development supplementation brain",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-12 months",
#     # },
#     # "vitamin_a_infant": {
#     #     "name": "Vitamin A Deficiency",
#     #     "query": "vitamin A deficiency infant supplementation infection mortality vision",
#     #     "food_type_hint": "general",
#     #     "age_hint": "6-24 months",
#     # },
#     # "vitamin_b12_infant": {
#     #     "name": "Vitamin B12 in Infant Nutrition",
#     #     "query": "vitamin B12 deficiency infant vegan vegetarian breastfeeding supplementation",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-24 months",
#     # },
#     # "vitamin_k_infant": {
#     #     "name": "Vitamin K in Newborns",
#     #     "query": "vitamin K newborn haemorrhagic disease supplementation prophylaxis",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-6 months",
#     # },
#     # "choline_infant": {
#     #     "name": "Choline & Brain Development",
#     #     "query": "choline infant brain development cognitive supplementation breast milk egg",
#     #     "food_type_hint": "eggs",
#     #     "age_hint": "0-24 months",
#     # },
#     # "probiotics_infant": {
#     #     "name": "Probiotics in Infant Nutrition",
#     #     "query": "probiotics infant colic eczema allergy gut lactobacillus bifidobacterium",
#     #     "food_type_hint": "probiotics",
#     #     "age_hint": "0-12 months",
#     # },
#     # "prebiotics_infant": {
#     #     "name": "Prebiotics & Infant Gut",
#     #     "query": "prebiotics infant gut microbiome human milk oligosaccharides HMO formula",
#     #     "food_type_hint": "probiotics",
#     #     "age_hint": "0-12 months",
#     # },
#
#     # ── SPECIFIC FOODS (12) ──────────────────────────────────────────────────
#     # "vegetable_introduction": {
#     #     "name": "Vegetable Introduction",
#     #     "query": "vegetable acceptance infant repeated exposure food neophobia taste",
#     #     "food_type_hint": "vegetables",
#     #     "age_hint": "4-12 months",
#     # },
#     # "fruit_introduction": {
#     #     "name": "Fruit Introduction",
#     #     "query": "fruit introduction infant diet sweetness preference early exposure",
#     #     "food_type_hint": "fruits",
#     #     "age_hint": "4-12 months",
#     # },
#     # "meat_introduction": {
#     #     "name": "Meat Introduction",
#     #     "query": "meat introduction infant iron zinc complementary food protein haem",
#     #     "food_type_hint": "meat",
#     #     "age_hint": "6-12 months",
#     # },
#     # "fish_introduction": {
#     #     "name": "Fish Introduction",
#     #     "query": "fish introduction infant omega-3 DHA mercury allergy complementary",
#     #     "food_type_hint": "fish",
#     #     "age_hint": "6-12 months",
#     # },
#     # "dairy_introduction": {
#     #     "name": "Cow's Milk Introduction",
#     #     "query": "cow milk introduction toddler dairy transition infant formula 12 months",
#     #     "food_type_hint": "cow-milk",
#     #     "age_hint": "12-24 months",
#     # },
#     # "legume_introduction": {
#     #     "name": "Legumes & Pulses",
#     #     "query": "legume bean lentil infant introduction protein complementary feeding",
#     #     "food_type_hint": "legumes",
#     #     "age_hint": "6-12 months",
#     # },
#     # "whole_grain_infant": {
#     #     "name": "Whole Grains & Infant Cereals",
#     #     "query": "whole grain cereal infant porridge oat rice complementary feeding fibre",
#     #     "food_type_hint": "grains",
#     #     "age_hint": "6-12 months",
#     # },
#     # "organic_baby_food": {
#     #     "name": "Organic Baby Food",
#     #     "query": "organic baby food infant pesticide nutrient content commercial puree",
#     #     "food_type_hint": "baby-food",
#     #     "age_hint": "6-12 months",
#     # },
#     # "sugar_salt_babies": {
#     #     "name": "Sugar & Salt in Infant Diet",
#     #     "query": "added sugar salt sodium intake infant toddler processed food diet",
#     #     "food_type_hint": "general",
#     #     "age_hint": "6-36 months",
#     # },
#     # "ultra_processed_infant": {
#     #     "name": "Ultra-Processed Foods in Infant Diet",
#     #     "query": "ultra-processed food toddler infant diet health obesity early childhood",
#     #     "food_type_hint": "general",
#     #     "age_hint": "12-36 months",
#     # },
#     # "commercial_baby_food": {
#     #     "name": "Commercial Baby Food Pouches",
#     #     "query": "commercial baby food pouch jar puree nutrition labelling composition quality",
#     #     "food_type_hint": "baby-food",
#     #     "age_hint": "6-12 months",
#     # },
#     # "plant_based_infant": {
#     #     "name": "Plant-Based Infant Diets",
#     #     "query": "plant-based vegan vegetarian infant toddler diet nutrition deficiency risk",
#     #     "food_type_hint": "legumes",
#     #     "age_hint": "0-24 months",
#     # },
#
#     # ── GUT HEALTH (6) ───────────────────────────────────────────────────────
#     # "gut_microbiome": {
#     #     "name": "Gut Microbiome",
#     #     "query": "infant gut microbiome diet colonisation early life diversity",
#     #     "food_type_hint": "probiotics",
#     #     "age_hint": "0-24 months",
#     # },
#     # "infant_colic": {
#     #     "name": "Infant Colic & Diet",
#     #     "query": "infant colic excessive crying probiotic maternal diet elimination",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-6 months",
#     # },
#     # "infant_constipation": {
#     #     "name": "Infant Constipation & Diet",
#     #     "query": "infant constipation diet fibre prune juice complementary feeding",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-24 months",
#     # },
#     # "infant_reflux": {
#     #     "name": "Infant Reflux & GERD",
#     #     "query": "gastroesophageal reflux infant GERD diet thickening formula positioning",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-12 months",
#     # },
#     # "gut_dysbiosis_infant": {
#     #     "name": "Gut Dysbiosis in Infants",
#     #     "query": "gut dysbiosis infant antibiotic microbiome disruption diet restoration",
#     #     "food_type_hint": "probiotics",
#     #     "age_hint": "0-24 months",
#     # },
#     # "food_texture_progression": {
#     #     "name": "Food Texture Progression",
#     #     "query": "food texture lumpy pureed infant feeding development swallowing",
#     #     "food_type_hint": "solid-food",
#     #     "age_hint": "6-18 months",
#     # },
#
#     # ── GROWTH & DEVELOPMENT (7) ─────────────────────────────────────────────
#     # "infant_growth_faltering": {
#     #     "name": "Infant Growth Faltering",
#     #     "query": "infant growth faltering failure to thrive undernutrition feeding intervention",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-24 months",
#     # },
#     # "childhood_obesity_diet": {
#     #     "name": "Childhood Obesity & Early Diet",
#     #     "query": "childhood obesity early diet infant overweight prevention risk factor",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-24 months",
#     # },
#     # "stunting_wasting": {
#     #     "name": "Stunting & Wasting",
#     #     "query": "stunting wasting infant malnutrition complementary food therapeutic nutrition",
#     #     "food_type_hint": "general",
#     #     "age_hint": "6-24 months",
#     # },
#     # "brain_development_nutrition": {
#     #     "name": "Brain & Cognitive Development",
#     #     "query": "brain development infant nutrition cognitive outcomes DHA iron choline iodine",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-24 months",
#     # },
#     # "catch_up_growth": {
#     #     "name": "Catch-Up Growth",
#     #     "query": "catch up growth preterm low birth weight infant nutrition formula enriched",
#     #     "food_type_hint": "formula",
#     #     "age_hint": "preterm",
#     # },
#     # "dental_health_infant": {
#     #     "name": "Dental Health & Early Diet",
#     #     "query": "early childhood caries dental health sugar infant bottle feeding fluoride",
#     #     "food_type_hint": "general",
#     #     "age_hint": "12-36 months",
#     # },
#     # "toddler_milk_drinks": {
#     #     "name": "Toddler Milk & Growing-Up Drinks",
#     #     "query": "toddler milk growing up formula drink nutrition marketing necessity",
#     #     "food_type_hint": "formula",
#     #     "age_hint": "12-36 months",
#     # },
#
#     # ── FEEDING BEHAVIOUR (7) ────────────────────────────────────────────────
#     # "food_neophobia": {
#     #     "name": "Food Neophobia in Toddlers",
#     #     "query": "food neophobia toddler new food refusal exposure intervention variety",
#     #     "food_type_hint": "general",
#     #     "age_hint": "12-36 months",
#     # },
#     # "picky_eating": {
#     #     "name": "Picky Eating",
#     #     "query": "picky eating toddler selective eating diet variety intervention outcomes",
#     #     "food_type_hint": "general",
#     #     "age_hint": "12-36 months",
#     # },
#     # "feeding_difficulties": {
#     #     "name": "Paediatric Feeding Difficulties",
#     #     "query": "feeding difficulties infant ARFID avoidant restrictive food intake disorder paediatric",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-36 months",
#     # },
#     # "appetite_regulation": {
#     #     "name": "Appetite Regulation in Infants",
#     #     "query": "appetite regulation infant satiety hunger cues overfeeding parental feeding style",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-12 months",
#     # },
#     # "flavor_learning": {
#     #     "name": "Flavour Learning & Taste Exposure",
#     #     "query": "flavour flavor learning infant taste exposure amniotic fluid breast milk preference",
#     #     "food_type_hint": "general",
#     #     "age_hint": "0-12 months",
#     # },
#     # "mealtime_behaviour": {
#     #     "name": "Mealtime Behaviour & Family",
#     #     "query": "mealtime behaviour family infant toddler feeding practices parenting shared meals",
#     #     "food_type_hint": "general",
#     #     "age_hint": "12-36 months",
#     # },
#     # "division_of_responsibility": {
#     #     "name": "Division of Responsibility in Feeding",
#     #     "query": "division of responsibility feeding toddler parental role child autonomy Satter",
#     #     "food_type_hint": "general",
#     #     "age_hint": "12-36 months",
#     # },
#
#     # ── MATERNAL NUTRITION (8) ───────────────────────────────────────────────
#     # "maternal_diet_breastmilk": { ... },
#     # "maternal_nutrition_pregnancy": { ... },
#     # "prenatal_allergy_prevention": { ... },
#     # "gestational_diabetes_feeding": { ... },
#     # "maternal_microbiome": { ... },
#     # "prenatal_omega3": { ... },
#     # "maternal_iodine_pregnancy": { ... },
#     # "maternal_anaemia_infant": { ... },
#
#     # ── SPECIAL POPULATIONS (8) ──────────────────────────────────────────────
#     # "low_birth_weight_feeding": { ... },
#     # "celiac_disease_infant": { ... },
#     # "fpies": { ... },
#     # "eosinophilic_esophagitis": { ... },
#     # "cleft_palate_feeding": { ... },
#     # "downs_syndrome_feeding": { ... },
#     # "immune_development_diet": { ... },
#     # "fortified_complementary_foods": { ... },
#
#     # ── FOOD SAFETY & CONTAMINANTS (6) ──────────────────────────────────────
#     # "heavy_metals_baby_food": { ... },
#     # "pesticides_infant_food": { ... },
#     # "nitrates_baby_food": { ... },
#     # "microplastics_formula": { ... },
#     # "bpa_packaging_infant": { ... },
#     # "food_safety_preparation": { ... },
#
#     # ── SOCIOECONOMIC, CULTURAL & GLOBAL (8) ────────────────────────────────
#     # "food_insecurity_infant": { ... },
#     # "cultural_complementary_feeding": { ... },
#     # "global_malnutrition_infant": { ... },
#     # "baby_food_marketing": { ... },
#     # "baby_food_labelling": { ... },
#     # "socioeconomic_infant_diet": { ... },
#     # "sleep_feeding_infant": { ... },
#     # "screen_time_feeding": { ... },
# }
# fmt: on


# ── Database setup ────────────────────────────────────────────────────────────

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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS claim_evaluations (
            paperId TEXT,
            claim_key TEXT,
            keyword_match INTEGER DEFAULT 0,
            llm_stance TEXT,
            llm_confidence INTEGER,
            llm_summary TEXT,
            PRIMARY KEY (paperId, claim_key)
        )
    """)
    conn.commit()
    return conn


# ── Keyword pre-pass ──────────────────────────────────────────────────────────

def keyword_prepass(db_path, topic_key=None, force=False):
    """
    Fast scan: for each paper, check which claims' keyword_hints appear in
    title+abstract. Records matches in claim_evaluations with keyword_match=1.

    Run this before the LLM step to narrow down which (paper, claim) pairs
    need full AI evaluation.
    """
    # Determine which claims apply to this DB
    if topic_key:
        relevant_claims = {k: v for k, v in CLAIMS.items() if v["topic"] == topic_key}
    else:
        # Infer topic from DB filename
        db_name = os.path.basename(db_path).replace("papers_", "").replace(".db", "")
        relevant_claims = {k: v for k, v in CLAIMS.items() if v["topic"] == db_name}

    if not relevant_claims:
        print(f"  [prepass] no claims found for topic '{topic_key}'")
        return 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT paperId, title, abstract FROM papers WHERE abstract IS NOT NULL"
    ).fetchall()

    matched = 0
    for row in rows:
        text = ((row["title"] or "") + " " + (row["abstract"] or "")).lower()
        for claim_key, claim_cfg in relevant_claims.items():
            if not force:
                existing = conn.execute(
                    "SELECT keyword_match FROM claim_evaluations WHERE paperId=? AND claim_key=?",
                    (row["paperId"], claim_key)
                ).fetchone()
                if existing is not None:
                    continue

            hit = any(kw.lower() in text for kw in claim_cfg["keyword_hints"])
            if hit:
                conn.execute(
                    """INSERT OR REPLACE INTO claim_evaluations
                       (paperId, claim_key, keyword_match)
                       VALUES (?, ?, 1)""",
                    (row["paperId"], claim_key)
                )
                matched += 1

    conn.commit()
    conn.close()
    print(f"  [prepass] {matched} (paper, claim) keyword matches across {len(rows)} papers")
    return matched


# ── OpenAlex fetch helpers ────────────────────────────────────────────────────

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
        resp = _get_with_retry(f"{OPENALEX_BASE}/works", params)
        return resp.json().get("meta", {}).get("count", 0)
    except BudgetExhaustedError:
        raise
    except Exception as e:
        print(f"  [warn] count fetch failed: {e}")
        return 0


def fetch_all_topic_counts(out_path=None):
    """Fetch total OpenAlex paper counts for all active topics and save to JSON."""
    if out_path is None:
        out_path = os.path.join(DATA_DIR, "topic_counts.json")
    existing = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)

    counts = dict(existing)
    total = len(TOPIC_QUERIES)
    for i, (key, cfg) in enumerate(TOPIC_QUERIES.items(), 1):
        count = fetch_topic_count(cfg["query"], cfg.get("concepts"))
        counts[key] = count
        print(f"  [{i:3d}/{total}] {key:45s} {count:>8,d}")
        time.sleep(0.5)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(counts, f, indent=2)
    print(f"\nSaved topic counts → {out_path}")
    return counts


def fetch_works(query, concepts=None, max_results=200, filter_str=None):
    """Cursor-based pagination from OpenAlex /works with retry logic."""
    filters = ["type:article", "has_abstract:true"]
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
        resp = _get_with_retry(f"{OPENALEX_BASE}/works", params)
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
        time.sleep(0.5)

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
        "AI_primary_field": None,
        "AI_summary": None,
        "recommendation_summary": None,
        "evidence_strength": None,
        "likelihood_score": None,
        "seriousness_score": None,
        "participant_count": None,
    }, [r.replace("https://openalex.org/", "") for r in work.get("referenced_works", [])]


def import_topic(topic_key, query=None, max_results=200, min_citations=0, run_prepass=False):
    if topic_key in TOPIC_QUERIES:
        cfg = TOPIC_QUERIES[topic_key]
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
    print(f"[import] DB:    {db_path}")

    conn = create_db(db_path)
    existing = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    print(f"[import] Existing papers: {len(existing)}")
    conn.close()

    total_count = fetch_topic_count(query, concepts)
    print(f"[import] Total in OpenAlex: {total_count:,}")

    counts_path = os.path.join(DATA_DIR, "topic_counts.json")
    counts = {}
    if os.path.exists(counts_path):
        with open(counts_path) as f:
            counts = json.load(f)
    counts[topic_key] = total_count
    with open(counts_path, "w") as f:
        json.dump(counts, f, indent=2)

    works = fetch_works(query, concepts=concepts, max_results=max_results)

    conn = sqlite3.connect(db_path)
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
        citation_pairs.extend((paper["paperId"], ref_id) for ref_id in ref_ids)
        inserted += 1

    existing_ids = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    citation_count = 0
    for source, target in citation_pairs:
        if source in existing_ids and target in existing_ids:
            conn.execute(
                "INSERT OR IGNORE INTO citations (source, target) VALUES (?,?)",
                (source, target)
            )
            citation_count += 1

    conn.commit()
    conn.close()
    print(f"[import] Done. Inserted: {inserted}, Skipped: {skipped}, Citations: {citation_count}")

    if run_prepass:
        print(f"[import] Running keyword pre-pass...")
        keyword_prepass(db_path, topic_key=topic_key)

    return db_path


def main():
    parser = argparse.ArgumentParser(description="Import baby food papers from OpenAlex")
    parser.add_argument("--topic", help="Topic key (use --list-topics to see options)")
    parser.add_argument("--query", help="Custom search query (overrides default for topic)")
    parser.add_argument("--max", type=int, default=200, help="Max papers to fetch (default: 200)")
    parser.add_argument("--min-citations", type=int, default=0, help="Min citations filter")
    parser.add_argument("--list-topics", action="store_true", help="List active topics")
    parser.add_argument("--list-claims", action="store_true", help="List all claims")
    parser.add_argument("--all", action="store_true", help="Import all active topics")
    parser.add_argument("--prepass", action="store_true",
                        help="Run keyword pre-pass after fetch (or standalone on existing DB)")
    args = parser.parse_args()

    if args.list_topics:
        print("\nActive topics:")
        for key, cfg in TOPIC_QUERIES.items():
            claims = [k for k, v in CLAIMS.items() if v["topic"] == key]
            print(f"  {key:20s} — {cfg['name']}  ({len(claims)} claims)")
        return

    if args.list_claims:
        print("\nClaims:")
        for key, cfg in CLAIMS.items():
            print(f"  {key:30s} [{cfg['direction']:7s}] {cfg['claim'][:70]}")
        return

    if args.all:
        for key in TOPIC_QUERIES:
            print(f"\n{'='*60}")
            try:
                import_topic(key, max_results=args.max, min_citations=args.min_citations,
                             run_prepass=args.prepass)
            except BudgetExhaustedError as e:
                print(f"\n[BUDGET] {e}")
                print(f"Resume with: python import_openalex.py --topic {key} --max {args.max}")
                break
        return

    if args.prepass and not args.topic:
        # Standalone pre-pass on all existing topic DBs
        for key in TOPIC_QUERIES:
            db_path = os.path.join(DATA_DIR, f"papers_{key}.db")
            if os.path.exists(db_path):
                print(f"\n[prepass] {key}")
                keyword_prepass(db_path, topic_key=key)
        return

    if not args.topic:
        parser.print_help()
        return

    try:
        import_topic(
            args.topic,
            query=args.query,
            max_results=args.max,
            min_citations=args.min_citations,
            run_prepass=args.prepass,
        )
    except BudgetExhaustedError as e:
        print(f"\n[BUDGET] {e}")
        print(f"Resume later with: python import_openalex.py --topic {args.topic} --max {args.max}")


if __name__ == "__main__":
    main()
