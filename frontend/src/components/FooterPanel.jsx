import React, { useState, useRef } from 'react';
import { STANCE_COLORS } from './Graph';

/**
 * Detail panel along the bottom. Shows whatever is under the cursor, falling
 * back to the pinned selection. Content differs per node type:
 *
 *   topic   what it covers, how much of it has been researched
 *   claim   the claim, its verdict, how strong the evidence is, coverage
 *   paper   the study, the evaluator's verdict on it, and the abstract
 */

const STANCE_LABELS = {
    supports: 'Supports this claim',
    refutes: 'Refutes this claim',
    mixed: 'Cuts both ways on this claim',
    neutral: 'Does not test this claim',
};

/**
 * What official guidance tells a parent, beside what the evidence says.
 *
 * These are two different questions and the map has only ever answered one. A
 * body can be confident where the literature is thin, and the gap between the
 * two is worth seeing rather than resolving.
 *
 * Where the NHS and the AAP DISAGREE, both are shown and the disagreement is
 * labelled. Seven claims are in that state - abstinence versus harm reduction
 * on bed-sharing, 4-6 months versus around 6 on peanut - and picking a winner
 * would throw away the most useful thing here: that confident official advice
 * is not unanimous. A parent is told that nowhere else.
 *
 * Every paraphrase is backed by a quote that was re-fetched and proved present
 * on the cited page. The URL is shown because a claim about what a body says
 * should be checkable in one click.
 */
const Guidance = ({ node }) => {
    const g = node.guidance;
    if (!g || (!g.nhs && !g.aap)) return null;
    const differ = g.agreement === 'differ';

    const Body = ({ label, body }) => body ? (
        <div style={{ margin: '4px 0 0' }}>
            <a href={body.url} target="_blank" rel="noopener noreferrer"
               style={{
                   fontSize: '0.66rem', fontWeight: 700, letterSpacing: '0.06em',
                   color: '#64748b', textDecoration: 'none', borderBottom: '1px dotted #cbd5e1',
               }}>{label}</a>
            <span style={{ fontSize: '0.84rem', color: '#475569', lineHeight: 1.45 }}>
                {' '}{body.says}
            </span>
        </div>
    ) : null;

    return (
        <div style={{
            margin: '10px 0 4px', padding: '8px 12px',
            background: differ ? '#fffbeb' : '#f8fafc',
            border: `1px solid ${differ ? '#fde68a' : '#e2e8f0'}`,
            borderLeft: `3px solid ${differ ? '#f59e0b' : '#94a3b8'}`,
            borderRadius: '6px',
        }}>
            <span style={{
                display: 'block', fontSize: '0.66rem', fontWeight: 700,
                textTransform: 'uppercase', letterSpacing: '0.07em',
                color: differ ? '#b45309' : '#94a3b8', marginBottom: '2px',
            }}>
                {differ ? 'official advice — the two bodies differ' : 'official advice'}
            </span>
            <Body label="NHS" body={g.nhs} />
            <Body label="AAP" body={g.aap} />
            {differ && g.note && (
                <p style={{
                    margin: '6px 0 0', fontSize: '0.78rem',
                    color: '#92400e', lineHeight: 1.4,
                }}>{g.note}</p>
            )}
        </div>
    );
};

const TestedAs = ({ node }) => {
    // Only worth showing where the two wordings diverge - i.e. where the
    // headline is prescriptive and no study could test it verbatim. The reader
    // asked their question in everyday terms; this is the honest translation
    // the evidence was actually graded against.
    if (!node.isPrescriptive || !node.testedAs) return null;
    return (
        <div style={{
            margin: '10px 0 4px', padding: '8px 12px',
            background: '#f8fafc', border: '1px solid #e2e8f0',
            borderLeft: '3px solid #94a3b8', borderRadius: '6px',
        }}>
            <span style={{
                display: 'block', fontSize: '0.66rem', fontWeight: 700,
                textTransform: 'uppercase', letterSpacing: '0.07em', color: '#94a3b8',
            }}>
                what the evidence was tested against
            </span>
            <span style={{ fontSize: '0.86rem', color: '#475569', lineHeight: 1.45 }}>
                {node.testedAs}
            </span>
        </div>
    );
};

