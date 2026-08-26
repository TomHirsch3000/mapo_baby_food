import { useState, useEffect, useMemo } from 'react';
import { LayoutEngine } from '../modules/LayoutEngine';

/**
 * Loads the JSON produced by backend/build_claims_data.py and shapes it into
 * the node arrays the Graph renders.
 *
 *   TOPICS    topic nodes, sized by how much literature exists
 *   CLAIMS    claim nodes for one topic
 *   EVIDENCE  papers for one claim, tagged with stance
 *
 * There is no backend: everything here is static JSON.
 */

const CLAIMS_BASE = './claims';

// Shared empty array. Returning a fresh [] each render would change the Graph
// effect's dependency identity on every hover, re-running the force simulation
// and visibly jolting the nodes.
const NO_EDGES = [];

/**
 * Node radius from an OpenAlex match count.
 *
 * Log-scaled because the counts span three orders of magnitude (28 works for
 * "walkers delay motor development" against 34,155 for "early motor development
 * predicts cognition"). On a linear scale every small claim would collapse to a
 * dot.
 */
const countToRadius = (count, min, max, ceiling) => {
    if (!count) return min;
    const frac = Math.log10(1 + count) / Math.log10(1 + ceiling);
    return min + (max - min) * Math.min(1, Math.max(0, frac));
};

// At most this many neutral papers survive the filter below, however
// well-connected they are. A claim with 40 well-cited background papers is
// still a claim whose evidence view is unreadable.
const MAX_NEUTRALS_SHOWN = 8;

/**
 * Decide which neutral papers earn a place on the map.
 *
 * A neutral paper took no position on the claim, so it contributes nothing to
 * the verdict and nothing to either axis - it is pure clutter unless the field
 * itself treats it as load-bearing. The proxy for that is how often the claim's
 * OTHER papers cite it.
 *
 * The bar has to be relative, not absolute. Citation density varies more than
 * fivefold between claims (74 edges across screen_language_delay's papers
 * against 359 across peanut_intro_early's), so a fixed "degree >= 3" keeps 61%
 * of one claim's neutrals and 14% of another's. Instead a neutral has to be
 * cited as often as a typical DECISIVE paper in the same claim, which
 * calibrates itself to whatever that literature looks like.
 */
const selectNeutrals = (papers, edges) => {
    const degree = new Map(papers.map(p => [p.id, 0]));
    (edges || []).forEach(e => {
        if (degree.has(e.source)) degree.set(e.source, degree.get(e.source) + 1);
        if (degree.has(e.target)) degree.set(e.target, degree.get(e.target) + 1);
    });

    const decisive = papers.filter(p => p.stance === 'supports' || p.stance === 'refutes');
    const neutral = papers.filter(p => p.stance === 'neutral');

    const decisiveDegrees = decisive.map(p => degree.get(p.id) || 0).sort((a, b) => a - b);
    const medianDecisive = decisiveDegrees.length
        ? decisiveDegrees[Math.floor(decisiveDegrees.length / 2)]
        : 0;
    // Never let the bar fall to zero, or an unconnected claim keeps everything.
    const bar = Math.max(1, medianDecisive);

    const kept = neutral
        .filter(p => (degree.get(p.id) || 0) >= bar)
        .sort((a, b) => (degree.get(b.id) || 0) - (degree.get(a.id) || 0))
        .slice(0, MAX_NEUTRALS_SHOWN);

    return { kept, keptIds: new Set(kept.map(p => p.id)), degree, bar };
};

