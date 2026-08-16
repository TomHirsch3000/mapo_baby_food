import React, { useState, useRef, useEffect, useCallback } from 'react';

/**
 * Claim finder. Filters the flat claim index client-side and jumps straight to
 * the selected claim's evidence view — there is no server-side search.
 */
export const SearchBar = ({ claimIndex = [], onClaimSelect }) => {
    const [value, setValue] = useState('');
    const [suggestions, setSuggestions] = useState([]);
    const [highlightIndex, setHighlightIndex] = useState(-1);
    const [showDropdown, setShowDropdown] = useState(false);
    const inputRef = useRef(null);
    const wrapperRef = useRef(null);
    const debounceRef = useRef(null);

    const handleInputChange = useCallback((e) => {
        const q = e.target.value;
        setValue(q);
        setHighlightIndex(-1);

        clearTimeout(debounceRef.current);
        if (!q.trim() || claimIndex.length === 0) {
            setSuggestions([]);
            setShowDropdown(false);
            return;
        }

        debounceRef.current = setTimeout(() => {
            // Every term must appear somewhere in the claim, its topic or its
            // group, so "sleep peanut" matches nothing and "early peanut" does.
            const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
            const matches = claimIndex.filter(c => {
                const haystack =
                    `${c.title} ${c.topicName} ${c.group}`.toLowerCase();
                return terms.every(t => haystack.includes(t));
            }).slice(0, 8);
            setSuggestions(matches);
            setShowDropdown(matches.length > 0);
        }, 150);
    }, [claimIndex]);

    useEffect(() => {
        const handleMouseDown = (e) => {
            if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
                setShowDropdown(false);
            }
        };
        document.addEventListener('mousedown', handleMouseDown);
        return () => document.removeEventListener('mousedown', handleMouseDown);
    }, []);

    const handleSelect = (claim) => {
        setValue('');
        setSuggestions([]);
        setShowDropdown(false);
        setHighlightIndex(-1);
        if (onClaimSelect) onClaimSelect(claim);
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const pick = highlightIndex >= 0 ? suggestions[highlightIndex] : suggestions[0];
        if (pick) handleSelect(pick);
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Escape') {
            setValue('');
            setSuggestions([]);
            setShowDropdown(false);
            inputRef.current?.blur();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            setHighlightIndex(i => Math.min(i + 1, suggestions.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setHighlightIndex(i => Math.max(i - 1, -1));
        }
    };

    const truncate = (str, len) => (str && str.length > len ? `${str.slice(0, len)}…` : str);

    return (
        <form className="search-bar" onSubmit={handleSubmit} role="search">
            <div className="search-bar-inner" ref={wrapperRef}>
                <svg className="search-icon" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" strokeWidth="2">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                    ref={inputRef}
                    className="search-input"
                    type="text"
                    value={value}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    onFocus={() => { if (suggestions.length > 0) setShowDropdown(true); }}
                    placeholder="Find a claim, e.g. peanut…"
                    aria-label="Find a claim"
                    autoComplete="off"
                />
                {value && (
                    <button
                        type="button"
                        className="search-clear-btn"
                        onClick={() => { setValue(''); setSuggestions([]); setShowDropdown(false); }}
                        aria-label="Clear search"
                    >
                        ✕
                    </button>
                )}
                {showDropdown && suggestions.length > 0 && (
                    <ul className="autocomplete-dropdown" role="listbox">
                        {suggestions.map((s, i) => (
                            <li
                                key={s.id}
                                className={`autocomplete-item${i === highlightIndex ? ' highlighted' : ''}`}
                                onMouseDown={() => handleSelect(s)}
                                onMouseEnter={() => setHighlightIndex(i)}
                                role="option"
                                aria-selected={i === highlightIndex}
                            >
                                <span className="autocomplete-title">{truncate(s.title, 84)}</span>
                                <span className="autocomplete-galaxy">
                                    {s.topicName}{s.hasEvidence ? '' : ' · no evidence yet'}
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </form>
    );
};