const Badge = ({ text, colour }) => (
    <span style={{
        display: 'inline-block', padding: '2px 10px', borderRadius: '12px',
        fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: '0.05em', color: '#fff', backgroundColor: colour,
        marginLeft: '8px',
    }}>{text}</span>
);

const Stat = ({ value, label, colour = '#334155' }) => (
    <div style={{ textAlign: 'center', minWidth: '78px' }}>
        <div style={{ fontSize: '1.3rem', fontWeight: 700, color: colour }}>{value}</div>
        <div style={{
            fontSize: '0.68rem', color: '#94a3b8',
            textTransform: 'uppercase', letterSpacing: '0.5px',
        }}>{label}</div>
    </div>
);

const StatRow = ({ children }) => (
    <div style={{ display: 'flex', gap: '20px', margin: '10px 0 4px' }}>{children}</div>
);

// A claim's verdict in words. netSupport is a weighted ratio, not a vote count,
// so the wording deliberately avoids implying a simple tally.
const verdictOf = (net, decided) => {
    if (!decided) return { text: 'Not yet assessed', colour: STANCE_COLORS.unevaluated };
    if (net >= 0.6) return { text: 'Strongly supported', colour: STANCE_COLORS.supports };
    if (net >= 0.2) return { text: 'Leans supported', colour: STANCE_COLORS.supports };
    if (net > -0.2) return { text: 'Contested', colour: STANCE_COLORS.neutral };
    if (net > -0.6) return { text: 'Leans refuted', colour: STANCE_COLORS.refutes };
    return { text: 'Strongly refuted', colour: STANCE_COLORS.refutes };
};

/**
 * Everything known about one node. Two of these can be on screen at once: the
 * one you pinned by clicking, and the one under the cursor.
 */
