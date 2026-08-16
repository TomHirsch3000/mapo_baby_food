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
}) => {
    const titles = {
        TOPICS: 'Map of Baby Science by Topic',
        CLAIMS: topicName || 'Claims',
        EVIDENCE: claimText || 'Evidence',
    };

    return (
        <div className="galaxy-header">
            <div
                className="controls-row"
                style={{
                    display: 'flex', flexDirection: 'column', gap: '12px',
                    alignItems: 'flex-start', position: 'absolute',
                    top: 20, left: 20, pointerEvents: 'auto',
                }}
            >
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

            <div style={{ position: 'absolute', top: 20, right: 20, pointerEvents: 'auto' }}>
                <SearchBar claimIndex={claimIndex} onClaimSelect={onClaimSelect} />
            </div>

            <div className="galaxy-title">{titles[viewMode]}</div>
        </div>
    );
};
