import React, { useEffect, useRef, useMemo, useState } from 'react';
import * as d3 from 'd3';
import { roundedHexagonPath, sanitizeId, topRoundedRectPath,
         relativeLuminance, contrastRatio } from '../utils/d3-helpers';
import { LayoutEngine } from '../modules/LayoutEngine';

// Evidence palette, shared by claim nodes and evidence cards so a green node in
// the claims view and a green card in the evidence view mean the same thing.
export const STANCE_COLORS = {
    supports: '#2e9e5b',
    refutes: '#d64545',
    // Mixed is deliberately NOT on the red-green axis. A paper that cuts both
    // ways should not be readable as a washed-out version of either verdict.
    mixed: '#b8860b',
    neutral: '#94a3b8',
    unevaluated: '#cbd5e1',
};

/**
 * Darken a stance colour until white type on it clears a contrast ratio.
 *
 * WCAG AA wants 4.5:1 for body text. Measured against this very scale, white
 * never clears 4.38:1 anywhere on it and sits at 2.56:1 at the neutral
 * midpoint - under even the 3:1 allowed for large text - and a third of the
 * claims land in that pale middle. Walking lightness down in HSL keeps the hue,
 * so the verdict still reads as green or red; it just stops being a tint that
 * swallows white text. Colour is never the only channel anyway - every card
 * spells out its counts underneath.
 */
const onColourTextCache = new Map();
const readableOnWhiteText = (colour, target = 4.5) => {
    const key = `${colour}|${target}`;
    if (onColourTextCache.has(key)) return onColourTextCache.get(key);
    const whiteLum = relativeLuminance({ r: 255, g: 255, b: 255 });
    const hsl = d3.hsl(colour);
    let out = d3.rgb(colour);
    for (let i = 0; i < 60; i++) {
        if (contrastRatio(relativeLuminance(out), whiteLum) >= target) break;
        hsl.l = Math.max(0, hsl.l - 0.015);
        out = d3.rgb(hsl);
    }
    const hex = out.formatHex();
    onColourTextCache.set(key, hex);
    return hex;
};

/**
 * How dark a weak paper's text is allowed to be, by design rank.
 *
 * Fading the text with opacity is not available: the darkened stance colours
 * clear 4.5:1 with nothing to spare, so any transparency puts 12.5px type under
 * the AA floor. Ramping the CONTRAST TARGET instead gets the same gradient
 * legitimately - the weakest paper sits exactly on 4.5:1, the strongest is
 * pushed to 10:1 and reads as near-black. Nothing on the screen is ever less
 * readable than the standard allows; the strong end is simply much stronger.
 */
const STRENGTH_TEXT = d3.scaleLinear().domain([0, 1]).range([4.5, 10]).clamp(true);

// What a paper's stance is called on its own card. "for"/"against" rather than
// "supports"/"refutes" because the card is only about 100px wide.
const VERDICT_WORD = { supports: 'for', refutes: 'against', mixed: 'mixed', neutral: 'context' };

// The study design, trimmed to fit. The data carries a normalised studyDesign
// and the model's raw studyType, and the raw one runs to phrases like
// "randomized controlled trial" that no small card can hold.
const DESIGN_SHORT = {
    'meta-analysis': 'meta-analysis',
    'randomized controlled trial': 'RCT',
    'randomised controlled trial': 'RCT',
    'rct': 'RCT',
    'clinical trial': 'trial',
    'prospective cohort': 'cohort',
    'cross-sectional': 'cross-sect.',
    'case-control': 'case-control',
    'case-report': 'case report',
    'case report': 'case report',
};
const designLabel = (d) => {
    const raw = String(d.studyDesign || d.studyType || 'other').toLowerCase().trim();
    return DESIGN_SHORT[raw] || (raw.length > 13 ? `${raw.slice(0, 12)}\u2026` : raw);
};

/**
 * How solidly a paper is drawn, from how good its design is.
 *
 * Bound to designRank, NOT to the x coordinate. In strength mode the two are
 * the same thing and it reads as the left-to-right fade it is; in year mode x
 * means date, and fading by it would say "old is weak", which is a different
 * and false claim. This way a meta-analysis stays prominent on both axes.
 *
 * Floored well above zero because the ranks are lumpy: 63 of the 108 papers on
 * a typical claim sit at exactly 0.30, so a fade running to nothing would take
 * two thirds of the screen with it and read as a rendering fault.
 *
 * Only the fill and the border fade. The text does not - see the card render.
 */
const STRENGTH_FILL = d3.scaleLinear().domain([0, 1]).range([0.05, 0.58]).clamp(true);
const STRENGTH_STROKE = d3.scaleLinear().domain([0, 1]).range([0.18, 1]).clamp(true);

const STANCE_DIVERGING = d3.scaleLinear()
    .domain([-1, 0, 1])
    .range([STANCE_COLORS.refutes, STANCE_COLORS.neutral, STANCE_COLORS.supports])
    .interpolate(d3.interpolateRgb)
    .clamp(true);

