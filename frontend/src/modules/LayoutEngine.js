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
    // Flat-top hexagons on a true hex grid, filled from the centre outwards in
    // rings, so all shared edges meet exactly however many topics there are.
    //
    // This used to be five hand-placed cells. Splitting the five broad topics
    // into fourteen specific ones - allergens and first foods and milk are
    // separate decisions, made at separate moments - meant the grid had to be
    // generated rather than enumerated.
    //
    // Tessellation forces a uniform hexagon size, so on this screen node size
    // no longer encodes paper count - the count is in the label instead. Size
    // still encodes literature volume on the claims screen, where the range is
    // three orders of magnitude and actually worth seeing.

    static TOPIC_HEX_R = 150;

    /**
     * Hexagon centres on a true hex grid, arranged as offset columns.
     *
     * For this orientation - vertices left and right, so columns interlock -
     * neighbours sit at (+-1.5R, +-0.866R) and (0, +-sqrt(3)R). Stepping one
     * column right and half a row down therefore lands exactly on a shared
     * edge, which is what makes the block tessellate.
     *
     * Column count is chosen to match the canvas rather than fixed, because a
     * ring-filled cluster of fourteen comes out markedly taller than it is wide
     * and wastes a landscape screen.
     */
    static hexCells(count, R, aspect = 1.7) {
        const colStep = 1.5 * R;
        const rowStep = Math.sqrt(3) * R;

        // Pick the column count whose resulting block best matches the canvas.
        let cols = 1, best = Infinity;
        for (let c = 1; c <= count; c++) {
            const r = Math.ceil(count / c);
            const w = (c - 1) * colStep + 2 * R;
            const h = (r - 1) * rowStep + rowStep;
            const score = Math.abs((w / h) - aspect);
            if (score < best) { best = score; cols = c; }
        }
        const rows = Math.ceil(count / cols);

        const cells = [];
        for (let i = 0; i < count; i++) {
            const col = i % cols;
            const row = Math.floor(i / cols);
            // Short final row is centred rather than left-aligned.
            const inRow = Math.min(cols, count - row * cols);
            const rowOffset = (cols - inRow) / 2;
            cells.push({
                x: (col + rowOffset - (cols - 1) / 2) * colStep,
                y: (row - (rows - 1) / 2) * rowStep
                   + ((col + rowOffset) % 2 ? rowStep / 2 : 0),
            });
        }
        return cells;
    }

    applyTopicsLayout(nodes, sim) {
        const R = LayoutEngine.TOPIC_HEX_R;
        const aspect = this.height ? (this.width / this.height) * 0.95 : 1.7;
        const cells = LayoutEngine.hexCells(nodes.length, R, aspect);

        // Biggest topic takes the centre cell; nodes arrive sorted by volume.
        nodes.forEach((n, i) => {
            const cell = cells[i];
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
            // Generous padding: each node's caption hangs below it, so leaving
            // only the circle's own radius guarantees text-on-text collisions
            // that the label pass then has to unpick.
            .force("collide", d3.forceCollide().radius(d => (d.val || 20) + 40).iterations(8));

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

        // Papers that take no position on the claim are not evidence for or
        // against it, so they have no honest place on either axis - parked on
        // the midline they read as "contested" and crowd the one part of the
        // plot where a genuinely contested claim needs room. But they are not
        // noise either: they are here because the papers that DO test the claim
        // cite them, so they are the shared groundwork the argument stands on.
        //
        // They get a labelled box outside the plot, up and to the left, and the
        // citation ribbons still run from the box into the papers that lean on
        // it - which is the useful thing about them made visible.
        const decisive = papers.filter(n => n.stance !== 'neutral');
        const context = papers.filter(n => n.stance === 'neutral');

        let neutralBox = null;
        if (context.length) {
            const cardW = 132, cardH = 46, pad = 14;
            const cols = context.length > 4 ? 2 : 1;
            const rows = Math.ceil(context.length / cols);
            const boxW = cols * cardW + (cols + 1) * pad;
            const boxH = rows * cardH + (rows + 1) * pad + 20;   // +20 for the caption
            const right = -plotW / 2 - 64;                        // clear of the plot edge
            const top = plotCY - plotH / 2;                       // aligned with the plot top

            // The box must not reach the midline: the axis crosshair and its
            // "WEAKER" label live there, and a panel painted over them would
            // hide the orientation the whole plot depends on.
            neutralBox = {
                x: right - boxW, y: top, w: boxW, h: boxH,
                count: context.length,
                // Only the best-connected context papers are shown; say so
                // rather than implying this is all of them.
                total: anchor && anchor.neutral != null ? anchor.neutral : context.length,
            };

            context
                .sort((a, b) => (b.localCitations || 0) - (a.localCitations || 0))
                .forEach((n, i) => {
                    const col = i % cols;
                    const row = Math.floor(i / cols);
                    n._targetX = neutralBox.x + pad + col * (cardW + pad) + cardW / 2;
                    n._targetY = neutralBox.y + 20 + pad + row * (cardH + pad) + cardH / 2;
                    // Pinned: the simulation must not drag context back over the
                    // plot, and a fixed node still pushes papers out of the box.
                    n.x = n.fx = n._targetX;
                    n.y = n.fy = n._targetY;
                    n._inBox = true;
                    n._dim = false;
                });
        }

        decisive.forEach((n, i) => {
            const sign = n.stance === 'mixed'
                ? mixedSign
                : (LayoutEngine.STANCE_SIGN[n.stance] ?? 0);
            const certainty = (n.confidence ?? 50) / 100;
            const spread = ((i * 2654435761) % 1000) / 1000 - 0.5;   // stable hash

            n._targetX = xValueOf(n) + spread * jitterSpan * 2;

            // A mixed paper under the balanced reading has no net direction, so
            // it sits on the midline - which for it is the honest answer, not an
            // absence of one.
            n._targetY = plotCY + yScale(sign * certainty);
            n._dim = false;
            n._inBox = false;

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
            xAxisMode, reading, yScale, neutralBox,
            xScale: useYear ? yearScale : strengthScale,
            strengthLevels: Object.entries(LayoutEngine.STRENGTH_X)
                .map(([key, v]) => ({ key, x: strengthScale(v) })),
        };

        sim.force("center", null)
            .force("link", d3.forceLink(safeEdges).id(d => d.id).strength(0))
            .force("x", d3.forceX(d => d._targetX).strength(d => d._inBox ? 0 : 0.9))
            .force("y", d3.forceY(d => d._targetY).strength(d => d._inBox ? 0 : 0.85))
            .force("charge", d3.forceManyBody().strength(-60))
            .force("collide", d3.forceCollide()
                .radius(d => d.type === 'claim-anchor'
                    ? (d.val || 46) + 18
                    : (d._w ? d._w / 2 + 6 : 50))
                .iterations(6));

        return sim;
    }

}
