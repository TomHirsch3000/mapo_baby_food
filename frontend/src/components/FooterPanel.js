import React from 'react';
import * as d3 from 'd3';

export const FooterPanel = ({ selected, hovered, layoutMode, onDetailedViewClick }) => {
    const formatAbstract = (text) => {
        if (!text) return '';
        return text.replace(/<(\/?)[a-zA-Z0-9]+:([a-zA-Z0-9-]+)/g, '<$1$2');
    };

    const handleWheel = (e) => {
        e.stopPropagation();
    };

    const renderEvidenceBadge = (strength) => {
        const colors = {
            strong: '#10b981',
            moderate: '#6366f1',
            limited: '#f59e0b',
            mixed: '#94a3b8',
        };
        if (!strength) return null;
        return (
            <span style={{
                display: 'inline-block', padding: '2px 10px', borderRadius: '12px',
                fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase',
                letterSpacing: '0.05em', color: '#fff',
                backgroundColor: colors[strength.toLowerCase()] || '#94a3b8',
                marginLeft: '8px'
            }}>
                {strength} evidence
            </span>
        );
    };

    if (!selected && !hovered) {
        return (
            <div className="galaxy-footer" style={{ transform: 'translateY(0)', opacity: 1, pointerEvents: 'none' }}>
                <div className="footer-empty" style={{ textAlign: 'center', color: '#94a3b8', padding: '10px' }}>
                    Hover or select a node to view details
                </div>
            </div>
        );
    }

    return (
        <div className="galaxy-footer" style={{ transform: 'translateY(0)', opacity: 1, pointerEvents: 'auto' }} onWheel={handleWheel}>
            <div className="footer-panels" style={{ pointerEvents: 'auto' }}>

                {(selected?.isMenuNode || hovered?.isMenuNode) && (
                    <div className="footer-panel menu-panel" style={{ gridColumn: '1 / -1' }}>
                        <h4>About This Map</h4>
                        <h3>Map of Baby Food Science</h3>
                        <div className="footer-abstract" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(0,0,0,0.05)' }}>
                            <p>
                                This interactive map visualises the scientific evidence on infant and toddler nutrition.
                                Each cluster represents a body of research on a specific topic — from allergen introduction
                                to nutrient timing. Papers are sourced from OpenAlex and synthesised using a local LLM.
                            </p>
                            <p style={{ marginTop: '12px' }}>
                                <strong>How to use:</strong> Click a topic cluster to explore its papers.
                                Use the Layout and Group controls to switch between baby-age, food-type, and recommendation views.
                            </p>
                        </div>
                    </div>
                )}

                {selected && !selected.isMenuNode && (
                    <div className="footer-panel selected-panel">
                        <h4>Selected</h4>
                        <h3 dangerouslySetInnerHTML={{ __html: formatAbstract(selected.title) }}></h3>
                        <div className="footer-meta">
                            <span>{selected.year}</span>
                            {selected.citationCount !== undefined && <> • <span>{selected.citationCount} Citations</span></>}
                            {selected.studyType && <> • <span>{selected.studyType}</span></>}
                            {selected.evidenceStrength && renderEvidenceBadge(selected.evidenceStrength)}
                        </div>

                        {selected.recommendationSummary && (
                            <div style={{ margin: '12px 0 8px', padding: '10px 14px', backgroundColor: 'rgba(99,102,241,0.06)', borderRadius: '8px', borderLeft: '3px solid #6366f1' }}>
                                <strong style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#6366f1', letterSpacing: '1px' }}>Recommendation</strong>
                                <p style={{ margin: '4px 0 0', fontSize: '0.9rem', color: '#334155', lineHeight: 1.5 }}>{selected.recommendationSummary}</p>
                            </div>
                        )}

                        {(selected.likelihoodScore !== undefined || selected.seriousnessScore !== undefined) && (
                            <div style={{ display: 'flex', gap: '16px', margin: '8px 0' }}>
                                {selected.likelihoodScore !== undefined && (
                                    <div style={{ textAlign: 'center' }}>
                                        <div style={{ fontSize: '1.4rem', fontWeight: '700', color: '#6366f1' }}>{selected.likelihoodScore}%</div>
                                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>likelihood</div>
                                    </div>
                                )}
                                {selected.seriousnessScore !== undefined && (
                                    <div style={{ textAlign: 'center' }}>
                                        <div style={{ fontSize: '1.4rem', fontWeight: '700', color: '#f59e0b' }}>{selected.seriousnessScore}/10</div>
                                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>seriousness</div>
                                    </div>
                                )}
                                {selected.participantCount !== undefined && (
                                    <div style={{ textAlign: 'center' }}>
                                        <div style={{ fontSize: '1.4rem', fontWeight: '700', color: '#10b981' }}>{d3.format(",")(selected.participantCount)}</div>
                                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.5px' }}>participants</div>
                                    </div>
                                )}
                            </div>
                        )}

                        <div className="footer-abstract" style={{ marginBottom: '12px' }}>
                            <strong>Abstract</strong>
                            <p dangerouslySetInnerHTML={{ __html: formatAbstract(selected.abstract) }}></p>
                        </div>
                        {selected.authors && <div style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '8px' }}><strong>Authors:</strong> {selected.authors}</div>}
                        {selected.institutions && <div style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '16px' }}><strong>Institution:</strong> {selected.institutions}</div>}

                        <button
                            className="back-to-galaxy"
                            style={{ width: '100%', marginTop: 'auto', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', boxShadow: '0 2px 8px rgba(16,185,129,0.3)' }}
                            onClick={() => onDetailedViewClick && onDetailedViewClick(selected)}
                        >
                            Open Study Network
                        </button>
                    </div>
                )}

                {hovered && !hovered.isMenuNode && hovered.id !== selected?.id && (
                    <div className="footer-panel hover-panel" style={!selected ? { gridColumn: '1 / -1', pointerEvents: 'auto' } : { pointerEvents: 'auto' }}>
                        <h4>Hovering</h4>
                        {hovered.field === "Galaxy" || hovered.type === "galaxy" ? (
                            <>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                                    {hovered.iconPath && (
                                        <img
                                            src={hovered.iconPath?.startsWith('http') ? hovered.iconPath : (process.env.PUBLIC_URL + hovered.iconPath)}
                                            alt={hovered.name || hovered.title}
                                            style={{ width: '40px', height: '40px', objectFit: 'cover', borderRadius: '50%', opacity: 0.9 }}
                                        />
                                    )}
                                    <h3 style={{ margin: 0 }} dangerouslySetInnerHTML={{ __html: formatAbstract(hovered.title || hovered.name) }}></h3>
                                </div>
                                <div className="footer-meta" style={{ marginBottom: '8px' }}>
                                    <strong>{d3.format(",")(hovered.totalWorksCount || 0)}</strong> known works
                                    <span style={{ color: '#94a3b8' }}> • </span>
                                    <strong>{d3.format(",")(hovered.nodeCount || 0)}</strong> in map
                                </div>
                                {!hovered.hasPapers && (
                                    <div style={{ marginTop: '10px', color: '#64748b', fontStyle: 'italic', fontSize: '0.8rem' }}>
                                        Papers not yet imported. Run the notebook to fetch this topic.
                                    </div>
                                )}
                            </>
                        ) : (
                            <>
                                <h3 dangerouslySetInnerHTML={{ __html: formatAbstract(hovered.title || hovered.name) }}></h3>
                                <div className="footer-meta">
                                    {hovered.year && <span>{hovered.year} • </span>}
                                    {hovered.citationCount !== undefined && <span>{hovered.citationCount} Citations</span>}
                                    {hovered.nodeCount !== undefined && <span> • Papers: {hovered.nodeCount}</span>}
                                </div>
                                {hovered.abstract && (
                                    <div className="footer-abstract" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(0,0,0,0.05)', marginBottom: '8px' }}>
                                        <strong>Abstract</strong>
                                        <p style={{ fontSize: '0.9rem', lineHeight: '1.5' }} dangerouslySetInnerHTML={{ __html: formatAbstract(hovered.abstract) }}></p>
                                    </div>
                                )}
                                {hovered.authors && <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '5px' }}>{hovered.authors}</div>}
                            </>
                        )}
                    </div>
                )}
            </div>

            <div style={{ position: 'fixed', bottom: 10, right: 10, background: 'rgba(255,255,255,0.8)', backdropFilter: 'blur(4px)', padding: '4px 8px', borderRadius: '4px', fontSize: '10px', color: '#94a3b8', pointerEvents: 'none', fontFamily: 'monospace' }}>
                <span id="nav-debug-info">Zoom: 1.00 | X: 0 | Y: 0</span>
            </div>
        </div>
    );
};
