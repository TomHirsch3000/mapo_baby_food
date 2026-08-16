import { useState, useEffect, useMemo } from 'react';

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
    const evidenceNodes = useMemo(() => {
        if (viewMode !== 'EVIDENCE' || !evidence) return [];
        return (evidence.papers || []).map(p => ({
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
            evidenceStrength: p.evidenceStrength,
            studyType: p.studyType,
            weight: p.weight,
            group: p.stance,
            xGroup: p.stance,
            primaryField: p.studyType,
            val: Math.min(46, Math.max(8, Math.sqrt(p.citationCount || 0) * 2)),
            data: p,
        }));
    }, [viewMode, evidence]);

    const evidenceEdges = useMemo(() => {
        if (viewMode !== 'EVIDENCE' || !evidence) return NO_EDGES;
        const ids = new Set((evidence.papers || []).map(p => p.id));
        return (evidence.edges || [])
            .filter(e => ids.has(e.source) && ids.has(e.target))
            .map(e => ({ source: e.source, target: e.target, importance: 1 }));
    }, [viewMode, evidence]);

    const evidenceStats = useMemo(() => {
        if (!evidence) return null;
        const stats = { supports: 0, refutes: 0, neutral: 0, unevaluated: 0 };
        (evidence.papers || []).forEach(p => {
            if (stats[p.stance] !== undefined) stats[p.stance] += 1;
            else stats.unevaluated += 1;
        });
        return { ...stats, claim: evidence.claim };
    }, [evidence]);

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
