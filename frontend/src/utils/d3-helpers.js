// Geometry helpers shared by the Graph component and the layout engine.

export const roundedHexagonPath = (radius) => {
    const points = [];
    for (let i = 0; i < 6; i++) {
        const angle = (i * 60) * (Math.PI / 180);
        points.push([radius * Math.cos(angle), radius * Math.sin(angle)]);
    }
    return points.map((p, i) => (i === 0 ? "M" : "L") + p[0] + "," + p[1]).join(" ") + " Z";
};

// Stable pseudo-random source. Layouts hash node ids instead of calling
// Math.random() so that re-running a layout reproduces the same positions.
export const hashString = (value) => {
    let hash = 0;
    const str = String(value);
    for (let i = 0; i < str.length; i += 1) {
        hash = ((hash << 5) - hash) + str.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash);
};

// SVG ids may not contain arbitrary characters (clipPath references break).
export const sanitizeId = (value) => String(value).replace(/[^a-zA-Z0-9_-]/g, "_");

// A rectangle with only its top two corners rounded, for a header band that has
// to sit flush inside a rounded card.
export const topRoundedRectPath = (w, h, r) => {
    const x = -w / 2, y = -h / 2;
    return `M${x},${y + r}`
         + `a${r},${r} 0 0 1 ${r},${-r}`
         + `h${w - 2 * r}`
         + `a${r},${r} 0 0 1 ${r},${r}`
         + `v${h - r}`
         + `h${-w}`
         + `Z`;
};

// --- Contrast -------------------------------------------------------------
//
// White on the raw stance colour is not readable. Measured against the actual
// diverging scale, white never clears 4.38:1 anywhere on it and sits at 2.56:1
// at the neutral midpoint - below even the 3:1 allowed for large text - and a
// third of the claims land in that pale middle.
//
// So the header takes a darkened derivative instead: same hue, lightness walked
// down until it clears the ratio. Green still reads green and red still reads
// red, they are simply deep enough to carry white type.

const srgbToLinear = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
};

export const relativeLuminance = ({ r, g, b }) =>
    0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);

export const contrastRatio = (lumA, lumB) =>
    (Math.max(lumA, lumB) + 0.05) / (Math.min(lumA, lumB) + 0.05);
