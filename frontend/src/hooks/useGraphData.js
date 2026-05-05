import { useState, useEffect, useMemo, useRef } from 'react';
import * as d3 from 'd3';

export const useGraphData = (viewMode, activeGalaxy, groupingMode, yGroupingMode, activeGroup, selected, detailFilter, setShowTimeoutPrompt, searchFilter) => {
    const [universeData, setUniverseData] = useState(null);
    const [rawNodes, setRawNodes] = useState([]);
    const [rawEdges, setRawEdges] = useState([]);
    const [isLoadingDetail, setIsLoadingDetail] = useState(false);
    const [searchResult, setSearchResult] = useState(null);
    const [paperIndex, setPaperIndex] = useState([]);
    const abortControllerRef = useRef(null);
    const nodeByIdRef = useRef(new Map());

    useEffect(() => {
        fetch("./universe.json")
            .then(r => r.json())
            .then(data => setUniverseData(data))
            .catch(err => console.error("Failed to load universe data:", err));
    }, []);

    useEffect(() => {
        if (!universeData) return;
        const galaxiesWithPapers = (universeData.nodes || []).filter(g => g.hasPapers && g.nodesFile);
        Promise.all(
            galaxiesWithPapers.map(g =>
                fetch(`./${g.nodesFile}`)
                    .then(r => r.json())
                    .then(nodes => nodes.map(n => ({
                        id: n.id || n.paperId,
                        title: n.title ? n.title.replace(/<[^>]+>/g, '') : '',
                        primaryField: n.primaryField,
                        galaxyId: g.id,
                        galaxyName: g.name,
                    })))
                    .catch(() => [])
            )
        ).then(arrays => setPaperIndex(arrays.flat()));
    }, [universeData]);

    useEffect(() => {
        if (!activeGalaxy || !universeData) return;
        const galaxy = universeData.nodes?.find(g => g.id === activeGalaxy);
        if (!galaxy || !galaxy.nodesFile) return;

        Promise.all([
            fetch(`./${galaxy.nodesFile}`).then(r => r.json()),
            fetch(`./${galaxy.edgesFile}`).then(r => r.json()),
        ])
            .then(([n, e]) => {
                setRawNodes(Array.isArray(n) ? n : []);
                setRawEdges(Array.isArray(e) ? e : []);
            })
            .catch(err => console.error("Failed to load galaxy data:", err));
    }, [activeGalaxy, universeData]);

    useEffect(() => {
        if (viewMode !== 'DETAIL' || !detailFilter) return;
        setIsLoadingDetail(true);
        if (abortControllerRef.current) abortControllerRef.current.abort();
        const controller = new AbortController();
        abortControllerRef.current = controller;

        const { id, minCitations, maxPapers } = detailFilter;
        const backendUrl = process.env.REACT_APP_API_URL || 'http://localhost:5001';
        const url = `${backendUrl}/api/paper/${id}/details?min_citations=${minCitations}&max_papers=${maxPapers}`;

        const timeoutId = setTimeout(() => {
            if (setShowTimeoutPrompt) setShowTimeoutPrompt(true);
        }, 10000);

        fetch(url, { signal: controller.signal })
            .then(res => {
                clearTimeout(timeoutId);
                if (!res.ok) throw new Error("API request failed");
                return res.json();
            })
            .then(data => {
                if (setShowTimeoutPrompt) setShowTimeoutPrompt(false);
                setRawNodes(data.nodes || []);
                setRawEdges(data.edges || []);
                setIsLoadingDetail(false);
            })
            .catch(err => {
                if (err.name !== 'AbortError') {
                    console.error("Failed to fetch paper details:", err);
                    clearTimeout(timeoutId);
                    setIsLoadingDetail(false);
                }
            });

        return () => { clearTimeout(timeoutId); };
    }, [viewMode, detailFilter, setShowTimeoutPrompt]);

    const cancelDetailFetch = () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            setIsLoadingDetail(false);
        }
    };

    useEffect(() => {
        if (viewMode !== 'SEARCH' || !searchFilter) return;
        setIsLoadingDetail(true);
        setSearchResult(null);
        setRawNodes([]);
        setRawEdges([]);

        if (abortControllerRef.current) abortControllerRef.current.abort();
        const controller = new AbortController();
        abortControllerRef.current = controller;

        const { query, minCitations, maxPapers } = searchFilter;
        const backendUrl = process.env.REACT_APP_API_URL || 'http://localhost:5001';
        const url = `${backendUrl}/api/search?query=${encodeURIComponent(query)}&min_citations=${minCitations}&max_papers=${maxPapers}`;

        fetch(url, { signal: controller.signal })
            .then(res => {
                if (!res.ok) throw new Error(`Server returned ${res.status}`);
                return res.json();
            })
            .then(data => {
                const nodes = data.nodes || [];
                const stats = data.stats || {
                    core: nodes.filter(n => n.nodeType === 'core').length,
                    foundation: nodes.filter(n => n.nodeType === 'foundation').length,
                    impact: nodes.filter(n => n.nodeType === 'impact').length,
                };
                setRawNodes(nodes);
                setRawEdges(data.edges || []);
                setSearchResult(
                    nodes.length === 0
                        ? { status: 'error', message: 'No papers found. Try broader keywords or set Min Citations to 0.' }
                        : { status: 'success', stats }
                );
                setIsLoadingDetail(false);
            })
            .catch(err => {
                if (err.name !== 'AbortError') {
                    setSearchResult({ status: 'error', message: `Could not reach the server (${err.message}). Is the backend running?` });
                    setIsLoadingDetail(false);
                }
            });

        return () => controller.abort();
    }, [viewMode, searchFilter]);

    const { nodes, groupStats, xGroups, groupEdges, yGroups } = useMemo(() => {
        if (!rawNodes || rawNodes.length === 0) return { nodes: [], groupStats: [], xGroups: [], groupEdges: [], yGroups: [] };

        const gMap = new Map();
        const nodeIdToGroup = new Map();

        const getXAxisKey = (d) => {
            if (groupingMode === 'AGE') return d.ageGroup || d.minAge || "Unspecified Age";
            if (groupingMode === 'RECOMMENDATION') return d.recommendationCategory || d.primaryField || "Unassigned";
            // FOOD_TYPE (default)
            return d.foodType || d.primaryField || d.AI_primary_field || "Unassigned";
        };

        const getYAxisKey = (d) => {
            if (yGroupingMode === 'NONE' || yGroupingMode === 'TIMELINE') return null;
            return d.primaryField || "Unassigned";
        };

        const ns = rawNodes.map(d => {
            const yr = d.year ?? d.publication_year ?? (d.publicationDate ? new Date(d.publicationDate).getFullYear() : 2000);
            const xGroup = getXAxisKey(d);
            const cites = d.citationCount ?? d.cited_by_count ?? 0;
            const yGroup = getYAxisKey(d);
            const groupKey = xGroup;

            const n = {
                id: String(d.id || d.paperId),
                title: d.title,
                year: yr,
                citationCount: cites,
                group: groupKey,
                xGroup,
                yGroup,
                field: d.primaryField,
                primaryField: d.primaryField,
                abstract: d.abstract || d.AI_summary || "No abstract available.",
                authors: d.allAuthors || d.all_author_names || d.firstAuthor || d.first_author_name || "Unknown",
                institutions: d.institutions || d.all_institution_names || "",
                val: Math.min(50, Math.max(5, Math.sqrt(cites) * 2)),
                nodeType: d.nodeType || null,
                paperNature: d.paper_nature || d.paperNature || null,
                iconCategory: d.icon_category || d.iconCategory || null,
                // Baby food specific fields
                foodType: d.food_type || d.foodType || null,
                ageGroup: d.age_group || d.ageGroup || null,
                recommendationSummary: d.recommendation_summary || d.AI_recommendation || null,
                evidenceStrength: d.evidence_strength || null,
                likelihoodScore: d.likelihood_score != null ? d.likelihood_score : undefined,
                seriousnessScore: d.seriousness_score != null ? d.seriousness_score : undefined,
                participantCount: d.participant_count || null,
                studyType: d.study_type || d.paper_nature || null,
                data: d
            };

            nodeIdToGroup.set(n.id, groupKey);

            if (!gMap.has(groupKey)) {
                gMap.set(groupKey, { key: groupKey, name: groupKey, xGroup, yGroup, count: 0, totalCitations: 0, minYear: Infinity, maxYear: -Infinity });
            }
            const g = gMap.get(groupKey);
            g.count += 1;
            g.totalCitations += cites;
            g.minYear = Math.min(g.minYear, yr);
            g.maxYear = Math.max(g.maxYear, yr);

            if (viewMode === 'DETAIL' && activeGroup) n.group = activeGroup;
            return n;
        });

        nodeByIdRef.current = new Map(ns.map(n => [n.id, n]));

        const gStats = Array.from(gMap.values()).map(g => ({
            ...g,
            minYear: g.minYear === Infinity ? 2000 : g.minYear,
            maxYear: g.maxYear === -Infinity ? 2025 : g.maxYear
        })).sort((a, b) => b.totalCitations - a.totalCitations);

        const finalGroupStats = gStats;
        const validGroups = new Set(finalGroupStats.map(g => g.key));
        const finalXGroups = Array.from(new Set(finalGroupStats.map(g => g.xGroup)));
        const finalYGroups = Array.from(new Set(finalGroupStats.map(g => g.yGroup).filter(Boolean)));

        const groupEdgeMap = new Map();
        const encodeEdgeKey = (s, t) => `${s.length}::${s}${t}`;
        const decodeEdgeKey = (key) => {
            const splitIdx = key.indexOf("::");
            if (splitIdx === -1) return { source: key, target: "" };
            const len = Number(key.slice(0, splitIdx));
            const rest = key.slice(splitIdx + 2);
            return { source: rest.slice(0, len), target: rest.slice(len) };
        };

        rawEdges.forEach(e => {
            const sourceGroup = nodeIdToGroup.get(String(e.source));
            const targetGroup = nodeIdToGroup.get(String(e.target));
            if (sourceGroup && targetGroup && sourceGroup !== targetGroup && validGroups.has(sourceGroup) && validGroups.has(targetGroup)) {
                const edgeKey = encodeEdgeKey(sourceGroup, targetGroup);
                groupEdgeMap.set(edgeKey, (groupEdgeMap.get(edgeKey) || 0) + 1);
            }
        });

        const calculatedGroupEdges = Array.from(groupEdgeMap.entries()).map(([key, count]) => {
            const { source, target } = decodeEdgeKey(key);
            return { source, target, weight: count };
        }).sort((a, b) => b.weight - a.weight).slice(0, 100);

        return { nodes: ns, groupStats: finalGroupStats, xGroups: finalXGroups, groupEdges: calculatedGroupEdges, yGroups: finalYGroups };
    }, [rawNodes, rawEdges, groupingMode, yGroupingMode]);

    const universeNodes = useMemo(() => {
        if (viewMode !== 'UNIVERSE' || !universeData) return [];
        const sortedRaw = (universeData.nodes || []).sort((a, b) => (b.totalWorksCount || 0) - (a.totalWorksCount || 0));
        const galaxyNodes = sortedRaw.map((galaxy) => {
            const totalWorks = galaxy.totalWorksCount || 0;
            const val = totalWorks > 0 ? 30 + Math.sqrt(totalWorks) * 0.05 : 25;
            if (galaxy.worksByDecade && Array.isArray(galaxy.worksByDecade)) {
                galaxy.worksByDecade.sort((a, b) => a.decade - b.decade);
            }
            return {
                id: galaxy.id,
                key: galaxy.id,
                type: 'galaxy',
                name: galaxy.name,
                nodeCount: galaxy.nodeCount || 0,
                edgeCount: galaxy.edgeCount || 0,
                totalWorksCount: totalWorks,
                val: Math.max(val, 30),
                data: galaxy,
                x: 0, y: 0,
                field: 'Galaxy',
                group: galaxy.group || 'Uncategorized',
                iconPath: galaxy.iconPath || null,
                citationCount: galaxy.totalCitations || 0,
                hasPapers: (galaxy.nodeCount > 0) && !!galaxy.nodesFile,
                nodesFile: galaxy.nodesFile || null,
                edgesFile: galaxy.edgesFile || null,
            };
        });

        galaxyNodes.push({
            id: 'menu-node', key: 'menu-node', type: 'menu', name: 'Menu',
            val: 40, x: 0, y: 0, isMenuNode: true, data: {}
        });

        return galaxyNodes;
    }, [universeData, viewMode]);

    const aggregatedNodes = useMemo(() => {
        if (viewMode !== 'GALAXY') return [];
        return groupStats.map(g => ({
            id: g.key, key: g.key, type: 'group', name: g.name,
            nodeCount: g.count, totalWorksCount: g.count,
            val: Math.max(20, Math.sqrt(g.totalCitations || g.count) * 1.5),
            x: 0, y: 0,
            field: g.xGroup, xGroup: g.xGroup, yGroup: g.yGroup,
            minYear: g.minYear, maxYear: g.maxYear, year: g.minYear,
            citationCount: g.totalCitations
        }));
    }, [groupStats, viewMode]);

    const activeNodes = useMemo(() => {
        if (viewMode === 'UNIVERSE') return universeNodes;
        if (viewMode === 'GALAXY') return aggregatedNodes;
        if (viewMode === 'FIELD') {
            if (!activeGroup) return nodes;
            if (selected) {
                const connectedIndices = new Set([selected.id]);
                rawEdges.forEach(e => {
                    const src = String(e.source.id || e.source);
                    const tgt = String(e.target.id || e.target);
                    if (src === selected.id) connectedIndices.add(tgt);
                    if (tgt === selected.id) connectedIndices.add(src);
                });
                return nodes.filter(n => connectedIndices.has(n.id));
            }
            return nodes.filter(n => n.group === activeGroup);
        }
        if (viewMode === 'DETAIL') {
            if (!selected) return nodes;
            const connectedIndices = new Set([selected.id]);
            rawEdges.forEach(e => {
                const src = String(e.source.id ?? e.source);
                const tgt = String(e.target.id ?? e.target);
                if (src === selected.id) connectedIndices.add(tgt);
                if (tgt === selected.id) connectedIndices.add(src);
            });
            return nodes.filter(n => connectedIndices.has(String(n.id)));
        }
        if (viewMode === 'SEARCH') {
            const dummyNode = {
                id: 'search-dummy', title: searchFilter?.query || '', name: searchFilter?.query || '',
                isSearchDummy: true, nodeType: 'search_dummy', val: 60,
                citationCount: 0, year: null, group: 'search', xGroup: 'search', field: 'search',
                abstract: `Search results for: "${searchFilter?.query}".`,
                authors: '', institutions: ''
            };
            return [dummyNode, ...nodes];
        }
        return nodes;
    }, [viewMode, universeNodes, aggregatedNodes, nodes, activeGroup, selected, rawEdges, searchFilter]);

    const edges = useMemo(() => {
        if (viewMode === 'GALAXY') return groupEdges;
        if (viewMode !== 'FIELD' && viewMode !== 'DETAIL' && viewMode !== 'SEARCH') return [];

        const activeIds = new Set(activeNodes.map(n => n.id));
        const paperEdges = rawEdges
            .map(e => ({
                source: String(e.source),
                target: String(e.target),
                importance: e.importance ?? 1,
                edgeType: e.edgeType || null
            }))
            .filter(e => activeIds.has(e.source) && activeIds.has(e.target) && e.source !== e.target);

        if (viewMode === 'DETAIL') {
            if (!selected) return [];
            return paperEdges.filter(e => e.source === selected.id || e.target === selected.id);
        }

        if (viewMode === 'SEARCH') {
            const coreSpokes = activeNodes
                .filter(n => n.nodeType === 'core')
                .map(n => ({ source: 'search-dummy', target: n.id, importance: 1, edgeType: 'spoke' }));
            return [...coreSpokes, ...paperEdges];
        }

        return paperEdges;
    }, [rawEdges, activeNodes, viewMode, groupEdges]);

    return {
        universeData, nodes: activeNodes, edges, groupStats, xGroups, yGroups, groupEdges,
        rawNodes, rawEdges, nodeByIdRef, isLoadingDetail, cancelDetailFetch, searchResult, paperIndex
    };
};