const NodeDetail = ({ node, kind }) => {
    const formatText = (t) => (t || '').replace(/<(\/?)[a-zA-Z0-9]+:([a-zA-Z0-9-]+)/g, '<$1$2');
    return (
        <>
                {node.type === 'topic' && (
                    <>
                        <h4>Topic</h4>
                        <h3>{node.name}</h3>
                        <p style={{ color: '#64748b', margin: '4px 0 0', fontSize: '0.92rem' }}>
                            {node.description}
                        </p>
                        <StatRow>
                            <Stat value={node.claimCount} label="claims" />
                            <Stat value={(node.openAlexCount || 0).toLocaleString()} label="papers published" />
                            <Stat value={node.paperCount} label="papers held" />
                        </StatRow>
                        <p style={{ color: '#94a3b8', fontSize: '0.82rem', margin: '6px 0 0' }}>
                            {node.researchedClaimCount === 0
                                ? 'No evidence gathered for this topic yet — click to see its claims.'
                                : `Click to explore all ${node.claimCount} claims.`}
                        </p>
                    </>
                )}

                {(node.type === 'claim' || node.type === 'claim-anchor') && (() => {
                    const decided = (node.supports || 0) + (node.refutes || 0);
                    const verdict = verdictOf(node.netSupport || 0, decided);
                    return (
                        <>
                            <h4>{node.group} · {node.topicName}</h4>
                            <h3>{node.claim}</h3>
                            <div className="footer-meta">
                                <span style={{ color: verdict.colour, fontWeight: 700 }}>{verdict.text}</span>
                                {node.ageRange && <> • <span>{node.ageRange}</span></>}
                            </div>
                            <TestedAs node={node} />
                            <Guidance node={node} />
                            {node.hasEvidence ? (
                                <>
                                    <StatRow>
                                        <Stat value={node.supports} label="support" colour={STANCE_COLORS.supports} />
                                        <Stat value={node.refutes} label="refute" colour={STANCE_COLORS.refutes} />
                                        <Stat value={node.neutral} label="neutral" colour={STANCE_COLORS.neutral} />
                                        <Stat value={`${Math.round((node.evidenceQuality || 0) * 100)}%`}
                                              label="study quality" />
                                    </StatRow>
                                    <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '6px 0 0' }}>
                                        Assessed {node.paperCount} of{' '}
                                        <strong>{(node.openAlexCount || 0).toLocaleString()}</strong> papers
                                        matching this claim's search.
                                    </p>
                                </>
                            ) : (
                                <p style={{ color: '#64748b', fontSize: '0.9rem', margin: '10px 0 0', lineHeight: 1.5 }}>
                                    No evidence gathered yet.{' '}
                                    <strong>{(node.openAlexCount || 0).toLocaleString()}</strong> papers match
                                    this claim's search in OpenAlex — the node is sized by that, so a large
                                    circle here means a well-published question nobody has assessed.
                                </p>
                            )}
                        </>
                    );
                })()}

                {node.type === 'paper' && (
                    <>
                        <h4>
                            Study
                            {node.rank != null && (
                                <span style={{
                                    marginLeft: 8, padding: '2px 7px', borderRadius: 999,
                                    background: '#eef2ff', color: '#4f46e5',
                                    fontWeight: 800, letterSpacing: 0,
                                }}>#{node.rank}{node.rankTotal ? ` of ${node.rankTotal}` : ''} on this claim</span>
                            )}
                        </h4>
                        <h3 dangerouslySetInnerHTML={{ __html: formatText(node.title) }} />
                        <div className="footer-meta">
                            <span>{node.year}</span>
                            {node.citationCount !== undefined && <> • <span>{node.citationCount} citations</span></>}
                            {/* studyType used to print here too, but the badge
                                below already carries it - and carries the
                                normalised form ("randomised trial" rather than
                                "rct"), so this was the worse of the two. */}
                            {node.venue && <> • <span>{node.venue}</span></>}
                            {node.journalImpact != null && (
                                <> • <span title="OpenAlex 2-year mean citedness: the quantity a journal impact factor measures">
                                    journal impact <strong style={{ color: '#475569' }}>{node.journalImpact}</strong>
                                </span></>
                            )}
                            {node.studyDesign && (
                                <Badge text={node.studyDesign} colour="#64748b" />
                            )}
                            {/* The model's evidence-strength label used to be
                                badged here. It is gone: it duplicated the study
                                design beside it and disagreed with it, and the
                                design is the half that is right. Of the papers
                                it called "strong", 16% were a meta-analysis or
                                RCT and 23% were designs its own instructions
                                call limited; cross-sectional studies got
                                "strong" 359 times and "limited" 31 times. The
                                field is still in the data for auditing. */}
                        </div>

                        {node.stance && node.stance !== 'unevaluated' && (
                            <div style={{
                                margin: '12px 0 8px', padding: '10px 14px',
                                backgroundColor: `${STANCE_COLORS[node.stance]}14`,
                                borderRadius: '8px',
                                borderLeft: `3px solid ${STANCE_COLORS[node.stance]}`,
                            }}>
                                <strong style={{
                                    fontSize: '0.75rem', textTransform: 'uppercase',
                                    color: STANCE_COLORS[node.stance], letterSpacing: '1px',
                                }}>
                                    {STANCE_LABELS[node.stance]}
                                    {node.confidence != null && ` · ${node.confidence}% confidence`}
                                </strong>
                                {node.stanceSummary && (
                                    <p style={{ margin: '4px 0 0', fontSize: '0.9rem', color: '#334155', lineHeight: 1.5 }}>
                                        {node.stanceSummary}
                                    </p>
                                )}
                            </div>
                        )}

                        {node.abstract && (
                            <div className="footer-abstract" style={{ marginBottom: '10px' }}>
                                <strong>Abstract</strong>
                                <p dangerouslySetInnerHTML={{ __html: formatText(node.abstract) }} />
                            </div>
                        )}
                        {node.authors && (
                            <div style={{ fontSize: '0.84rem', color: '#64748b', marginBottom: '6px' }}>
                                <strong>Authors:</strong> {node.authors}
                            </div>
                        )}
                        {node.url && (
                            <a href={node.url} target="_blank" rel="noopener noreferrer"
                               style={{ fontSize: '0.85rem', color: '#6366f1', fontWeight: 600 }}>
                                Open paper ↗
                            </a>
                        )}
                    </>
                )}
        </>
    );
};