export const useClaimsData = (viewMode, activeTopic, activeClaim) => {
    const [topicsData, setTopicsData] = useState(null);
    const [topicClaims, setTopicClaims] = useState(null);
    const [evidence, setEvidence] = useState(null);
    const [claimIndex, setClaimIndex] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetch(`${CLAIMS_BASE}/topics.json`)
            .then(r => {
                if (!r.ok) throw new Error(`topics.json: ${r.status}`);
                return r.json();
            })
            .then(setTopicsData)
            .catch(err => {
                console.error('Failed to load topics:', err);
                setError('Could not load topics. Run backend/build_claims_data.py.');
            });
    }, []);

    // Flat index of every claim, for the search box.
    useEffect(() => {
        if (!topicsData) return;
        Promise.all(
            (topicsData.topics || []).map(t =>
                fetch(`${CLAIMS_BASE}/${t.id}/claims.json`)
                    .then(r => r.json())
                    .then(d => (d.claims || []).map(c => ({
                        id: c.id,
                        title: c.claim,
                        topic: c.topic,
                        topicName: c.topicName,
                        group: c.group,
                        hasEvidence: c.hasEvidence,
                    })))
                    .catch(() => [])
            )
        ).then(arrays => setClaimIndex(arrays.flat()));
    }, [topicsData]);

    useEffect(() => {
        if (!activeTopic) { setTopicClaims(null); return; }
        let cancelled = false;
        setIsLoading(true);
        fetch(`${CLAIMS_BASE}/${activeTopic}/claims.json`)
            .then(r => {
                if (!r.ok) throw new Error(`claims.json: ${r.status}`);
                return r.json();
            })
            .then(data => { if (!cancelled) { setTopicClaims(data); setError(null); } })
            .catch(err => {
                if (cancelled) return;
                console.error('Failed to load claims:', err);
                setError(`No claims data for "${activeTopic}".`);
                setTopicClaims(null);
            })
            .finally(() => { if (!cancelled) setIsLoading(false); });
        return () => { cancelled = true; };
    }, [activeTopic]);

    useEffect(() => {
        if (!activeTopic || !activeClaim) { setEvidence(null); return; }
        let cancelled = false;
        setIsLoading(true);
        fetch(`${CLAIMS_BASE}/${activeTopic}/${activeClaim}/evidence.json`)
            .then(r => {
                if (!r.ok) throw new Error(`evidence.json: ${r.status}`);
                return r.json();
            })
            .then(data => { if (!cancelled) { setEvidence(data); setError(null); } })
            .catch(err => {
                if (cancelled) return;
                console.error('Failed to load evidence:', err);
                setError(`No evidence data for "${activeClaim}".`);
                setEvidence(null);
            })
            .finally(() => { if (!cancelled) setIsLoading(false); });
        return () => { cancelled = true; };
    }, [activeTopic, activeClaim]);

    // ── Topic nodes ──────────────────────────────────────────────────────────
    const topicNodes = useMemo(() => {
        if (viewMode !== 'TOPICS' || !topicsData) return [];
        const topics = topicsData.topics || [];
        const ceiling = Math.max(...topics.map(t => t.openAlexCount), 1);

        return topics.map(t => ({
            id: t.id,
            key: t.id,
            type: 'topic',
            name: t.name,
            description: t.blurb,
            group: t.id,
            colour: t.colour,
            claimCount: t.claimCount,
            researchedClaimCount: t.researchedClaimCount,
            openAlexCount: t.openAlexCount,
            paperCount: t.paperCount,
            supports: t.supports,
            refutes: t.refutes,
            neutral: t.neutral,
            netSupport: t.netSupport,
            val: countToRadius(t.openAlexCount, 34, 76, ceiling),
            citationCount: t.paperCount,
            iconPath: t.iconPath,
            x: 0, y: 0,
            data: t,
        }));
    }, [viewMode, topicsData]);

    // ── Claim nodes ──────────────────────────────────────────────────────────
    const claimNodes = useMemo(() => {
        if (viewMode !== 'CLAIMS' || !topicClaims) return [];
        const claims = topicClaims.claims || [];
        const ceiling = Math.max(...claims.map(c => c.openAlexCount), 1);

        return claims.map(c => ({
            id: c.id,
            key: c.id,
            type: 'claim',
            name: c.claim,
            claim: c.claim,
            testedAs: c.testedAs,
            isPrescriptive: c.isPrescriptive,
            group: c.group,
            topic: c.topic,
            topicName: c.topicName,
            ageRange: c.ageRange,
            supports: c.supports,
            refutes: c.refutes,
            neutral: c.neutral,
            unevaluated: c.unevaluated,
            paperCount: c.paperCount,
            openAlexCount: c.openAlexCount,
            hasEvidence: c.hasEvidence,
            netSupport: c.netSupport,
            netSupportByReading: {
                conservative: c.netSupportConservative ?? c.netSupport,
                balanced: c.netSupportBalanced ?? c.netSupport,
                liberal: c.netSupportLiberal ?? c.netSupport,
            },
            mixed: c.mixed,
            evidenceQuality: c.evidenceQuality,
            consensus: c.consensus,
            evidenceVolume: c.evidenceVolume,
            strengthMix: c.strengthMix,
            citationCount: c.paperCount,
            // Size tracks the literature, not what we hold - an unresearched
            // claim still shows how much has been written around it.
            val: countToRadius(c.openAlexCount, 18, 64, ceiling),
            x: 0, y: 0,
            data: c,
        }));
    }, [viewMode, topicClaims]);

    // ── Evidence nodes ───────────────────────────────────────────────────────

    // Which papers are on the map, resolved ONCE. Both the node list and the
    // edge list derive from this: d3.forceLink throws on any edge naming a node
    // it cannot find, so an edge surviving the neutral filter that its endpoint
    // did not would blank the whole view.
    const visibleEvidence = useMemo(() => {
        if (viewMode !== 'EVIDENCE' || !evidence) return null;
        const all = evidence.papers || [];
        const { keptIds, degree } = selectNeutrals(all, evidence.edges);
        const papers = all.filter(p => p.stance !== 'neutral' || keptIds.has(p.id));
        return { papers, degree, ids: new Set(papers.map(p => p.id)) };
    }, [viewMode, evidence]);

    const evidenceNodes = useMemo(() => {
        if (viewMode !== 'EVIDENCE' || !evidence || !visibleEvidence) return [];

        const { papers: visible, degree } = visibleEvidence;

        const papers = visible.map(p => ({
            id: p.id,
            type: 'paper',
            title: p.title,
            name: p.title,
            year: p.year,
            citationCount: p.citationCount || 0,
            abstract: p.abstract,
            authors: p.authors,
            institutions: p.institutions,
            venue: p.venue,
            doi: p.doi,
            url: p.url,
            stance: p.stance,
            confidence: p.confidence,
            stanceSummary: p.stanceSummary,
            finding: p.finding,
            direction: p.direction,
            evidenceStrength: p.evidenceStrength,
            studyType: p.studyType,
            studyDesign: p.studyDesign,
            designRank: p.designRank,
            weight: p.weight,
            // Read-this-first order within the claim, and the score behind it:
            // study design, citations relative to the claim, and the journal's
            // own impact.
            rank: p.rank,
            rankTotal: p.rankTotal,
            importance: p.importance,
            journalName: p.journalName,
            journalImpact: p.journalImpact,
            journalHIndex: p.journalHIndex,
            group: p.stance,
            xGroup: p.stance,
            primaryField: p.studyDesign || p.studyType,
            val: Math.min(46, Math.max(8, Math.sqrt(p.citationCount || 0) * 2)),
            localCitations: degree.get(p.id) || 0,
            data: p,
        }));

        // The claim travels down into its own evidence view as a node, holding
        // the position the claims screen gave it. Reading the cloud against a
        // fixed anchor is the whole point: you can see at a glance whether the
        // verdict sits where the bulk of the papers do, or whether a handful of
        // heavily-cited studies dragged it there.
        const c = evidence.claim;
        if (!c) return papers;

        const years = papers.map(p => p.year).filter(y => y && y > 1900).sort((a, b) => a - b);
        const medianYear = years.length ? years[Math.floor(years.length / 2)] : null;

        return [...papers, {
            id: `claim-anchor:${c.id}`,
            type: 'claim-anchor',
            name: c.claim,
            claim: c.claim,
            testedAs: c.testedAs,
            isPrescriptive: c.isPrescriptive,
            netSupport: c.netSupport ?? 0,
            netSupportByReading: {
                conservative: c.netSupportConservative ?? c.netSupport ?? 0,
                balanced: c.netSupportBalanced ?? c.netSupport ?? 0,
                liberal: c.netSupportLiberal ?? c.netSupport ?? 0,
            },
            evidenceQuality: c.evidenceQuality ?? 0,
            medianYear,
            supports: c.supports,
            refutes: c.refutes,
            neutral: c.neutral,
            mixedCount: c.mixed,
            paperCount: c.paperCount,
            // The anchor reuses the claims screen's footer panel verbatim, so it
            // needs the same fields that panel reads.
            group: c.group,
            topicName: c.topicName,
            ageRange: c.ageRange,
            hasEvidence: c.hasEvidence,
            openAlexCount: c.openAlexCount,
            unevaluated: c.unevaluated,
            strengthMix: c.strengthMix,
            consensus: c.consensus,
            consensus: c.consensus,
            val: 52,
            citationCount: 0,
            data: c,
        }];
    }, [viewMode, evidence, visibleEvidence]);

    const evidenceEdges = useMemo(() => {
        if (viewMode !== 'EVIDENCE' || !evidence) return NO_EDGES;
        if (LayoutEngine.EVIDENCE_EDGE_MODE === 'none') return NO_EDGES;
        const ids = visibleEvidence ? visibleEvidence.ids : new Set();

        // Only ribbons that touch the context box survive by default. A
        // paper-to-paper citation says one author read another; it says nothing
        // about whether either is right or on-topic, which is the only question
        // this screen exists to answer - and at a hundred papers those ribbons
        // are most of the ink. Set EVIDENCE_EDGE_MODE to "all" to get them back.
        const contextIds = new Set(
            (visibleEvidence ? visibleEvidence.papers : [])
                .filter(p => p.stance === 'neutral')
                .map(p => p.id));
        const keep = LayoutEngine.EVIDENCE_EDGE_MODE === 'all'
            ? () => true
            : (e) => contextIds.has(e.source) || contextIds.has(e.target);

        return (evidence.edges || [])
            .filter(e => ids.has(e.source) && ids.has(e.target))
            .filter(e => e.source !== e.target)     // the data carries self-loops
            .filter(keep)
            .map(e => ({ source: e.source, target: e.target, importance: 1 }));
    }, [viewMode, evidence, visibleEvidence]);

    const evidenceStats = useMemo(() => {
        if (!evidence) return null;
        const stats = { supports: 0, refutes: 0, neutral: 0, mixed: 0, unevaluated: 0 };
        (evidence.papers || []).forEach(p => {
            if (stats[p.stance] !== undefined) stats[p.stance] += 1;
            else stats.unevaluated += 1;
        });
        // How many neutrals actually made it onto the map. Reported in the
        // banner so a filtered paper is never silently disappeared.
        const shown = visibleEvidence
            ? visibleEvidence.papers.filter(p => p.stance === 'neutral').length
            : stats.neutral;
        return {
            ...stats,
            neutralShown: shown,
            neutralHidden: stats.neutral - shown,
            claim: evidence.claim,
        };
    }, [evidence, visibleEvidence]);

    const nodes =
        viewMode === 'TOPICS' ? topicNodes :
        viewMode === 'CLAIMS' ? claimNodes :
        viewMode === 'EVIDENCE' ? evidenceNodes : [];

    return {
        topicsData,
        topicClaims,
        evidence,
        evidenceStats,
        claimIndex,
        nodes,
        edges: viewMode === 'EVIDENCE' ? evidenceEdges : NO_EDGES,
        isLoading,
        error,
    };
};
