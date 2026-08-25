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

  // ── History ───────────────────────────────────────────────────────────────
  //
  // Each level of the map is a history entry, so the phone's own back gesture
  // walks back up it instead of leaving the site - which is what it did when
  // the whole app lived at one URL. The in-app back button goes through the
  // same door (history.back()), so the two can never disagree about where
  // "up" is.

  const applyState = (st) => {
    const view = st?.view || 'TOPICS';
    setViewMode(view);
    setActiveTopic(view === 'TOPICS' ? null : (st?.topic ?? null));
    setActiveClaim(view === 'EVIDENCE' ? (st?.claim ?? null) : null);
    setSelected(null);
  };

  useEffect(() => {
    window.history.replaceState({ view: 'TOPICS' }, '');
    const onPop = (e) => {
      // Anything reached by popstate is a return, forward or back: the Graph
      // must not re-focus a selection belonging to the view being left.
      isReturningRef.current = true;
      applyState(e.state);
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // ── Navigation ────────────────────────────────────────────────────────────

  const openTopic = (topicId) => {
    isReturningRef.current = false;
    setActiveTopic(topicId);
    setActiveClaim(null);
    setViewMode('CLAIMS');
    setSelected(null);
    window.history.pushState({ view: 'CLAIMS', topic: topicId }, '');
  };

  const openClaim = (topicId, claimId) => {
    isReturningRef.current = false;
    setActiveTopic(topicId);
    setActiveClaim(claimId);
    setViewMode('EVIDENCE');
    setSelected(null);
    window.history.pushState({ view: 'EVIDENCE', topic: topicId, claim: claimId }, '');
  };

  // No hover on a touch screen, so a tap has to do both jobs: the first one
  // selects, which is what hovering does on a laptop and what fills the panel
  // at the bottom, and a second tap on the same node opens it. Without this a
  // phone could never see a node's details at all - the tap that would have
  // shown them navigated away instead.
  const isTouch = () =>
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(hover: none)').matches;

  const handleNodeClick = (d) => {
    if (viewMode === 'EVIDENCE') {
      if (d.type === 'claim-anchor') return;   // a reference mark, not a paper
      isReturningRef.current = false;
      return setSelected(d);                   // EVIDENCE: select the paper
    }
    if (isTouch() && selected?.id !== d.id) {
      isReturningRef.current = false;
      return setSelected(d);                   // first tap: preview it
    }
    if (viewMode === 'TOPICS') return openTopic(d.id);
    if (viewMode === 'CLAIMS') return openClaim(activeTopic, d.id);
  };

  // Both breadcrumbs defer to history, so the button and the device gesture
  // are the same action.
  const handleBackToTopics = () => window.history.back();
  const handleBackToClaims = () => window.history.back();

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
    <div className="App galaxy-theme" data-view={viewMode}
         data-has-focus={(hovered || selected) ? '1' : '0'} ref={wrapRef}>
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

      <div className="galaxy-topbar">
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

      {viewMode === 'TOPICS' && stats && (
        <div className="galaxy-banner" style={bannerStyle}>
          <span style={{ fontWeight: 700, color: '#334155' }}>{stats.claims}</span> claims
          <span style={dotStyle}>·</span>
          <span style={{ color: '#64748b' }}>{stats.papers} papers, {stats.evaluated} assessed</span>
        </div>
      )}

      {viewMode === 'CLAIMS' && topicClaims && (
        <div className="galaxy-banner" style={bannerStyle}>
          <span style={{ color: '#64748b' }}>
            Up→down: <strong style={{ color: '#334155' }}>how true</strong> ·
            Left→right: <strong style={{ color: '#334155' }}>how strong the studies are</strong> ·
            Colour: <strong style={{ color: '#334155' }}>the verdict</strong>
          </span>
        </div>
      )}

      {viewMode === 'EVIDENCE' && evidenceStats && (
        <div className="galaxy-banner" style={bannerStyle}>
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
        <div className="galaxy-banner" style={{ ...bannerStyle, color: '#ef4444' }}>⚠ {error}</div>
      )}
      </div>

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