export const FooterPanel = ({ selected, hovered }) => {
    // A click pins; hovering something else shows it alongside rather than
    // replacing it. Comparing two papers was impossible before - reading the
    // second one threw the first one away - and comparing is most of what this
    // screen is for.
    //
    // Pinned goes left because it is the one you chose and it stays put;
    // whatever is under the cursor arrives on the right.
    const pinned = selected || null;
    const peeked = hovered && (!pinned || hovered.id !== pinned.id) ? hovered : null;
    const both = !!(pinned && peeked);
    const node = pinned || peeked;

    // Drag height. Null means "whatever the stylesheet says", which is the
    // 30-33vh band; once dragged the panel keeps the height it was given.
    //
    // A phone has no second screen to put this on and no hover to reveal it,
    // so it is the only way to read a node in full - and at a third of the
    // viewport it cuts off long claims. Dragging the grip is cheaper than a
    // scroll inside a panel that is itself inside a pannable map, where a
    // vertical swipe is ambiguous.
    const [height, setHeight] = useState(null);
    const footerRef = useRef(null);

    const startDrag = (e) => {
        const startY = e.clientY;
        const startH = footerRef.current?.getBoundingClientRect().height || 0;
        const handle = e.currentTarget;
        handle.setPointerCapture?.(e.pointerId);

        const move = (ev) => {
            // Up is taller: the panel grows out of the bottom edge.
            const next = startH + (startY - ev.clientY);
            const cap = (typeof window !== 'undefined' ? window.innerHeight : 800) * 0.85;
            setHeight(Math.max(64, Math.min(cap, next)));
        };
        const end = (ev) => {
            handle.releasePointerCapture?.(ev.pointerId);
            window.removeEventListener('pointermove', move);
            window.removeEventListener('pointerup', end);
            window.removeEventListener('pointercancel', end);
        };
        window.addEventListener('pointermove', move);
        window.addEventListener('pointerup', end);
        window.addEventListener('pointercancel', end);
    };

    // An explicit height has to beat the stylesheet's min AND max, or the
    // panel snaps back to the 30-33vh band the moment it leaves it.
    const sizing = height == null
        ? undefined
        : { height: `${height}px`, minHeight: 0, maxHeight: 'none' };

    const grip = (
        <div className="footer-grip" onPointerDown={startDrag}
             role="separator" aria-label="Resize panel" aria-orientation="horizontal">
            <span className="footer-grip-bar" />
        </div>
    );

    if (!node) {
        return (
            <div className="galaxy-footer" ref={footerRef}
                 style={{ opacity: 1, pointerEvents: 'none', ...sizing }}>
                {grip}
                <div style={{ textAlign: 'center', color: '#94a3b8', padding: '10px' }}>
                    Hover a node for details · click to open it
                </div>
            </div>
        );
    }

    const formatText = (t) => (t || '').replace(/<(\/?)[a-zA-Z0-9]+:([a-zA-Z0-9-]+)/g, '<$1$2');

    return (
        <div className="galaxy-footer" ref={footerRef} style={{ opacity: 1, ...sizing }}>
            {grip}
            <div className="footer-panels" onWheel={e => e.stopPropagation()}>
                {pinned && (
                    <div className="footer-panel selected-panel"
                         style={both ? undefined : { gridColumn: '1 / -1' }}>
                        <NodeDetail node={pinned} kind="pinned" />
                    </div>
                )}
                {peeked && (
                    <div className="footer-panel hover-panel"
                         style={both ? undefined : { gridColumn: '1 / -1' }}>
                        <NodeDetail node={peeked} kind="hovered" />
                    </div>
                )}
            </div>
        </div>
    );
};
