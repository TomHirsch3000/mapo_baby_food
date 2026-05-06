import React from 'react';
import '../styles/Galaxy.css';
import { SearchBar } from './SearchBar';

export const ControlPanel = ({
    viewMode,
    layout,
    grouping,
    selected,
    activeGroupLabel,
    galaxyName,
    searchQuery,
    onBackToUniverse,
    onBackToGalaxy,
    onBackFromSearch,
    onLayoutChange,
    onGroupingChange,
    onSearch,
    paperIndex,
    onAutocompleteSelect
}) => {

    const layoutOptions = [
        { label: "Central", value: "CENTRAL" },
        { label: "Timeline", value: "TIMELINE" }
    ];

    // Grouping dimensions for baby food
    const groupingOptions = [
        { label: "Food Type", value: "FOOD_TYPE" },
        { label: "Baby Age", value: "AGE" },
        { label: "Recommendation", value: "RECOMMENDATION" }
    ];

    let headerTitle = "Map of Baby Food Science";
    if (viewMode === 'UNIVERSE') {
        headerTitle = "Map of Baby Food Science";
    } else if (viewMode === 'GALAXY') {
        headerTitle = galaxyName || "Topic View";
    } else if (viewMode === 'FIELD' || viewMode === 'DETAIL') {
        headerTitle = selected ? selected.title : (activeGroupLabel || "Papers");
    } else if (viewMode === 'SEARCH') {
        headerTitle = searchQuery ? `"${searchQuery}"` : "Search Results";
    }

    const isSearch = viewMode === 'SEARCH';

    return (
        <div className="galaxy-header">
            <div className="controls-row" style={{ display: 'flex', flexDirection: 'column', gap: '12px', alignItems: 'flex-start', position: 'absolute', top: 20, left: 20, pointerEvents: 'auto' }}>
                {viewMode === 'GALAXY' && <button className="back-to-galaxy" onClick={onBackToUniverse}>← Back</button>}
                {(viewMode === 'FIELD' || viewMode === 'DETAIL') && <button className="back-to-galaxy" onClick={onBackToGalaxy}>← Back</button>}
                {isSearch && <button className="back-to-galaxy" onClick={onBackFromSearch}>← Back</button>}

                {!isSearch && (
                    <div className="control-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <strong style={{ color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Layout</strong>
                        <div className="toggle-group">
                            {layoutOptions.map(opt => (
                                <button
                                    key={opt.value}
                                    className={`toggle-btn ${layout === opt.value ? 'active' : ''}`}
                                    onClick={() => onLayoutChange(opt.value)}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {viewMode === 'GALAXY' && (
                    <div className="control-group" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <strong style={{ color: '#64748b', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Group by</strong>
                        <div className="toggle-group">
                            {groupingOptions.map(opt => (
                                <button
                                    key={opt.value}
                                    className={`toggle-btn ${grouping === opt.value ? 'active' : ''}`}
                                    onClick={() => onGroupingChange(opt.value)}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            <div style={{ position: 'absolute', top: 20, right: 20, pointerEvents: 'auto' }}>
                <SearchBar onSearch={onSearch} currentQuery={searchQuery} paperIndex={paperIndex} onAutocompleteSelect={onAutocompleteSelect} />
            </div>

            <div className="galaxy-title">
                {headerTitle}
            </div>
        </div>
    );
};
