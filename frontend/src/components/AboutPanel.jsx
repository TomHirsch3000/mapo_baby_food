import React, { useEffect } from 'react';
import { STANCE_COLORS } from './Graph';

/**
 * "How to read this map", reachable from the ? button in the header.
 *
 * The map encodes five things at once - position on two axes, size, colour, and
 * which level you are on - and none of that is guessable. A reader who has not
 * been told that up means supported and right means better studies is looking
 * at a scatter of dots.
 *
 * The limitations section is not a disclaimer bolted on the end. Stating plainly
 * that stances are machine-assigned, that prescriptive claims get translated,
 * and that coverage is partial is what earns the rest of it any credibility.
 */

const Dot = ({ colour, label }) => (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginRight: 14 }}>
        <span style={{
            width: 11, height: 11, borderRadius: '50%',
            background: colour, flexShrink: 0,
        }} />
        <span style={{ fontSize: '0.82rem', color: '#475569' }}>{label}</span>
    </span>
);

const Section = ({ title, children }) => (
    <section style={{ marginBottom: 22 }}>
        <h3 style={{
            margin: '0 0 8px', fontSize: '0.72rem', fontWeight: 800,
            letterSpacing: '0.09em', textTransform: 'uppercase', color: '#94a3b8',
        }}>{title}</h3>
        {children}
    </section>
);

const Level = ({ n, name, children }) => (
    <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
        <div style={{
            flexShrink: 0, width: 26, height: 26, borderRadius: '50%',
            background: '#eef2ff', color: '#6366f1', fontWeight: 800,
            fontSize: '0.8rem', display: 'flex', alignItems: 'center',
            justifyContent: 'center',
        }}>{n}</div>
        <div>
            <strong style={{ fontSize: '0.92rem', color: '#1e293b' }}>{name}</strong>
            <div style={{ fontSize: '0.88rem', color: '#475569', lineHeight: 1.55, marginTop: 2 }}>
                {children}
            </div>
        </div>
    </div>
);

/** The quadrant diagram, drawn rather than described - it reads far faster. */
const AxisDiagram = () => (
    <svg viewBox="0 0 300 190" style={{ width: '100%', maxWidth: 330, display: 'block' }}
         role="img" aria-label="Supported at top, refuted at bottom; weaker studies left, stronger right">
        <line x1="150" y1="14" x2="150" y2="176" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4 4" />
        <line x1="18" y1="95" x2="282" y2="95" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4 4" />

        <text x="150" y="10" textAnchor="middle" fontSize="9.5" fontWeight="800"
              fill="#94a3b8" letterSpacing="0.08em">SUPPORTED</text>
        <text x="150" y="186" textAnchor="middle" fontSize="9.5" fontWeight="800"
              fill="#94a3b8" letterSpacing="0.08em">REFUTED</text>
        <text x="14" y="99" textAnchor="end" fontSize="9.5" fontWeight="800"
              fill="#94a3b8" letterSpacing="0.08em" transform="rotate(-90 14 99)">WEAKER</text>
        <text x="288" y="99" textAnchor="start" fontSize="9.5" fontWeight="800"
              fill="#94a3b8" letterSpacing="0.08em" transform="rotate(90 288 99)">STRONGER</text>

        <text x="160" y="36" fontSize="11" fontWeight="700" fill="#2e9e5b">SETTLED</text>
        <text x="160" y="49" fontSize="9.5" fill="#94a3b8">strong + supported</text>
        <text x="140" y="36" fontSize="11" fontWeight="700" fill="#7ba05b" textAnchor="end">PROMISING</text>
        <text x="140" y="49" fontSize="9.5" fill="#94a3b8" textAnchor="end">weak + supported</text>
        <text x="160" y="150" fontSize="11" fontWeight="700" fill="#d64545">DEBUNKED</text>
        <text x="160" y="163" fontSize="9.5" fill="#94a3b8">strong + refuted</text>
        <text x="140" y="150" fontSize="11" fontWeight="700" fill="#c07a7a" textAnchor="end">DOUBTFUL</text>
        <text x="140" y="163" fontSize="9.5" fill="#94a3b8" textAnchor="end">weak + refuted</text>

        <circle cx="150" cy="95" r="16" fill="#94a3b8" fillOpacity="0.12" />
        <text x="150" y="98" textAnchor="middle" fontSize="8.5" fontWeight="700" fill="#64748b">contested</text>
    </svg>
);

