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
    // Closed, this is one more icon button in the cluster. The input only
    // exists once it is asked for, so the header carries three equal buttons
    // instead of two buttons and a 260px field that was the widest thing on
    // the screen and set how much room the title could have.
    const [open, setOpen] = useState(false);
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
                // Only fold away again if nothing has been typed - closing a
                // field mid-query would throw the query away.
                setOpen(o => (inputRef.current?.value ? o : false));
            }
        };
        document.addEventListener('mousedown', handleMouseDown);
        return () => document.removeEventListener('mousedown', handleMouseDown);
    }, []);

    // Focus follows opening, or the button would need a second tap to type.
    useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

    const handleSelect = (claim) => {
        setValue('');
        setSuggestions([]);
        setShowDropdown(false);
        setHighlightIndex(-1);
        setOpen(false);
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
            setOpen(false);
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

    const magnifier = (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
    );

    if (!open) {
        return (
            <button
                type="button"
                className="icon-button search-open-btn"
                onClick={() => setOpen(true)}
                aria-label="Find a claim"
                aria-expanded={false}
                title="Find a claim"
            >
                {magnifier}
            </button>
        );
    }

    return (
        <form className="search-bar is-open" onSubmit={handleSubmit} role="search">
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
                {!value && (
                    <button
                        type="button"
                        className="search-clear-btn"
                        onClick={() => setOpen(false)}
                        aria-label="Close search"
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