export const Graph = ({
    nodes,
    edges,
    viewMode,
    layoutMode,
    groupingMode,
    activeGroup,
    selected,
    hovered,
    onNodeClick,
    onNodeHover,
    onBackgroundClick,
    scales,
    isReturning,
    width,
    height,
    onNodeDoubleClick,
    isLoadingDetail,
    evidenceXAxis = 'strength',
    reading = 'balanced'
}) => {
    const svgRef = useRef(null);
    const layoutEngine = useRef(new LayoutEngine(width, height));

    const simulationRef = useRef(null);
    const nodePositionsCache = useRef(new Map());
    const groupPositionsMatch = useRef(new Map());
    const layoutPositionCacheRef = useRef(new Map());
    const isTransitioningView = useRef(false);

    const prevViewMode = useRef(viewMode);
    const prevLayoutMode = useRef(layoutMode);
    const prevSelectedIdRef = useRef(null);
    const edgeRevealTimeoutRef = useRef(null);
    const edgeRevealPendingRef = useRef(false);
    const firstDataRenderRef = useRef(true);

    useEffect(() => {
        layoutEngine.current.updateDimensions(width, height);
    }, [width, height]);

    // Resolve icon href — supports both external URLs and public-relative paths
    const resolveIconHref = (iconPath) => {
        if (!iconPath) return null;
        if (iconPath.startsWith('http://') || iconPath.startsWith('https://')) return iconPath;
        return iconPath;
    };

    useEffect(() => {
        isTransitioningView.current = false;
        if (!svgRef.current || !width || !height) return;

        const svg = d3.select(svgRef.current);
        // The claim flow reuses the existing visual vocabulary rather than
        // inventing new node shapes:
        //   RECOMMENDATIONS -> hexagons grouped by domain  (as UNIVERSE)
        //   CLAIMS          -> labelled circles            (as GALAXY)
        //   EVIDENCE        -> paper cards                 (as FIELD)
        const isTopics = viewMode === 'TOPICS';
        const isClaims = viewMode === 'CLAIMS';
        const isEvidence = viewMode === 'EVIDENCE';

        const currentNodes = nodes.map(n => ({ ...n }));
        const currentEdges = edges.map(e => ({ ...e }));

        if (isEvidence) {
            // Stretch importance across the range actually present before it
            // becomes a size. Raw importance never uses its full 0-1 scale -
            // on a typical claim it sits between 0.31 and 0.86 - so mapping it
            // straight to pixels gave a 1.6x spread and cards that all looked
            // the same, which is the complaint this is answering. Normalised
            // per view, the least important paper is always the smallest and
            // the range is always the full 3x.
            const imps = currentNodes
                .filter(n => n.type !== 'claim-anchor' && n.stance !== 'neutral')
                .map(n => (Number.isFinite(n.importance) ? n.importance : 0.3));
            const impLo = imps.length ? Math.min(...imps) : 0;
            const impHi = imps.length ? Math.max(...imps) : 1;
            const impSpan = (impHi - impLo) || 1;

            currentNodes.forEach(n => {
                if (n.type === 'claim-anchor') return;   // drawn as a circle, not a card
                if (n.stance === 'neutral') {
                    // Uniform: these sit in the context box, where size would
                    // imply a ranking as evidence they were excluded from.
                    n._w = 132;
                    n._h = 46;
                    n._compactW = n._w;
                    n._compactH = n._h;
                    return;
                }
                // Size is importance, and the range is deliberately wide.
                //
                // It used to be citations over 96-132px - a 1.4x spread that
                // said almost nothing, because every card looked the same size.
                // Importance spans 58-154px, 2.7x, so the papers worth reading
                // are visibly bigger and the rest genuinely recede.
                const imp = Number.isFinite(n.importance) ? n.importance : 0.3;
                const t = Math.max(0, Math.min(1, (imp - impLo) / impSpan));
                n._w = 52 + t * 104;
                n._h = 38 + t * 54;
                n._compactW = n._w;
                n._compactH = n._h;
            });
        }

        let gMain = svg.select(".g-main");
        if (gMain.empty()) {
            const gRoot = svg.append("g");
            gMain = gRoot.append("g").attr("class", "g-main");
        }

        let gLinks = gMain.select(".g-links");
        if (gLinks.empty()) gLinks = gMain.append("g").attr("class", "g-links");

        // Chevrons ride above the ribbons but below the cards, so a citation
        // arrow is never drawn over the paper it points at.
        let gLinkHeads = gMain.select(".g-link-heads");
        if (gLinkHeads.empty()) gLinkHeads = gMain.append("g").attr("class", "g-link-heads");

        let gAxisLayer = gMain.select(".g-axis-layer");
        if (gAxisLayer.empty()) gAxisLayer = gMain.append("g").attr("class", "g-axis-layer");

        let gHexBg = gMain.select(".g-hex-bg");
        if (gHexBg.empty()) gHexBg = gMain.append("g").attr("class", "g-hex-bg");

        let gSpokes = gMain.select(".g-spokes");
        if (gSpokes.empty()) gSpokes = gMain.append("g").attr("class", "g-spokes");

        let gNodes = gMain.select(".g-nodes");
        if (gNodes.empty()) gNodes = gMain.append("g").attr("class", "g-nodes");

        gAxisLayer.lower();
        gSpokes.lower();
        gHexBg.lower();
        gLinks.lower();
        gLinkHeads.raise();
        gNodes.raise();

        const zoom = d3.zoom()
            .scaleExtent([0.01, 8])
            .on("zoom", (event) => {
                gMain.attr("transform", event.transform);
                if (isTransitioningView.current) return;
            });

        svg.call(zoom);
        // Tap-to-dismiss, via pointer events rather than click.
        //
        // d3-zoom owns the touch sequence and preventDefaults it, so on a phone
        // the synthetic click never arrived and a selected paper could not be
        // dismissed at all. Pointer events fire for mouse and touch alike; the
        // movement threshold is what stops the end of a pan from counting as a
        // tap on the background.
        let tapStart = null;
        svg.on("pointerdown.unselect", (event) => {
            tapStart = { x: event.clientX, y: event.clientY, target: event.target };
        });
        svg.on("pointerup.unselect pointercancel.unselect", (event) => {
            const start = tapStart;
            tapStart = null;
            if (!start || event.type === 'pointercancel') return;
            const moved = Math.hypot(event.clientX - start.x, event.clientY - start.y);
            if (moved > 8) return;                            // that was a pan
            if (event.target !== start.target) return;
            if (event.target.tagName === 'svg') onBackgroundClick();
        });

        if (simulationRef.current) simulationRef.current.stop();

        if (prevViewMode.current !== viewMode || prevLayoutMode.current !== layoutMode) {
            gLinks.selectAll("*").remove();
            gLinkHeads.selectAll("*").remove();
            gNodes.selectAll("*").interrupt().remove();
            gHexBg.selectAll("*").remove();
            gNodes.style("opacity", 0);
            gLinks.style("opacity", 0);
        }

        const sim = d3.forceSimulation(currentNodes);

        if (isClaims) {
            layoutEngine.current.applyClaimsLayout(currentNodes, sim, reading);
        } else if (isEvidence) {
            layoutEngine.current.applyEvidenceLayout(currentNodes, currentEdges, sim, evidenceXAxis, reading);
        } else {
            layoutEngine.current.applyTopicsLayout(currentNodes, sim);
        }

        // ── Theme headings (landing) ─────────────────────────────────────────
        // Redrawn every render, not just on a view change: a resize repacks the
        // clusters into a different number of rows, so stale headings would sit
        // over the wrong block.
        gHexBg.selectAll("*").remove();
        if (isTopics) {
            (layoutEngine.current.topicClusters || []).forEach(c => {
                // No container. The gap between blocks does the grouping, and a
                // box around a honeycomb fights the tessellation it encloses -
                // the shape is already the boundary. That leaves the heading as
                // the only marker, so it carries a little more weight than it
                // would sitting inside a panel.
                gHexBg.append("text")
                    .attr("x", c.labelX).attr("y", c.labelY)
                    .attr("text-anchor", "middle")
                    .style("font-family", "Inter, system-ui, sans-serif")
                    .style("font-size", "25px").style("font-weight", 800)
                    .style("letter-spacing", "0.12em")
                    .style("fill", "#64748b").style("pointer-events", "none")
                    .text(c.name.toUpperCase());
            });
        }

        /**
         * Push overlapping claim labels apart, vertically.
         *
         * The force layout only knows about circles, but each claim also carries
         * a block of text hanging below it - the claim itself, the for/against
         * tally, the volume - roughly 60-90px tall and wider than the node. Two
         * nodes can sit a comfortable distance apart and still have their labels
         * printed straight through each other, which is what turned a busy
         * screen into an unreadable one.
         *
         * So after the simulation settles, walk the nodes top to bottom and slide
         * any label that would collide with one already placed far enough down to
         * clear it. Deterministic, and it never moves a node - only its text -
         * so the positions still mean exactly what the axes say they mean.
         */
        const CHAR_PX = 6.35;          // Inter 12.5px, mixed-case prose
        const LABEL_LEAD = 10;         // gap between node edge and its label
        const LABEL_GAP = 8;           // minimum gap between two labels

        const resolveLabelOverlaps = (list) => {
            // Cards carry their text inside them, so there is no floating
            // caption to unpick and the solver has already guaranteed the
            // separation this pass exists to create.
            if (LayoutEngine.CLAIM_NODE_STYLE === "card") return;
            const boxes = [];
            [...list]
                .sort((a, b) => (a.y - (a.val || 20)) - (b.y - (b.val || 20)))
                .forEach(d => {
                    const r = d.val || 20;
                    const w = Math.max(180, Math.min(240, r * 3.2));
                    d._labelW = w;
                    const lines = Math.max(1, Math.ceil(((d.claim || d.name || '').length * CHAR_PX) / w));
                    const h = lines * 17 + 34;      // text lines + tally + volume
                    const left = d.x - w / 2;
                    const right = d.x + w / 2;
                    let top = d.y + r + LABEL_LEAD;

                    // Slide down past anything it would run into.
                    let moved = true;
                    while (moved) {
                        moved = false;
                        for (const b of boxes) {
                            const overlapX = left < b.right && right > b.left;
                            const overlapY = top < b.bottom && (top + h) > b.top;
                            if (overlapX && overlapY) {
                                top = b.bottom + LABEL_GAP;
                                moved = true;
                            }
                        }
                    }
                    d._labelDy = top - d.y;          // offset from the node centre
                    boxes.push({ left, right, top, bottom: top + h });
                });
        };

        const DRY_RUN_TICKS = (isClaims || isEvidence) ? 300 : 120;
        sim.stop();
        sim.alpha(1);
        for (let i = 0; i < DRY_RUN_TICKS; ++i) {
            sim.tick();
        }

        if (isClaims) resolveLabelOverlaps(currentNodes);

        // ── Spokes (evidence) ────────────────────────────────────────────────
        // With paper-to-paper ribbons gone, nothing said these papers all belong
        // to one claim. A hairline to the anchor says it without competing: it
        // reads as texture radiating from the card, not as a network to trace.
        // Context papers are excluded - they sit outside the plot precisely
        // because they do NOT test the claim, and a spoke would assert they do.
        gSpokes.selectAll("*").remove();
        if (isEvidence && LayoutEngine.EVIDENCE_SPOKES) {
            const anchorNode = currentNodes.find(n => n.type === 'claim-anchor');
            if (anchorNode) {
                gSpokes.selectAll("line")
                    .data(currentNodes.filter(n => n.type !== 'claim-anchor' && !n._inBox))
                    .enter().append("line")
                    .attr("x1", d => d.x).attr("y1", d => d.y)
                    .attr("x2", anchorNode.x).attr("y2", anchorNode.y)
                    .attr("stroke", "#94a3b8")
                    .attr("stroke-opacity", 0.13)
                    .attr("stroke-width", 1)
                    .style("pointer-events", "none");
            }
        }


        const getEdgeKey = (d) => `${(isClaims || isEvidence) ? "G" : "P"}|${d.source.id || d.source}|${d.target.id || d.target}`;
        const getGradientId = (d) => `link-gradient-${sanitizeId(getEdgeKey(d))}`;
        const defs = svg.select("defs").empty() ? svg.append("defs") : svg.select("defs");

        const updateLinkPaths = (s) => {
            s.attr("d", d => {
                const src = d.source;
                const tgt = d.target;

                if (isClaims) {
                    const dx = tgt.x - src.x;
                    const dy = tgt.y - src.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist === 0) return `M${src.x},${src.y} L${tgt.x},${tgt.y}`;
                    const curvature = 0.2;
                    const offset = dist * curvature;
                    const midX = (src.x + tgt.x) / 2;
                    const midY = (src.y + tgt.y) / 2;
                    const nx = -dy / dist;
                    const ny = dx / dist;
                    const cx = midX + nx * offset;
                    const cy = midY + ny * offset;
                    return `M${src.x},${src.y} Q${cx},${cy} ${tgt.x},${tgt.y}`;
                } else if (isEvidence) {
                    const dx = tgt.x - src.x;
                    const dy = tgt.y - src.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist === 0) return "";

                    const curvature = 0.2;
                    const offset = dist * curvature;
                    const midX = (src.x + tgt.x) / 2;
                    const midY = (src.y + tgt.y) / 2;
                    const nx = -dy / dist;
                    const ny = dx / dist;
                    const cx = midX + nx * offset;
                    const cy = midY + ny * offset;

                    const getT = (w, h, pX, pY) => {
                        let tx = pX === 0 ? Infinity : Math.abs((w / 2) / pX);
                        let ty = pY === 0 ? Infinity : Math.abs((h / 2) / pY);
                        return Math.min(tx, ty);
                    };

                    const dirXs = cx - src.x;
                    const dirYs = cy - src.y;
                    let ts = getT(src._w || 80, src._h || 50, dirXs, dirYs);
                    ts = Math.min(ts, 0.95);
                    const nsx = src.x + dirXs * ts;
                    const nsy = src.y + dirYs * ts;

                    const dirXt = cx - tgt.x;
                    const dirYt = cy - tgt.y;
                    let tt = getT(tgt._w || 80, tgt._h || 50, dirXt, dirYt);
                    tt = Math.min(tt, 0.95);
                    const ntx = tgt.x + dirXt * tt;
                    const nty = tgt.y + dirYt * tt;

                    // Direction follows the flow of INFLUENCE, not the
                    // direction of the reference: an older paper's findings
                    // travel forward into the newer paper that cites it.
                    //
                    // The edge itself is stored the other way round -
                    // import_claims.py writes (citing, cited) straight off
                    // OpenAlex's referenced_works, so `source` is the NEWER
                    // paper in 91.6% of edges. The ribbon therefore has to be
                    // drawn against the edge's own orientation: hairline at the
                    // TARGET (cited, older) end, fanning out at the SOURCE
                    // (citing, newer) end, which is where influence arrives.
                    const wAtSource = 13;    // citing paper - destination
                    const wAtTarget = 1.5;   // cited paper  - origin
                    const wStart = wAtSource;
                    const wEnd = wAtTarget;

                    const dx1 = cx - nsx;
                    const dy1 = cy - nsy;
                    const len1 = Math.sqrt(dx1 * dx1 + dy1 * dy1) || 1;
                    const nx1 = -dy1 / len1;
                    const ny1 = dx1 / len1;

                    const dx2 = ntx - cx;
                    const dy2 = nty - cy;
                    const len2 = Math.sqrt(dx2 * dx2 + dy2 * dy2) || 1;
                    const nx2 = -dy2 / len2;
                    const ny2 = dx2 / len2;

                    const s1x = nsx + nx1 * (wStart / 2);
                    const s1y = nsy + ny1 * (wStart / 2);
                    const s2x = nsx - nx1 * (wStart / 2);
                    const s2y = nsy - ny1 * (wStart / 2);

                    const t1x = ntx + nx2 * (wEnd / 2);
                    const t1y = nty + ny2 * (wEnd / 2);
                    const t2x = ntx - nx2 * (wEnd / 2);
                    const t2y = nty - ny2 * (wEnd / 2);

                    const wMid = (wStart + wEnd) / 2;
                    const c1x = cx + nx * (wMid / 2);
                    const c1y = cy + ny * (wMid / 2);
                    const c2x = cx - nx * (wMid / 2);
                    const c2y = cy - ny * (wMid / 2);

                    d._spine = {
                        x0: ntx, y0: nty,          // cited (older): flow starts
                        cx, cy,
                        x1: nsx, y1: nsy,          // citing (newer): flow ends
                        w0: wAtTarget, w1: wAtSource,
                    };

                    return `M${s1x},${s1y} Q${c1x},${c1y} ${t1x},${t1y} L${t2x},${t2y} Q${c2x},${c2y} ${s2x},${s2y} Z`;
                } else {
                    return `M${src.x},${src.y} L${tgt.x},${tgt.y}`;
                }
            });
            if (isClaims) {
                defs.selectAll(".link-gradient")
                    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
                    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
            }
        };

        /**
         * Direction markers along each citation ribbon.
         *
         * The taper alone is ambiguous once ribbons overlap, and an arrowhead
         * parked at the tip gets hidden behind the target card. So chevrons sit
         * ON the ribbon, at fixed fractions of its length, pointing the way the
         * citation runs: from the paper doing the citing to the paper cited.
         *
         * They are drawn in white on top of the coloured ribbon, which reads as
         * a notch cut out of it rather than another line competing with it.
         */
        const CHEVRON_AT = [0.45, 0.72, 0.9];

        const updateLinkHeads = (sel) => {
            sel.attr("d", d => {
                const sp = d._spine;
                if (!sp) return "";

                // Quadratic Bezier position and tangent, same curve as the ribbon.
                const at = (t) => {
                    const mt = 1 - t;
                    return {
                        x: mt * mt * sp.x0 + 2 * mt * t * sp.cx + t * t * sp.x1,
                        y: mt * mt * sp.y0 + 2 * mt * t * sp.cy + t * t * sp.y1,
                        tx: 2 * mt * (sp.cx - sp.x0) + 2 * t * (sp.x1 - sp.cx),
                        ty: 2 * mt * (sp.cy - sp.y0) + 2 * t * (sp.y1 - sp.cy),
                    };
                };

                let path = "";
                CHEVRON_AT.forEach(t => {
                    const p = at(t);
                    const len = Math.hypot(p.tx, p.ty) || 1;
                    const ux = p.tx / len, uy = p.ty / len;      // along the ribbon
                    const px = -uy, py = ux;                      // across it

                    // Scale with the local ribbon width so the notch always fits
                    // inside the taper instead of spilling over the edges.
                    const localW = sp.w0 + (sp.w1 - sp.w0) * t;
                    const half = Math.max(3.6, localW * 0.66);
                    const reach = Math.max(5.0, localW * 0.92);

                    const bx = p.x - ux * reach * 0.5;
                    const by = p.y - uy * reach * 0.5;
                    const tipX = bx + ux * reach;
                    const tipY = by + uy * reach;

                    path += `M${bx + px * half},${by + py * half} `
                          + `L${tipX},${tipY} `
                          + `L${bx - px * half},${by - py * half} `;
                });
                return path;
            });
        };

        const headJoin = gLinkHeads.selectAll(".d3-link-head")
            .data(isEvidence ? currentEdges : [], getEdgeKey);
        headJoin.exit().remove();
        const headEnter = headJoin.enter().append("path")
            .attr("class", "d3-link-head")
            .attr("fill", "none")
            .attr("stroke", "#ffffff")
            .attr("stroke-width", 2.6)
            .attr("stroke-linecap", "round")
            .attr("stroke-linejoin", "round")
            .style("pointer-events", "none");
        const allHeads = headEnter.merge(headJoin);

        const linkJoin = gLinks.selectAll(".d3-link").data(currentEdges, getEdgeKey);
        linkJoin.exit().remove();
        const linkEnter = linkJoin.enter().append("path")
            .attr("class", `d3-link ${(isClaims || isEvidence) ? 'type-galaxy-link' : 'type-paper-link'}`)
            .attr("fill", isEvidence ? "#999" : "none")
            .attr("stroke-linecap", "round");

        const allLinks = linkEnter.merge(linkJoin);

        if (isClaims || isEvidence) {
            allLinks.each(function (d) {
                const id = getGradientId(d);
                let grad = defs.select(`#${id}`);
                if (grad.empty()) {
                    grad = defs.append("linearGradient").attr("id", id).attr("gradientUnits", "userSpaceOnUse");
                    grad.append("stop").attr("offset", "0%").attr("class", "grad-stop-start");
                    grad.append("stop").attr("offset", "100%").attr("class", "grad-stop-end");
                }
                const srcNode = currentNodes.find(n => n.id === (d.source.id || d.source));
                const tgtNode = currentNodes.find(n => n.id === (d.target.id || d.target));
                const cScale = scales.colorScale || d3.scaleOrdinal(d3.schemeTableau10);
                const srcColor = srcNode ? (srcNode.groupColor || cScale(srcNode.xGroup || srcNode.id)) : "#ccc";
                const tgtColor = tgtNode ? (tgtNode.groupColor || cScale(tgtNode.xGroup || tgtNode.id)) : "#ccc";
                grad.select(".grad-stop-start").attr("stop-color", srcColor).attr("stop-opacity", isEvidence ? 0.8 : 0.6);
                grad.select(".grad-stop-end").attr("stop-color", tgtColor).attr("stop-opacity", isEvidence ? 0.2 : 0.6);
                if (isEvidence) {
                    d3.select(this).attr("fill", `url(#${id})`).attr("stroke", "none");
                } else {
                    d3.select(this).attr("stroke", `url(#${id})`).attr("fill", "none");
                }
            });
        }

        updateLinkPaths(allLinks);
        updateLinkHeads(allHeads);
        allLinks.attr("stroke-width", d => (isClaims || isEvidence) ? Math.max(2, Math.sqrt(d.weight || 1)) : 1)
            .attr("stroke-opacity", 0);

        const nodeJoin = gNodes.selectAll(".d3-node").data(currentNodes, d => d.id);
        nodeJoin.exit().remove();

        const nodeEnter = nodeJoin.enter().append("g")
            .attr("class", "d3-node")
            .attr("cursor", "pointer")
            .on("click", (e, d) => { e.stopPropagation(); onNodeClick(d); })
            .on("dblclick", (e, d) => { e.stopPropagation(); if (onNodeDoubleClick) onNodeDoubleClick(d); })
            .on("mouseover", (e, d) => onNodeHover(d))
            .on("mouseout", (e, d) => onNodeHover(null));

        nodeEnter.each(function (d) {
            const el = d3.select(this);
            if (isTopics) {
                const clipId = `topic-clip-${sanitizeId(d.id)}`;
                el.append("path").attr("class", "orbit");
                el.append("path").attr("class", "core");
                el.append("defs").append("clipPath").attr("id", clipId)
                    .append("circle").attr("class", "topic-clip-circle");
                el.append("image")
                    .attr("class", "node-icon")
                    .attr("clip-path", `url(#${clipId})`)
                    .style("pointer-events", "none")
                    .style("display", "none");
                el.append("circle").attr("class", "topic-photo-ring")
                    .style("pointer-events", "none");
                const fo = el.append("foreignObject").attr("class", "hex-label-fo");
                fo.append("xhtml:div").attr("class", "hex-label-div");
            } else if (isClaims) {
                el.append("circle").attr("class", "orbit");
                el.append("circle").attr("class", "core");
                // Card furniture, appended before the label so the text sits on
                // top of it. Whichever style is off is hidden, not removed.
                el.append("rect").attr("class", "claim-card");
                el.append("path").attr("class", "claim-card-bar");
                const fo = el.append("foreignObject").attr("class", "galaxy-label-fo");
                fo.append("xhtml:div").attr("class", "galaxy-label-div");
                // The border goes on top of everything, so one outline traces
                // the whole card - header included - and doubles as the focus
                // ring without the header band painting over it.
                el.append("rect").attr("class", "claim-card-edge");
            } else if (isEvidence && d.type === 'claim-anchor') {
                // The claim keeps the CARD it wore one level up - same header
                // band, same white counts strip - so drilling in reads as the
                // same object moving rather than a different one appearing.
                el.append("circle").attr("class", "orbit");
                el.append("circle").attr("class", "core");
                el.append("rect").attr("class", "claim-card");
                el.append("path").attr("class", "claim-card-bar");
                const fo = el.append("foreignObject").attr("class", "galaxy-label-fo");
                fo.append("xhtml:div").attr("class", "galaxy-label-div");
                el.append("rect").attr("class", "claim-card-edge");
            } else if (isEvidence) {
                const w = d._w || 80;
                const h = d._h || 50;
                el.append("rect").attr("class", "node-paper-bg")
                    .attr("x", -w / 2).attr("y", -h / 2)
                    .attr("width", w).attr("height", h)
                    .attr("fill", "#ffffff").attr("rx", 6);
                el.append("rect").attr("class", "node-paper-card")
                    .attr("x", -w / 2).attr("y", -h / 2)
                    .attr("width", w).attr("height", h).attr("rx", 6);
                el.append("foreignObject").attr("class", "node-fo-wrapper")
                    .attr("x", -w / 2).attr("y", -h / 2)
                    .attr("width", w).attr("height", h)
                    .append("xhtml:div")
                    .attr("class", "node-paper-content")
                    .style("width", "100%").style("height", "100%")
                    .style("display", "flex").style("align-items", "center")
                    .style("justify-content", "center")
                    .style("text-align", "center").style("overflow", "hidden")
                    .style("padding", "4px").style("box-sizing", "border-box")
                    // Both states live in the DOM. Hover toggles display and
                    // resizes the rects - no re-rendering of markup, so it stays
                    // smooth across a hundred nodes.
                    .html(() => `<div class="node-paper-compact"></div>`
                              + `<div class="node-paper-title" style="display:none;width:100%;`
                              + `word-wrap:break-word;overflow-wrap:break-word;white-space:normal;`
                              + `line-height:1.25;text-align:center;"></div>`);
            }
            el.append("text").attr("class", "label-main");
            el.append("text").attr("class", "label-sub");
        });

        const allNodes = nodeEnter.merge(nodeJoin);

        // Rebind every render, not just on enter.
        //
        // Bound on enter alone, a handler keeps the closure it was created with
        // for as long as the node lives - so onNodeClick was permanently the
        // very first one, reading a `selected` that was null when the map was
        // built and null forever after. Nothing depending on current props
        // could work: tap-to-select saw no previous selection, so a second tap
        // on the same node selected it again instead of opening it.
        allNodes
            .on("click", (e, d) => { e.stopPropagation(); onNodeClick(d); })
            .on("dblclick", (e, d) => { e.stopPropagation(); if (onNodeDoubleClick) onNodeDoubleClick(d); })
            .on("mouseover", (e, d) => onNodeHover(d))
            .on("mouseout", () => onNodeHover(null));

        allNodes.attr("transform", d => `translate(${d.x}, ${d.y})`);

        const cScale = scales.colorScale || d3.scaleOrdinal(d3.schemeTableau10);
        allNodes.each(function (d) {
            const el = d3.select(this);
            if (isClaims) {
                const decided = (d.supports || 0) + (d.refutes || 0);
                const colour = d.hasEvidence
                    ? STANCE_DIVERGING(LayoutEngine.netFor(d, reading))
                    : STANCE_COLORS.unevaluated;

                if (LayoutEngine.CLAIM_NODE_STYLE === "card") {
                    const w = d._cardW || LayoutEngine.CARD_W;
                    const h = d._cardH || 120;
                    const headerH = d._cardHeaderH || (h - LayoutEngine.CARD_FOOT_H);
                    // White type demands a darker ground than the plot colour.
                    const header = d.hasEvidence ? readableOnWhiteText(colour) : "#7c8b9e";

                    el.select(".orbit").attr("r", 0).style("display", "none");
                    el.select(".core").attr("r", 0).style("display", "none");

                    el.select(".claim-card")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h)
                        .attr("rx", 14).attr("fill", "#ffffff").attr("stroke", "none")
                        .style("display", null);

                    // Header band: rounded at the top to match the card, square
                    // at the bottom where the counts strip meets it.
                    el.select(".claim-card-bar")
                        .attr("d", topRoundedRectPath(w, headerH, 14))
                        .attr("transform", `translate(0, ${-h / 2 + headerH / 2})`)
                        .attr("fill", header)
                        .style("display", null);

                    el.select(".claim-card-edge")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h)
                        .attr("rx", 14).attr("fill", "none")
                        .attr("stroke", header)
                        .attr("stroke-opacity", d.hasEvidence ? 0.5 : 0.35)
                        .attr("stroke-width", 1.5)
                        .attr("stroke-dasharray", d.hasEvidence ? null : "4 3")
                        .style("display", null);

                    el.select(".galaxy-label-fo")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h)
                        .style("overflow", "hidden").style("pointer-events", "none");

                    // Neutral and papers-published are gone from the plot; both
                    // are still on the hover card in the footer, which is where
                    // a number you have to actually read belongs.
                    let counts;
                    if (!d.hasEvidence) {
                        counts = `<span style="color:#94a3b8;font-style:italic;">no evidence gathered</span>`;
                    } else if (decided) {
                        counts = `<span style="color:${STANCE_COLORS.supports};font-weight:750;">${d.supports || 0}</span>`
                               + `<span style="color:#64748b;"> for</span>`
                               + `<span style="color:#cbd5e1;"> · </span>`
                               + `<span style="color:${STANCE_COLORS.refutes};font-weight:750;">${d.refutes || 0}</span>`
                               + `<span style="color:#64748b;"> against</span>`;
                    } else {
                        counts = `<span style="color:#94a3b8;">nothing decisive either way</span>`;
                    }

                    el.select(".galaxy-label-div")
                        .style("width", `${w}px`).style("height", `${h}px`)
                        .style("display", "flex").style("flex-direction", "column")
                        .style("font-family", "Inter, system-ui, sans-serif")
                        .style("overflow", "hidden")
                        .html(
                            // The claim owns the card: centred on both axes in
                            // the band, so a short claim sits as deliberately as
                            // a long one.
                            `<div style="height:${headerH}px;display:flex;align-items:center;` +
                            `justify-content:center;text-align:center;padding:0 14px;` +
                            `box-sizing:border-box;color:#ffffff;font-size:15px;` +
                            `font-weight:640;line-height:1.34;letter-spacing:0.005em;` +
                            `text-wrap:balance;">${d.claim || d.name || ""}</div>` +
                            `<div style="height:${LayoutEngine.CARD_FOOT_H}px;display:flex;` +
                            `align-items:center;justify-content:center;font-size:12.5px;` +
                            `letter-spacing:0.01em;">${counts}</div>`
                        );

                    el.select(".label-main").text("");
                    el.select(".label-sub").text("");
                    return;
                }

                el.select(".claim-card").style("display", "none");
                el.select(".claim-card-bar").style("display", "none");
                el.select(".claim-card-edge").style("display", "none");
                el.select(".orbit").style("display", null);
                el.select(".core").style("display", null);

                // Radius arrives in pixels from the OpenAlex match count, so size
                // means "how much has been published around this question".
                // Fill means stance: a claim with evidence is tinted by
                // netSupport; one without is left hollow and grey.
                const r = d.val || 20;

                el.select(".orbit")
                    .attr("r", r + 9).attr("width", null).attr("height", null)
                    .attr("fill", colour).attr("fill-opacity", d.hasEvidence ? 0.12 : 0.05)
                    .attr("stroke", colour).attr("stroke-opacity", 0.3).attr("stroke-width", 1.5);
                el.select(".core")
                    .attr("r", r)
                    .attr("fill", colour)
                    .attr("fill-opacity", d.hasEvidence ? (decided ? 0.85 : 0.4) : 0.18)
                    .attr("stroke", d.hasEvidence ? "#ffffff" : STANCE_COLORS.neutral)
                    .attr("stroke-width", 2)
                    .attr("stroke-dasharray", d.hasEvidence ? null : "4 3");

                // Narrower than before: r * 4.5 let a big node claim a 290px-wide
                // strip of the plot for its caption and collide with everything
                // either side of it.
                const labelW = Math.max(180, Math.min(240, r * 3.2));
                const labelH = 150;
                d._labelW = labelW;
                el.select(".galaxy-label-fo")
                    .attr("x", -labelW / 2)
                    .attr("y", d._labelDy != null ? d._labelDy : r + 10)
                    .attr("width", labelW).attr("height", labelH)
                    .style("overflow", "visible").style("pointer-events", "none");

                // Literature volume always shows - it is what sized the node.
                const volume = `<div style="font-size:10px;color:#94a3b8;margin-top:3px;">
                                  ${(d.openAlexCount || 0).toLocaleString()} papers published
                                </div>`;

                let status;
                if (!d.hasEvidence) {
                    status = `<div style="font-size:11px;margin-top:3px;color:#94a3b8;font-style:italic;">
                                no evidence gathered
                              </div>`;
                } else if (decided || d.neutral) {
                    status = `<div style="font-size:11px;margin-top:3px;">
                                <span style="color:${STANCE_COLORS.supports};font-weight:700;">${d.supports || 0}</span>
                                <span style="color:#94a3b8;"> for · </span>
                                <span style="color:${STANCE_COLORS.refutes};font-weight:700;">${d.refutes || 0}</span>
                                <span style="color:#94a3b8;"> against · ${d.neutral || 0} neutral</span>
                              </div>`;
                } else {
                    status = `<div style="font-size:11px;margin-top:3px;color:#94a3b8;">
                                ${d.unevaluated || 0} papers awaiting assessment
                              </div>`;
                }

                el.select(".galaxy-label-div")
                    .style("width", `${labelW}px`).style("height", `${labelH}px`)
                    .style("display", "flex").style("flex-direction", "column")
                    .style("align-items", "center").style("justify-content", "flex-start")
                    .style("text-align", "center").style("font-family", "Inter, system-ui, sans-serif")
                    .style("color", "#1e293b").style("line-height", "1.3")
                    .html(
                        `<div style="font-size:12.5px;font-weight:600;max-width:${labelW}px;">${d.claim || d.name || ""}</div>` +
                        status +
                        volume
                    );

                el.select(".label-main").text("");
                el.select(".label-sub").text("");
                return;
            }
            if (isTopics) {
                // Uniform tessellating hexagon: photo centred, text along the
                // bottom edge. Size is fixed by the hex grid, so paper count is
                // carried by the label rather than by area.
                const hexR = d.hexR || 190;
                const fill = d.colour || cScale(d.group || "Default");

                el.select(".orbit")
                    .attr("d", roundedHexagonPath(hexR))
                    .attr("fill", fill)
                    .attr("fill-opacity", 0.4)
                    .attr("stroke", "#ffffff")
                    .attr("stroke-width", 2);

                const photoR = hexR * 0.34;
                const photoCY = -hexR * 0.20;
                const iconEl = el.select(".node-icon");

                if (d.iconPath) {
                    el.select(".topic-clip-circle")
                        .attr("r", photoR).attr("cx", 0).attr("cy", photoCY);
                    iconEl.attr("href", resolveIconHref(d.iconPath))
                        .attr("width", photoR * 2).attr("height", photoR * 2)
                        .attr("x", -photoR).attr("y", photoCY - photoR)
                        .attr("preserveAspectRatio", "xMidYMid slice")
                        .style("display", null);
                    el.select(".topic-photo-ring")
                        .attr("r", photoR).attr("cx", 0).attr("cy", photoCY)
                        .attr("fill", "none")
                        .attr("stroke", "#ffffff").attr("stroke-width", 3)
                        .style("display", null);
                    el.select(".core").attr("d", null).attr("r", 0).style("display", "none");
                } else {
                    iconEl.style("display", "none");
                    el.select(".topic-photo-ring").style("display", "none");
                    el.select(".core")
                        .attr("d", roundedHexagonPath(hexR * 0.34))
                        .attr("r", null).attr("fill", fill)
                        .style("display", null).style("filter", "blur(1px)");
                }

                // Text block sits in the lower third, inside the flat bottom edge.
                const labelW = hexR * 1.36;
                const labelH = hexR * 0.70;
                el.select(".hex-label-fo")
                    .attr("x", -labelW / 2).attr("y", hexR * 0.20)
                    .attr("width", labelW).attr("height", labelH)
                    .style("overflow", "visible").style("pointer-events", "none");

                el.select(".hex-label-div")
                    .style("width", `${labelW}px`).style("height", `${labelH}px`)
                    .style("display", "flex").style("flex-direction", "column")
                    .style("align-items", "center").style("justify-content", "flex-start")
                    .style("text-align", "center")
                    .style("font-family", "Inter, system-ui, sans-serif")
                    .style("color", "#1e293b").style("line-height", "1.25")
                    .style("word-break", "break-word").style("overflow-wrap", "break-word")
                    .style("padding", "0 6px").style("box-sizing", "border-box")
                    // Type scales with the hexagon, but what reaches the eye is
                    // the fraction times the zoom-to-fit scale, and hexR cancels
                    // out of that - so the fraction is the only real lever on
                    // legibility. Clustering costs roughly a third of the scale
                    // (gaps and headings are area the fit has to swallow), so
                    // the name is set well above the old 0.098 to come out ahead
                    // rather than merely level.
                    //
                    // Dropping the researched count pays for the extra line the
                    // larger name needs: with every claim judged it read
                    // "7 claims · 7 researched" on all fourteen topics.
                    .html(
                        `<div style="font-size:${(hexR * 0.155).toFixed(1)}px;font-weight:700;">${d.name}</div>` +
                        `<div style="font-size:${(hexR * 0.082).toFixed(1)}px;font-weight:500;color:#475569;margin-top:4px;">` +
                        `${d.claimCount} claims</div>` +
                        `<div style="font-size:${(hexR * 0.072).toFixed(1)}px;color:#64748b;margin-top:2px;">` +
                        `~${(d.openAlexCount || 0).toLocaleString()} papers published</div>`
                    );
                el.select(".label-main").text("");
            } else if (isEvidence && d.type === 'claim-anchor') {
                // Same card as the claims screen, so the node reads as the very
                // one you clicked to get here rather than a new object.
                const colour = STANCE_DIVERGING(LayoutEngine.netFor(d, reading));
                const header = readableOnWhiteText(colour);
                const w = d._cardW || LayoutEngine.ANCHOR_CARD_W;
                const h = d._cardH || 140;
                const headerH = d._cardHeaderH || (h - LayoutEngine.CARD_FOOT_H);

                el.select(".orbit").attr("r", 0).style("display", "none");
                el.select(".core").attr("r", 0).style("display", "none");

                el.select(".claim-card")
                    .attr("x", -w / 2).attr("y", -h / 2)
                    .attr("width", w).attr("height", h)
                    .attr("rx", 16).attr("fill", "#ffffff").attr("stroke", "none")
                    .style("display", null);

                el.select(".claim-card-bar")
                    .attr("d", topRoundedRectPath(w, headerH, 16))
                    .attr("transform", `translate(0, ${-h / 2 + headerH / 2})`)
                    .attr("fill", header)
                    .style("display", null);

                // Heavier ring than a claim card carries upstairs: this one is
                // the subject of the screen, not one of a set.
                el.select(".claim-card-edge")
                    .attr("x", -w / 2).attr("y", -h / 2)
                    .attr("width", w).attr("height", h)
                    .attr("rx", 16).attr("fill", "none")
                    .attr("stroke", header).attr("stroke-opacity", 0.85)
                    .attr("stroke-width", 2.5)
                    .style("display", null);

                el.select(".galaxy-label-fo")
                    .attr("x", -w / 2).attr("y", -h / 2)
                    .attr("width", w).attr("height", h)
                    .style("overflow", "hidden").style("pointer-events", "none");

                el.select(".galaxy-label-div")
                    .style("width", `${w}px`).style("height", `${h}px`)
                    .style("display", "flex").style("flex-direction", "column")
                    .style("font-family", "Inter, system-ui, sans-serif")
                    .style("overflow", "hidden")
                    .html(
                        `<div style="height:${headerH}px;display:flex;align-items:center;` +
                        `justify-content:center;text-align:center;padding:0 16px;` +
                        `box-sizing:border-box;color:#ffffff;font-size:15.5px;` +
                        `font-weight:640;line-height:1.34;text-wrap:balance;">` +
                        `${d.claim || ""}</div>` +
                        `<div style="height:${LayoutEngine.CARD_FOOT_H}px;display:flex;` +
                        `align-items:center;justify-content:center;font-size:12.5px;">` +
                        `<span style="color:${STANCE_COLORS.supports};font-weight:750;">${d.supports || 0}</span>` +
                        `<span style="color:#64748b;"> for</span>` +
                        `<span style="color:#cbd5e1;"> · </span>` +
                        `<span style="color:${STANCE_COLORS.refutes};font-weight:750;">${d.refutes || 0}</span>` +
                        `<span style="color:#64748b;"> against</span></div>`
                    );
                el.select(".label-main").text("");
                el.select(".label-sub").text("");
            } else if (isEvidence) {
                const w = d._w || 80;
                const h = d._h || 50;
                const isNeutral = d.stance === 'neutral';
                // Context papers are flat grey. They no longer need dimming to
                // stay out of the way - being outside the plot does that - and
                // dimming only made the ones a reader might want to click hard
                // to read.
                const cardColor = isNeutral
                    ? STANCE_COLORS.neutral
                    : (STANCE_COLORS[d.stance] || STANCE_COLORS.unevaluated);

                // Weak studies recede, strong ones hold the eye. Context papers
                // are exempt: they sit outside the plot and carry no design
                // rank, so fading them would rank something never ranked.
                const rank = Number.isFinite(d.designRank)
                    ? d.designRank : LayoutEngine.DESIGN_X_FALLBACK;
                d._strengthFill = isNeutral ? 0.14 : STRENGTH_FILL(rank);
                d._strengthStroke = isNeutral ? 1 : STRENGTH_STROKE(rank);

                // Geometry is skipped while a card is open. The open size is
                // owned by the hover/pin pass, and this render would otherwise
                // stamp the compact size back over it - so whichever effect
                // happened to run last decided the size, which is a race, not
                // a rule. Colours and content still update.
                if (!d._paperOpen) {
                    el.select(".node-paper-bg").attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h);
                    el.select(".node-paper-card").attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h);
                    el.select(".node-fo-wrapper").attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h);
                }
                el.select(".node-paper-bg").attr("fill-opacity", 1);
                el.select(".node-paper-card")
                    .attr("fill", cardColor)
                    .attr("fill-opacity", d._paperOpen ? 0.30 : d._strengthFill)
                    .style("stroke", cardColor).style("stroke-width", isNeutral ? 1.25 : 2)
                    .style("stroke-opacity", d._paperOpen ? 1 : d._strengthStroke);

                // The card carries its rank. "Which should I read first" is the
                // question a hundred papers actually raise, and a position in a
                // ranking answers it in two characters - which is all that fits
                // on the smallest card. The verdict is already the colour.
                //
                // Everything else waits for the cursor. The design label only
                // appears once the card is wide enough to hold it without
                // squeezing the number.
                const textColour = readableOnWhiteText(cardColor, STRENGTH_TEXT(rank));
                const rankMark = d.rank != null
                    ? `<div style="font-size:${Math.min(21, Math.max(13, w * 0.16)).toFixed(1)}px;` +
                      `font-weight:800;letter-spacing:-0.02em;line-height:1;` +
                      `color:${textColour};">` +
                      `<span style="font-size:0.62em;font-weight:700;opacity:0.65;">#</span>` +
                      `${d.rank}</div>`
                    : `<div style="font-size:12.5px;font-weight:750;color:${textColour};">` +
                      `${isNeutral ? 'context' : (VERDICT_WORD[d.stance] || 'untested')}</div>`;

                // Only a card with room to spare gets the design label. Below
                // that the number is the whole message - a squeezed rank with a
                // clipped word under it reads as neither.
                const designMark = w >= 124
                    ? `<div style="font-size:9.5px;font-weight:600;` +
                      `color:${readableOnWhiteText("#64748b", 4.5 + 3 * rank)};` +
                      `letter-spacing:0.05em;text-transform:uppercase;white-space:nowrap;` +
                      `overflow:hidden;text-overflow:ellipsis;max-width:${w - 14}px;">` +
                      `${designLabel(d)}</div>`
                    : '';

                el.select(".node-paper-compact")
                    .style("width", "100%")
                    .style("display", "flex").style("flex-direction", "column")
                    .style("align-items", "center").style("justify-content", "center")
                    .style("gap", "2px").style("text-align", "center")
                    .html(rankMark + designMark);

                // The expanded content is built HERE and only here, once per
                // render, hidden until the card opens. It used to be built in
                // the hover pass while this one wrote a plain title over the
                // top, so whether a card showed its detail came down to which
                // effect happened to run last - which is why some had it and
                // some did not.
                //
                // The model's own strength label is deliberately absent. It
                // duplicated the design while disagreeing with it: only 16% of
                // what it calls strong is a meta-analysis or RCT, and 23% are
                // designs its own instructions call limited.
                const detail = [];
                if (isNeutral) {
                    detail.push(`<span style="color:#64748b;">context only</span>`);
                } else {
                    const conf = d.confidence != null ? `${Math.round(d.confidence)}% ` : '';
                    detail.push(`<span style="color:${readableOnWhiteText(cardColor)};` +
                                `font-weight:750;">${conf}${VERDICT_WORD[d.stance] || 'untested'}</span>`);
                }
                detail.push(`<span style="color:#475569;">${designLabel(d)}</span>`);
                if (d.journalImpact != null) {
                    detail.push(`<span style="color:#475569;">impact <strong>${d.journalImpact}</strong></span>`);
                }
                detail.push(`<span style="color:#94a3b8;">${d.citationCount || 0} cites</span>`);

                el.select(".node-paper-title")
                    .style("padding", "0 4px")
                    .style("overflow-wrap", "anywhere")
                    .html(
                        // The title is clamped and the detail is not, so if the
                        // height is ever wrong again it is the title that loses
                        // a line rather than the detail vanishing. The title is
                        // also in the panel at the bottom; the detail is only
                        // here. Belt and braces for the measurement above.
                        `<div style="font-size:12.5px;font-weight:650;color:#1e293b;` +
                        `line-height:1.28;display:-webkit-box;-webkit-line-clamp:5;` +
                        `-webkit-box-orient:vertical;overflow:hidden;">` +
                        `${d.title || d.name || 'Untitled'}</div>` +
                        `<div style="margin-top:6px;padding-top:5px;` +
                        `border-top:1px solid rgba(0,0,0,0.07);font-size:10.5px;` +
                        `line-height:1.5;display:flex;flex-wrap:wrap;gap:0 8px;` +
                        `justify-content:center;flex:0 0 auto;">` +
                        (d.rank != null
                            ? `<span style="color:#4f46e5;font-weight:800;">#${d.rank}` +
                              `${d.rankTotal ? `/${d.rankTotal}` : ''}</span>`
                            : '') +
                        detail.join('') + `</div>`
                    );
            }
        });

        // ── Axes & guides ────────────────────────────────────────────────────
        gAxisLayer.selectAll("*").remove();
        gAxisLayer.style("opacity", 1);

        const axisLabel = (x, y, text, anchor = "middle", size = 12, weight = 600) =>
            gAxisLayer.append("text")
                .attr("x", x).attr("y", y).attr("text-anchor", anchor)
                .style("font-family", "Inter, system-ui, sans-serif")
                .style("font-size", `${size}px`).style("font-weight", weight)
                .style("fill", "#94a3b8").style("pointer-events", "none")
                .text(text);

        /**
         * The quadrant frame both scatter screens share.
         *
         * Zoomed out far enough to see every cluster, 12px axis captions vanish
         * long before the clusters do, which leaves four blobs and no way to
         * tell which is which. So the orientation is carried by oversized,
         * very-low-contrast type set OUTSIDE the plot: legible at a glance when
         * the whole map is on screen, and quiet enough to ignore up close.
         *
         * Quadrant captions sit at the corners rather than the middle of each
         * quadrant, keeping the centre - where a contested claim's papers pile
         * up - clear.
         */
        const drawQuadrantFrame = ({ cy, halfW, halfH, endTop, endBottom, endLeft, endRight, quadrants }) => {
            const overhangX = halfW * 0.30;
            const overhangY = halfH * 0.34;
            const l = -halfW, r = halfW;
            const t = cy - halfH, b = cy + halfH;

            // Crosshair, run well past the data so the eye can follow it out.
            gAxisLayer.append("line")
                .attr("x1", 0).attr("x2", 0)
                .attr("y1", t - overhangY).attr("y2", b + overhangY)
                .attr("stroke", "#cbd5e1").attr("stroke-width", 1.5)
                .attr("stroke-dasharray", "6 5");
            gAxisLayer.append("line")
                .attr("x1", l - overhangX).attr("x2", r + overhangX)
                .attr("y1", cy).attr("y2", cy)
                .attr("stroke", "#cbd5e1").attr("stroke-width", 1.5)
                .attr("stroke-dasharray", "6 5");

            // Arrowheads, so each axis reads as a direction and not a divider.
            const tip = (x, y, dx, dy) => gAxisLayer.append("path")
                .attr("d", `M${x},${y} L${x + dx - dy * 0.5},${y + dy + dx * 0.5} `
                          + `M${x},${y} L${x + dx + dy * 0.5},${y + dy - dx * 0.5}`)
                .attr("stroke", "#cbd5e1").attr("stroke-width", 1.5).attr("fill", "none");
            tip(0, t - overhangY, 0, 14);
            tip(0, b + overhangY, 0, -14);
            tip(l - overhangX, cy, 14, 0);
            tip(r + overhangX, cy, -14, 0);

            const BIG = { size: 46, weight: 800, fill: "#dfe6ee", spacing: "0.10em" };
            const big = (x, y, text, anchor) => gAxisLayer.append("text")
                .attr("x", x).attr("y", y).attr("text-anchor", anchor)
                .style("font-family", "Inter, system-ui, sans-serif")
                .style("font-size", `${BIG.size}px`).style("font-weight", BIG.weight)
                .style("letter-spacing", BIG.spacing)
                .style("fill", BIG.fill).style("pointer-events", "none")
                .text(text);

            big(0, t - overhangY - 34, endTop, "middle");
            big(0, b + overhangY + 66, endBottom, "middle");
            big(l - overhangX - 26, cy + 16, endLeft, "end");
            big(r + overhangX + 26, cy + 16, endRight, "start");

            // Corner captions: [dx, dy, anchor] per quadrant.
            const corners = {
                topRight:    [r - 12, t + 46, "end"],
                topLeft:     [l + 12, t + 46, "start"],
                bottomRight: [r - 12, b - 26, "end"],
                bottomLeft:  [l + 12, b - 26, "start"],
            };
            Object.entries(quadrants || {}).forEach(([key, lines]) => {
                const spot = corners[key];
                if (!spot || !lines) return;
                const [x, y, anchor] = spot;
                lines.forEach((line, i) => {
                    gAxisLayer.append("text")
                        .attr("x", x).attr("y", y + i * 21)
                        .attr("text-anchor", anchor)
                        .style("font-family", "Inter, system-ui, sans-serif")
                        .style("font-size", i === 0 ? "17px" : "14px")
                        .style("font-weight", i === 0 ? 700 : 500)
                        .style("letter-spacing", i === 0 ? "0.04em" : "0")
                        .style("fill", i === 0 ? "#b6c2d0" : "#c3cdda")
                        .style("pointer-events", "none")
                        .text(line);
                });
            });
        };

        if (isClaims && layoutEngine.current.claimsFrame) {
            const f = layoutEngine.current.claimsFrame;
            const left = -f.plotW / 2, right = f.plotW / 2;
            const top = f.plotCY - f.plotH / 2, bottom = f.plotCY + f.plotH / 2;

            if (f.hasPlot) {
                drawQuadrantFrame({
                    cy: f.plotCY, halfW: f.plotW / 2, halfH: f.plotH / 2,
                    endTop: "SUPPORTED", endBottom: "REFUTED",
                    endLeft: "WEAKER", endRight: "STRONGER",
                    quadrants: {
                        topRight:    ["SETTLED", "supported by strong studies"],
                        topLeft:     ["PROMISING", "supported, but weak studies"],
                        bottomRight: ["DEBUNKED", "refuted by strong studies"],
                        bottomLeft:  ["DOUBTFUL", "refuted, but weak studies"],
                    },
                });
            }

            if (f.shelfTop !== null) {
                const shelfY = f.shelfTop - 130;
                gAxisLayer.append("line")
                    .attr("x1", left - 60).attr("x2", right + 60)
                    .attr("y1", shelfY).attr("y2", shelfY)
                    .attr("stroke", "#e2e8f0").attr("stroke-width", 1.5);
                axisLabel(left - 60, shelfY - 14, "NOT YET ASSESSED — sized by how much has been published",
                          "start", 12, 600);
            }
        } else if (isEvidence && layoutEngine.current.evidenceFrame) {
            const f = layoutEngine.current.evidenceFrame;
            const left = -f.plotW / 2, right = f.plotW / 2;
            const top = f.plotCY - f.plotH / 2, bottom = f.plotCY + f.plotH / 2;

            const byYear = f.xAxisMode === 'year';
            drawQuadrantFrame({
                cy: f.plotCY, halfW: f.plotW / 2, halfH: f.plotH / 2,
                endTop: "SUPPORTS", endBottom: "REFUTES",
                endLeft: byYear ? "OLDER" : "WEAKER",
                endRight: byYear ? "NEWER" : "STRONGER",
                quadrants: byYear ? {
                    topRight:    ["SUPPORTS", "recent work"],
                    topLeft:     ["SUPPORTS", "older work"],
                    bottomRight: ["REFUTES", "recent work"],
                    bottomLeft:  ["REFUTES", "older work"],
                } : {
                    topRight:    ["SUPPORTS", "on strong studies"],
                    topLeft:     ["SUPPORTS", "on weak studies"],
                    bottomRight: ["REFUTES", "on strong studies"],
                    bottomLeft:  ["REFUTES", "on weak studies"],
                },
            });

            // Confidence gridlines, so vertical distance is readable as a number.
            [0.5, 1].forEach(v => {
                [1, -1].forEach(sign => {
                    const y = f.plotCY + f.yScale(sign * v);
                    gAxisLayer.append("line")
                        .attr("x1", left).attr("x2", right)
                        .attr("y1", y).attr("y2", y)
                        .attr("stroke", "#eef2f6").attr("stroke-width", 1);
                    axisLabel(left - 10, y + 4, `${Math.round(v * 100)}%`, "end", 10, 500);
                });
            });

            if (f.xAxisMode === 'year') {
                const span = f.maxYear - f.minYear;
                const stepYears = span > 60 ? 10 : span > 30 ? 5 : span > 12 ? 2 : 1;
                const firstTick = Math.ceil(f.minYear / stepYears) * stepYears;
                for (let y = firstTick; y <= f.maxYear; y += stepYears) {
                    const x = f.xScale(y);
                    gAxisLayer.append("line")
                        .attr("x1", x).attr("x2", x)
                        .attr("y1", bottom).attr("y2", bottom + 8)
                        .attr("stroke", "#cbd5e1").attr("stroke-width", 1);
                    axisLabel(x, bottom + 26, String(y), "middle", 11, 500);
                }
                axisLabel(0, bottom + 52, "publication year  →", "middle", 12, 500);
            } else {
                f.strengthLevels.forEach(({ key, x }) => {
                    gAxisLayer.append("line")
                        .attr("x1", x).attr("x2", x)
                        .attr("y1", top).attr("y2", bottom + 8)
                        .attr("stroke", "#eef2f6").attr("stroke-width", 1);
                    axisLabel(x, bottom + 26, key.toUpperCase(), "middle", 11, 600);
                });
                axisLabel(0, bottom + 52, "strength of the study  →", "middle", 12, 500);
            }

            // The context box: drawn as a container so the papers inside it read
            // as set aside from the verdict rather than as a cluster within it.
            if (f.neutralBox) {
                const b = f.neutralBox;
                gAxisLayer.append("rect")
                    .attr("x", b.x).attr("y", b.y)
                    .attr("width", b.w).attr("height", b.h)
                    .attr("rx", 12)
                    .attr("fill", "#f8fafc")
                    .attr("stroke", "#cbd5e1")
                    .attr("stroke-width", 1.25)
                    .attr("stroke-dasharray", "6 4");

                gAxisLayer.append("text")
                    .attr("x", b.x + 14).attr("y", b.y + 21)
                    .style("font-family", "Inter, system-ui, sans-serif")
                    .style("font-size", "10.5px").style("font-weight", 800)
                    .style("letter-spacing", "0.07em")
                    .style("fill", "#94a3b8").style("pointer-events", "none")
                    .text(b.total > b.count
                        ? `BACKGROUND · ${b.count} OF ${b.total}`
                        : `BACKGROUND · ${b.count}`);

                gAxisLayer.append("text")
                    .attr("x", b.x + b.w / 2).attr("y", b.y + b.h + 18)
                    .attr("text-anchor", "middle")
                    .style("font-family", "Inter, system-ui, sans-serif")
                    .style("font-size", "11px").style("font-weight", 500)
                    .style("fill", "#b6c2d0").style("pointer-events", "none")
                    .text("cited by the evidence, but does not test the claim");
            }
        } else {
            gAxisLayer.style("opacity", 0);
        }

        if (prevViewMode.current !== viewMode && (isClaims || isEvidence)) {
            gNodes.style("opacity", 1);
            allNodes.attr("transform", d => `translate(${d.x}, ${d.y}) scale(0)`);

            const xExtent = d3.extent(currentNodes, d => d.x);
            const yExtent = d3.extent(currentNodes, d => d.y);
            const padding = 100;
            if (xExtent[0] !== undefined && yExtent[0] !== undefined) {
                // d.x/d.y are centres, so half of every edge card hangs past
                // the extent. With circles that was a few pixels; a 240x150
                // card loses 120 of them off each side and 75 off the top.
                const halfW = d3.max(currentNodes, n => (n._cardW || n._w || n.val * 2 || 0) / 2) || 0;
                const halfH = d3.max(currentNodes, n => (n._cardH || n._h || n.val * 2 || 0) / 2) || 0;

                // On mobile the header is a fixed bar over the map rather than
                // controls tucked into the corners, so the usable canvas starts
                // below it. Measured, not guessed - its height depends on how
                // many rows of controls this view has.
                const topInset = width < 768
                    ? (document.querySelector('.galaxy-topbar')?.getBoundingClientRect().height || 140)
                    : 0;
                const usableH = Math.max(120, height - topInset);

                const gw = (xExtent[1] - xExtent[0]) + halfW * 2;
                const gh = (yExtent[1] - yExtent[0]) + halfH * 2;
                const cx = (xExtent[0] + xExtent[1]) / 2;
                const cy = (yExtent[0] + yExtent[1]) / 2;

                const scale = Math.min(
                    width / (gw + padding * 2), usableH / (gh + padding * 2), 2);
                svg.transition().duration(1000).call(zoom.transform,
                    d3.zoomIdentity
                        .translate(width / 2, topInset + usableH / 2)
                        .scale(scale)
                        .translate(-cx, -cy));
                // Records that THIS view got its camera set, not merely that a
                // camera exists. The failure being guarded is a fit that was
                // skipped on an empty node list and never retried, which leaves
                // a perfectly valid transform in place - the previous screen's.
                svg.attr("data-fitted-view", viewMode);
            }

            allNodes.transition("flyin").duration(800).ease(d3.easeBackOut.overshoot(0.8))
                .attr("transform", d => `translate(${d.x}, ${d.y}) scale(1)`);
            gLinks.transition("flyin-links").delay(600).duration(500).style("opacity", 1);
            gLinkHeads.transition("flyin-heads").delay(600).duration(500).style("opacity", 1);
            allLinks.transition("flyin-links-stroke").delay(600).duration(500).attr("stroke-opacity", 0.6);
        } else {
            gNodes.style("opacity", 1);
            gLinks.style("opacity", 1);
            gLinkHeads.style("opacity", 1);
            allLinks.attr("stroke-opacity", 0.6);

            // Fit the tessellated hex cluster whenever we land on Topics —
            // not just on first paint, or coming back from Claims would keep
            // the previous view's zoom. Extents are padded by the hex radius
            // because d.x/d.y are centres, and half a hexagon sticks out past
            // each edge node.
            if (isTopics && currentNodes.length) {
                const hexR = currentNodes[0].hexR || 190;
                const xExtent = d3.extent(currentNodes, d => d.x);
                const yExtent = d3.extent(currentNodes, d => d.y);
                // Trimmed from a full hexR + 70. Padding is dead space the fit
                // has to swallow, and on this screen it comes straight back out
                // of the label type.
                const padding = hexR * 0.4 + 40;
                const gw = (xExtent[1] - xExtent[0]) + hexR * 2;
                // + the heading band above each cluster row, or the top row's
                // heading is scrolled off the canvas by its own fit.
                const gh = (yExtent[1] - yExtent[0]) + hexR * 2
                           + hexR * LayoutEngine.CLUSTER_HEAD;
                const topInset = width < 768
                    ? (document.querySelector('.galaxy-topbar')?.getBoundingClientRect().height || 140)
                    : 0;
                const usableH = Math.max(120, height - topInset);
                const scale = Math.min(
                    width / (gw + padding), usableH / (gh + padding), 1.4);
                const cx = (xExtent[0] + xExtent[1]) / 2;
                const cy = (yExtent[0] + yExtent[1]) / 2;
                const target = d3.zoomIdentity
                    .translate(width / 2, topInset + usableH / 2).scale(scale).translate(-cx, -cy);
                if (firstDataRenderRef.current) svg.call(zoom.transform, target);
                else svg.transition().duration(700).call(zoom.transform, target);
            }
        }

        if (firstDataRenderRef.current && currentNodes.length > 0) {
            firstDataRenderRef.current = false;
        }

        // Only count this view as rendered once it actually has nodes.
        //
        // Claim and evidence data is fetched, so the first render after a
        // navigation has an empty node list. That render was still marking the
        // view as seen, which spent the one-shot "view changed" fit on nothing:
        // the extents were undefined, the fit was skipped, and by the time the
        // data arrived the branch no longer fired. The map simply stayed
        // wherever the previous screen's camera had left it.
        if (currentNodes.length) {
            prevViewMode.current = viewMode;
            prevLayoutMode.current = layoutMode;
        }
        simulationRef.current = sim;

    }, [nodes, edges, viewMode, layoutMode, groupingMode, activeGroup, selected, width, height, scales, evidenceXAxis, reading]);

    useEffect(() => {
        if (!svgRef.current) return;
        const svg = d3.select(svgRef.current);
        const isClaims = viewMode === 'CLAIMS';
        const isEvidence = viewMode === 'EVIDENCE';
        const isTopics = viewMode === 'TOPICS';

        const gLinks = svg.select(".g-links");
        const gLinkHeads = svg.select(".g-link-heads");
        const gNodes = svg.select(".g-nodes");

        // Chevrons must track their ribbon's opacity exactly. Left at full
        // strength they would hover over faded-out lines as detached ticks.
        const fadeHeads = (keep) => gLinkHeads.selectAll(".d3-link-head")
            .transition("highlight-heads").duration(200)
            .style("opacity", function () {
                const d = d3.select(this).datum();
                if (!keep) return 1;
                const key = `${d.source.id || d.source}|${d.target.id || d.target}`;
                return keep.has(key) ? 1 : 0.05;
            });

        // On the evidence view a click pins a paper; elsewhere only hover focuses.
        // Focus has to be a node on THIS screen.
        //
        // Clicking a claim leaves the cursor on it, so `hovered` still holds
        // that claim when the evidence view mounts - and no paper carries a
        // claim's id, so every one of them fell through to "not connected to
        // the focus" and dimmed to 0.15. The whole screen arrived grey, and
        // stayed grey until the pointer moved or something was selected, which
        // cleared the stale value. Same trap on the way back up.
        const presentIds = new Set();
        gNodes.selectAll(".d3-node").each(function (d) { presentIds.add(d.id); });

        // `selected` now focuses on every screen, not only Evidence: on a touch
        // device the first tap selects, and that has to light the node up the
        // way hovering does on a laptop. On a laptop `selected` stays null on
        // Topics and Claims - a click there navigates - so nothing changes.
        const candidate = hovered || (selected && !isReturning ? selected : null);
        const focusNode = candidate && presentIds.has(candidate.id) ? candidate : null;
        const isHovering = !!hovered;

        if (focusNode) {
            const connectedEdgeIds = new Set();
            const connectedNodeIds = new Set([focusNode.id]);

            edges.forEach(e => {
                const sId = e.source?.id ?? e.source;
                const tId = e.target?.id ?? e.target;
                if (sId === focusNode.id || tId === focusNode.id) {
                    connectedEdgeIds.add(`${sId}|${tId}`);
                    connectedNodeIds.add(sId);
                    connectedNodeIds.add(tId);
                }
            });

            if (isEvidence) {
                gLinks.selectAll(".d3-link")
                    .transition("highlight").duration(200)
                    .style("opacity", function () {
                        const d = d3.select(this).datum();
                        const key = `${d.source.id || d.source}|${d.target.id || d.target}`;
                        return connectedEdgeIds.has(key) ? 1 : 0.05;
                    })
                    .attr("stroke-width", function () {
                        const d = d3.select(this).datum();
                        const key = `${d.source.id || d.source}|${d.target.id || d.target}`;
                        const weight = d.weight || 1;
                        return connectedEdgeIds.has(key)
                            ? Math.max(2, Math.sqrt(weight) + 1)
                            : Math.max(1, Math.sqrt(weight));
                    });
                fadeHeads(connectedEdgeIds);
            }

            // Evidence papers open on hover. The compact card cannot show a
            // title, so hovering trades the summary for it and grows the card to
            // fit - and raises the node, or the expanded card would slide under
            // its neighbours. Both states are already in the DOM, so this only
            // toggles display and animates a rect.
            if (isEvidence) {
                // The open card is sized in SCREEN pixels, not world ones.
                //
                // Everything here lives under the zoom transform, so a card
                // built to a fixed world size shrinks with the plot: zoomed out
                // far enough to see all hundred papers - which is the view you
                // are in when you want to skim titles - an 11.5px title renders
                // at three or four. Counter-scaling the node group by 1/k makes
                // the open card the same physical size at every zoom level, and
                // scales the type with it, because scale() takes the text along.
                const k = d3.zoomTransform(svgRef.current).k || 1;
                const inv = 1 / k;

                // Two cards can be open: the one pinned by clicking and the
                // one under the cursor. Keying "open" off the single focus node
                // meant a pinned card closed the moment anything else was
                // hovered - and in a plot this dense, moving the pointer away
                // from a card almost always crosses another one, so pinning
                // looked like it simply did not work.
                const pinnedId = selected && !isReturning ? selected.id : null;
                const hoverId = hovered ? hovered.id : null;

                gNodes.selectAll(".d3-node").each(function (d) {
                    if (d.type === 'claim-anchor') return;
                    const el = d3.select(this);
                    const open = d.id === pinnedId || d.id === hoverId;
                    const cw = d._compactW || d._w || 96;
                    const ch = d._compactH || d._h || 54;

                    // Capped against the viewport, not just a fixed 288px.
                    // Sized in screen pixels the card was the same width on a
                    // phone as on a desktop, which is three quarters of a 390px
                    // screen before any of the detail below is added - it stops
                    // being a card on the map and becomes a takeover.
                    const openW = Math.min(300, width * 0.72);
                    const w = open ? openW : cw;

                    // Height is MEASURED, not estimated.
                    //
                    // It used to be guessed from the title's character count at
                    // an assumed 37 characters a line - optimistic for 12.5px
                    // semibold in a 276px box, where the truth is nearer 30 -
                    // plus a flat 44px for a detail row that wraps to two lines
                    // once a paper has five things to say about itself. Long
                    // titles therefore overflowed a box with overflow: hidden
                    // and lost their detail entirely, while short ones kept it.
                    // That is the "some cards show the data and some do not"
                    // report: it was never about which card, it was about how
                    // long its title happened to be.
                    //
                    // So the content is laid out unconstrained and then asked
                    // how tall it is. scrollHeight reads 0 where nothing lays
                    // out - jsdom - so the old estimate stays as the fallback.
                    let h = ch;
                    if (open) {
                        el.select(".node-paper-compact").style("display", "none");
                        el.select(".node-paper-title").style("display", null);
                        el.select(".node-fo-wrapper")
                            .attr("x", -w / 2).attr("width", w).attr("height", 4000);

                        const titleEl = el.select(".node-paper-title").node();
                        const measured = titleEl ? titleEl.scrollHeight : 0;
                        const fallback = 26 + Math.ceil((d.title || '').length / 30) * 16 + 60;
                        h = Math.min(height * 0.5,
                                     Math.max(ch, (measured > 0 ? measured + 18 : fallback)));
                    }

                    d._paperOpen = open;

                    // Three transitions, three DIFFERENT names. Two with the
                    // same name on one element interrupt each other, and
                    // .node-paper-card was the target of both the ink and the
                    // geometry - so whichever was created second cancelled the
                    // first outright and the card never resized. It looked like
                    // hover working on some cards and not others, because the
                    // survivor depended on which pass had touched them last.
                    el.transition("paper-xform").duration(160)
                        .attr("transform", open
                            ? `translate(${d.x}, ${d.y}) scale(${inv})`
                            : `translate(${d.x}, ${d.y})`);

                    el.select(".node-paper-card")
                        .transition("paper-ink").duration(160)
                        .attr("fill-opacity", open ? 0.30 : (d._strengthFill ?? 0.2))
                        .style("stroke-opacity", open ? 1 : (d._strengthStroke ?? 1));

                    // Geometry is set outright, not animated.
                    //
                    // A named transition on these rects reliably failed to run
                    // for a card opening from compact - scheduled, never
                    // started, so the card kept its small size while every
                    // other signal said it was open. That is the "some cards
                    // show their detail and some do not" symptom. Interrupting
                    // first, raising later and renaming the transition all
                    // failed to shift it, so the animation is not worth the
                    // correctness: the size is applied directly and the fade of
                    // the ink still carries the change.
                    el.selectAll(".node-paper-bg, .node-paper-card, .node-fo-wrapper")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h);

                    if (!open) {
                        el.select(".node-paper-compact").style("display", null);
                        el.select(".node-paper-title").style("display", "none");
                    }

                    // Raised LAST, after the transitions are scheduled. Raising
                    // is a DOM move, and moving the element first left the
                    // geometry transition scheduled but never running - the card
                    // stayed its compact size while every other sign said it was
                    // open. Ordering it after costs nothing: the paint happens
                    // once this pass returns either way.
                    if (open) el.raise();
                });
            }

            // Topics and claims emphasise in place. No transform changes here -
            // moving a node under the cursor makes the map feel unstable.
            if (isTopics || isClaims) {
                gNodes.selectAll(".d3-node").each(function (d) {
                    const isFocus = d.id === focusNode.id;
                    const isCard = isClaims && LayoutEngine.CLAIM_NODE_STYLE === "card";
                    const shape = isTopics ? ".orbit" : (isCard ? ".claim-card-edge" : ".core");
                    const resting = isTopics ? "none"
                        : (isCard
                            ? readableOnWhiteText(STANCE_DIVERGING(LayoutEngine.netFor(d, reading)))
                            : "#ffffff");
                    d3.select(this).select(shape)
                        .transition("focus-ring").duration(150)
                        .attr("stroke", isFocus ? "#1e293b" : resting)
                        .attr("stroke-opacity", isCard && !isFocus ? 0.5 : 1)
                        .attr("stroke-width", isFocus ? 2.5 : (isCard ? 1.5 : 2));
                });
            }

            gNodes.selectAll(".d3-node")
                .transition("highlight").duration(200)
                .style("opacity", function () {
                    const d = d3.select(this).datum();
                    if (d.id === focusNode.id) return 1;
                    if (isTopics || isClaims) return 0.35;
                    if (connectedNodeIds.has(d.id)) return 1;
                    return selected && !isHovering ? 0.08 : 0.15;
                });
        } else {
            if (isEvidence) {
                fadeHeads(null);
                gLinks.selectAll(".d3-link").transition("highlight").duration(200)
                    .style("opacity", 1)
                    .attr("stroke-width", function () {
                        const d = d3.select(this).datum();
                        return Math.max(1, Math.sqrt(d.weight || 1));
                    });
            }
            // Papers collapse back to their summary. Only the ones actually
            // open: this used to rewrite every node's transform, which on a
            // fresh view collided with the fly-in animating the same attribute.
            if (isEvidence) {
                gNodes.selectAll(".d3-node").each(function (d) {
                    if (d.type === 'claim-anchor' || !d._paperOpen) return;
                    d._paperOpen = false;
                    const el = d3.select(this);
                    const w = d._compactW || d._w || 96;
                    const h = d._compactH || d._h || 54;
                    el.transition("paper-xform").duration(160)
                        .attr("transform", `translate(${d.x}, ${d.y})`);
                    el.selectAll(".node-paper-bg, .node-paper-card, .node-fo-wrapper")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h);
                    el.select(".node-paper-card")
                        .transition("paper-ink").duration(160)
                        .attr("fill-opacity", d._strengthFill ?? 0.2)
                        .style("stroke-opacity", d._strengthStroke ?? 1);
                    el.select(".node-paper-compact").style("display", null);
                    el.select(".node-paper-title").style("display", "none");
                });
            }
            if (isTopics || isClaims) {
                const isCard = isClaims && LayoutEngine.CLAIM_NODE_STYLE === "card";
                gNodes.selectAll(".d3-node").each(function (d) {
                    const el = d3.select(this);
                    if (isCard) {
                        // The ring is the card's own border here, so it goes
                        // back to its resting colour rather than to none - and
                        // the last-hovered card keeps a black outline if this
                        // is skipped.
                        el.select(".claim-card-edge").transition("focus-ring").duration(150)
                            .attr("stroke", readableOnWhiteText(
                                STANCE_DIVERGING(LayoutEngine.netFor(d, reading))))
                            .attr("stroke-opacity", 0.5)
                            .attr("stroke-width", 1.5);
                        return;
                    }
                    el.select(".orbit").transition("focus-ring").duration(150)
                        .attr("stroke", "none").attr("stroke-width", 0);
                    el.select(".core").transition("focus-ring").duration(150)
                        .attr("stroke", "#ffffff").attr("stroke-width", 2);
                });
            }
            gNodes.selectAll(".d3-node")
                .transition("highlight").duration(200).style("opacity", 1);
        }
        // width/height are here because the open card is capped against the
        // viewport: without them a resize leaves an already-open card sized for
        // the old one until the next hover.
    }, [hovered, selected, viewMode, edges, isReturning, width, height, reading]);

    return <svg ref={svgRef} className="galaxy-canvas" width={width} height={height} />;
};
