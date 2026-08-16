import * as d3 from "d3";

export class LayoutEngine {
    constructor(width, height) {
        this.width = width;
        this.height = height;
        this.graphCenterY = -height * 0.1;
    }

    updateDimensions(width, height) {
        this.width = width;
        this.height = height;
        this.graphCenterY = -height * 0.1;
    }

    // --- Topics (landing) Layout ---
    //
    // Flat-top hexagons on a true hex grid: one in the centre, four on the
    // diagonal neighbour cells, so all five edges meet exactly.
    //
    // Tessellation forces a uniform hexagon size, so on this screen node size
    // no longer encodes paper count - the count is in the label instead. Size
    // still encodes literature volume on the claims screen, where the range is
    // three orders of magnitude and actually worth seeing.

    static TOPIC_HEX_R = 190;

    applyTopicsLayout(nodes, sim) {
        const R = LayoutEngine.TOPIC_HEX_R;
        // Flat-top hex neighbours sit at 30/150/210/330 degrees, sqrt(3)*R away.
        const step = Math.sqrt(3) * R;
        const dx = step * Math.cos(Math.PI / 6);   // 1.5 * R
        const dy = step * Math.sin(Math.PI / 6);   // 0.866 * R
        const cells = [
            { x: 0, y: 0 },
            { x: -dx, y: -dy }, { x: dx, y: -dy },
            { x: -dx, y: dy }, { x: dx, y: dy },
        ];

        // Biggest topic takes the centre cell; nodes arrive sorted by volume.
        nodes.forEach((n, i) => {
            const cell = cells[i % cells.length];
            n.hexR = R;
            n.fx = cell.x;
            n.fy = cell.y + this.graphCenterY;
            n.x = n.fx;
            n.y = n.fy;
            n.vx = 0;
            n.vy = 0;
        });

        // Positions are fixed - no forces, or the hexagons would drift apart.
        sim.force("center", null).force("x", null).force("y", null)
            .force("charge", null).force("collide", null).force("link", null);

        return sim;
    }

    // --- Claim View Layout ---
    //
    // A scatter plot on two independent axes:
    //
    //   X = netSupport     how true does the evidence say this is
    //                      (refuted left, contested centre, supported right)
    //   Y = evidenceQuality how good the studies are
    //                      (meta-analyses and RCTs top, cross-sectional bottom)
    //
    // Size stays on paper count, so nothing is encoded twice. The quadrants
    // read: top-right "solid and supported", bottom-right "supported but on
    // weak studies", top-left "solidly refuted", centre "genuinely contested".
    //
    // Claims with no evidence have neither coordinate, so they sit on a
    // labelled shelf below the plot rather than piling up at the origin.

    applyClaimsLayout(nodes, sim) {
        const assessed = nodes.filter(n => n.hasEvidence);
        const unassessed = nodes.filter(n => !n.hasEvidence);

        const plotW = Math.min(this.width * 0.66, 1250);
        const plotH = 560;
        const xScale = d3.scaleLinear().domain([-1, 1]).range([-plotW / 2, plotW / 2]);
        const yScale = d3.scaleLinear().domain([0, 1]).range([plotH / 2, -plotH / 2]);

        const plotCY = this.graphCenterY - (unassessed.length ? 200 : 0);

        assessed.forEach(n => {
            n._targetX = xScale(n.netSupport ?? 0);
            n._targetY = plotCY + yScale(n.evidenceQuality ?? 0);
            n._inPlot = true;
        });

        // Shelf: a plain grid ordered by literature volume, biggest first, so
        // the most-published unexplored questions read first.
        let shelfTop = null;
        if (unassessed.length) {
            const perRow = Math.max(3, Math.ceil(Math.sqrt(unassessed.length * 1.7)));
            const colStep = Math.min(plotW / (perRow - 1 || 1), 330);
            const rowStep = 205;
            shelfTop = plotCY + plotH / 2 + 300;

            [...unassessed]
                .sort((a, b) => (b.openAlexCount || 0) - (a.openAlexCount || 0))
                .forEach((n, i) => {
                    const row = Math.floor(i / perRow);
                    const col = i % perRow;
                    const rowCount = Math.min(perRow, unassessed.length - row * perRow);
                    n._targetX = (col - (rowCount - 1) / 2) * colStep;
                    n._targetY = shelfTop + row * rowStep;
                    n._inPlot = false;
                });
        }

        // Geometry the Graph needs to draw axes and the shelf divider.
        this.claimsFrame = {
            plotCX: 0, plotCY, plotW, plotH, shelfTop,
            xScale, yScale, hasPlot: assessed.length > 0,
        };

        nodes.forEach(n => {
            n.x = n._targetX;
            n.y = n._targetY;
            n.fx = null;
            n.fy = null;
        });

        sim.force("center", null)
            .force("link", null)
            .force("x", d3.forceX(d => d._targetX).strength(0.9))
            .force("y", d3.forceY(d => d._targetY).strength(d => d._inPlot ? 0.9 : 0.7))
            .force("charge", d3.forceManyBody().strength(d => -50 - (d.val || 20)))
            .force("collide", d3.forceCollide().radius(d => (d.val || 20) + 22).iterations(6));

        return sim;
    }

