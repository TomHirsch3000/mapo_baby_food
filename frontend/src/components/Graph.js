import React, { useEffect, useRef, useMemo, useState } from 'react';
import * as d3 from 'd3';
import { roundedHexagonPath, getDeterministicPoint, hashString, EDGE_COLORS, getEdgeId, sanitizeId, generateHexPositions } from '../utils/d3-helpers';
import { LayoutEngine } from '../modules/LayoutEngine';
import { getIconPath, shouldShowIcon } from '../config/categoryIcons';

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
    onGalaxyClick,
    onGroupClick,
    onBackToUniverse,
    onBackToGalaxy,
    scales,
    isReturning,
    width,
    height,
    onNodeDoubleClick,
    isLoadingDetail
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

    const handlersRef = useRef({ onNodeClick, onNodeHover, onBackgroundClick, onGalaxyClick, onGroupClick, onNodeDoubleClick });
    handlersRef.current = { onNodeClick, onNodeHover, onBackgroundClick, onGalaxyClick, onGroupClick, onNodeDoubleClick };

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
        const isUniverse = viewMode === 'UNIVERSE';
        const isGalaxy = viewMode === 'GALAXY';
        const isSearch = viewMode === 'SEARCH';
        const isField = viewMode === 'FIELD' || viewMode === 'DETAIL' || isSearch;

        const currentNodes = nodes.map(n => ({ ...n }));
        const currentEdges = edges.map(e => ({ ...e }));

        if (isField) {
            currentNodes.forEach(n => {
                const cites = n.citationCount || 0;
                const hasIcon = shouldShowIcon(n);
                if (hasIcon) {
                    n._w = 70 + Math.sqrt(cites) * 2;
                    n._h = 100 + Math.sqrt(cites) * 2.5;
                    n._hasIcon = true;
                } else {
                    n._w = 80 + Math.sqrt(cites) * 3;
                    n._h = 50 + Math.sqrt(cites) * 1.5;
                    n._hasIcon = false;
                }
            });
        }

        let gMain = svg.select(".g-main");
        if (gMain.empty()) {
            const gRoot = svg.append("g");
            gMain = gRoot.append("g").attr("class", "g-main");
        }

        let gLinks = gMain.select(".g-links");
        if (gLinks.empty()) gLinks = gMain.append("g").attr("class", "g-links");

        let gAxisLayer = gMain.select(".g-axis-layer");
        if (gAxisLayer.empty()) gAxisLayer = gMain.append("g").attr("class", "g-axis-layer");

        let gNodes = gMain.select(".g-nodes");
        if (gNodes.empty()) gNodes = gMain.append("g").attr("class", "g-nodes");

        gAxisLayer.lower();
        gLinks.lower();
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
            gNodes.selectAll("*").interrupt().remove();
            gNodes.style("opacity", 0);
            gLinks.style("opacity", 0);
        }

        const sim = d3.forceSimulation(currentNodes);

        if (isUniverse) {
            if (layoutMode === 'TIMELINE') {
                layoutEngine.current.applyUniverseTimelineLayout(currentNodes, sim, scales.universeXScale, scales.timelineHeightScale);
            } else {
                layoutEngine.current.applyUniverseCentralLayout(currentNodes, sim);
            }
        } else if (isGalaxy) {
            layoutEngine.current.applyGalaxyLayout(currentNodes, currentEdges, sim, layoutMode, scales);
        } else if (isSearch) {
            layoutEngine.current.applySearchLayout(currentNodes, currentEdges, sim);
        } else {
            layoutEngine.current.applyFieldLayout(currentNodes, currentEdges, sim, selected, layoutMode, scales);
        }

        const DRY_RUN_TICKS = (isGalaxy || isField) ? 300 : 120;
        sim.stop();
        sim.alpha(1);
        for (let i = 0; i < DRY_RUN_TICKS; ++i) {
            sim.tick();
        }

        const getEdgeKey = (d) => `${(isGalaxy || isField) ? "G" : "P"}|${d.source.id || d.source}|${d.target.id || d.target}`;
        const getGradientId = (d) => `link-gradient-${sanitizeId(getEdgeKey(d))}`;
        const defs = svg.select("defs").empty() ? svg.append("defs") : svg.select("defs");

        const updateLinkPaths = (s) => {
            s.attr("d", d => {
                const src = d.source;
                const tgt = d.target;

                if (isGalaxy) {
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
                } else if (isField) {
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

                    const wStart = 2;
                    const wEnd = 8;

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

                    return `M${s1x},${s1y} Q${c1x},${c1y} ${t1x},${t1y} L${t2x},${t2y} Q${c2x},${c2y} ${s2x},${s2y} Z`;
                } else {
                    return `M${src.x},${src.y} L${tgt.x},${tgt.y}`;
                }
            });
            if (isGalaxy) {
                defs.selectAll(".link-gradient")
                    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
                    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
            }
        };

        const linkJoin = gLinks.selectAll(".d3-link").data(currentEdges, getEdgeKey);
        linkJoin.exit().remove();
        const linkEnter = linkJoin.enter().append("path")
            .attr("class", `d3-link ${(isGalaxy || isField) ? 'type-galaxy-link' : 'type-paper-link'}`)
            .attr("fill", isField ? "#999" : "none")
            .attr("stroke-linecap", "round");

        const allLinks = linkEnter.merge(linkJoin);

        if (isGalaxy || isField) {
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
                grad.select(".grad-stop-start").attr("stop-color", srcColor).attr("stop-opacity", isField ? 0.8 : 0.6);
                grad.select(".grad-stop-end").attr("stop-color", tgtColor).attr("stop-opacity", isField ? 0.2 : 0.6);
                if (isField) {
                    d3.select(this).attr("fill", `url(#${id})`).attr("stroke", "none");
                } else {
                    d3.select(this).attr("stroke", `url(#${id})`).attr("fill", "none");
                }
            });
        }

        updateLinkPaths(allLinks);
        allLinks.attr("stroke-width", d => (isGalaxy || isField) ? Math.max(2, Math.sqrt(d.weight || 1)) : 1)
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
            if (isUniverse && !d.isMenuNode) {
                el.append("path").attr("class", "orbit");
                el.append("path").attr("class", "core");
                el.append("image")
                    .attr("class", "node-icon")
                    .style("pointer-events", "none")
                    .style("display", "none");
                const fo = el.append("foreignObject").attr("class", "hex-label-fo");
                fo.append("xhtml:div").attr("class", "hex-label-div");
            } else if (isGalaxy) {
                if (layoutMode === 'TIMELINE') {
                    el.append("rect").attr("class", "orbit");
                    el.append("rect").attr("class", "core").attr("display", "none");
                } else {
                    el.append("circle").attr("class", "orbit");
                    el.append("circle").attr("class", "core");
                    const fo = el.append("foreignObject").attr("class", "galaxy-label-fo");
                    fo.append("xhtml:div").attr("class", "galaxy-label-div");
                }
            } else if (isField) {
                if (d.isSearchDummy) {
                    el.append("circle").attr("class", "search-dummy-orbit").attr("r", 90);
                    el.append("circle").attr("class", "search-dummy-core").attr("r", 72);
                    const fo = el.append("foreignObject")
                        .attr("class", "search-dummy-fo")
                        .attr("x", -72).attr("y", -72)
                        .attr("width", 144).attr("height", 144);
                    fo.append("xhtml:div").attr("class", "search-dummy-label");
                } else {
                    const w = d._w || 80;
                    const h = d._h || 50;
                    el.append("rect").attr("class", "node-paper-bg")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h)
                        .attr("fill", "#ffffff").attr("rx", 6);
                    el.append("rect").attr("class", "node-paper-card")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h).attr("rx", 6);
                    const fo = el.append("foreignObject").attr("class", "node-fo-wrapper")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h);
                    fo.append("xhtml:div")
                        .attr("class", d => `node-paper-content${d._hasIcon ? ' node-paper-vertical' : ''}`)
                        .style("width", "100%").style("height", "100%")
                        .style("display", "flex")
                        .style("flex-direction", d => d._hasIcon ? "column" : "row")
                        .style("align-items", "center")
                        .style("justify-content", d => d._hasIcon ? "flex-start" : "center")
                        .style("text-align", "center").style("overflow", "hidden")
                        .style("padding", "4px").style("box-sizing", "border-box")
                        .html(d => {
                            const title = `<div class="node-paper-title" style="width:100%;word-wrap:break-word;overflow-wrap:break-word;white-space:normal;line-height:1.2;text-align:center;">${d.title || d.name || 'Untitled'}</div>`;
                            if (d._hasIcon) {
                                const iconPath = getIconPath(d);
                                const iconUrl = resolveIconHref(iconPath);
                                return title + `<div class="node-paper-icon-wrap" style="flex:1;width:100%;display:flex;align-items:center;justify-content:center;overflow:hidden;min-height:0;"><img class="node-paper-icon" src="${iconUrl}" alt="" style="max-width:90%;max-height:90%;object-fit:contain;" /></div>`;
                            }
                            return title;
                        });
                }
            } else {
                el.append("rect").attr("class", "node-rect").attr("rx", 6);
                el.append("foreignObject").attr("class", "fo-content").append("xhtml:div").attr("class", "node-fo");
            }
            el.append("text").attr("class", "label-main");
            el.append("text").attr("class", "label-sub");
            if (isUniverse) el.append("text").attr("class", "label-right");
        });

        const allNodes = nodeEnter.merge(nodeJoin);
        allNodes.attr("transform", d => `translate(${d.x}, ${d.y})`);

        const cScale = scales.colorScale || d3.scaleOrdinal(d3.schemeTableau10);
        allNodes.each(function (d) {
            const el = d3.select(this);
            if (isGalaxy) {
                if (layoutMode === 'TIMELINE') {
                    const w = d._layoutWidth || 30;
                    const h = d._layoutHeight || 14;
                    el.select(".orbit")
                        .attr("x", -w / 2).attr("y", -h / 2)
                        .attr("width", w).attr("height", h)
                        .attr("rx", 6)
                        .attr("fill", cScale(d.xGroup))
                        .attr("fill-opacity", 0.6)
                        .attr("stroke", "none").attr("r", null);
                    el.select(".label-main")
                        .text((d.name || "").substring(0, 30))
                        .attr("x", 0).attr("y", -h / 2 - 5)
                        .attr("dy", 0).attr("text-anchor", "middle")
                        .style("font-size", "14px").style("fill", "#64748b").style("pointer-events", "none");
                    el.select(".label-sub").text("");
                } else {
                    const val = d.val || 20;
                    const radius = val * 0.16;
                    el.select(".orbit").attr("r", radius).attr("fill", cScale(d.xGroup)).attr("fill-opacity", 0.15)
                        .attr("width", null).attr("height", null);
                    el.select(".core").attr("r", radius * 0.6).attr("fill", cScale(d.xGroup));

                    const labelW = Math.max(120, radius * 3);
                    const labelH = 60;
                    const labelY = radius + 4;
                    el.select(".galaxy-label-fo")
                        .attr("x", -labelW / 2).attr("y", labelY)
                        .attr("width", labelW).attr("height", labelH)
                        .style("overflow", "visible").style("pointer-events", "none");
                    el.select(".galaxy-label-div")
                        .style("width", `${labelW}px`).style("height", `${labelH}px`)
                        .style("display", "flex").style("flex-direction", "column")
                        .style("align-items", "center").style("justify-content", "flex-start")
                        .style("text-align", "center").style("font-family", "Inter, system-ui, sans-serif")
                        .style("font-size", `${Math.max(10, Math.min(20, val * 0.04))}px`)
                        .style("color", "#1e293b").style("line-height", "1.2")
                        .html(`<div style="font-weight:600;margin-bottom:2px;">${d.name || ""}</div>${d.nodeCount ? `<div style="font-weight:400;font-size:0.8em;color:#475569;">${d.nodeCount} papers</div>` : ""}`);
                    el.select(".label-main").text("");
                    el.select(".label-sub").text("");
                }
            } else if (isUniverse) {
                const val = d.val || 20;
                if (!d.isMenuNode) {
                    if (layoutMode === 'TIMELINE' && d.data?.worksByDecade && scales.universeXScale) {
                        el.select(".orbit").attr("d", null).attr("r", null);
                        el.select(".core").attr("d", null).attr("r", null);
                        const h = d._height || 60;
                        const projectionFactor = 2.0;
                        const dataForChart = d.data.worksByDecade.map(w =>
                            w.decade === 2020 ? { ...w, works_count: w.works_count * projectionFactor } : w
                        );
                        const maxWorks = d3.max(dataForChart, w => w.works_count) || 1;
                        const yScaleLocal = d3.scaleLinear().domain([0, maxWorks]).range([0, h - 10]);
                        const areaGenerator = d3.area()
                            .x(D => scales.universeXScale(D.decade))
                            .y0(D => -yScaleLocal(D.works_count) / 2)
                            .y1(D => yScaleLocal(D.works_count) / 2)
                            .curve(d3.curveMonotoneX);
                        el.select(".orbit").attr("d", areaGenerator(dataForChart))
                            .attr("fill", cScale(d.group || d.data?.group || "Default"))
                            .attr("fill-opacity", 0.6).attr("stroke", "none");
                        el.select(".core").attr("d", null).attr("r", 0);
                        const lastYearX = scales.universeXScale(2020);
                        el.select(".label-main").text(d.name)
                            .attr("x", lastYearX + 20).attr("y", 0)
                            .attr("dx", 0).attr("dy", 5)
                            .attr("text-anchor", "start")
                            .style("font-size", "18px").style("font-weight", "500").style("fill", "#334155");
                    } else {
                        el.select(".orbit")
                            .attr("d", roundedHexagonPath(val * 2.5))
                            .attr("fill", cScale(d.group || d.data?.group || "Default"))
                            .attr("fill-opacity", 0.4)
                            .attr("stroke", d.hasPapers ? "#475569" : "none")
                            .attr("stroke-width", d.hasPapers ? 12 : 0);
                        el.select(".core")
                            .attr("d", roundedHexagonPath(val * 0.8))
                            .attr("r", null)
                            .attr("fill", cScale(d.group || d.data?.group || "Default"))
                            .style("filter", "blur(1px)");

                        let iconEl = el.select(".node-icon");
                        if (d.iconPath) {
                            const iconSize = val * 1.8;
                            const href = resolveIconHref(d.iconPath);
                            iconEl.attr("href", href)
                                .attr("width", iconSize).attr("height", iconSize)
                                .attr("x", -iconSize / 2).attr("y", -iconSize / 2 - 15)
                                .style("display", null);
                        } else {
                            iconEl.style("display", "none");
                        }

                        const hexR = val * 2.5;
                        const labelW = hexR * 1.4;
                        const labelH = hexR * 0.8;
                        const labelY = hexR * 0.25;
                        el.select(".hex-label-fo")
                            .attr("x", -labelW / 2).attr("y", labelY)
                            .attr("width", labelW).attr("height", labelH)
                            .style("overflow", "visible").style("pointer-events", "none");
                        el.select(".hex-label-div")
                            .style("width", `${labelW}px`).style("height", `${labelH}px`)
                            .style("display", "flex").style("align-items", "center")
                            .style("justify-content", "center").style("text-align", "center")
                            .style("font-family", "Inter, system-ui, sans-serif")
                            .style("font-size", `${Math.max(10, Math.min(16, val * 0.28))}px`)
                            .style("font-weight", "600").style("color", "#1e293b")
                            .style("line-height", "1.2").style("word-break", "break-word")
                            .style("overflow-wrap", "break-word").style("white-space", "normal")
                            .style("padding", "0 4px").style("box-sizing", "border-box")
                            .text(d.name);
                        el.select(".label-main").text("");
                    }
                } else {
                    el.select(".orbit").attr("r", val * 2.5);
                }
            } else if (isField) {
                if (d.isSearchDummy) {
                    el.select(".search-dummy-orbit").attr("r", 90).attr("fill", "#6366f1").attr("fill-opacity", 0.12)
                        .attr("stroke", "#6366f1").attr("stroke-width", 2).attr("stroke-dasharray", "6 3");
                    el.select(".search-dummy-core").attr("r", 72).attr("fill", "#6366f1").attr("fill-opacity", 0.18);
                    el.select(".search-dummy-fo").attr("x", -72).attr("y", -72).attr("width", 144).attr("height", 144);
                    el.select(".search-dummy-label")
                        .style("width", "144px").style("height", "144px")
                        .style("display", "flex").style("flex-direction", "column")
                        .style("align-items", "center").style("justify-content", "center")
                        .style("text-align", "center").style("font-family", "Inter, system-ui, sans-serif")
                        .style("padding", "8px").style("box-sizing", "border-box")
                        .html(`<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#6366f1;margin-bottom:4px;">Search</div><div style="font-size:13px;font-weight:700;color:#1e293b;line-height:1.3;word-break:break-word;">${d.name || d.title || ''}</div>`);
                } else {
                    const w = d._w || 80;
                    const h = d._h || 50;
                    const nodeTypeColors = { core: '#6366f1', foundation: '#10b981', impact: '#f59e0b' };
                    const cardColor = (isSearch && d.nodeType && nodeTypeColors[d.nodeType])
                        ? nodeTypeColors[d.nodeType] : cScale(d.xGroup || d.field);

                    el.select(".node-paper-bg").attr("x", -w / 2).attr("y", -h / 2).attr("width", w).attr("height", h);
                    el.select(".node-paper-card").attr("x", -w / 2).attr("y", -h / 2).attr("width", w).attr("height", h)
                        .attr("fill", cardColor).attr("fill-opacity", 0.2)
                        .style("stroke", cardColor).style("stroke-width", 2);
                    el.select(".node-fo-wrapper").attr("x", -w / 2).attr("y", -h / 2).attr("width", w).attr("height", h);
                    el.select(".node-paper-title")
                        .style("font-size", `${Math.min(12, Math.max(9, w / 12))}px`)
                        .style("width", "100%").style("word-wrap", "break-word")
                        .style("white-space", "normal").style("text-align", "center")
                        .style("overflow-wrap", "anywhere");
                }
            }
        });

        if ((isUniverse || isGalaxy || isField) && layoutMode === 'TIMELINE') {
            let xAxisScale = null;
            if (isUniverse) {
                xAxisScale = scales.universeXScale;
            } else if (isGalaxy) {
                const minYear = d3.min(currentNodes, d => d.minYear) || 1990;
                const maxYear = d3.max(currentNodes, d => d.maxYear || d.minYear) || 2025;
                const padding = width * 0.05;
                const effectiveWidth = width - (padding * 2);
                xAxisScale = d3.scaleLinear().domain([minYear, maxYear]).range([-effectiveWidth / 2, effectiveWidth / 2]);
            } else if (isField) {
                const minYear = d3.min(currentNodes, d => d.year) || 1990;
                const maxYear = d3.max(currentNodes, d => d.year) || 2025;
                xAxisScale = d3.scaleLinear().domain([minYear, maxYear]).range([-width * 0.8, width * 0.8]);
            }

            if (xAxisScale) {
                const axisBottom = d3.axisBottom(xAxisScale).tickFormat(d3.format("d")).ticks(10);
                const yExtent = d3.extent(currentNodes, d => d.y);
                const lowestY = (yExtent[1] !== undefined && !isNaN(yExtent[1])) ? yExtent[1] : (height / 2 - 40);
                const axisY = isUniverse ? (height / 2 - 40) : (lowestY + 60);
                gAxisLayer.attr("transform", `translate(0, ${axisY})`).style("opacity", 1).call(axisBottom);
                gAxisLayer.selectAll("text").style("fill", "#64748b").style("font-size", "18px");
                gAxisLayer.selectAll("line").style("stroke", "#cbd5e1");
                gAxisLayer.selectAll("path").style("stroke", "#cbd5e1");
            }
        } else {
            gAxisLayer.style("opacity", 0);
        }

        if (prevViewMode.current !== viewMode && (viewMode === 'GALAXY' || viewMode === 'FIELD' || viewMode === 'SEARCH')) {
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
            allLinks.transition("flyin-links-stroke").delay(600).duration(500).attr("stroke-opacity", 0.6);
        } else {
            gNodes.style("opacity", 1);
            gLinks.style("opacity", 1);
            allLinks.attr("stroke-opacity", 0.6);

            if (viewMode === 'SEARCH' && currentNodes.length > 1) {
                const xExtent = d3.extent(currentNodes, d => d.x);
                const yExtent = d3.extent(currentNodes, d => d.y);
                const padding = 150;
                if (xExtent[0] !== undefined && yExtent[0] !== undefined) {
                    const gw = xExtent[1] - xExtent[0];
                    const gh = yExtent[1] - yExtent[0];
                    const scale = Math.min(width / (gw + padding * 2), height / (gh + padding * 2), 2);
                    const cx = (xExtent[0] + xExtent[1]) / 2;
                    const cy = (yExtent[0] + yExtent[1]) / 2;
                    svg.transition().duration(800).call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-cx, -cy));
                }
            }

            if (viewMode === 'UNIVERSE' && layoutMode === 'CENTRAL' && (firstDataRenderRef.current || prevLayoutMode.current !== layoutMode)) {
                const layoutNodes = currentNodes.filter(n => !n.isMenuNode);
                const xExtent = d3.extent(layoutNodes, d => d.x);
                const yExtent = d3.extent(layoutNodes, d => d.y);
                const padding = 100;
                if (xExtent[0] !== undefined && yExtent[0] !== undefined) {
                    const gw = xExtent[1] - xExtent[0];
                    const gh = yExtent[1] - yExtent[0];
                    const scale = Math.min(width / (gw + padding * 2), height / (gh + padding * 2), 2);
                    const cx = (xExtent[0] + xExtent[1]) / 2;
                    const cy = (yExtent[0] + yExtent[1]) / 2;
                    if (firstDataRenderRef.current) {
                        svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-cx, -cy));
                    } else {
                        svg.transition().duration(1000).call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-cx, -cy));
                    }
                }
            }
        }

        if (firstDataRenderRef.current && currentNodes.length > 0) {
            firstDataRenderRef.current = false;
        }

        prevViewMode.current = viewMode;
        prevLayoutMode.current = layoutMode;
        simulationRef.current = sim;

    }, [nodes, edges, viewMode, layoutMode, groupingMode, activeGroup, selected, width, height, scales]);

    useEffect(() => {
        if (!svgRef.current) return;
        const svg = d3.select(svgRef.current);
        const isGalaxy = viewMode === 'GALAXY';
        const isField = viewMode === 'FIELD';
        const isDetail = viewMode === 'DETAIL';
        const isSearch = viewMode === 'SEARCH';
        const isUniverseTimeline = viewMode === 'UNIVERSE' && layoutMode === 'TIMELINE';
        const isUniverseCentral = viewMode === 'UNIVERSE' && layoutMode === 'CENTRAL';

        if (isGalaxy || isField || isDetail || isSearch || isUniverseTimeline || isUniverseCentral) {
            const gLinks = svg.select(".g-links");
            const gNodes = svg.select(".g-nodes");
            const currentEdges = edges;

            const focusNode = hovered || ((isField || isDetail || isSearch) && selected && !isReturning ? selected : null);
            const isHovering = !!hovered;

            if (focusNode) {
                const connectedEdgeIds = new Set();
                const connectedNodeIds = new Set();
                connectedNodeIds.add(focusNode.id);

                if (isGalaxy || isField || isDetail || isSearch) {
                    const prefix = (isField || isDetail || isSearch) ? "P" : "G";
                    const keyFn = (s, t) => `${prefix}|${s}|${t}`;
                    currentEdges.forEach(e => {
                        const sId = (e.source && e.source.id) ? e.source.id : e.source;
                        const tId = (e.target && e.target.id) ? e.target.id : e.target;
                        if (sId === focusNode.id || tId === focusNode.id) {
                            connectedEdgeIds.add(keyFn(sId, tId));
                            connectedNodeIds.add(sId);
                            connectedNodeIds.add(tId);
                        }
                    });
                }

                if (isGalaxy || isField || isDetail || isSearch) {
                    const prefix = (isField || isDetail || isSearch) ? "P" : "G";
                    gLinks.selectAll(".d3-link")
                        .transition("highlight").duration(200)
                        .attr("stroke-opacity", function () {
                            if (isField || isDetail || isSearch) return null;
                            const d = d3.select(this).datum();
                            const s = (d.source.id || d.source);
                            const t = (d.target.id || d.target);
                            const key = `${prefix}|${s}|${t}`;
                            return connectedEdgeIds.has(key) ? 0.8 : 0.05;
                        })
                        .style("opacity", function () {
                            if (!isField && !isDetail && !isSearch) return null;
                            const d = d3.select(this).datum();
                            const s = (d.source.id || d.source);
                            const t = (d.target.id || d.target);
                            const key = `${prefix}|${s}|${t}`;
                            if (isDetail || isSearch) return connectedEdgeIds.has(key) ? 1 : 0;
                            if (isField && selected) {
                                const isConnectedToSelected = s === selected.id || t === selected.id;
                                if (!isConnectedToSelected) return 0;
                                if (isHovering && !connectedEdgeIds.has(key)) return 0.2;
                                return 1;
                            }
                            if (isField && isHovering) return connectedEdgeIds.has(key) ? 1 : 0.05;
                            return connectedEdgeIds.has(key) ? 1 : 0;
                        })
                        .attr("stroke-width", function () {
                            const d = d3.select(this).datum();
                            const s = (d.source.id || d.source);
                            const t = (d.target.id || d.target);
                            const key = `${prefix}|${s}|${t}`;
                            const weight = d.weight || 1;
                            return connectedEdgeIds.has(key) ? Math.max(2, Math.sqrt(weight) + 1) : Math.max(1, Math.sqrt(weight));
                        });
                }

                gNodes.selectAll(".d3-node")
                    .classed("node-shimmer", d => d.id === focusNode.id && isHovering)
                    .transition("highlight").duration(200)
                    .style("opacity", function () {
                        const d = d3.select(this).datum();
                        if (d.id === focusNode.id) return 1;
                        if (d.isSearchDummy) return 1;
                        if (isGalaxy || isField || isSearch) {
                            if (connectedNodeIds.has(d.id)) return 1;
                            return ((isField || isSearch) && selected && !isHovering) ? 0 : 0.1;
                        }
                        if (isDetail) return connectedNodeIds.has(d.id) ? 1 : 0.02;
                        return 1;
                    });
            } else {
                if (isGalaxy || isField) {
                    gLinks.selectAll(".d3-link").transition("highlight").duration(200)
                        .attr("stroke-opacity", isField ? null : 0.6)
                        .style("opacity", isField ? 1 : null)
                        .attr("stroke-width", function () {
                            const d = d3.select(this).datum();
                            return Math.max(1, Math.sqrt(d.weight || 1));
                        });
                } else if (isDetail || isSearch) {
                    gLinks.selectAll(".d3-link").transition("highlight").duration(200)
                        .style("opacity", isSearch ? 0.5 : 0).attr("stroke-opacity", null);
                }
                gNodes.selectAll(".d3-node").classed("node-shimmer", false)
                    .transition("highlight").duration(200).style("opacity", 1);
            }
        }
    }, [hovered, selected, viewMode, edges, layoutMode, isReturning]);

    return <svg ref={svgRef} className="galaxy-canvas" width={width} height={height} />;
};
