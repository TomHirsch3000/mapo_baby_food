import React from 'react';
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
    neutral: 'Does not test this claim',
};

const STRENGTH_COLORS = {
    strong: '#10b981',
    moderate: '#6366f1',
    limited: '#f59e0b',
    mixed: '#94a3b8',
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

export const FooterPanel = ({ selected, hovered }) => {
    const node = hovered || selected;

    if (!node) {
        return (
            <div className="galaxy-footer" style={{ opacity: 1, pointerEvents: 'none' }}>
                <div style={{ textAlign: 'center', color: '#94a3b8', padding: '10px' }}>
                    Hover a node for details · click to open it
                </div>
            </div>
        );
    }

    const formatText = (t) => (t || '').replace(/<(\/?)[a-zA-Z0-9]+:([a-zA-Z0-9-]+)/g, '<$1$2');

    return (
        <div className="galaxy-footer" style={{ opacity: 1 }}>
            <div className="footer-content" onWheel={e => e.stopPropagation()}>
                <div className="footer-panel selected-panel" style={{ gridColumn: '1 / -1' }}>

                    {node.type === 'topic' && (
                        <>
                            <h4>Topic</h4>
                            <h3>{node.name}</h3>
                            <p style={{ color: '#64748b', margin: '4px 0 0', fontSize: '0.92rem' }}>
                                {node.description}
                            </p>
                            <StatRow>
                                <Stat value={node.claimCount} label="claims" />
                                <Stat value={node.researchedClaimCount} label="researched"
                                      colour={node.researchedClaimCount ? STANCE_COLORS.supports : '#cbd5e1'} />
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

                    {node.type === 'claim' && (() => {
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
                            <h4>Study</h4>
                            <h3 dangerouslySetInnerHTML={{ __html: formatText(node.title) }} />
                            <div className="footer-meta">
                                <span>{node.year}</span>
                                {node.citationCount !== undefined && <> • <span>{node.citationCount} citations</span></>}
                                {node.studyType && <> • <span>{node.studyType}</span></>}
                                {node.venue && <> • <span>{node.venue}</span></>}
                                {node.evidenceStrength && (
                                    <Badge text={`${node.evidenceStrength} evidence`}
                                           colour={STRENGTH_COLORS[node.evidenceStrength] || '#94a3b8'} />
                                )}
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
                </div>
            </div>
        </div>
    );
};
