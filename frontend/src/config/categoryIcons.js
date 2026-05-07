// Maps food icon_category keys to image paths.
// Local images are served from /images/foods/<key>.jpg (downloaded by backend/download_food_images.py).
// Falls back to loremflickr for any key without a local file.

const local = (key) => `/images/foods/${key}.jpg`;
const flickr = (term, lock) => `https://loremflickr.com/200/200/${encodeURIComponent(term)}?lock=${lock}`;

export const CATEGORY_ICONS = {
    // ── Vegetables ───────────────────────────────────────────────────────────
    "broccoli":           local("broccoli"),
    "carrot":             local("carrot"),
    "sweet-potato":       local("sweet-potato"),
    "spinach":            local("spinach"),
    "pea":                local("pea"),
    "avocado":            local("avocado"),
    "tomato":             local("tomato"),
    "zucchini":           local("zucchini"),
    "cauliflower":        local("cauliflower"),
    "beetroot":           local("beetroot"),
    "parsnip":            local("parsnip"),
    "butternut-squash":   local("butternut-squash"),
    "green-bean":         local("green-bean"),
    "kale":               local("kale"),
    "bell-pepper":        local("bell-pepper"),
    "cucumber":           local("cucumber"),
    "leek":               local("leek"),

    // ── Fruits ───────────────────────────────────────────────────────────────
    "apple":              local("apple"),
    "banana":             local("banana"),
    "mango":              local("mango"),
    "strawberry":         local("strawberry"),
    "blueberry":          local("blueberry"),
    "pear":               local("pear"),
    "orange-fruit":       local("orange-fruit"),
    "grape":              local("grape"),
    "watermelon":         local("watermelon"),
    "kiwi":               local("kiwi"),
    "papaya":             local("papaya"),
    "peach":              local("peach"),
    "plum":               local("plum"),
    "raspberry":          local("raspberry"),
    "apricot":            local("apricot"),

    // ── Proteins ─────────────────────────────────────────────────────────────
    "chicken-meat":       local("chicken-meat"),
    "beef":               local("beef"),
    "salmon-fish":        local("salmon-fish"),
    "sardine":            local("sardine"),
    "egg-food":           local("egg-food"),
    "lentil":             local("lentil"),
    "tuna-fish":          local("tuna-fish"),
    "tofu":               local("tofu"),
    "cod-fish":           local("cod-fish"),
    "tempeh":             local("tempeh"),

    // ── Dairy ────────────────────────────────────────────────────────────────
    "cows-milk":          local("cows-milk"),
    "yogurt-food":        local("yogurt-food"),
    "cheese-food":        local("cheese-food"),
    "breast-milk-f":      local("breast-milk-f"),
    "butter":             local("butter"),
    "kefir":              local("kefir"),

    // ── Grains ───────────────────────────────────────────────────────────────
    "oats-food":          local("oats-food"),
    "rice-food":          local("rice-food"),
    "wheat-food":         local("wheat-food"),
    "quinoa":             local("quinoa"),
    "corn":               local("corn"),
    "barley":             local("barley"),
    "millet":             local("millet"),
    "bread":              local("bread"),
    "buckwheat":          local("buckwheat"),

    // ── Legumes & Nuts ───────────────────────────────────────────────────────
    "chickpea":           local("chickpea"),
    "kidney-bean":        local("kidney-bean"),
    "peanut-food":        local("peanut-food"),
    "soy-food":           local("soy-food"),
    "almond":             local("almond"),
    "black-bean":         local("black-bean"),
    "cashew":             local("cashew"),
    "walnut":             local("walnut"),
    "sunflower-seeds":    local("sunflower-seeds"),
    "pumpkin-seeds":      local("pumpkin-seeds"),
    "tahini":             local("tahini"),

    // ── Fats & Oils ──────────────────────────────────────────────────────────
    "olive-oil":          local("olive-oil"),
    "coconut-oil":        local("coconut-oil"),
    "flaxseed":           local("flaxseed"),
    "chia-seed":          local("chia-seed"),
    "ghee":               local("ghee"),
    "hemp-seed":          local("hemp-seed"),

    // ── Functional ───────────────────────────────────────────────────────────
    "probiotic-food":     local("probiotic-food"),
    "prebiotic-food":     local("prebiotic-food"),
    "dark-chocolate":     local("dark-chocolate"),
    "herbs-spices":       local("herbs-spices"),
    "turmeric":           local("turmeric"),
    "ginger":             local("ginger"),
    "fortified-cereal":   local("fortified-cereal"),

    // ── Meat ─────────────────────────────────────────────────────────────────
    "turkey-meat":        local("turkey-meat"),
    "lamb-meat":          local("lamb-meat"),
    "pork-meat":          local("pork-meat"),
    "duck-meat":          local("duck-meat"),
    "venison":            local("venison"),
    "rabbit-meat":        local("rabbit-meat"),

    // ── Sweets ───────────────────────────────────────────────────────────────
    "dates-fruit":        local("dates-fruit"),
    "raisins":            local("raisins"),
    "honey":              local("honey"),
    "maple-syrup":        local("maple-syrup"),
    "rice-cake":          local("rice-cake"),
    "fruit-puree":        local("fruit-puree"),

    // ── Drinks ───────────────────────────────────────────────────────────────
    "water-drink":        local("water-drink"),
    "formula-milk":       local("formula-milk"),
    "fruit-juice":        local("fruit-juice"),
    "coconut-water":      local("coconut-water"),
    "herbal-tea":         local("herbal-tea"),

    // ── Food group anchor hexagons ────────────────────────────────────────────
    "group-vegetables":   local("group-vegetables"),
    "group-fruits":       local("group-fruits"),
    "group-proteins":     local("group-proteins"),
    "group-meat":         local("group-meat"),
    "group-dairy":        local("group-dairy"),
    "group-grains":       local("group-grains"),
    "group-legumes":      local("group-legumes"),
    "group-fats":         local("group-fats"),
    "group-functional":   local("group-functional"),
    "group-sweets":       local("group-sweets"),
    "group-drinks":       local("group-drinks"),

    // ── Legacy slugs (topic/recommendation view) ─────────────────────────────
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

// Flickr fallbacks keyed by icon_category — used when local image 404s
const FLICKR_FALLBACKS = {
    "broccoli": flickr("broccoli", 100), "carrot": flickr("carrot", 101),
    "sweet-potato": flickr("sweet potato", 102), "spinach": flickr("spinach", 103),
    "pea": flickr("green peas", 104), "avocado": flickr("avocado", 105),
    "tomato": flickr("tomato", 106), "zucchini": flickr("zucchini", 107),
    "cauliflower": flickr("cauliflower", 108), "beetroot": flickr("beetroot", 109),
    "parsnip": flickr("parsnip", 150), "butternut-squash": flickr("butternut squash", 151),
    "green-bean": flickr("green beans", 152), "kale": flickr("kale", 153),
    "bell-pepper": flickr("bell pepper", 154), "cucumber": flickr("cucumber", 155),
    "leek": flickr("leek vegetable", 156),
    "apple": flickr("apple fruit", 110), "banana": flickr("banana", 111),
    "mango": flickr("mango", 112), "strawberry": flickr("strawberry", 113),
    "blueberry": flickr("blueberry", 114), "pear": flickr("pear fruit", 115),
    "orange-fruit": flickr("orange fruit", 116), "grape": flickr("grapes", 117),
    "watermelon": flickr("watermelon", 118), "kiwi": flickr("kiwi fruit", 157),
    "papaya": flickr("papaya", 158), "peach": flickr("peach fruit", 159),
    "plum": flickr("plum fruit", 160), "raspberry": flickr("raspberry", 161),
    "apricot": flickr("apricot", 162),
    "chicken-meat": flickr("roast chicken", 120), "beef": flickr("beef steak", 121),
    "salmon-fish": flickr("salmon", 4), "sardine": flickr("sardine fish", 123),
    "egg-food": flickr("eggs", 3), "lentil": flickr("lentils", 124),
    "tuna-fish": flickr("tuna fish", 163), "tofu": flickr("tofu", 164),
    "cod-fish": flickr("cod fish", 165), "tempeh": flickr("tempeh", 166),
    "turkey-meat": flickr("turkey meat", 167), "lamb-meat": flickr("lamb meat", 168),
    "pork-meat": flickr("pork", 169), "duck-meat": flickr("duck meat", 170),
    "venison": flickr("venison deer", 171), "rabbit-meat": flickr("rabbit meat", 172),
    "cows-milk": flickr("milk glass", 126), "yogurt-food": flickr("yogurt", 127),
    "cheese-food": flickr("cheese", 128), "breast-milk-f": flickr("baby breastfeed", 129),
    "butter": flickr("butter", 173), "kefir": flickr("kefir", 174),
    "oats-food": flickr("oatmeal porridge", 131), "rice-food": flickr("rice bowl", 132),
    "wheat-food": flickr("wheat bread", 133), "quinoa": flickr("quinoa", 134),
    "corn": flickr("corn cob", 135), "barley": flickr("barley grain", 175),
    "millet": flickr("millet grain", 176), "bread": flickr("bread loaf", 177),
    "buckwheat": flickr("buckwheat", 178),
    "chickpea": flickr("chickpeas", 136), "kidney-bean": flickr("red beans", 137),
    "peanut-food": flickr("peanuts", 138), "soy-food": flickr("soybeans", 139),
    "almond": flickr("almonds", 140), "black-bean": flickr("black beans", 179),
    "cashew": flickr("cashew nuts", 180), "walnut": flickr("walnuts", 181),
    "sunflower-seeds": flickr("sunflower seeds", 182), "pumpkin-seeds": flickr("pumpkin seeds", 183),
    "tahini": flickr("tahini", 184),
    "olive-oil": flickr("olive oil", 141), "coconut-oil": flickr("coconut", 142),
    "flaxseed": flickr("flaxseed", 143), "chia-seed": flickr("chia seeds", 185),
    "ghee": flickr("ghee butter", 186), "hemp-seed": flickr("hemp seeds", 187),
    "probiotic-food": flickr("kefir yogurt", 144), "prebiotic-food": flickr("fermented food", 145),
    "dark-chocolate": flickr("dark chocolate", 146), "herbs-spices": flickr("herbs spices", 147),
    "turmeric": flickr("turmeric", 188), "ginger": flickr("ginger root", 189),
    "fortified-cereal": flickr("cereal breakfast", 190),
    "dates-fruit": flickr("dates fruit", 191), "raisins": flickr("raisins", 192),
    "honey": flickr("honey jar", 193), "maple-syrup": flickr("maple syrup", 194),
    "rice-cake": flickr("rice cake", 195), "fruit-puree": flickr("baby puree", 196),
    "water-drink": flickr("water glass", 197), "formula-milk": flickr("baby bottle", 198),
    "fruit-juice": flickr("fruit juice", 199), "coconut-water": flickr("coconut water", 200),
    "herbal-tea": flickr("herbal tea", 201),
    "group-vegetables": flickr("vegetables", 210), "group-fruits": flickr("fruits", 211),
    "group-proteins": flickr("meat fish egg", 212), "group-meat": flickr("meat", 213),
    "group-dairy": flickr("dairy milk", 214), "group-grains": flickr("grains cereals", 215),
    "group-legumes": flickr("beans legumes", 216), "group-fats": flickr("olive oil avocado", 217),
    "group-functional": flickr("probiotics fermented", 218), "group-sweets": flickr("sweets candy", 219),
    "group-drinks": flickr("drinks beverages", 220),
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

export function getFallbackIconPath(iconCategory) {
    return FLICKR_FALLBACKS[iconCategory] || flickr("healthy food", 73);
}

export function shouldShowIcon(node) {
    return node.paperNature === "experimental" || node.paperNature === "clinical_trial" || node.iconCategory != null;
}
