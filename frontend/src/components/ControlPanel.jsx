import React from 'react';
import '../styles/Galaxy.css';
import { SearchBar } from './SearchBar';

/**
 * Header: breadcrumb back-button, claim search, title.
 *
 *   TOPICS -> CLAIMS -> EVIDENCE
 */
export const ControlPanel = ({
    viewMode,
    topicName,
    claimText,
    claimIndex,
    onClaimSelect,
    onBackToTopics,
    onBackToClaims,
    evidenceXAxis,
    onEvidenceXAxisChange,
    reading,
    onReadingChange,
    onOpenAbout,
}) => {
    const titles = {
        TOPICS: 'Map of Baby Science by Topic',
        CLAIMS: topicName || 'Claims',
        EVIDENCE: claimText || 'Evidence',
    };

    return (
        <div className="galaxy-header">
            <div className="controls-row controls-left">
                {viewMode === 'CLAIMS' && (
                    <button className="back-to-galaxy" onClick={onBackToTopics}>
                        ← All topics
                    </button>
                )}
                {/* How a two-sided paper is counted. Shown on both scatter
                    screens, because a claim's own position depends on it. */}
                {(viewMode === 'CLAIMS' || viewMode === 'EVIDENCE') && (
                    <div className="axis-toggle" role="group" aria-label="Reading of mixed evidence">
                        <span className="axis-toggle-label" title="How papers that cut both ways are counted">
                            mixed evidence
                        </span>
                        {[
                            { key: 'conservative', label: 'Conservative', hint: 'A mixed paper counts as supporting - the claim is technically upheld' },
                            { key: 'balanced', label: 'Balanced', hint: 'A mixed paper takes no side and sits on the midline' },
                            { key: 'liberal', label: 'Liberal', hint: 'A mixed paper counts as refuting - its caveats carry equal weight' },
                        ].map(opt => (
                            <button
                                key={opt.key}
                                className={`axis-toggle-btn${reading === opt.key ? ' is-active' : ''}`}
                                aria-pressed={reading === opt.key}
                                title={opt.hint}
                                onClick={() => onReadingChange(opt.key)}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                )}

                {viewMode === 'EVIDENCE' && (
                    <>
                        <button className="back-to-galaxy" onClick={onBackToClaims}>
                            ← {topicName || 'Claims'}
                        </button>
                        {/* Only the horizontal axis is swappable. Stance owns the
                            vertical everywhere, so it is never up for grabs. */}
                        <div className="axis-toggle" role="group" aria-label="Horizontal axis">
                            <span className="axis-toggle-label">x axis</span>
                            {[
                                { key: 'strength', label: 'Study strength' },
                                { key: 'year', label: 'Publication year' },
                            ].map(opt => (
                                <button
                                    key={opt.key}
                                    className={`axis-toggle-btn${evidenceXAxis === opt.key ? ' is-active' : ''}`}
                                    aria-pressed={evidenceXAxis === opt.key}
                                    onClick={() => onEvidenceXAxisChange(opt.key)}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </>
                )}
            </div>

            <div className="controls-right">
                <SearchBar claimIndex={claimIndex} onClaimSelect={onClaimSelect} />
                {/* Nothing on this map is guessable without it - the axes, the
                    sizes and the limits all need stating somewhere reachable. */}
                <button
                    className="about-button"
                    onClick={onOpenAbout}
                    aria-label="How to read this map"
                    title="How to read this map"
                >?</button>
            </div>

            <div className={`galaxy-title${viewMode === 'EVIDENCE' ? ' is-claim' : ''}`}>
                {titles[viewMode]}
            </div>
        </div>
    );
};
