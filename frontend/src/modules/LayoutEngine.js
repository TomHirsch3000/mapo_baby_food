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
    //   Y = netSupport     how true does the evidence say this is
    //                      (supported top, contested middle, refuted bottom)
    //   X = evidenceQuality how good the studies are
    //                      (cross-sectional left, meta-analyses and RCTs right)
    //
    // Stance owns the VERTICAL on every screen, claims and evidence alike, so
    // "higher means more supported" never changes meaning as you drill in.
    //
    // Size stays on paper count, so nothing is encoded twice. The quadrants
    // read: top-right "solid and supported", top-left "supported but on weak
    // studies", bottom-right "solidly refuted", middle "genuinely contested".
    //
    // Claims with no evidence have neither coordinate, so they sit on a
    // labelled shelf below the plot rather than piling up at the origin.

    applyClaimsLayout(nodes, sim, reading = 'balanced') {
        const assessed = nodes.filter(n => n.hasEvidence);
        const unassessed = nodes.filter(n => !n.hasEvidence);

        const plotW = Math.min(this.width * 0.66, 1250);
        const plotH = 560;
        const xScale = d3.scaleLinear().domain([0, 1]).range([-plotW / 2, plotW / 2]);
        const yScale = d3.scaleLinear().domain([-1, 1]).range([plotH / 2, -plotH / 2]);

        const plotCY = this.graphCenterY - (unassessed.length ? 200 : 0);

        assessed.forEach(n => {
            n._targetX = xScale(n.evidenceQuality ?? 0);
            n._targetY = plotCY + yScale(LayoutEngine.netFor(n, reading));
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
            xScale, yScale, reading, hasPlot: assessed.length > 0,
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
    // The same scatter as the claims screen, one level down, so the axes never
    // change meaning between levels:
    //
    //   Y = stance x confidence   supported top, refuted bottom
    //   X = evidence strength     weak studies left, strong right
    //                             (toggleable to publication year)
    //
    // Size still encodes citations, so nothing is doubled up.
    //
    // Y is signed confidence rather than bare stance: a 95%-sure refutation
    // belongs at the bottom edge, a hesitant 60% one belongs near the middle.
    // Placing all refutations on one line would throw away the evaluator's
    // certainty, which is the only continuous signal a single paper carries.

    // Normalised from the backend's STRENGTH_WEIGHT (strong 3, moderate 2,
    // mixed 1.5, limited 1) via (w - 1) / 2 -- the identical transform
    // build_claims_data.py uses for a claim's evidenceQuality. That keeps the
    // claim anchor's X honest: it is exactly the mean of its papers' X.
    static STRENGTH_X = { strong: 1.0, moderate: 0.5, mixed: 0.25, limited: 0.0 };

    static STANCE_SIGN = { supports: 1, refutes: -1, neutral: 0, mixed: 0 };

    /**
     * How each interpretation reads a paper that cuts both ways.
     *
     * A mixed paper genuinely has no single position, so rather than pick one
     * for the reader we ship all three readings and let them switch:
     *
     *   conservative  the claim is technically supported, caveats aside  -> +1
     *   balanced      a two-sided paper takes no side                    ->  0
     *   liberal       the caveats count as much as the headline          -> -1
     *
     * Watching a claim's papers swing as you toggle is the point: if the picture
     * only holds under one reading, that is worth seeing.
     */
    static MIXED_SIGN = { conservative: 1, balanced: 0, liberal: -1 };

    /** A claim's net support under one reading, falling back to the balanced one. */
    static netFor(node, reading) {
        const byReading = node && node.netSupportByReading;
        const v = byReading ? byReading[reading] : undefined;
        return v ?? node?.netSupport ?? 0;
    }

    applyEvidenceLayout(nodes, edges, sim, xAxisMode = 'strength', reading = 'balanced') {
        const papers = nodes.filter(n => n.type !== 'claim-anchor');
        const anchor = nodes.find(n => n.type === 'claim-anchor');

        // d3.forceLink throws on any edge naming a node it cannot find, which
        // takes the whole view down rather than dropping one line. Callers
        // filter their own edges, but this is the last line of defence.
        const present = new Set(nodes.map(n => n.id));
        const safeEdges = (edges || []).filter(
            e => present.has(e.source.id ?? e.source) && present.has(e.target.id ?? e.target));

        const plotW = Math.min(Math.max(this.width * 0.78, 900), 2000);
        const plotH = 680;
        const plotCY = this.graphCenterY;
        const useYear = xAxisMode === 'year';

        const years = papers.map(n => n.year).filter(y => y && y > 1900);
        const minYear = years.length ? Math.min(...years) : 1990;
        const maxYearRaw = years.length ? Math.max(...years) : 2025;
        const maxYear = maxYearRaw === minYear ? minYear + 1 : maxYearRaw;

        const yearScale = d3.scaleLinear()
            .domain([minYear, maxYear]).range([-plotW / 2, plotW / 2]);
        const strengthScale = d3.scaleLinear()
            .domain([0, 1]).range([-plotW / 2, plotW / 2]);
        const yScale = d3.scaleLinear()
            .domain([-1, 1]).range([plotH / 2, -plotH / 2]);

        const xValueOf = (n) => useYear
            ? yearScale((n.year && n.year > 1900) ? n.year : minYear)
            : strengthScale(LayoutEngine.STRENGTH_X[n.evidenceStrength] ?? 0.25);

        // Strength has only four levels, so in strength mode every paper would
        // land on one of four hairlines. A deterministic per-node offset gives
        // each band width to breathe in; collision does the rest.
        const jitterSpan = useYear ? 30 : plotW * 0.05;

        const mixedSign = LayoutEngine.MIXED_SIGN[reading] ?? 0;

        papers.forEach((n, i) => {
            const sign = n.stance === 'mixed'
                ? mixedSign
                : (LayoutEngine.STANCE_SIGN[n.stance] ?? 0);
            const certainty = (n.confidence ?? 50) / 100;
            const spread = ((i * 2654435761) % 1000) / 1000 - 0.5;   // stable hash

            n._targetX = xValueOf(n) + spread * jitterSpan * 2;

            if (sign === 0) {
                // No net direction to plot - either the paper took no position
                // at all, or this reading declines to pick a side for it. Either
                // way it sits on the midline rather than implying "contested".
                n._targetY = plotCY + spread * 46;
                n._dim = n.stance !== 'mixed';   // mixed stays legible, it matters
            } else {
                n._targetY = plotCY + yScale(sign * certainty);
                n._dim = false;
            }

            n.x = n._targetX;
            n.y = n._targetY;
            n.fx = null;
            n.fy = null;
        });

        // The claim itself, pinned at the coordinates the claims screen gave
        // it -- NOT at the centroid of the dots. The two differ, because
        // netSupport weights each paper by strength x log(citations) x
        // confidence and drops neutrals entirely. Pinning to the authoritative
        // value is what makes the node hold still when you drill into it.
        if (anchor) {
            anchor._targetX = useYear
                ? yearScale(anchor.medianYear ?? minYear)
                : strengthScale(anchor.evidenceQuality ?? 0);
            // The claim moves with the reading too, using the netSupport the
            // backend computed for that same interpretation.
            anchor._targetY = plotCY + yScale(LayoutEngine.netFor(anchor, reading));
            anchor.x = anchor.fx = anchor._targetX;
            anchor.y = anchor.fy = anchor._targetY;
        }

        this.evidenceFrame = {
            minYear, maxYear, plotW, plotH, plotCY,
            xAxisMode, reading, yScale,
            xScale: useYear ? yearScale : strengthScale,
            strengthLevels: Object.entries(LayoutEngine.STRENGTH_X)
                .map(([key, v]) => ({ key, x: strengthScale(v) })),
        };

        sim.force("center", null)
            .force("link", d3.forceLink(safeEdges).id(d => d.id).strength(0))
            .force("x", d3.forceX(d => d._targetX).strength(0.9))
            .force("y", d3.forceY(d => d._targetY).strength(d => d._dim ? 0.5 : 0.85))
            .force("charge", d3.forceManyBody().strength(-60))
            .force("collide", d3.forceCollide()
                .radius(d => d.type === 'claim-anchor'
                    ? (d.val || 46) + 18
                    : (d._w ? d._w / 2 + 6 : 50))
                .iterations(6));

        return sim;
    }

}