    // --- Evidence View Layout ---
    //
    // A timeline. X is publication year, left to right. Supporting papers sit
    // above the axis, refuting below, neutral on it. Reading left to right
    // shows whether a claim settled over time or is still being argued, and
    // spreads the papers along an axis that actually means something.
    //
    // Distance from the axis encodes citation impact, so the papers that moved
    // the field sit furthest out and are easiest to spot.

    applyEvidenceLayout(nodes, edges, sim) {
        const years = nodes.map(n => n.year).filter(y => y && y > 1900);
        const minYear = years.length ? Math.min(...years) : 1990;
        const maxYear = years.length ? Math.max(...years) : 2025;

        const plotW = Math.min(Math.max(this.width * 0.82, 900), 2200);
        const xScale = d3.scaleLinear()
            .domain([minYear, maxYear === minYear ? minYear + 1 : maxYear])
            .range([-plotW / 2, plotW / 2]);

        const maxCites = d3.max(nodes, n => n.citationCount || 0) || 1;
        const citeScale = d3.scaleSqrt().domain([0, maxCites]).range([0, 300]).clamp(true);

        const axisY = this.graphCenterY;
        const stanceSign = { supports: -1, refutes: 1, neutral: 0 };  // SVG y grows downward

        // Papers published in the same year need vertical separation or they
        // stack into a single column; bucket by year and fan within the bucket.
        const buckets = new Map();

        nodes.forEach(n => {
            const year = (n.year && n.year > 1900) ? n.year : minYear;
            const sign = stanceSign[n.stance] ?? 0;
            const key = `${year}|${n.stance}`;
            const index = buckets.get(key) || 0;
            buckets.set(key, index + 1);

            n._targetX = xScale(year) + (index % 3 - 1) * 26;

            if (sign === 0) {
                // Neutral papers hug the axis, alternating side to side.
                n._targetY = axisY + (index % 2 === 0 ? -1 : 1) * (26 + index * 5);
            } else {
                const impact = citeScale(n.citationCount || 0);
                n._targetY = axisY + sign * (90 + impact + index * 34);
            }

            n.x = n._targetX;
            n.y = n._targetY;
            n.fx = null;
            n.fy = null;
        });

        this.evidenceFrame = { minYear, maxYear, plotW, axisY, xScale };

        sim.force("center", null)
            .force("link", d3.forceLink(edges).id(d => d.id).strength(0))
            .force("x", d3.forceX(d => d._targetX).strength(0.95))
            .force("y", d3.forceY(d => d._targetY).strength(0.5))
            .force("charge", d3.forceManyBody().strength(-90))
            .force("collide", d3.forceCollide().radius(d => (d._w ? d._w / 2 + 6 : 50)).iterations(6));

        return sim;
    }

}
