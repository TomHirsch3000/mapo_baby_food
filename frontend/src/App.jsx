import React, { useState, useMemo, useRef, useEffect } from "react";
import * as d3 from "d3";
import "./App.css";
import "./styles/Galaxy.css";
import "./styles/Toggle.css";

import { useGraphData } from "./hooks/useGraphData";
import { Graph } from "./components/Graph";
import { ControlPanel } from "./components/ControlPanel";
import { FooterPanel } from "./components/FooterPanel";

export default function App() {
  const wrapRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: window.innerWidth, height: window.innerHeight });

  const [viewMode, setViewMode] = useState('HOME');
  const [fieldSource, setFieldSource] = useState('GALAXY');
  const [activeGalaxy, setActiveGalaxy] = useState(null);
  const [activeGroup, setActiveGroup] = useState(null);
  const [selected, setSelected] = useState(null);
  const [hovered, setHovered] = useState(null);

  const [searchFilter, setSearchFilter] = useState(null);
  const [showSearchPrompt, setShowSearchPrompt] = useState(false);
  const [pendingSearchQuery, setPendingSearchQuery] = useState('');
  const [minSearchCitations, setMinSearchCitations] = useState(0);
  const [maxSearchPapers, setMaxSearchPapers] = useState(50);

  const [layout, setLayout] = useState('CENTRAL');
  // AGE | FOOD_TYPE | RECOMMENDATION
  const [grouping, setGrouping] = useState('FOOD_TYPE');

  const [showDetailPrompt, setShowDetailPrompt] = useState(false);
  const [activeDoubleClickPaper, setActiveDoubleClickPaper] = useState(null);
  const [detailFilter, setDetailFilter] = useState(null);
  const [minCitationsInput, setMinCitationsInput] = useState(0);
  const [maxPapersInput, setMaxPapersInput] = useState(200);
  const [showTimeoutPrompt, setShowTimeoutPrompt] = useState(false);

  const xAxisMode = layout === 'TIMELINE' ? 'TIMELINE' : (viewMode === 'GALAXY' ? grouping : 'NONE');
  const yGroupingMode = 'NONE';
  const layoutMode = layout;
  const groupingMode = grouping;

  const isReturningRef = useRef(false);
  const [pendingAutocompleteId, setPendingAutocompleteId] = useState(null);

  const { nodes, edges, groupStats, xGroups, yGroups, universeData, rawNodes, rawEdges, isLoadingDetail, cancelDetailFetch, searchResult, paperIndex } = useGraphData(viewMode, activeGalaxy, groupingMode, yGroupingMode, activeGroup, selected, detailFilter, setShowTimeoutPrompt, searchFilter);

  const handleGalaxyClick = (galaxyId) => {
    setActiveGalaxy(galaxyId);
    setViewMode('GALAXY');
    setActiveGroup(null);
    setSelected(null);
    setFieldSource('GALAXY');
  };

  const handleSearch = (query) => {
    setPendingSearchQuery(query);
    setShowSearchPrompt(true);
  };

  const confirmSearch = () => {
    setShowSearchPrompt(false);
    setSearchFilter({ query: pendingSearchQuery, minCitations: minSearchCitations, maxPapers: maxSearchPapers });
    setViewMode('SEARCH');
    setSelected(null);
  };

  const cancelSearch = () => {
    setShowSearchPrompt(false);
    setPendingSearchQuery('');
  };

  const handleBackFromSearch = () => {
    setViewMode('UNIVERSE');
    setSearchFilter(null);
    setSelected(null);
    setActiveGalaxy(null);
    setActiveGroup(null);
  };

  const handleBackToUniverse = () => {
    isReturningRef.current = true;
    setActiveGalaxy(null);
    setActiveGroup(null);
    setViewMode('UNIVERSE');
    setSearchFilter(null);
    setSelected(null);
  };

  const handleGroupClick = (groupKey) => {
    setActiveGroup(groupKey);
    setViewMode('FIELD');
    setSelected(null);
  };

  const handleBackToGalaxy = () => {
    isReturningRef.current = true;
    setActiveGroup(null);
    setSelected(null);
    if (fieldSource === 'FOOD_GALAXY') {
      setViewMode('FOOD_GALAXY');
    } else {
      setViewMode('GALAXY');
    }
  };

  const handleBackToHome = () => {
    setViewMode('HOME');
    setActiveGalaxy(null);
    setActiveGroup(null);
    setSelected(null);
    setSearchFilter(null);
    setFieldSource('GALAXY');
  };

  const handlePaperClick = (paper) => {
    setSelected(paper);
    if (paper.group) setActiveGroup(paper.group);
  };

  const handleNodeClick = (d) => {
    if (viewMode === 'HOME') {
      if (d.id === 'food_map') setViewMode('FOOD_GALAXY');
      else if (d.id === 'recommendations') setViewMode('UNIVERSE');
    } else if (viewMode === 'FOOD_GALAXY') {
      if (d.isMenuNode || d.isFoodGroupLabel) return;
      setActiveGalaxy(d.id);
      setViewMode('FIELD');
      setActiveGroup(null);
      setSelected(null);
      setFieldSource('FOOD_GALAXY');
    } else if (viewMode === 'UNIVERSE') {
      if (d.isMenuNode) return;
      if (d.data?.hasPapers === false) { setSelected(d); return; }
      handleGalaxyClick(d.id);
    } else if (viewMode === 'GALAXY') {
      handleGroupClick(d.key);
    } else if (viewMode === 'SEARCH') {
      if (d.isSearchDummy) return;
      handlePaperClick(d);
    } else {
      handlePaperClick(d);
    }
  };

  const handleBackgroundClick = () => {
    if (selected) setSelected(null);
  };

  const handleNodeDoubleClick = (paper) => {
    if (viewMode === 'UNIVERSE' || viewMode === 'GALAXY') return;
    if (paper.isSearchDummy) return;
    const searchTerm = paper.primaryField && paper.primaryField !== 'Unassigned'
      ? paper.primaryField
      : paper.title;
    handleSearch(searchTerm);
  };

  const handleDetailedViewClick = (paper) => {
    if (viewMode === 'UNIVERSE' || viewMode === 'GALAXY') return;
    setActiveDoubleClickPaper(paper);
    setShowDetailPrompt(true);
  };

  const confirmDetailView = () => {
    setShowDetailPrompt(false);
    setDetailFilter({
      id: activeDoubleClickPaper.id,
      minCitations: minCitationsInput,
      maxPapers: maxPapersInput
    });
    setViewMode('DETAIL');
    setSelected(activeDoubleClickPaper);
    setActiveGroup(activeDoubleClickPaper.group);
  };

  const cancelDetailView = () => {
    setShowDetailPrompt(false);
    setActiveDoubleClickPaper(null);
  };

  const handleAutocompleteSelect = (paper) => {
    setActiveGalaxy(paper.galaxyId);
    setActiveGroup(paper.primaryField);
    setViewMode('FIELD');
    setSearchFilter(null);
    setSelected(null);
    setPendingAutocompleteId(paper.id);
  };

  useEffect(() => {
    if (!pendingAutocompleteId || nodes.length === 0) return;
    const found = nodes.find(n => n.id === pendingAutocompleteId);
    if (found) {
      setSelected(found);
      if (found.group) setActiveGroup(found.group);
      setPendingAutocompleteId(null);
    }
  }, [nodes, pendingAutocompleteId]);

  const handleTimeoutCancel = () => {
    setShowTimeoutPrompt(false);
    cancelDetailFetch();
    setViewMode('FIELD');
    setDetailFilter(null);
    setActiveDoubleClickPaper(null);
  };

  const handleTimeoutWait = () => {
    setShowTimeoutPrompt(false);
  };

  const scales = useMemo(() => {
    const width = dimensions.width;
    const height = dimensions.height;
    const graphCenterY = -height * 0.1;

    const colorScaleDomain = (viewMode === 'UNIVERSE' || viewMode === 'FOOD_GALAXY' || viewMode === 'HOME')
      ? [...new Set(nodes.filter(n => !n.isMenuNode).map(n => n.group).filter(Boolean))]
      : xGroups;
    const colorScale = d3.scaleOrdinal(d3.schemeTableau10).domain(colorScaleDomain);

    let universeXScale = null;
    let timelineHeightScale = null;

    if (viewMode === 'UNIVERSE') {
      const allDecades = nodes.flatMap(n => n.data?.worksByDecade?.map(d => d.decade) || []);
      const minYear = d3.min(allDecades) || 1800;
      const maxYear = 2026;

      universeXScale = d3.scalePow()
        .exponent(3)
        .domain([1900, maxYear])
        .range([-width * 1.2, width * 1.2]);

      const validNodes = nodes.filter(n => !n.isMenuNode && n.data?.worksByDecade);
      const absMaxWorksSingleDecade = d3.max(validNodes, d => d3.max(d.data.worksByDecade, w => w.works_count) || 0) || 1000;

      timelineHeightScale = d3.scaleLinear()
        .domain([0, absMaxWorksSingleDecade])
        .range([0, 320]);
    }

    return {
      colorScale,
      universeXScale,
      timelineHeightScale,
      xGroupScale: null,
      yTimelineScale: null,
      yScale: null
    };
  }, [dimensions, xGroups, yGroups, nodes, layout, grouping, viewMode]);

  useEffect(() => {
    const handleResize = () => setDimensions({ width: wrapRef.current.clientWidth, height: wrapRef.current.clientHeight });
    window.addEventListener('resize', handleResize);
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="App galaxy-theme" ref={wrapRef}>
      <ControlPanel
        viewMode={viewMode}
        layout={layout}
        grouping={grouping}
        selected={selected}
        activeGroupLabel={activeGroup}
        galaxyName={activeGalaxy && universeData ? (universeData.nodes?.find(n => n.id === activeGalaxy)?.name || "Topic View") : "Topic View"}
        searchQuery={searchFilter?.query || ''}
        onBackToHome={handleBackToHome}
        onBackToUniverse={handleBackToUniverse}
        onBackToGalaxy={handleBackToGalaxy}
        onBackFromSearch={handleBackFromSearch}
        onLayoutChange={setLayout}
        onGroupingChange={setGrouping}
        onSearch={handleSearch}
        paperIndex={paperIndex}
        onAutocompleteSelect={handleAutocompleteSelect}
        fieldSource={fieldSource}
      />

      <Graph
        nodes={nodes}
        edges={edges}
        viewMode={viewMode}
        layoutMode={layoutMode}
        groupingMode={groupingMode}
        activeGroup={activeGroup}
        selected={selected}
        hovered={hovered}
        onNodeClick={handleNodeClick}
        onGalaxyClick={handleGalaxyClick}
        onGroupClick={handleGroupClick}
        onBackgroundClick={handleBackgroundClick}
        onNodeDoubleClick={handleNodeDoubleClick}
        onSearch={handleSearch}
        onNodeHover={setHovered}
        scales={scales}
        isReturning={isReturningRef.current}
        width={dimensions.width}
        height={dimensions.height}
        isLoadingDetail={isLoadingDetail}
      />

      {viewMode === 'SEARCH' && (
        <div style={searchResultsBannerStyle}>
          {isLoadingDetail ? (
            <span style={{ color: '#6366f1' }}>Searching for "{searchFilter?.query}"…</span>
          ) : searchResult?.status === 'error' ? (
            <span style={{ color: '#ef4444' }}>⚠ {searchResult.message}</span>
          ) : searchResult?.status === 'success' ? (
            <>
              <span style={{ color: '#6366f1', fontWeight: 700 }}>{searchResult.stats.core}</span> core
              <span style={dotStyle}>·</span>
              <span style={{ color: '#10b981', fontWeight: 700 }}>{searchResult.stats.foundation}</span> foundation
              <span style={dotStyle}>·</span>
              <span style={{ color: '#f59e0b', fontWeight: 700 }}>{searchResult.stats.impact}</span> impact
              <span style={dotStyle}>·</span>
              <span style={{ color: '#64748b' }}>
                {(searchResult.stats.core || 0) + (searchResult.stats.foundation || 0) + (searchResult.stats.impact || 0)} papers total
              </span>
            </>
          ) : null}
        </div>
      )}

      <FooterPanel
        selected={selected}
        hovered={hovered}
        layoutMode={layoutMode}
        onDetailedViewClick={handleDetailedViewClick}
      />

      {(viewMode === 'DETAIL' || viewMode === 'SEARCH') && isLoadingDetail && (
        <div style={modalOverlayStyle}>
          <div style={{ ...modalContentStyle, textAlign: 'center', padding: '40px 30px' }}>
            <div style={spinnerStyle} />
            {viewMode === 'SEARCH' ? (
              <>
                <h3 style={{ margin: '20px 0 8px 0', color: '#1e293b' }}>Searching the Map</h3>
                <p style={{ color: '#64748b', margin: 0, fontSize: '14px' }}>
                  Loading papers for <strong style={{ color: '#6366f1' }}>"{searchFilter?.query}"</strong>…
                </p>
              </>
            ) : (
              <>
                <h3 style={{ margin: '20px 0 8px 0', color: '#1e293b' }}>Loading Study Network</h3>
                <p style={{ color: '#64748b', margin: 0, fontSize: '14px' }}>Querying connected papers…</p>
              </>
            )}
          </div>
        </div>
      )}

      {showSearchPrompt && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3 style={{ margin: '0 0 4px 0' }}>Search the Map</h3>
            <p style={{ color: '#64748b', fontSize: '14px', margin: '0 0 20px 0' }}>
              Querying papers related to <strong style={{ color: '#6366f1' }}>"{pendingSearchQuery}"</strong>
            </p>
            <label style={labelStyle}>
              Minimum Citations
              <input type="number" min="0" value={minSearchCitations} onChange={e => setMinSearchCitations(Number(e.target.value))} style={inputStyle} />
            </label>
            <label style={labelStyle}>
              Max Papers to Return
              <input type="number" min="1" max="200" value={maxSearchPapers} onChange={e => setMaxSearchPapers(Number(e.target.value))} style={inputStyle} />
            </label>
            <div style={buttonContainerStyle}>
              <button onClick={cancelSearch} style={cancelButtonStyle}>Cancel</button>
              <button onClick={confirmSearch} style={confirmButtonStyle}>Search</button>
            </div>
          </div>
        </div>
      )}

      {showDetailPrompt && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3>Load Study Network</h3>
            <p>Load all papers connected to this one…</p>
            <label style={labelStyle}>
              Minimum Citations:
              <input type="number" value={minCitationsInput} onChange={(e) => setMinCitationsInput(Number(e.target.value))} style={inputStyle} />
            </label>
            <label style={labelStyle}>
              Max Papers to Display:
              <input type="number" value={maxPapersInput} onChange={(e) => setMaxPapersInput(Number(e.target.value))} style={inputStyle} />
            </label>
            <div style={buttonContainerStyle}>
              <button onClick={cancelDetailView} style={cancelButtonStyle}>Cancel</button>
              <button onClick={confirmDetailView} style={confirmButtonStyle}>Load</button>
            </div>
          </div>
        </div>
      )}

      {showTimeoutPrompt && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <h3>Request Taking Longer Than Expected</h3>
            <p>The query has taken more than 10 seconds. Keep waiting or cancel?</p>
            <div style={buttonContainerStyle}>
              <button onClick={handleTimeoutCancel} style={cancelButtonStyle}>Cancel</button>
              <button onClick={handleTimeoutWait} style={confirmButtonStyle}>Keep Waiting</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const modalOverlayStyle = {
  position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
  backgroundColor: 'rgba(255,255,255,0.7)', backdropFilter: 'blur(4px)',
  display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000,
};
const modalContentStyle = {
  backgroundColor: '#ffffff', color: '#1e293b', padding: '30px', borderRadius: '12px',
  width: '450px', maxWidth: '90%', fontFamily: 'Inter, sans-serif',
  boxShadow: '0 10px 40px rgba(0,0,0,0.1)', border: '1px solid rgba(0,0,0,0.05)'
};
const labelStyle = { display: 'block', margin: '16px 0 8px 0', fontSize: '14px', color: '#64748b', fontWeight: '600' };
const inputStyle = {
  width: '100%', padding: '10px', marginTop: '4px',
  backgroundColor: '#f8fafc', border: '1px solid #cbd5e1',
  color: '#334155', borderRadius: '6px', boxSizing: 'border-box',
  fontFamily: 'Inter, sans-serif', fontSize: '14px'
};
const buttonContainerStyle = { display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' };
const cancelButtonStyle = {
  padding: '10px 20px', backgroundColor: 'transparent',
  border: '1px solid #cbd5e1', color: '#64748b', borderRadius: '6px', cursor: 'pointer', fontWeight: '600'
};
const confirmButtonStyle = {
  padding: '10px 20px', backgroundColor: '#6366f1',
  border: 'none', color: 'white', borderRadius: '6px', cursor: 'pointer',
  fontWeight: 'bold', boxShadow: '0 2px 8px rgba(99, 102, 241, 0.3)'
};
const searchResultsBannerStyle = {
  position: 'fixed', top: 72, left: '50%', transform: 'translateX(-50%)',
  backgroundColor: 'rgba(255,255,255,0.92)', backdropFilter: 'blur(8px)',
  border: '1px solid rgba(0,0,0,0.08)', borderRadius: '20px', padding: '6px 18px',
  fontSize: '13px', fontFamily: 'Inter, sans-serif', boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
  zIndex: 100, pointerEvents: 'none', display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap',
};
const dotStyle = { color: '#cbd5e1', fontSize: '16px' };
const spinnerStyle = {
  width: '40px', height: '40px', border: '3px solid rgba(99, 102, 241, 0.15)',
  borderTopColor: '#6366f1', borderRadius: '50%', margin: '0 auto',
  animation: 'spin 0.8s linear infinite'
};
