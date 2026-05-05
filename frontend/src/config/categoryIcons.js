// Maps food categories to icon image URLs (loremflickr for development).
// Replace with curated images for production.

const flickr = (term, lock) => `https://loremflickr.com/200/200/${term}?lock=${lock}`;

export const CATEGORY_ICONS = {
    // Allergens
    "peanuts":        flickr("peanuts", 1),
    "tree-nuts":      flickr("almonds", 2),
    "eggs":           flickr("eggs", 3),
    "fish":           flickr("salmon", 4),
    "shellfish":      flickr("shrimp", 5),
    "cow-milk":       flickr("milk", 6),
    "wheat-gluten":   flickr("wheat", 7),
    "soy":            flickr("soybeans", 8),
    "sesame":         flickr("sesame", 9),

    // Fruits & vegetables
    "fruits":         flickr("fruits", 10),
    "vegetables":     flickr("vegetables", 11),
    "leafy-greens":   flickr("spinach", 12),
    "root-veg":       flickr("carrots", 13),
    "berries":        flickr("berries", 14),
    "citrus":         flickr("orange", 15),

    // Grains & cereals
    "grains":         flickr("grains", 20),
    "oats":           flickr("oatmeal", 21),
    "rice":           flickr("rice", 22),
    "bread":          flickr("bread", 23),

    // Protein sources
    "meat":           flickr("chicken", 30),
    "poultry":        flickr("chicken", 31),
    "legumes":        flickr("lentils", 32),
    "beans":          flickr("beans", 33),

    // Dairy
    "dairy":          flickr("yogurt", 40),
    "yogurt":         flickr("yogurt", 41),
    "cheese":         flickr("cheese", 42),
    "formula":        flickr("baby bottle", 43),
    "breast-milk":    flickr("breastfeeding", 44),

    // Fats & oils
    "oils":           flickr("olive oil", 50),
    "avocado":        flickr("avocado", 51),

    // Supplements
    "iron":           flickr("iron supplement", 60),
    "vitamin-d":      flickr("sunlight vitamin", 61),
    "omega3":         flickr("fish oil", 62),
    "probiotics":     flickr("probiotics", 63),
    "zinc":           flickr("zinc", 64),

    // General fallbacks
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

// Show food image icons for experimental/study papers (those with actual trial data)
export function shouldShowIcon(node) {
    return node.paperNature === "experimental" || node.paperNature === "clinical_trial" || node.iconCategory != null;
}
