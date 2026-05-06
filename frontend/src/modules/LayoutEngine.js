import * as d3 from "d3";
import { getDeterministicPoint, hashString } from "../utils/d3-helpers";

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

    // --- Universe View Layouts ---

    applyUniverseCentralLayout(nodes, sim) {
        const groups = [...new Set(nodes.map(n => n.group || n.data?.group || "Default"))];
        const groupCenters = {};
        const radius = 450;
        groups.forEach((g, i) => {
            const angle = (i / groups.length) * 2 * Math.PI;
            groupCenters[g] = {
                x: Math.cos(angle) * radius,
                y: Math.sin(angle) * radius + this.graphCenterY
            };
        });

        nodes.forEach(n => {
            n.fx = null;
            n.fy = null;
            if (n.isMenuNode) {
                n.x = 800; n.y = -600;
            } else {
                const group = n.group || 'Default';
                const target = groupCenters[group] || { x: 0, y: this.graphCenterY };
                n.x = target.x + (Math.random() - 0.5) * 60;
                n.y = target.y + (Math.random() - 0.5) * 60;
            }
        });

        sim.force("center", null)
            .force("x", d3.forceX(d => {
                if (d.isMenuNode) return 800;
                return groupCenters[d.group || 'Default']?.x ?? 0;
            }).strength(0.5))
            .force("y", d3.forceY(d => {
                if (d.isMenuNode) return -600;
                return groupCenters[d.group || 'Default']?.y ?? 0;
            }).strength(0.5))
            .force("charge", d3.forceManyBody().strength(d => -30 - (d.val * 1.5)))
            .force("collide", d3.forceCollide().radius(d => (d.val * 2.5 + 15)).iterations(5))
            .force("globalCenter", null)
            .force("link", null);

        return sim;
    }

    applyUniverseTimelineLayout(nodes, sim, universeXScale, timelineHeightScale) {
        const sortedForLayout = [...nodes]
            .filter(n => !n.isMenuNode)
            .sort((a, b) => {
                const yearDiff = (a.data.firstPublicationYear || 0) - (b.data.firstPublicationYear || 0);
                if (yearDiff !== 0) return yearDiff;
                return a.id.localeCompare(b.id);
            });

        let totalHeight = 0;
        const nodeHeights = new Map();

        sortedForLayout.forEach(n => {
            let dynamicSize = 0;
            if (timelineHeightScale && n.data && n.data.worksByDecade) {
                const projectedData = n.data.worksByDecade.map(w =>
                    w.decade === 2020 ? { ...w, works_count: w.works_count * 2.0 } : w
                );
                const maxWorks = d3.max(projectedData, w => w.works_count) || 0;
                dynamicSize = timelineHeightScale(maxWorks);
            }
            if (!dynamicSize) dynamicSize = 10;
            const slotH = 35 + dynamicSize;
            nodeHeights.set(n.id, slotH);
            n._height = slotH;
            totalHeight += slotH;
        });

        const bottomY = (this.height / 2) - 75;
        let currentY = bottomY - totalHeight;

        sortedForLayout.forEach((n) => {
            n.fx = 0;
            const h = nodeHeights.get(n.id);
            n.fy = currentY + (h / 2);
            currentY += h;
            if (n.x === undefined || n.y === undefined) { n.x = n.fx; n.y = n.fy; }
            n.vx = 0; n.vy = 0;
        });

        const menuNode = nodes.find(n => n.isMenuNode);
        if (menuNode) {
            menuNode.fx = 800; menuNode.fy = -600;
            if (menuNode.x === undefined) { menuNode.x = 800; menuNode.y = -600; }
        }

        sim.force("center", null).force("link", null).force("charge", null).force("collide", null)
            .force("x", d3.forceX(0).strength(1))
            .force("y", d3.forceY(d => d.fy).strength(1));

        return sim;
    }

    // --- Galaxy View Layouts ---

    applyGalaxyLayout(nodes, edges, sim, layoutMode, scales) {
        if (layoutMode === 'TIMELINE') {
            const minYear = d3.min(nodes, d => d.minYear) || 1990;
            const maxYear = d3.max(nodes, d => d.maxYear || d.minYear) || 2025;
            const paddingX = this.width * 0.05;
            const effectiveWidth = this.width - (paddingX * 2);
            const xScale = d3.scaleLinear().domain([minYear, maxYear]).range([-effectiveWidth / 2, effectiveWidth / 2]);

            const sorted = [...nodes].sort((a, b) => {
                const startA = a.minYear || d3.min(nodes, n => n.minYear);
                const startB = b.minYear || d3.min(nodes, n => n.minYear);
                if (startA !== startB) return startA - startB;
                return (b.val || 0) - (a.val || 0);
            });

            const maxPapers = d3.max(nodes, d => d.nodeCount || 0) || 50;
            const heightScale = d3.scaleLinear().domain([1, maxPapers]).range([10, 60]);
            const lanes = [];
            const MAX_ROW_HEIGHT = 60;
            const LANE_PADDING = 8;
            const ROW_SPACE = MAX_ROW_HEIGHT + LANE_PADDING;

            sorted.forEach(node => {
                const startYear = node.minYear !== undefined ? node.minYear : minYear;
                const endYear = node.maxYear !== undefined ? node.maxYear : startYear;
                const xStart = xScale(startYear);
                const xEnd = xScale(endYear);
                let width = xEnd - xStart;
                if (width < 30) width = 30;
                const visualXEnd = xStart + width;
                const height = heightScale(node.nodeCount || 1);

                let assignedLaneIndex = -1;
                const X_BUFFER = 10;
                for (let i = 0; i < lanes.length; i++) {
                    if (lanes[i] + X_BUFFER < xStart) {
                        assignedLaneIndex = i;
                        lanes[i] = visualXEnd;
                        break;
                    }
                }
                if (assignedLaneIndex === -1) {
                    assignedLaneIndex = lanes.length;
                    lanes.push(visualXEnd);
                }

                node._laneIndex = assignedLaneIndex;
                node._layoutX = xStart;
                node._layoutWidth = width;
                node._layoutHeight = height;
            });

            sorted.forEach(node => {
                const lane = node._laneIndex;
                let laneOffset = 0;
                if (lane > 0) {
                    const sign = lane % 2 !== 0 ? -1 : 1;
                    const multiplier = Math.ceil(lane / 2);
                    laneOffset = sign * multiplier * ROW_SPACE;
                }
                const centerX = node._layoutX + (node._layoutWidth / 2);
                const centerY = this.graphCenterY + laneOffset;
                node.fx = centerX; node.fy = centerY;
                node.x = centerX; node.y = centerY;
                node.vx = 0; node.vy = 0;
            });

            sim.force("x", null).force("y", null).force("collide", null).force("charge", null)
                .force("link", d3.forceLink(edges).id(d => d.id).strength(0));
        } else {
            const sorted = [...nodes].sort((a, b) => (b.val || 0) - (a.val || 0) || a.id.localeCompare(b.id));
            sorted.forEach((n, i) => {
                n.fx = null; n.fy = null;
                const theta = i * 2.39996;
                const spread = 8;
                const r = spread * Math.sqrt(i) + (n.val * 0.2);
                const tx = Math.cos(theta) * r;
                const ty = Math.sin(theta) * r + this.graphCenterY;
                if (!n.x && !n.y) { n.x = tx; n.y = ty; }
                n._targetX = tx; n._targetY = ty;
            });

            sim.force("link", d3.forceLink(edges).id(d => d.id).strength(0.05))
                .force("x", d3.forceX(d => d._targetX).strength(0.3))
                .force("y", d3.forceY(d => d._targetY).strength(0.3))
                .force("collide", d3.forceCollide().radius(d => (d.val * 0.3 + 5)).iterations(3))
                .force("charge", d3.forceManyBody().strength(d => -5 - (d.val * 0.5)));
        }
        return sim;
    }

    // --- Field / Paper View Layouts ---

    applyFieldLayout(nodes, edges, sim, selectedNode, layoutMode, scales) {
        if (layoutMode === 'TIMELINE') {
            const minYear = d3.min(nodes, d => d.year) || 1990;
            const maxYear = d3.max(nodes, d => d.year) || 2025;
            const xScale = d3.scaleLinear().domain([minYear, maxYear]).range([-this.width * 0.8, this.width * 0.8]);
            const sorted = [...nodes].sort((a, b) => (b.citationCount || 0) - (a.citationCount || 0));
            sorted.forEach((d, i) => {
                const sign = i % 2 === 0 ? 1 : -1;
                const offset = Math.ceil(i / 2) * 50;
                d._targetY = offset * sign;
            });
            sim.force("x", d3.forceX(d => xScale(d.year)).strength(0.9))
                .force("y", d3.forceY(d => d._targetY + this.graphCenterY).strength(0.6))
                .force("collide", d3.forceCollide().radius(d => (d._w ? d._w / 1.8 : 35)).iterations(2))
                .force("charge", d3.forceManyBody().strength(-50))
                .force("link", d3.forceLink(edges).id(d => d.id).strength(0.1));
        } else {
            const linkDist = selectedNode ? 450 : 150;
            sim.force("link", d3.forceLink(edges).id(d => d.id).distance(linkDist));
            if (selectedNode) {
                sim.force("charge", d3.forceManyBody().strength(-3000))
                    .force("collide", d3.forceCollide().radius(d => {
                        if (d.id === selectedNode.id) return d._w * 0.8 + 80;
                        return d._w * 0.6 + 20;
                    }).iterations(4))
                    .force("center-pin", d3.forceRadial(0, selectedNode.x, selectedNode.y).strength(d => d.id === selectedNode.id ? 1 : 0));
                const maxCites = d3.max(nodes, d => d.citationCount) || 1;
                sim.force("neighbor-ring", d3.forceRadial(d => {
                    if (d.id === selectedNode.id) return 0;
                    const importance = (d.citationCount || 0) / maxCites;
                    return 300 + ((1 - importance) * 400);
                }, selectedNode.x, selectedNode.y).strength(0.6));
            } else {
                sim.force("charge", d3.forceManyBody().strength(d => d._isExtra ? -1600 : -600))
                    .force("collide", d3.forceCollide().radius(d => (d._w * 0.6) + (d._isExtra ? 260 : 40)).iterations(4))
                    .force("center", d3.forceCenter(0, this.graphCenterY));
                const maxCites = d3.max(nodes, n => n.citationCount) || 1;
                sim.force("radial", d3.forceRadial(d => (1 - (d.citationCount / maxCites)) * 500, 0, 0).strength(0.3));
            }
        }
        return sim;
    }

    applyHomeLayout(nodes, sim) {
        const spacing = Math.max(300, Math.min(450, this.width * 0.28));
        nodes.forEach((n, i) => {
            n.fx = (i === 0 ? -1 : 1) * spacing;
            n.fy = 0;
        });
        sim.force('x', null).force('y', null).force('charge', null)
            .force('collide', null).force('link', null).force('center', null);
        return sim;
    }

    applyFoodGalaxyLayout(nodes, sim) {
        // Reuse universe central layout — radial by group
        return this.applyUniverseCentralLayout(nodes, sim);
    }

    // Search layout — uses field layout defaults
    applySearchLayout(nodes, edges, sim) {
        return this.applyFieldLayout(nodes, edges, sim, null, 'CENTRAL', {});
    }
}
