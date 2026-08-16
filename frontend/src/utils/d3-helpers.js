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
