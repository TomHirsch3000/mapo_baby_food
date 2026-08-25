import React, { useState, useRef, useEffect } from 'react';
import '../styles/Galaxy.css';
import { SearchBar } from './SearchBar';

/**
 * Header: breadcrumb back-button, title, and a cluster of icon buttons.
 *
 *   TOPICS -> CLAIMS -> EVIDENCE
 *
 * The reading and axis toggles used to sit in a column under the back button.
 * They are the least-used controls on the screen - both defaults are the ones
 * almost everyone wants - and they were the widest thing in the header, so on a
 * phone they either overlapped the title or pushed it off its own row. They now
 * live behind the tune button, which costs one tap and gives the title the
 * width it needs. Same on a laptop: one control cluster rather than two.
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

    const [settingsOpen, setSettingsOpen] = useState(false);
    const settingsRef = useRef(null);

    // Both screens with a scatter have something to tune; Topics has nothing.
    const hasSettings = viewMode === 'CLAIMS' || viewMode === 'EVIDENCE';

    useEffect(() => {
        if (!settingsOpen) return undefined;
        const onDown = (e) => {
            if (settingsRef.current && !settingsRef.current.contains(e.target)) {
                setSettingsOpen(false);
            }
        };
        const onKey = (e) => { if (e.key === 'Escape') setSettingsOpen(false); };
        document.addEventListener('mousedown', onDown);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDown);
            document.removeEventListener('keydown', onKey);
        };
    }, [settingsOpen]);

    // Closing on navigation matters: the panel's contents change with the view,
    // so leaving it open would show the previous screen's controls.
    useEffect(() => { setSettingsOpen(false); }, [viewMode]);

    const readingOptions = [
        { key: 'conservative', label: 'Conservative', hint: 'A mixed paper counts as supporting - the claim is technically upheld' },
        { key: 'balanced', label: 'Balanced', hint: 'A mixed paper takes no side and sits on the midline' },
        { key: 'liberal', label: 'Liberal', hint: 'A mixed paper counts as refuting - its caveats carry equal weight' },
    ];

    return (
        <div className={`galaxy-header galaxy-header--${viewMode.toLowerCase()}`}>
            <div className="controls-row controls-left">
                {viewMode === 'CLAIMS' && (
                    <button className="back-to-galaxy" onClick={onBackToTopics}>
                        ← All topics
                    </button>
                )}
                {viewMode === 'EVIDENCE' && (
                    <button className="back-to-galaxy" onClick={onBackToClaims}>
                        ← {topicName || 'Claims'}
                    </button>
                )}
            </div>

            <div className="controls-right">
                <SearchBar claimIndex={claimIndex} onClaimSelect={onClaimSelect} />

                {hasSettings && (
                    <div className="settings-wrap" ref={settingsRef}>
                        <button
                            className={`icon-button${settingsOpen ? ' is-open' : ''}`}
                            onClick={() => setSettingsOpen(o => !o)}
                            aria-expanded={settingsOpen}
                            aria-label="Display options"
                            title="Display options"
                        >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                 strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                                <line x1="4" y1="8" x2="20" y2="8" />
                                <circle cx="10" cy="8" r="2.4" fill="currentColor" stroke="none" />
                                <line x1="4" y1="16" x2="20" y2="16" />
                                <circle cx="16" cy="16" r="2.4" fill="currentColor" stroke="none" />
                            </svg>
                        </button>

                        {settingsOpen && (
                            <div className="settings-popover" role="dialog" aria-label="Display options">
                                {/* How a two-sided paper is counted. On both scatter
                                    screens, because a claim's own position depends on it. */}
                                <div className="settings-group">
                                    <span className="settings-label">Mixed evidence counts as</span>
                                    <div className="axis-toggle" role="group" aria-label="Reading of mixed evidence">
                                        {readingOptions.map(opt => (
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
                                </div>

                                {/* Only the horizontal axis is swappable. Stance owns
                                    the vertical everywhere, so it is never up for grabs. */}
                                {viewMode === 'EVIDENCE' && (
                                    <div className="settings-group">
                                        <span className="settings-label">Horizontal axis</span>
                                        <div className="axis-toggle" role="group" aria-label="Horizontal axis">
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
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

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
