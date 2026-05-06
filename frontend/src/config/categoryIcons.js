// Maps food categories and individual foods to image URLs.
// Pattern: loremflickr.com/200/200/<term>?lock=<n> gives a stable, consistent image.

const flickr = (term, lock) => `https://loremflickr.com/200/200/${encodeURIComponent(term)}?lock=${lock}`;

export const CATEGORY_ICONS = {
    // ── Individual vegetables ────────────────────────────────────────────────
    "broccoli":       flickr("broccoli", 100),
    "carrot":         flickr("carrot", 101),
    "sweet-potato":   flickr("sweet potato", 102),
    "spinach":        flickr("spinach", 103),
    "pea":            flickr("green peas", 104),
    "avocado":        flickr("avocado", 105),
    "tomato":         flickr("tomato", 106),
    "zucchini":       flickr("zucchini", 107),
    "cauliflower":    flickr("cauliflower", 108),

    // ── Individual fruits ────────────────────────────────────────────────────
    "apple":          flickr("apple fruit", 110),
    "banana":         flickr("banana", 111),
    "mango":          flickr("mango", 112),
    "strawberry":     flickr("strawberry", 113),
    "blueberry":      flickr("blueberry", 114),
    "pear":           flickr("pear fruit", 115),
    "orange-fruit":   flickr("orange fruit", 116),
    "grape":          flickr("grapes", 117),
    "watermelon":     flickr("watermelon", 118),

    // ── Individual proteins ──────────────────────────────────────────────────
    "chicken-meat":   flickr("roast chicken", 120),
    "beef":           flickr("beef steak", 121),
    "salmon-fish":    flickr("salmon", 4),
    "sardine":        flickr("sardine fish", 123),
    "egg-food":       flickr("eggs", 3),
    "lentil":         flickr("lentils", 124),

    // ── Individual dairy ─────────────────────────────────────────────────────
    "cows-milk":      flickr("milk glass", 126),
    "yogurt-food":    flickr("yogurt", 127),
    "cheese-food":    flickr("cheese", 128),
    "breast-milk-f":  flickr("baby breastfeed", 129),

    // ── Individual grains ────────────────────────────────────────────────────
    "oats-food":      flickr("oatmeal porridge", 131),
    "rice-food":      flickr("rice bowl", 132),
    "wheat-food":     flickr("wheat bread", 133),
    "quinoa":         flickr("quinoa", 134),
    "corn":           flickr("corn cob", 135),

    // ── Individual legumes & nuts ────────────────────────────────────────────
    "chickpea":       flickr("chickpeas", 136),
    "kidney-bean":    flickr("red beans", 137),
    "peanut-food":    flickr("peanuts", 138),
    "soy-food":       flickr("soybeans", 139),
    "almond":         flickr("almonds", 140),

    // ── Individual fats & oils ───────────────────────────────────────────────
    "olive-oil":      flickr("olive oil", 141),
    "coconut-oil":    flickr("coconut", 142),
    "flaxseed":       flickr("flaxseed", 143),

    // ── Functional foods ─────────────────────────────────────────────────────
    "probiotic-food": flickr("kefir yogurt", 144),
    "prebiotic-food": flickr("fermented food", 145),
    "dark-chocolate": flickr("dark chocolate", 146),
    "herbs-spices":   flickr("herbs spices", 147),

    // ── Food group category icons (for group anchor nodes) ───────────────────
    "group-vegetables": flickr("vegetables", 200),
    "group-fruits":     flickr("fruits", 201),
    "group-proteins":   flickr("meat fish egg", 202),
    "group-dairy":      flickr("dairy milk", 203),
    "group-grains":     flickr("grains cereals", 204),
    "group-legumes":    flickr("beans legumes", 205),
    "group-fats":       flickr("olive oil avocado", 206),
    "group-functional": flickr("probiotics fermented", 207),

    // ── Legacy category slugs (used by topic/recommendation view) ────────────
    "peanuts":        flickr("peanuts", 1),
    "tree-nuts":      flickr("almonds", 2),
    "eggs":           flickr("eggs", 3),
    "fish":           flickr("salmon", 4),
    "shellfish":      flickr("shrimp", 5),
    "cow-milk":       flickr("milk", 6),
    "wheat-gluten":   flickr("wheat", 7),
    "soy":            flickr("soybeans", 8),
    "sesame":         flickr("sesame", 9),
    "fruits":         flickr("fruits", 10),
    "vegetables":     flickr("vegetables", 11),
    "leafy-greens":   flickr("spinach", 12),
    "root-veg":       flickr("carrots", 13),
    "berries":        flickr("berries", 14),
    "citrus":         flickr("orange", 15),
    "grains":         flickr("grains", 20),
    "oats":           flickr("oatmeal", 21),
    "rice":           flickr("rice", 22),
    "bread":          flickr("bread", 23),
    "meat":           flickr("chicken", 30),
    "poultry":        flickr("chicken", 31),
    "legumes":        flickr("lentils", 32),
    "beans":          flickr("beans", 33),
    "dairy":          flickr("yogurt", 40),
    "yogurt":         flickr("yogurt", 41),
    "cheese":         flickr("cheese", 42),
    "formula":        flickr("baby bottle", 43),
    "breast-milk":    flickr("breastfeeding", 44),
    "oils":           flickr("olive oil", 50),
    "iron":           flickr("iron supplement", 60),
    "vitamin-d":      flickr("sunlight vitamin", 61),
    "omega3":         flickr("fish oil", 62),
    "probiotics":     flickr("probiotics", 63),
    "zinc":           flickr("zinc", 64),
    "baby-food":      flickr("baby food", 70),
    "solid-food":     flickr("baby puree", 71),
    "weaning":        flickr("spoon feeding baby", 72),
    "general":        flickr("healthy food", 73),
};

export const FIELD_FALLBACK_ICONS = {
    "Allergen Introduction":    flickr("peanuts", 1),
    "Feeding Milestones":       flickr("baby spoon", 72),
    "Nutrients & Supplements":  flickr("vitamins", 61),
    "Food Safety":              flickr("baby food safe", 70),
    "Gut Health":               flickr("probiotics", 63),
    "Growth & Development":     flickr("baby growth", 74),
    "Breastfeeding & Formula":  flickr("breastfeeding", 44),
};

export function getIconPath(node) {
    if (node.iconCategory && CATEGORY_ICONS[node.iconCategory]) {
        return CATEGORY_ICONS[node.iconCategory];
    }
    if (node.primaryField && FIELD_FALLBACK_ICONS[node.primaryField]) {
        return FIELD_FALLBACK_ICONS[node.primaryField];
    }
    return CATEGORY_ICONS["general"];
}

export function shouldShowIcon(node) {
    return node.paperNature === "experimental" || node.paperNature === "clinical_trial" || node.iconCategory != null;
}
