import React, { useEffect, useRef, useMemo, useState } from 'react';
import * as d3 from 'd3';
import { roundedHexagonPath, sanitizeId } from '../utils/d3-helpers';
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
            currentNodes.forEach(n => {
                if (n.type === 'claim-anchor') return;   // drawn as a circle, not a card
                if (n.stance === 'neutral') {
                    // Uniform: these sit in the context box, where size would
                    // imply a ranking as evidence they were excluded from.
                    n._w = 132;
                    n._h = 46;
                    return;
                }
                const cites = n.citationCount || 0;
                n._w = 80 + Math.sqrt(cites) * 3;
                n._h = 50 + Math.sqrt(cites) * 1.5;
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

        let gNodes = gMain.select(".g-nodes");
        if (gNodes.empty()) gNodes = gMain.append("g").attr("class", "g-nodes");

        gAxisLayer.lower();
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
        svg.on("click.unselect", (event) => {
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
                const fo = el.append("foreignObject").attr("class", "galaxy-label-fo");
                fo.append("xhtml:div").attr("class", "galaxy-label-div");
            } else if (isEvidence && d.type === 'claim-anchor') {
                // The claim keeps the circle it wore one level up.
                el.append("circle").attr("class", "orbit");
                el.append("circle").attr("class", "core");
                const fo = el.append("foreignObject").attr("class", "galaxy-label-fo");
                fo.append("xhtml:div").attr("class", "galaxy-label-div");
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
                    .html(n => `<div class="node-paper-title" style="width:100%;word-wrap:break-word;overflow-wrap:break-word;white-space:normal;line-height:1.2;text-align:center;">${n.title || n.name || 'Untitled'}</div>`);
            }
            el.append("text").attr("class", "label-main");
            el.append("text").attr("class", "label-sub");
        });

        const allNodes = nodeEnter.merge(nodeJoin);
        allNodes.attr("transform", d => `translate(${d.x}, ${d.y})`);

        const cScale = scales.colorScale || d3.scaleOrdinal(d3.schemeTableau10);
        allNodes.each(function (d) {
            const el = d3.select(this);
            if (isClaims) {
                // Radius arrives in pixels from the OpenAlex match count, so size
                // means "how much has been published around this question".
                // Fill means stance: a claim with evidence is tinted by
                // netSupport; one without is left hollow and grey.
                const r = d.val || 20;
                const decided = (d.supports || 0) + (d.refutes || 0);
                const colour = d.hasEvidence
                    ? STANCE_DIVERGING(LayoutEngine.netFor(d, reading))
                    : STANCE_COLORS.unevaluated;

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
                const labelW = hexR * 1.32;
                const labelH = hexR * 0.62;
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
                    // Type scales with the hexagon: fourteen topics need a
                    // smaller R than five did, and fixed 17px names overflowed
                    // the longer ones ("Movement & Motor Skills").
                    .html(
                        `<div style="font-size:${(hexR * 0.098).toFixed(1)}px;font-weight:700;">${d.name}</div>` +
                        `<div style="font-size:${(hexR * 0.072).toFixed(1)}px;font-weight:500;color:#475569;margin-top:3px;">` +
                        `${d.claimCount} claims · ${d.researchedClaimCount} researched</div>` +
                        `<div style="font-size:${(hexR * 0.066).toFixed(1)}px;color:#64748b;margin-top:2px;">` +
                        `~${(d.openAlexCount || 0).toLocaleString()} papers published</div>`
                    );
                el.select(".label-main").text("");
            } else if (isEvidence && d.type === 'claim-anchor') {
                // Same colour rule as the claims screen, so the node reads as
                // the very one you clicked to get here.
                const r = d.val || 52;
                const colour = STANCE_DIVERGING(LayoutEngine.netFor(d, reading));

                el.select(".orbit")
                    .attr("r", r + 16)
                    .attr("fill", colour).attr("fill-opacity", 0.10)
                    .attr("stroke", colour).attr("stroke-opacity", 0.55)
                    .attr("stroke-width", 2).attr("stroke-dasharray", "5 4");
                el.select(".core")
                    .attr("r", r)
                    .attr("fill", colour).attr("fill-opacity", 0.9)
                    .attr("stroke", "#ffffff").attr("stroke-width", 3);

                const labelW = 320;
                el.select(".galaxy-label-fo")
                    .attr("x", -labelW / 2).attr("y", r + 24)
                    .attr("width", labelW).attr("height", 130)
                    .style("overflow", "visible").style("pointer-events", "none");
                el.select(".galaxy-label-div")
                    .style("width", `${labelW}px`)
                    .style("display", "flex").style("flex-direction", "column")
                    .style("align-items", "center").style("text-align", "center")
                    .style("font-family", "Inter, system-ui, sans-serif")
                    .style("color", "#1e293b").style("line-height", "1.3")
                    .html(
                        `<div style="font-size:13px;font-weight:700;">${d.claim || ""}</div>` +
                        `<div style="font-size:11px;margin-top:4px;">` +
                        `<span style="color:${STANCE_COLORS.supports};font-weight:700;">${d.supports || 0}</span>` +
                        `<span style="color:#94a3b8;"> for · </span>` +
                        `<span style="color:${STANCE_COLORS.refutes};font-weight:700;">${d.refutes || 0}</span>` +
                        `<span style="color:#94a3b8;"> against · ${d.neutral || 0} neutral</span></div>`
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

                el.select(".node-paper-bg").attr("x", -w / 2).attr("y", -h / 2)
                    .attr("width", w).attr("height", h).attr("fill-opacity", 1);
                el.select(".node-paper-card").attr("x", -w / 2).attr("y", -h / 2).attr("width", w).attr("height", h)
                    .attr("fill", cardColor).attr("fill-opacity", isNeutral ? 0.14 : 0.2)
                    .style("stroke", cardColor).style("stroke-width", isNeutral ? 1.25 : 2)
                    .style("stroke-opacity", 1);
                el.select(".node-fo-wrapper").attr("x", -w / 2).attr("y", -h / 2).attr("width", w).attr("height", h);
                el.select(".node-paper-title")
                    .style("font-size", `${Math.min(12, Math.max(9, w / 12))}px`)
                    .style("width", "100%").style("word-wrap", "break-word")
                    .style("white-space", "normal").style("text-align", "center")
                    .style("overflow-wrap", "anywhere");
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
                const gw = xExtent[1] - xExtent[0];
                const gh = yExtent[1] - yExtent[0];
                const scale = Math.min(width / (gw + padding * 2), height / (gh + padding * 2), 2);
                const cx = (xExtent[0] + xExtent[1]) / 2;
                const cy = (yExtent[0] + yExtent[1]) / 2;
                svg.transition().duration(1000).call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-cx, -cy));
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
                const padding = hexR + 70;
                const gw = (xExtent[1] - xExtent[0]) + hexR * 2;
                const gh = (yExtent[1] - yExtent[0]) + hexR * 2;
                const scale = Math.min(
                    width / (gw + padding), height / (gh + padding), 1.4);
                const cx = (xExtent[0] + xExtent[1]) / 2;
                const cy = (yExtent[0] + yExtent[1]) / 2;
                const target = d3.zoomIdentity
                    .translate(width / 2, height / 2).scale(scale).translate(-cx, -cy);
                if (firstDataRenderRef.current) svg.call(zoom.transform, target);
                else svg.transition().duration(700).call(zoom.transform, target);
            }
        }

        if (firstDataRenderRef.current && currentNodes.length > 0) {
            firstDataRenderRef.current = false;
        }

        prevViewMode.current = viewMode;
        prevLayoutMode.current = layoutMode;
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
        const focusNode = hovered || (isEvidence && selected && !isReturning ? selected : null);
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

            // Topics and claims emphasise in place. No transform changes here -
            // moving a node under the cursor makes the map feel unstable.
            if (isTopics || isClaims) {
                gNodes.selectAll(".d3-node").each(function (d) {
                    const isFocus = d.id === focusNode.id;
                    d3.select(this).select(isTopics ? ".orbit" : ".core")
                        .transition("focus-ring").duration(150)
                        .attr("stroke", isFocus ? "#1e293b" : (isTopics ? "none" : "#ffffff"))
                        .attr("stroke-width", isFocus ? 2.5 : 2);
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
            if (isTopics || isClaims) {
                gNodes.selectAll(".d3-node").each(function () {
                    const el = d3.select(this);
                    el.select(".orbit").transition("focus-ring").duration(150)
                        .attr("stroke", "none").attr("stroke-width", 0);
                    el.select(".core").transition("focus-ring").duration(150)
                        .attr("stroke", "#ffffff").attr("stroke-width", 2);
                });
            }
            gNodes.selectAll(".d3-node")
                .transition("highlight").duration(200).style("opacity", 1);
        }
    }, [hovered, selected, viewMode, edges, isReturning]);

    return <svg ref={svgRef} className="galaxy-canvas" width={width} height={height} />;
};
