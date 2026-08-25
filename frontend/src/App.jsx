import React, { useState, useMemo, useRef, useEffect } from "react";
import * as d3 from "d3";
import "./App.css";
import "./styles/Galaxy.css";
import "./styles/Toggle.css";

import { useClaimsData } from "./hooks/useClaimsData";
import { Graph, STANCE_COLORS } from "./components/Graph";
import { ControlPanel } from "./components/ControlPanel";
import { FooterPanel } from "./components/FooterPanel";
import { AboutPanel } from "./components/AboutPanel";

/**
 * Three screens, one drill-down:
 *
 *   TOPICS ──(topic)──> CLAIMS ──(claim)──> EVIDENCE
 *
 * Everything is served from static JSON under public/claims — no API.
 */
export default function App() {
  const wrapRef = useRef(null);
  const [dimensions, setDimensions] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  const [viewMode, setViewMode] = useState('TOPICS');
  // Which quantity the evidence view's horizontal axis carries. Stance is
  // always vertical, on both screens, so it is never toggleable.
  const [evidenceXAxis, setEvidenceXAxis] = useState('strength');
  // How a paper that cuts both ways is counted. Drives both the mixed papers'
  // own Y position and the claim's, via the per-reading netSupport the backend
  // ships. See LayoutEngine.MIXED_SIGN.
  const [reading, setReading] = useState('balanced');
  const [aboutOpen, setAboutOpen] = useState(false);
  const [activeTopic, setActiveTopic] = useState(null);
  const [activeClaim, setActiveClaim] = useState(null);
  const [selected, setSelected] = useState(null);
  const [hovered, setHovered] = useState(null);

  // One-shot: set when the user navigates BACK, so the Graph does not re-focus a
  // stale selection mid-transition. It MUST be cleared on the next forward
  // navigation - left set, it permanently disables click-to-select, because the
  // Graph reads `selected` only when this is false.
  const isReturningRef = useRef(false);

  const {
    topicsData, topicClaims, evidence, evidenceStats, claimIndex,
    nodes, edges, isLoading, error,
  } = useClaimsData(viewMode, activeTopic, activeClaim);

  const topicName =
    topicClaims?.name ||
    topicsData?.topics?.find(t => t.id === activeTopic)?.name ||
    null;
  const claimText = evidence?.claim?.claim || null;

  // ── Navigation ────────────────────────────────────────────────────────────

  const openTopic = (topicId) => {
    isReturningRef.current = false;
    setActiveTopic(topicId);
    setActiveClaim(null);
    setViewMode('CLAIMS');
    setSelected(null);
  };

  const openClaim = (topicId, claimId) => {
    isReturningRef.current = false;
    setActiveTopic(topicId);
    setActiveClaim(claimId);
    setViewMode('EVIDENCE');
    setSelected(null);
  };

  const handleNodeClick = (d) => {
    if (viewMode === 'TOPICS') return openTopic(d.id);
    if (viewMode === 'CLAIMS') return openClaim(activeTopic, d.id);
    if (d.type === 'claim-anchor') return;   // a reference mark, not a paper
    isReturningRef.current = false;
    setSelected(d);   // EVIDENCE: select the paper
  };

  const handleBackToTopics = () => {
    isReturningRef.current = true;
    setViewMode('TOPICS');
    setActiveTopic(null);
    setActiveClaim(null);
    setSelected(null);
  };

  const handleBackToClaims = () => {
    isReturningRef.current = true;
    setViewMode('CLAIMS');
    setActiveClaim(null);
    setSelected(null);
  };

  const handleBackgroundClick = () => {
    if (selected) setSelected(null);
  };

  // Search jumps straight to a claim's evidence.
  const handleClaimSelect = (claim) => openClaim(claim.topic, claim.id);

  // ── Scales ────────────────────────────────────────────────────────────────

  const scales = useMemo(() => {
    const topicColours = {};
    (topicsData?.topics || []).forEach(t => { topicColours[t.id] = t.colour; });

    const domain = [...new Set(nodes.map(n => n.group).filter(Boolean))];
    const fallback = d3.scaleOrdinal(d3.schemeTableau10).domain(domain);

    // Topic colours are defined in the registry; claim groups fall back to an
    // ordinal scheme, but every claim in a topic is tinted by its topic colour.
    const activeTopicColour = topicColours[activeTopic];
    const colorScale = (key) =>
      topicColours[key] || activeTopicColour || fallback(key);
    colorScale.domain = () => domain;

    return { colorScale, universeXScale: null, timelineHeightScale: null };
  }, [nodes, topicsData, activeTopic]);

  useEffect(() => {
    const handleResize = () =>
      setDimensions({
        width: wrapRef.current.clientWidth,
        height: wrapRef.current.clientHeight,
      });
    window.addEventListener('resize', handleResize);
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const stats = topicsData?.stats;

  return (
    <div className="App galaxy-theme" ref={wrapRef}>
      <ControlPanel
        viewMode={viewMode}
        topicName={topicName}
        claimText={claimText}
        claimIndex={claimIndex}
        onClaimSelect={handleClaimSelect}
        evidenceXAxis={evidenceXAxis}
        onEvidenceXAxisChange={setEvidenceXAxis}
        reading={reading}
        onReadingChange={setReading}
        onOpenAbout={() => setAboutOpen(true)}
        onBackToTopics={handleBackToTopics}
        onBackToClaims={handleBackToClaims}
      />

      <Graph
        nodes={nodes}
        edges={edges}
        viewMode={viewMode}
        layoutMode="CENTRAL"
        selected={selected}
        hovered={hovered}
        evidenceXAxis={evidenceXAxis}
        reading={reading}
        onNodeClick={handleNodeClick}
        onBackgroundClick={handleBackgroundClick}
        onNodeHover={setHovered}
        scales={scales}
        isReturning={isReturningRef.current}
        width={dimensions.width}
        height={dimensions.height}
        isLoadingDetail={isLoading}
      />

      {viewMode === 'TOPICS' && stats && (
        <div style={bannerStyle}>
          <span style={{ fontWeight: 700, color: '#334155' }}>{stats.claims}</span> claims
          <span style={dotStyle}>·</span>
          <span style={{ color: '#64748b' }}>{stats.papers} papers, {stats.evaluated} assessed</span>
        </div>
      )}

      {viewMode === 'CLAIMS' && topicClaims && (
        <div style={bannerStyle}>
          <span style={{ color: '#64748b' }}>
            Up→down: <strong style={{ color: '#334155' }}>how true</strong> ·
            Left→right: <strong style={{ color: '#334155' }}>how strong the studies are</strong> ·
            Colour: <strong style={{ color: '#334155' }}>the verdict</strong>
          </span>
        </div>
      )}

      {viewMode === 'EVIDENCE' && evidenceStats && (
        <div style={bannerStyle}>
          <span style={{ color: STANCE_COLORS.supports, fontWeight: 700 }}>{evidenceStats.supports}</span> support
          <span style={dotStyle}>·</span>
          <span style={{ color: STANCE_COLORS.refutes, fontWeight: 700 }}>{evidenceStats.refutes}</span> refute
          <span style={dotStyle}>·</span>
          {evidenceStats.mixed > 0 && (
            <>
              <span style={{ color: STANCE_COLORS.mixed, fontWeight: 700 }}>{evidenceStats.mixed}</span> mixed
              <span style={dotStyle}>·</span>
            </>
          )}
          <span style={{ color: STANCE_COLORS.neutral, fontWeight: 700 }}>{evidenceStats.neutral}</span> neutral
          {evidenceStats.neutralHidden > 0 && (
            <span style={{ color: '#94a3b8' }}>
              ({evidenceStats.neutralHidden} hidden, {evidenceStats.neutralShown} well-cited shown)
            </span>
          )}
          {evidenceStats.unevaluated > 0 && (
            <>
              <span style={dotStyle}>·</span>
              <span style={{ color: '#cbd5e1' }}>{evidenceStats.unevaluated} not yet assessed</span>
            </>
          )}
          <span style={dotStyle}>·</span>
          <span style={{ color: '#94a3b8' }}>
            {evidenceXAxis === 'year'
              ? 'oldest left, newest right'
              : 'weaker studies left, stronger right'}
          </span>
        </div>
      )}

      {viewMode === 'EVIDENCE' && evidence && evidence.papers.length === 0 && (
        <div style={emptyStateStyle}>
          <h3 style={{ margin: '0 0 8px 0', color: '#1e293b', fontSize: '17px' }}>
            No evidence gathered yet
          </h3>
          <p style={{ margin: 0, color: '#64748b', fontSize: '14px', lineHeight: 1.5 }}>
            About <strong>{(evidence.claim.openAlexCount || 0).toLocaleString()}</strong> papers
            match this claim's search in OpenAlex, but none have been collected.
            <br />
            Run <code style={codeStyle}>python backend/import_claims.py {evidence.claim.id}</code>
            {' '}then <code style={codeStyle}>evaluate_claims.py {evidence.claim.id}</code>.
          </p>
        </div>
      )}

      {error && (
        <div style={{ ...bannerStyle, color: '#ef4444' }}>⚠ {error}</div>
      )}

      <AboutPanel open={aboutOpen} onClose={() => setAboutOpen(false)} />

      <FooterPanel selected={selected} hovered={hovered} />
    </div>
  );
}

const bannerStyle = {
  position: 'fixed', top: 72, left: '50%', transform: 'translateX(-50%)',
  backgroundColor: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)',
  border: '1px solid rgba(0,0,0,0.08)', borderRadius: '20px', padding: '6px 18px',
  fontSize: '13px', fontFamily: 'Inter, sans-serif', boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
  zIndex: 100, pointerEvents: 'none', display: 'flex', alignItems: 'center',
  gap: '6px', whiteSpace: 'nowrap', maxWidth: '92vw',
};
const emptyStateStyle = {
  position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
  backgroundColor: 'rgba(255,255,255,0.96)', backdropFilter: 'blur(8px)',
  border: '1px solid rgba(0,0,0,0.08)', borderRadius: '12px', padding: '24px 28px',
  fontFamily: 'Inter, sans-serif', boxShadow: '0 8px 30px rgba(0,0,0,0.1)',
  zIndex: 100, pointerEvents: 'none', maxWidth: '520px', textAlign: 'center',
};
const codeStyle = {
  background: '#f1f5f9', padding: '2px 6px', borderRadius: '4px',
  fontSize: '12px', fontFamily: 'ui-monospace, monospace', color: '#334155',
};
const dotStyle = { color: '#cbd5e1', fontSize: '16px' };
