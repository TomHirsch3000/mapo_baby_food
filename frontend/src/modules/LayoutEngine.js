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

    // Fourteen topics in one undifferentiated honeycomb read as fourteen equal
    // decisions. They are not: a parent arrives already thinking "feeding" or
    // "sleep", so the grid should answer that question before it answers any
    // other. Topics are grouped into a handful of themes, each tessellating on
    // its own and separated by a gap wide enough to read as a break.
    //
    // A topic missing from this table is not dropped - it collects in a
    // trailing group - so adding a topic to claims.py cannot silently remove it
    // from the landing page.
    static TOPIC_THEMES = [
        { name: "Eating",              topics: ["milk", "solids", "allergies", "nutrients", "food_safety"] },
        { name: "Sleeping",            topics: ["safe_sleep", "sleep_patterns", "settling"] },
        { name: "Playing & Learning",  topics: ["language", "play", "motor", "active_play"] },
        { name: "Screens",             topics: ["screen_effects", "screen_time"] },
    ];

    // All × R. The gaps only have to beat the zero spacing of a shared edge to
    // read as a break, and every pixel spent on them is a pixel the zoom-to-fit
    // takes back out of the label type, so they stay tight.
    static CLUSTER_GAP_X = 0.80;
    static CLUSTER_GAP_Y = 0.70;
    static CLUSTER_HEAD  = 0.42;   // vertical room for the theme heading

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
            // Short final row is nudged toward the middle - but only by WHOLE
            // columns. Half a column looks tidier and does not tessellate: the
            // interlock comes from the parity test below, and a fractional
            // offset makes it fire the same way for adjacent cells, dropping
            // them onto one row 1.5R apart when a shared edge needs sqrt(3)R.
            // A five-cell block overlapped exactly this way.
            const inRow = Math.min(cols, count - row * cols);
            const rowOffset = Math.floor((cols - inRow) / 2);
            cells.push({
                x: (col + rowOffset - (cols - 1) / 2) * colStep,
                y: (row - (rows - 1) / 2) * rowStep
                   + ((col + rowOffset) % 2 ? rowStep / 2 : 0),
            });
        }
        return cells;
    }

    /**
     * Pack the theme blocks into rows and centre the result.
     *
     * Rows are contiguous chunks of the block list chosen to even out width, so
     * themes stay in their declared order and the page does not reshuffle
     * between renders.
     */
    static packRows(blocks, rowCount, gapX, gapY, head) {
        const target = blocks.reduce((s, b) => s + b.w, 0) / rowCount;
        const rows = [];
        let cur = [], acc = 0;
        blocks.forEach((b, i) => {
            cur.push(b);
            acc += b.w;
            const remaining = blocks.length - i - 1;
            const rowsLeft = rowCount - rows.length - 1;
            // Break only if enough blocks remain to fill the rows still to come.
            if (rowsLeft > 0 && acc >= target && remaining >= rowsLeft) {
                rows.push(cur);
                cur = [];
                acc = 0;
            }
        });
        if (cur.length) rows.push(cur);

        const rowW = rows.map(r => r.reduce((s, b) => s + b.w, 0) + gapX * (r.length - 1));
        const rowH = rows.map(r => Math.max(...r.map(b => b.h)) + head);
        const W = Math.max(...rowW);
        const H = rowH.reduce((s, h) => s + h, 0) + gapY * (rows.length - 1);

        const placements = [];
        let y = -H / 2;
        rows.forEach((r, ri) => {
            let x = -rowW[ri] / 2;
            r.forEach(b => {
                placements.push({ block: b, x, top: y, contentTop: y + head });
                x += b.w + gapX;
            });
            y += rowH[ri] + gapY;
        });
        return { placements, w: W, h: H };
    }

    applyTopicsLayout(nodes, sim) {
        const R = LayoutEngine.TOPIC_HEX_R;
        const gapX = R * LayoutEngine.CLUSTER_GAP_X;
        const gapY = R * LayoutEngine.CLUSTER_GAP_Y;
        const head = R * LayoutEngine.CLUSTER_HEAD;

        // The view mounts before the data arrives, so an empty first pass is
        // normal, not a fault.
        this.topicClusters = [];
        if (!nodes.length) return sim;

        // Group by theme. Anything not named in the table still gets a home.
        const byId = new Map(nodes.map(n => [n.id, n]));
        const claimed = new Set();
        const groups = [];
        for (const theme of LayoutEngine.TOPIC_THEMES) {
            const members = theme.topics.map(id => byId.get(id)).filter(Boolean);
            members.forEach(m => claimed.add(m.id));
            if (members.length) groups.push({ name: theme.name, members });
        }
        const rest = nodes.filter(n => !claimed.has(n.id));
        if (rest.length) groups.push({ name: "More", members: rest });

        // Each theme tessellates on its own, squarish so no one block dominates.
        const blocks = groups.map(g => {
            const cells = LayoutEngine.hexCells(g.members.length, R, 1.15);
            const minX = Math.min(...cells.map(c => c.x)) - R;
            const maxX = Math.max(...cells.map(c => c.x)) + R;
            const minY = Math.min(...cells.map(c => c.y)) - R * Math.sqrt(3) / 2;
            const maxY = Math.max(...cells.map(c => c.y)) + R * Math.sqrt(3) / 2;
            return { ...g, cells, minX, minY, w: maxX - minX, h: maxY - minY };
        });

        // Try every row count and keep whichever one the view can zoom in on
        // hardest.
        //
        // Scoring this by aspect-similarity - the obvious choice, and what
        // hexCells does one level down - picks the wrong arrangement here. On a
        // 1600x900 canvas it preferred two rows (aspect 0.88 against the
        // canvas's 1.69) over one (3.3), even though one row fits at 0.65 and
        // two only at 0.55. Aspect is a proxy; the scale is the thing itself,
        // and on this screen the scale IS the legibility of the labels.
        const pad = R * 0.4 + 40;              // must match the view's fit padding
        let best = null;
        for (let rowCount = 1; rowCount <= blocks.length; rowCount++) {
            const packed = LayoutEngine.packRows(blocks, rowCount, gapX, gapY, head);
            const scale = this.width && this.height
                ? Math.min(this.width / (packed.w + pad), this.height / (packed.h + pad), 1.4)
                : 1;
            if (!best || scale > best.scale) best = { ...packed, scale };
        }

        // Headings are drawn by the view, which has no idea where the blocks
        // ended up, so hand it the boxes rather than make it recompute them.
        this.topicClusters = best.placements.map(p => ({
            name: p.block.name,
            x: p.x,
            y: p.top + this.graphCenterY,
            w: p.block.w,
            h: p.block.h + head,
            labelX: p.x + p.block.w / 2,
            labelY: p.top + this.graphCenterY + head * 0.60,
        }));

        best.placements.forEach(p => {
            const b = p.block;
            const ox = p.x - b.minX;
            const oy = p.contentTop - b.minY;
            b.members.forEach((n, i) => {
                n.hexR = R;
                n.fx = b.cells[i].x + ox;
                n.fy = b.cells[i].y + oy + this.graphCenterY;
                n.x = n.fx;
                n.y = n.fy;
                n.vx = 0;
                n.vy = 0;
            });
        });

        // Positions are fixed - no forces, or the hexagons would drift apart.
        sim.force("center", null).force("x", null).force("y", null)
            .force("charge", null).force("collide", null).force("link", null);

        return sim;
    }

    // --- Claim nodes: card or circle ---
    //
    // Flip to "circle" to get the original plot back: circles sized by
    // literature volume with the caption floating underneath. Both paths are
    // live in LayoutEngine and Graph.jsx; this constant is the only switch.
    //
    // The cards exist because the caption was the thing being read and it was
    // the thing that collided - it hung free below a node, over whatever
    // happened to be there. Putting the text in the node makes that collision
    // impossible rather than merely resolved.
    //
    // The trade is real: a uniform card cannot also encode volume by area, so
    // on this screen size stops meaning anything and the count moves to the
    // footer. Position still means exactly what the axes say.
    static CLAIM_NODE_STYLE = "card";

    // Below this the scatter stops being a scatter. A 240px card on a 390px
    // screen leaves room for one and a half of them across, so spreading by
    // evidence quality just walks cards off both sides of the phone.
    static NARROW_W = 768;
    isNarrow() { return this.width > 0 && this.width < LayoutEngine.NARROW_W; }

    // 240 x ~25 characters, from a sweep. Widening used to cost positional
    // fidelity, because a wider card needs more room in a row. With the claim
    // set at 15px in a header band that stopped being true: a wider card wraps
    // to FEWER lines, so it is shorter, and height is what the packing is
    // actually short of. 240 reads better than 192 and displaces fewer cards -
    // 14 across the quality midline against 19, and 3 across the supported
    // line either way. Past ~260 the lines get too long and it reverses.
    static CARD_W = 240;
    static CARD_CHARS_PER_LINE = 25;   // ~15px semibold Inter across CARD_W
    static CARD_LINE_H = 20;
    static CARD_HEAD_PAD = 32;         // padding above and below the claim
    static CARD_FOOT_H = 38;           // the for/against strip under the header

    /**
     * The claim sits in a coloured header; the counts sit in a white strip
     * below it. Both halves are measured here rather than in the view, because
     * the solver has to know the card's real height before anything is drawn.
     */
    static claimCardSize(n) {
        const text = n.claim || n.name || "";
        const lines = Math.max(1, Math.ceil(text.length / LayoutEngine.CARD_CHARS_PER_LINE));
        const headerH = LayoutEngine.CARD_HEAD_PAD + lines * LayoutEngine.CARD_LINE_H;
        return {
            w: LayoutEngine.CARD_W,
            h: headerH + LayoutEngine.CARD_FOOT_H,
            headerH,
        };
    }

    /**
     * Place the cards: as near the axes' answer as possible, never overlapping.
     *
     * A force pair cannot promise this. forceX/forceY pull toward the true
     * position at a fixed strength while a collide force fades with alpha, so
     * the two settle into equilibrium wherever the pull balances the push -
     * which is frequently a few tens of pixels INSIDE an overlap. Tuning the
     * strengths trades one failure for the other: hard enough to always
     * separate is hard enough to fling cards off their real position.
     *
     * So this is solved rather than simulated. Relax toward the target, sweep
     * out every overlap, and finish with a separation-only pass that runs until
     * nothing intersects. Deterministic, and the result is fixed with fx/fy so
     * no later tick can walk it back.
     *
     * Overlaps are resolved along whichever axis needs the least movement, so a
     * card slides sideways when that is the shorter escape - which is what
     * keeps a column of claims at the same support level readable.
     */
    static separateCards(nodes, padding = 16, narrow = false) {
        const overlapOf = (a, b) => {
            const ox = (a._cardW + b._cardW) / 2 + padding - Math.abs(b.x - a.x);
            const oy = (a._cardH + b._cardH) / 2 + padding - Math.abs(b.y - a.y);
            return (ox > 0 && oy > 0) ? { ox, oy } : null;
        };
        // Least-movement is the wrong rule here. A card is 216 wide and about
        // 110 tall, so the cheaper escape from an overlap is nearly always
        // vertical - and vertical is netSupport, the axis carrying "how true",
        // the one thing a reader takes from this screen. Sliding sideways costs
        // more pixels and spends them on the axis that can afford it.
        // Wide screens push cards sideways to protect netSupport, the axis that
        // carries "how true". A phone has no sideways to give, so it inverts:
        // separate vertically and let the column become an ordering rather than
        // a position. Both are honest; they answer different questions.
        const VERTICAL_COST = narrow ? 0.4 : 2;
        const push = (a, b, o) => {
            if (o.ox < o.oy * VERTICAL_COST) {
                const shift = ((b.x - a.x) < 0 ? -1 : 1) * o.ox * 0.5;
                a.x -= shift; b.x += shift;
            } else {
                const shift = ((b.y - a.y) < 0 ? -1 : 1) * o.oy * 0.5;
                a.y -= shift; b.y += shift;
            }
        };

        nodes.forEach(n => { n.x = n._targetX; n.y = n._targetY; });

        // Relax: ease home, then push apart. The pull is deliberately weak - it
        // only has to reclaim ground the separation over-gave.
        for (let it = 0; it < 240; it++) {
            nodes.forEach(n => {
                n.x += (n._targetX - n.x) * 0.06;
                n.y += (n._targetY - n.y) * 0.06;
            });
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    const o = overlapOf(nodes[i], nodes[j]);
                    if (o) push(nodes[i], nodes[j], o);
                }
            }
        }

        // Separation only, to convergence. Without this the last relax step's
        // pull can leave a residual intersection behind.
        for (let sweep = 0; sweep < 400; sweep++) {
            let clean = true;
            for (let i = 0; i < nodes.length; i++) {
                for (let j = i + 1; j < nodes.length; j++) {
                    const o = overlapOf(nodes[i], nodes[j]);
                    if (o) { push(nodes[i], nodes[j], o); clean = false; }
                }
            }
            if (clean) break;
        }

        nodes.forEach(n => { n.fx = n.x; n.fy = n.y; });
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

        // Cards need materially more room than dots. Seven of them is roughly
        // 170,000 px of card against a 700,000 px plot, and they do not spread
        // evenly - netSupport bunches most claims into the supported band - so
        // a plot sized for circles forces the solver to shove cards a long way
        // from the position the axes gave them.
        const isCard = LayoutEngine.CLAIM_NODE_STYLE === "card";
        const narrow = this.isNarrow();
        // On a phone the plot becomes a tall narrow strip, so the cards stack
        // into a column instead of fanning out past both edges. Reading down a
        // column ordered by how-true is a fair use of a phone; a two-axis
        // scatter squeezed into 390px is not.
        const plotW = narrow ? Math.min(this.width * 0.92, 420)
            : (isCard ? Math.min(this.width * 0.84, 1560) : Math.min(this.width * 0.66, 1250));
        const plotH = narrow ? 1180 : (isCard ? 660 : 560);
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

        if (LayoutEngine.CLAIM_NODE_STYLE === "card") {
            nodes.forEach(n => {
                const { w, h, headerH } = LayoutEngine.claimCardSize(n);
                n._cardW = w;
                n._cardH = h;
                n._cardHeaderH = headerH;
            });
            LayoutEngine.separateCards(nodes, 16, narrow);
            // Solved, not simulated - so every force is off, exactly as on the
            // topics screen. A live force here would only undo the solution.
            sim.force("center", null).force("link", null).force("charge", null)
                .force("x", null).force("y", null).force("collide", null);
            return sim;
        }

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

    // --- Evidence view switches ---
    //
    // "context-only"  citation ribbons only where one end sits in the context
    //                 box at the side. Those are the useful ones: they show the
    //                 groundwork the argument leans on.
    // "all"           every ribbon, including paper-to-paper. This is the
    //                 original look. It is genuinely handsome and genuinely
    //                 unreadable - a hundred papers is thousands of crossings,
    //                 and none of them say anything about whether a paper is
    //                 right or relevant, which is what this screen is for.
    // "none"          no ribbons.
    static EVIDENCE_EDGE_MODE = "context-only";

    // A hairline from each paper to the claim it is evidence about. With the
    // paper-to-paper ribbons gone this is the only thing left carrying "these
    // all belong to that", so it is drawn faint enough to read as texture.
    static EVIDENCE_SPOKES = true;

    // The claim wears the same card here as it does one level up. It arrives by
    // being clicked, so it has to be recognisably the same object.
    static ANCHOR_CARD_W = 288;
    static ANCHOR_CHARS_PER_LINE = 30;

    static anchorCardSize(n) {
        const text = n.claim || n.name || "";
        const lines = Math.max(1, Math.ceil(text.length / LayoutEngine.ANCHOR_CHARS_PER_LINE));
        const headerH = LayoutEngine.CARD_HEAD_PAD + lines * LayoutEngine.CARD_LINE_H;
        return {
            w: LayoutEngine.ANCHOR_CARD_W,
            h: headerH + LayoutEngine.CARD_FOOT_H,
            headerH,
        };
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

    // X comes from designRank, computed in backend/design.py: the paper's study
    // design placed on an evidence hierarchy, 0..1. It replaced the model's own
    // strong/moderate/limited label, which mixed design with sample size - so a
    // modest RCT scored "moderate" and landed dead centre - and whose resulting
    // order was not a hierarchy at all: position papers came out above
    // meta-analyses, and an RCT spelled out in full ranked below a case report.
    //
    // A claim's evidenceQuality is the mean of its papers' designRank, so the
    // anchor's X is still exactly the centroid of the cloud beneath it.
    static DESIGN_X_FALLBACK = 0.30;   // unclassified; matches design.py

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
            : strengthScale(n.designRank ?? LayoutEngine.DESIGN_X_FALLBACK);

        // Designs are discrete, so papers still stack into columns. A
        // deterministic per-node offset gives each band width to breathe in;
        // collision does the rest.
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
            const card = LayoutEngine.anchorCardSize(anchor);
            anchor._cardW = card.w;
            anchor._cardH = card.h;
            anchor._cardHeaderH = card.headerH;
            anchor._targetX = useYear
                ? yearScale(anchor.medianYear ?? minYear)
                : strengthScale(anchor.evidenceQuality ?? 0);   // mean designRank
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
            // A readable subset of the ladder - all nineteen rungs would collide.
            strengthLevels: [
                ['case report', 0.20],
                ['cross-sectional', 0.30],
                ['case-control', 0.40],
                ['cohort', 0.50],
                ['trial', 0.72],
                ['randomised', 0.88],
                ['meta-analysis', 1.00],
            ].map(([key, v]) => ({ key, x: strengthScale(v) })),
        };

        sim.force("center", null)
            .force("link", d3.forceLink(safeEdges).id(d => d.id).strength(0))
            .force("x", d3.forceX(d => d._targetX).strength(d => d._inBox ? 0 : 0.9))
            .force("y", d3.forceY(d => d._targetY).strength(d => d._inBox ? 0 : 0.85))
            .force("charge", d3.forceManyBody().strength(-60))
            .force("collide", d3.forceCollide()
                .radius(d => d.type === 'claim-anchor'
                    // The anchor is a rectangle now. forceCollide only speaks
                    // radii, so use the half-diagonal - it over-reserves at the
                    // corners, which is the right way to be wrong for the one
                    // node everything else has to stay off.
                    ? Math.hypot(d._cardW || 240, d._cardH || 120) / 2 + 14
                    : (d._w ? d._w / 2 + 6 : 50))
                .iterations(6));

        return sim;
    }

}