export const AboutPanel = ({ open, onClose }) => {
    useEffect(() => {
        if (!open) return;
        const onKey = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div
            onClick={onClose}
            style={{
                position: 'fixed', inset: 0, zIndex: 400,
                background: 'rgba(15,23,42,0.32)', backdropFilter: 'blur(3px)',
                display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
                padding: '5vh 16px', overflowY: 'auto',
            }}
        >
            <div
                role="dialog" aria-modal="true" aria-label="How to read this map"
                onClick={e => e.stopPropagation()}
                style={{
                    background: '#fff', borderRadius: 16, maxWidth: 680, width: '100%',
                    padding: '28px 32px 32px', boxShadow: '0 24px 70px rgba(15,23,42,0.28)',
                    fontFamily: 'Inter, system-ui, sans-serif',
                }}
            >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: '1.35rem', color: '#1e293b', fontWeight: 800 }}>
                            Map of Baby Science
                        </h2>
                        <p style={{ margin: '6px 0 0', fontSize: '0.95rem', color: '#475569', lineHeight: 1.55 }}>
                            What the evidence actually says about the claims people make
                            about raising children — and how good that evidence is.
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        aria-label="Close"
                        style={{
                            flexShrink: 0, border: 0, background: '#f1f5f9', color: '#64748b',
                            width: 30, height: 30, borderRadius: '50%', cursor: 'pointer',
                            fontSize: '1.05rem', lineHeight: 1,
                        }}
                    >×</button>
                </div>

                <hr style={{ border: 0, borderTop: '1px solid #e2e8f0', margin: '20px 0 22px' }} />

                <Section title="Why it exists">
                    <p style={{ margin: 0, fontSize: '0.9rem', color: '#475569', lineHeight: 1.6 }}>
                        Advice about babies arrives constantly, and almost none of it comes
                        with any sign of how well established it is. “Don’t give honey before
                        one” and “screens harm attention” are said in the same confident tone,
                        though one is settled and the other is contested. This map shows the
                        difference — the weight of evidence behind a claim, how good the
                        studies are, and the papers themselves.
                    </p>
                </Section>

                <Section title="Three levels">
                    <Level n="1" name="Topics">
                        The areas of decision-making in raising a child, as hexagons. Each
                        shows how many claims it holds and how many have been researched.
                    </Level>
                    <Level n="2" name="Claims">
                        The common claims in that topic, plotted on the two axes below.
                        Node size is <strong>how much has been published</strong> on the
                        question — so a big, pale, unassessed node means a well-studied
                        question we haven’t collected yet.
                    </Level>
                    <Level n="3" name="Evidence">
                        The individual papers behind one claim, on the same axes. Size is
                        citations. The claim itself comes with you as a circle, pinned where
                        it sat on the level above, so you can see the verdict against the
                        papers it was drawn from.
                    </Level>
                </Section>

                <Section title="Reading the axes">
                    <p style={{ margin: '0 0 10px', fontSize: '0.9rem', color: '#475569', lineHeight: 1.6 }}>
                        The axes mean the same thing on every screen. <strong>Up is more
                        supported</strong>; <strong>right is better studies</strong>.
                    </p>
                    <AxisDiagram />
                    <p style={{ margin: '10px 0 0', fontSize: '0.85rem', color: '#64748b', lineHeight: 1.55 }}>
                        The middle is where genuinely contested claims sit. On the evidence
                        screen you can swap the horizontal axis to publication year to see
                        whether a question settled over time or is still being argued.
                    </p>
                    <p style={{ margin: '10px 0 0', fontSize: '0.85rem', color: '#64748b', lineHeight: 1.55 }}>
                        “Better studies” means the <strong>study design</strong>, ranked the way
                        medicine ranks it — meta-analyses and randomised trials furthest right,
                        then cohorts, then case-control, then cross-sectional surveys, with case
                        reports, animal work, opinion pieces and guidelines furthest left. A
                        claim’s position is the average of its own papers, so a claim only sits
                        right if the studies behind it genuinely do.
                    </p>
                </Section>

                <Section title="Colours">
                    <div style={{ marginBottom: 8 }}>
                        <Dot colour={STANCE_COLORS.supports} label="supports the claim" />
                        <Dot colour={STANCE_COLORS.refutes} label="refutes it" />
                        <Dot colour={STANCE_COLORS.mixed} label="cuts both ways" />
                        <Dot colour={STANCE_COLORS.neutral} label="background" />
                    </div>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b', lineHeight: 1.55 }}>
                        Grey <strong>background</strong> papers don’t test the claim, so they sit
                        in their own box to the left rather than on the axes — they aren’t
                        evidence for or against anything. They’re there because the papers that
                        <em> do</em> test the claim cite them, which makes them the shared
                        groundwork the argument rests on. Citation lines still run from the box
                        into the studies that lean on it. Only the most-cited are shown, and the
                        box says how many of the total that is.
                    </p>
                </Section>

                <Section title="Papers that cut both ways">
                    <p style={{ margin: '0 0 8px', fontSize: '0.9rem', color: '#475569', lineHeight: 1.6 }}>
                        A study can find that <em>a lot</em> of something is harmful while
                        <em> good-quality</em> exposure helps. Squeezing that into “supports”
                        or “refutes” throws away the most interesting thing it says, so it’s
                        marked <strong style={{ color: STANCE_COLORS.mixed }}>mixed</strong> and
                        you choose how it should count:
                    </p>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.88rem', color: '#475569', lineHeight: 1.7 }}>
                        <li><strong>Conservative</strong> — counts as supporting: technically the claim holds.</li>
                        <li><strong>Balanced</strong> — counts as neither; it sits in the middle.</li>
                        <li><strong>Liberal</strong> — counts as refuting: the caveats matter as much.</li>
                    </ul>
                    <p style={{ margin: '8px 0 0', fontSize: '0.85rem', color: '#64748b', lineHeight: 1.55 }}>
                        Watch what moves as you switch. A claim that looks solid under one
                        reading and shaky under another is not a settled claim.
                    </p>
                </Section>

                <Section title="What you should know before trusting it">
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.88rem', color: '#475569', lineHeight: 1.75 }}>
                        <li>
                            <strong>This is not medical advice.</strong> It’s a map of published
                            research. Decisions about your child belong with you and your
                            health professional.
                        </li>
                        <li>
                            <strong>Stances are assigned by an AI reading each abstract</strong>,
                            not by a human expert, and it gets some wrong. That’s why every
                            paper shows the finding the verdict was based on — if the badge and
                            the reason disagree, trust the reason and treat the badge as suspect.
                        </li>
                        <li>
                            <strong>Some claims are advice, and advice can’t be tested.</strong>
                            “Honey should be avoided before 12 months” is guidance; what studies
                            measure is whether honey before 12 months is linked to botulism. Where
                            the two differ, the tested wording is shown on the claim so you can
                            see exactly what was graded.
                        </li>
                        <li>
                            <strong>Coverage is partial.</strong> This samples the literature, it
                            doesn’t exhaust it. Claims with no evidence collected still appear,
                            sized by how much has been published, so you can see the gaps rather
                            than mistake them for absence of research.
                        </li>
                        <li>
                            <strong>Only abstracts are read</strong>, not full papers, so nuance
                            buried past the abstract is missed.
                        </li>
                    </ul>
                </Section>

                <p style={{
                    margin: 0, paddingTop: 16, borderTop: '1px solid #e2e8f0',
                    fontSize: '0.82rem', color: '#94a3b8', lineHeight: 1.55,
                }}>
                    Paper data from <strong>OpenAlex</strong>. Every paper links to its source —
                    follow it and read the original.
                </p>
            </div>
        </div>
    );
};
