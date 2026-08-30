/**
 * Mounts the real App in jsdom, walks TOPICS -> CLAIMS -> EVIDENCE, and fails
 * on any error thrown from a render or an effect.
 *
 * Three separate blank screens this session were runtime-only faults that
 * `npm run build` reported nothing about: a temporal-dead-zone call, an edge
 * pointing at a filtered-out node, and this one. A build that succeeds says
 * almost nothing, so the views need actually mounting.
 */
import { JSDOM } from 'jsdom';
import fs from 'fs';
import path from 'path';

const ROOT = path.resolve('public');
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>',
                      { pretendToBeVisual: true, url: 'http://localhost/' });

global.window = dom.window;
global.document = dom.window.document;
// Node 26 exposes navigator as a getter-only global.
Object.defineProperty(global, 'navigator', {
    value: dom.window.navigator, configurable: true, writable: true,
});
global.HTMLElement = dom.window.HTMLElement;
global.SVGElement = dom.window.SVGElement;
global.Node = dom.window.Node;
global.getComputedStyle = dom.window.getComputedStyle;
global.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
global.cancelAnimationFrame = clearTimeout;
global.IS_REACT_ACT_ENVIRONMENT = true;

// jsdom does no layout, so every element reports clientWidth/clientHeight 0 and
// the Graph effect bails out before drawing anything. Give it a real viewport.
for (const [prop, value] of [['clientWidth', 1440], ['clientHeight', 800],
                             ['offsetWidth', 1440], ['offsetHeight', 800]]) {
    Object.defineProperty(dom.window.HTMLElement.prototype, prop,
        { configurable: true, get() { return value; } });
}
// d3-zoom's defaultExtent reads svg.width.baseVal.value; jsdom implements no
// SVG animated attributes at all.
for (const [prop, value] of [['width', 1440], ['height', 800]]) {
    Object.defineProperty(dom.window.SVGSVGElement.prototype, prop,
        { configurable: true, get() { return { baseVal: { value } }; } });
}
// d3-transition interpolates transforms via svgNode.transform.baseVal
// .consolidate(); jsdom has no SVGAnimatedTransformList. Returning null is the
// library's own documented fallback - it interpolates from identity instead.
Object.defineProperty(dom.window.SVGElement.prototype, 'transform', {
    configurable: true,
    get() { return { baseVal: { consolidate: () => null, numberOfItems: 0 } }; },
});
dom.window.SVGElement.prototype.getScreenCTM = function () {
    return { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0, inverse: () => this.getScreenCTM() };
};
dom.window.SVGElement.prototype.createSVGPoint = function () {
    return { x: 0, y: 0, matrixTransform: () => ({ x: 0, y: 0 }) };
};

// Serve ./public off disk so the app's relative fetches resolve.
global.fetch = async (url) => {
    const rel = String(url).replace(/^\.\//, '').replace(/^\//, '');
    const file = path.join(ROOT, rel);
    if (!fs.existsSync(file)) return { ok: false, status: 404, json: async () => { throw new Error('404'); } };
    const body = fs.readFileSync(file, 'utf8');
    return { ok: true, status: 200, json: async () => JSON.parse(body) };
};

const errors = [];
const origError = console.error;
console.error = (...a) => { errors.push(a.map(String).join(' ')); origError(...a); };
dom.window.addEventListener('error', e => errors.push(`window.error: ${e.message}`));
process.on('unhandledRejection', r => errors.push(`unhandledRejection: ${r}`));

const React = (await import('react')).default;
const { createRoot } = await import('react-dom/client');
const { act } = await import('react');
const App = (await import('../src/App.jsx')).default;

const container = document.getElementById('root');
const root = createRoot(container);

const settle = async (ms = 120) => {
    await act(async () => { await new Promise(r => setTimeout(r, ms)); });
};

const clickFirstNode = async (label) => {
    const nodes = container.querySelectorAll('.d3-node');
    if (!nodes.length) throw new Error(`${label}: no .d3-node rendered`);
    // Pick the node with the most children — a real topic/claim, not a stray.
    const target = nodes[0];
    await act(async () => {
        // mouseover first, and never a mouseout: that is what a real click is,
        // and it is what left a stale `hovered` pointing at a node the next
        // screen has never heard of.
        target.dispatchEvent(new dom.window.MouseEvent('mouseover', { bubbles: true }));
        target.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
        await new Promise(r => setTimeout(r, 200));
    });
    return nodes.length;
};

let step = 'mount';
try {
    await act(async () => { root.render(React.createElement(App)); });
    await settle(400);
    const topics = container.querySelectorAll('.d3-node').length;
    console.log(`TOPICS   mounted, ${topics} hexagons, svg children ${container.querySelector('svg')?.childNodes.length ?? 0}`);
    if (!topics) throw new Error('no topic nodes rendered');

    // The theme headings are drawn straight to the DOM from the layout engine's
    // cluster boxes, a path no other screen exercises. A topic missing from
    // TOPIC_THEMES collects in a trailing "More" block rather than vanishing,
    // so the failure this guards against is silent by design: the page still
    // renders, just with an unnamed clump on the end.
    const headings = [...container.querySelectorAll('.g-hex-bg text')].map(t => t.textContent);
    console.log(`         themes: ${headings.join(' | ') || '(none)'}`);
    if (headings.length < 2) throw new Error('theme headings did not render');
    if (headings.some(h => h === 'MORE')) throw new Error('a topic is missing from TOPIC_THEMES');

    step = 'topics -> claims';
    await clickFirstNode('TOPICS');
    await settle(500);
    const claims = container.querySelectorAll('.d3-node').length;
    const title = container.querySelector('.galaxy-title')?.textContent?.trim();
    console.log(`CLAIMS   ${claims} nodes, title "${title}"`);
    if (!claims) throw new Error('CLAIMS view rendered no nodes (blank screen)');

    // Where the camera actually ended up. The claims data is fetched, so the
    // first render after navigating has no nodes - and that render used to
    // spend the one-shot "view changed" fit, leaving the map parked wherever
    // the topics screen had left it. Nothing about that is visible to a
    // node-count check.
    step = 'claims view is centred';
    {
        const fitted = container.querySelector('svg')?.getAttribute('data-fitted-view');
        if (fitted !== 'CLAIMS') {
            throw new Error(`CLAIMS never got its own fit (data-fitted-view="${fitted}") - `
                          + `the one-shot was spent on the empty loading render`);
        }
        const gMain = container.querySelector('.g-main');
        const t = gMain?.getAttribute('transform') || '';
        const m = t.match(/translate\(([-\d.]+)[ ,]+([-\d.]+)\)\s*scale\(([-\d.]+)\)/);
        if (!m) throw new Error(`no zoom transform on .g-main after entering CLAIMS (got "${t}")`);
        const [tx, ty, k] = [parseFloat(m[1]), parseFloat(m[2]), parseFloat(m[3])];
        const pts = [...container.querySelectorAll('.d3-node')]
            .map(n => n.__data__).filter(d => d && Number.isFinite(d.x));
        const cx = pts.reduce((a, d) => a + d.x, 0) / pts.length;
        const cy = pts.reduce((a, d) => a + d.y, 0) / pts.length;
        const sx = tx + k * cx, sy = ty + k * cy;
        const offX = Math.abs(sx - 1440 / 2), offY = Math.abs(sy - 800 / 2);
        console.log(`CENTRED  node centroid lands at ${sx.toFixed(0)},${sy.toFixed(0)} on a 1440x800 canvas (off by ${offX.toFixed(0)},${offY.toFixed(0)})`);
        if (offX > 200 || offY > 200) {
            throw new Error(`claims view is not centred: centroid off by ${offX.toFixed(0)},${offY.toFixed(0)}`);
        }
    }

    step = 'claims -> evidence';
    await clickFirstNode('CLAIMS');
    await settle(600);
    const ev = container.querySelectorAll('.d3-node').length;
    console.log(`EVIDENCE ${ev} nodes, title "${container.querySelector('.galaxy-title')?.textContent?.trim()?.slice(0,50)}"`);
    if (!ev) throw new Error('EVIDENCE view rendered no nodes (blank screen)');

    // The evidence view carries three pieces of bespoke furniture that no other
    // screen exercises, and each fails silently: a compact summary in place of
    // the paper title, hairline spokes to the claim, and a claim rendered as a
    // card rather than the circle it used to be. A blank-screen check passes
    // straight through all three.
    const compact = [...container.querySelectorAll('.node-paper-compact')]
        .filter(e => e.textContent.trim().length);
    // Every paper carries its rank, and the ranks must be a clean 1..n: a
    // duplicate or a gap means the scoring produced a tie it could not break,
    // or that a paper fell out of the ranking pass entirely.
    const ranks = [...container.querySelectorAll('.d3-node')]
        .map(n => n.__data__).filter(d => d && d.type === 'paper')
        .map(d => d.rank);
    const missing = ranks.filter(r => r == null).length;
    const unique = new Set(ranks).size;
    console.log(`         ranks 1..${Math.max(...ranks)} · ${unique} distinct · ${missing} missing`);
    if (missing) throw new Error(`${missing} papers have no rank`);
    if (unique !== ranks.length) throw new Error('duplicate ranks - the tie-break is not total');

    // Journal impact is the metric the ranking leans on; if the join silently
    // produced nothing the ranking still "works", just on two inputs.
    const withImpact = [...container.querySelectorAll('.d3-node')]
        .map(n => n.__data__).filter(d => d && d.type === 'paper' && d.journalImpact != null).length;
    console.log(`         ${withImpact}/${ranks.length} papers carry a journal impact`);
    // Size has to actually vary. It stopped meaning anything once cards were
    // uniform, and a normalisation bug would silently return it to that.
    const widths = [...container.querySelectorAll('.d3-node')]
        .map(n => n.__data__).filter(d => d && d.type === 'paper' && d.stance !== 'neutral')
        .map(d => d._w).filter(Number.isFinite);
    const spread = Math.max(...widths) / Math.min(...widths);
    console.log(`         card widths ${Math.min(...widths).toFixed(0)}-${Math.max(...widths).toFixed(0)}px (${spread.toFixed(1)}x spread)`);
    if (spread < 2) throw new Error(`card sizes barely differ (${spread.toFixed(2)}x) - importance is not driving size`);
    if (withImpact < ranks.length * 0.5) {
        throw new Error(`only ${withImpact} of ${ranks.length} papers have a journal impact`);
    }
    const spokes = container.querySelectorAll('.g-spokes line').length;
    const anchorCard = container.querySelectorAll('.claim-card-bar').length;
    console.log(`         ${compact.length} paper summaries e.g. "${compact[0]?.textContent.trim().replace(/\s+/g, ' ')}"`);
    console.log(`         ${spokes} spokes · ${anchorCard} claim card(s) · ${container.querySelectorAll('.d3-link').length} citation ribbons`);
    if (!compact.length) throw new Error('paper cards show no summary text');
    if (!anchorCard) throw new Error('the claim anchor did not render as a card');
    // The reading and axis toggles live behind the tune button now, so they
    // are only in the DOM once it is open. Opening it is part of the test:
    // a popover that fails to open takes both controls with it, silently.
    // Arriving greyed out. Every paper dimmed to 0.15 because the claim still
    // under the cursor was treated as the focus node, and nothing on this
    // screen shares its id - so nothing counted as connected to it. It cleared
    // as soon as the pointer moved, which is what made it look intermittent.
    step = 'evidence arrives at full opacity';
    const dimmed = [...container.querySelectorAll('.d3-node')]
        .filter(n => {
            const o = parseFloat(n.style.opacity);
            return Number.isFinite(o) && o < 0.9;
        });
    console.log(`         ${dimmed.length} of ${container.querySelectorAll('.d3-node').length} nodes dimmed on arrival`);
    if (dimmed.length) {
        throw new Error(`${dimmed.length} nodes arrived dimmed - stale focus from the previous view`);
    }

    // A clicked paper must stay open when the pointer leaves it. Clicking is
    // how you pin one to read; if it collapses the moment you move the mouse,
    // pinning is useless.
    // The claim sits where its best evidence is, not in the middle of the pack.
    // A plain mean of every design rank left it huddled among the weak studies
    // that make up most of any literature; it should be pulled right when
    // strong work exists.
    step = 'the claim sits toward the stronger studies';
    {
        const nodes = [...container.querySelectorAll('.d3-node')].map(n => n.__data__);
        const anchor = nodes.find(d => d && d.type === 'claim-anchor');
        const ranks = nodes.filter(d => d && d.type === 'paper' && Number.isFinite(d.designRank))
                           .map(d => d.designRank).sort((a, b) => a - b);
        const median = ranks[Math.floor(ranks.length / 2)];
        const best = ranks[ranks.length - 1];
        console.log(`ANCHOR   claim quality ${anchor.evidenceQuality?.toFixed(2)} vs median paper ${median.toFixed(2)}, best ${best.toFixed(2)}`);
        if (best > median && !(anchor.evidenceQuality > median)) {
            throw new Error(`the claim sits at ${anchor.evidenceQuality} - at or left of the median paper (${median}) despite stronger studies existing (${best})`);
        }
    }

    step = 'a pinned paper stays open';
    {
        const papers = [...container.querySelectorAll('.d3-node')]
            .filter(n => n.__data__ && n.__data__.type === 'paper');
        const target = papers[0];
        const compact = target.__data__._compactW;

        await act(async () => {
            target.dispatchEvent(new dom.window.MouseEvent('mouseover', { bubbles: true }));
            target.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
            await new Promise(r => setTimeout(r, 300));
        });
        const openW = parseFloat(target.querySelector('.node-paper-card')?.getAttribute('width'));

        await act(async () => {
            target.dispatchEvent(new dom.window.MouseEvent('mouseout', { bubbles: true }));
            await new Promise(r => setTimeout(r, 400));
        });
        const afterW = parseFloat(target.querySelector('.node-paper-card')?.getAttribute('width'));

        // Open, the card has to carry the detail - not just the title.
        const openText = target.querySelector('.node-paper-title')?.textContent || '';
        const has = (re, what) => { if (!re.test(openText)) throw new Error(`open card is missing ${what}: "${openText.slice(0,90)}"`); };
        has(/#\d+/, 'its rank');
        has(/\d+%\s*(for|against|mixed)|context only/, 'the verdict');
        // On a decisive paper the count moved into the breakdown, where it
        // carries the contribution it made; a context paper keeps the bare row.
        has(/\d+ cites|citations[\s\d,]+/, 'a citation count');
        // Structural guard, not a size one: the detail row must be a sibling of
        // the title with its own box, so a title that overruns clamps instead
        // of pushing the detail out of a box that hides its overflow.
        const titleDiv = target.querySelector('.node-paper-title');
        const kids = titleDiv ? [...titleDiv.children] : [];
        // Title + detail, plus the importance breakdown on anything that is
        // actually evidence. Context papers are ranked by the same arithmetic
        // but are excluded from the plot, so they do not get the block.
        const wantBlocks = target.__data__.stance === 'neutral' ? 2 : 3;
        if (kids.length !== wantBlocks) {
            throw new Error(`open card should be ${wantBlocks} blocks, found ${kids.length}`);
        }
        if (!/line-clamp/.test(kids[0].getAttribute('style') || '')) {
            throw new Error('the title is not clamped - a long one will push the detail out of view');
        }
        // The case that actually broke: hovering a DIFFERENT card must not
        // close the pinned one. In a plot this dense, moving the pointer off a
        // card nearly always crosses another, so keying "open" off a single
        // focus node made pinning look broken.
        const other = papers.find(n => n !== target && n.__data__.stance !== 'neutral');
        await act(async () => {
            other.dispatchEvent(new dom.window.MouseEvent('mouseover', { bubbles: true }));
            await new Promise(r => setTimeout(r, 350));
        });
        const pinnedStill = parseFloat(target.querySelector('.node-paper-card')?.getAttribute('width'));
        const otherW = parseFloat(other.querySelector('.node-paper-card')?.getAttribute('width'));
        console.log(`PIN      compact ${compact?.toFixed(0)}px -> clicked ${openW?.toFixed(0)}px -> pointer left ${afterW?.toFixed(0)}px`);
        console.log(`         hovering another card: pinned ${pinnedStill?.toFixed(0)}px, hovered ${otherW?.toFixed(0)}px (both should be open)`);
        if (!(pinnedStill > compact + 20)) {
            throw new Error(`the pinned card closed when another was hovered (${pinnedStill}px)`);
        }
        if (!(otherW > (other.__data__._compactW || 0) + 20)) {
            throw new Error(`the hovered card did not open (${otherW}px)`);
        }
        console.log(`         open card reads: "${openText.replace(/\s+/g,' ').slice(0, 96)}"`);
        if (!(openW > compact + 20)) throw new Error(`clicking did not open the card (${compact} -> ${openW})`);
        if (!(afterW > compact + 20)) throw new Error(`the pinned card collapsed when the pointer left (${afterW}px, compact is ${compact}px)`);
    }

    // The rank is the one number every compact card carries, so the open card
    // has to say where it came from. This asserts the arithmetic is ON SCREEN -
    // three named terms, each with its contribution - rather than a claim that
    // a formula exists somewhere.
    step = 'an open paper shows why it ranks where it does';
    {
        const decisive = [...container.querySelectorAll('.d3-node')]
            .filter(n => n.__data__ && n.__data__.type === 'paper'
                      && n.__data__.stance !== 'neutral' && n.__data__.importanceParts);
        if (!decisive.length) throw new Error('no decisive paper carries importanceParts');
        const target = decisive[0];
        await act(async () => {
            target.dispatchEvent(new dom.window.MouseEvent('mouseover', { bubbles: true }));
            await new Promise(r => setTimeout(r, 300));
        });
        const text = (target.querySelector('.node-paper-title')?.textContent || '')
            .replace(/\s+/g, ' ');
        const need = (re, what) => {
            if (!re.test(text)) throw new Error(`the breakdown is missing ${what}: "${text.slice(0, 140)}"`);
        };
        need(/why it ranks #\d+ of \d+/, 'its heading');
        need(/study design/, 'the design term');
        need(/citations/, 'the citation term');
        need(/journal/, 'the journal term');
        need(/importance \d\.\d\d/, 'the total');
        // The three parts must add up to the total the card prints, or the
        // page is showing working that does not reach its own answer.
        const d = target.__data__;
        const sum = d.importanceParts.design + d.importanceParts.citations + d.importanceParts.journal;
        if (Math.abs(sum - d.importance) > 0.001) {
            throw new Error(`parts sum to ${sum.toFixed(4)} but importance is ${d.importance}`);
        }
        console.log(`FORMULA  #${d.rank}/${d.rankTotal}: design ${d.importanceParts.design} + `
                    + `cites ${d.importanceParts.citations} + journal ${d.importanceParts.journal} `
                    + `= ${d.importance}`);
        await act(async () => {
            target.dispatchEvent(new dom.window.MouseEvent('mouseout', { bubbles: true }));
            await new Promise(r => setTimeout(r, 300));
        });
    }

    // Tapping the background must clear the selection. This ran through a
    // click handler, and d3-zoom preventDefaults the touch sequence, so on a
    // phone no click arrived and a selected paper could not be dismissed at
    // all. Pointer events are what a touch actually produces.
    step = 'tapping the background deselects';
    {
        // Clear the hover first: a card under the pointer is legitimately open
        // whatever the selection, so leaving it there tests nothing.
        await act(async () => {
            container.querySelectorAll('.d3-node').forEach(n =>
                n.dispatchEvent(new dom.window.MouseEvent('mouseout', { bubbles: true })));
            await new Promise(r => setTimeout(r, 200));
        });
        const svgEl = container.querySelector('svg');
        const pointerEvt = (type, x, y) => {
            const e = new dom.window.Event(type, { bubbles: true, cancelable: true });
            Object.assign(e, { clientX: x, clientY: y, pointerId: 1, pointerType: 'touch' });
            return e;
        };
        // Dispatch on a CHILD of the svg, not the svg itself. A finger hit-tests
        // to whatever is actually painted under it - an axis band, the context
        // box rect, a hexagon - and only lands on the <svg> element where the
        // canvas is genuinely bare. Firing on svgEl made `event.target` the svg
        // by construction, so the old assertion held on a device where the
        // feature did not work at all. jsdom has no layout and cannot hit-test,
        // so the target has to be chosen deliberately.
        const bare = container.querySelector('.g-axis-layer')
                  || container.querySelector('.g-main')
                  || svgEl;
        if (bare === svgEl) throw new Error('no non-svg background element to tap - test is vacuous');

        // The other direction first, while something is still pinned: a tap that
        // lands INSIDE a node must not clear the selection. The node's own
        // handler owns that gesture. Without this, "treat everything that is not
        // the svg as background" would pass the test below while dismissing the
        // selection on every tap, including on the card being read.
        const insideNode = container.querySelector('.d3-node rect')
                        || container.querySelector('.d3-node');
        if (insideNode) {
            await act(async () => {
                insideNode.dispatchEvent(pointerEvt('pointerdown', 300, 300));
                insideNode.dispatchEvent(pointerEvt('pointerup', 301, 301));
                await new Promise(r => setTimeout(r, 250));
            });
            const heldOn = [...container.querySelectorAll('.d3-node')]
                .filter(n => n.__data__ && n.__data__._paperOpen).length;
            console.log(`DESELECT tap on a node -> ${heldOn} papers still pinned (should be 1)`);
            if (!heldOn) throw new Error('tapping a node cleared the selection - only the background should');
        }

        await act(async () => {
            bare.dispatchEvent(pointerEvt('pointerdown', 20, 400));
            bare.dispatchEvent(pointerEvt('pointerup', 21, 401));
            await new Promise(r => setTimeout(r, 350));
        });
        const stillPinned = [...container.querySelectorAll('.d3-node')]
            .filter(n => n.__data__ && n.__data__._paperOpen).length;
        console.log(`DESELECT background tap -> ${stillPinned} papers still pinned`);
        if (stillPinned) throw new Error('tapping the background did not clear the selection');
    }

    step = 'display-options popover';
    if (container.querySelector('.axis-toggle-btn')) {
        throw new Error('toggles are in the DOM before the popover was opened');
    }
    await act(async () => {
        container.querySelector('.icon-button[aria-label="Display options"]')
            ?.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
        await new Promise(r => setTimeout(r, 120));
    });
    const popover = container.querySelector('.settings-popover');
    if (!popover) throw new Error('display-options popover did not open');
    console.log(`         popover opens with ${popover.querySelectorAll('.axis-toggle-btn').length} controls`);

    step = 'toggles on the evidence view';
    for (const label of ['Publication year', 'Study strength', 'Conservative', 'Liberal', 'Balanced']) {
        const btn = [...container.querySelectorAll('.axis-toggle-btn')]
            .find(b => b.textContent.trim() === label);
        if (!btn) throw new Error(`toggle "${label}" not found`);
        await act(async () => {
            btn.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
            await new Promise(r => setTimeout(r, 150));
        });
        const n = container.querySelectorAll('.d3-node').length;
        if (!n) throw new Error(`view went blank after "${label}"`);
        console.log(`  toggle ${label.padEnd(17)} -> ${n} nodes`);
    }

    step = 'back out, then a topic with no evidence';
    const back = container.querySelector('.back-to-galaxy');
    await act(async () => {
        back.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
        await new Promise(r => setTimeout(r, 250));
    });
    await act(async () => {
        container.querySelector('.back-to-galaxy')
            .dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
        await new Promise(r => setTimeout(r, 250));
    });
    await settle(300);
    if (!container.querySelectorAll('.d3-node').length) throw new Error('TOPICS blank after backing out');
    // "has nodes" was too weak to notice a back button that never fired: the
    // evidence view has 117 of them. The breadcrumbs go through history.back()
    // now, so this is really asking whether popstate came through.
    const backHexes = container.querySelectorAll('.d3-node').length;
    const backTitle = container.querySelector('.galaxy-title')?.textContent?.trim();
    console.log(`BACK     two backs -> ${backHexes} nodes, title "${backTitle}"`);
    if (backHexes !== 14) {
        throw new Error(`expected 14 topic hexagons after backing out, got ${backHexes} - history.back() did not land on TOPICS`);
    }

    // "motor" has claims but no gathered evidence - the shelf/empty-state path.
    const hexes = [...container.querySelectorAll('.d3-node')];
    const unresearched = hexes.find(h => /0 researched/.test(h.textContent));
    if (unresearched) {
        await act(async () => {
            unresearched.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
            await new Promise(r => setTimeout(r, 300));
        });
        const n = container.querySelectorAll('.d3-node').length;
        console.log(`CLAIMS   unresearched topic -> ${n} nodes on the shelf`);
        if (!n) throw new Error('unresearched topic rendered blank');
    }

    // The search is a button until it is opened, so the input does not exist
    // until something clicks it. If that click stops working the field is
    // simply unreachable, with nothing on screen to say so.
    step = 'search opens from its button';
    if (container.querySelector('.search-input')) {
        throw new Error('search input is in the DOM before its button was pressed');
    }
    await act(async () => {
        container.querySelector('.search-open-btn')
            ?.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
        await new Promise(r => setTimeout(r, 120));
    });
    if (!container.querySelector('.search-input')) throw new Error('search did not open');
    console.log('SEARCH   button opens a field');

    // Touch: no hover, so the first tap has to select rather than navigate.
    // Faked by claiming the device has no hover, which is exactly what the
    // app tests.
    step = 'tap to select on touch';
    const realMatchMedia = dom.window.matchMedia;
    dom.window.matchMedia = (q) => ({
        matches: /hover:\s*none/.test(q), media: q,
        addListener() {}, removeListener() {},
        addEventListener() {}, removeEventListener() {},
    });
    const beforeTitle = container.querySelector('.galaxy-title')?.textContent?.trim();
    const firstHex = container.querySelector('.d3-node');
    await act(async () => {
        firstHex.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
        await new Promise(r => setTimeout(r, 250));
    });
    const afterOneTap = container.querySelector('.galaxy-title')?.textContent?.trim();
    if (afterOneTap !== beforeTitle) {
        throw new Error('one tap navigated on a touch device - it should only select');
    }
    const footerAfterTap = container.querySelector('.galaxy-footer');
    console.log(`TOUCH    one tap selects (footer ${footerAfterTap ? 'filled' : 'MISSING'}, still on "${afterOneTap}")`);
    if (!footerAfterTap) throw new Error('nothing selected: the footer never appeared');
    if (!container.querySelector('.footer-grip')) throw new Error('footer drag grip missing');

    await act(async () => {
        container.querySelector('.d3-node')
            .dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
        await new Promise(r => setTimeout(r, 300));
    });
    const afterTwoTaps = container.querySelector('.galaxy-title')?.textContent?.trim();
    if (afterTwoTaps === beforeTitle) {
        throw new Error('a second tap on the selected node did not open it');
    }
    console.log(`TOUCH    second tap opens it -> "${afterTwoTaps}"`);
    dom.window.matchMedia = realMatchMedia;

    step = 'about panel';
    await act(async () => {
        container.querySelector('.about-button')
            .dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
        await new Promise(r => setTimeout(r, 120));
    });
    if (!container.querySelector('[role="dialog"]')) throw new Error('about panel did not open');
    console.log('ABOUT    panel opens');

    // Narrow viewport. The mobile path is not a stylesheet tweak: the claims
    // layout switches to a vertical column, the separation bias inverts, and
    // the zoom fit measures the header out of the DOM. None of that runs at
    // 1440px, so none of it is covered by anything above.
    step = 'narrow viewport';
    for (const [prop, value] of [['clientWidth', 390], ['clientHeight', 844],
                                 ['offsetWidth', 390], ['offsetHeight', 844]]) {
        Object.defineProperty(dom.window.HTMLElement.prototype, prop,
            { configurable: true, get() { return value; } });
    }
    await act(async () => {
        dom.window.dispatchEvent(new dom.window.Event('resize'));
        await new Promise(r => setTimeout(r, 400));
    });
    const narrowNodes = container.querySelectorAll('.d3-node').length;
    const topbar = container.querySelector('.galaxy-topbar');
    console.log(`MOBILE   390x844 -> ${narrowNodes} nodes, topbar ${topbar ? 'present' : 'MISSING'}`);
    if (!narrowNodes) throw new Error('view went blank at 390px');
    if (!topbar) throw new Error('.galaxy-topbar missing - the mobile header has nothing to lay out');

    console.log('\nall views mounted without error');
} catch (e) {
    console.log(`\nFAILED at step: ${step}`);
    console.log(e.stack || String(e));
}

const real = errors.filter(e => !/not wrapped in act|Warning: /.test(e));
if (real.length) {
    console.log(`\n--- ${real.length} console error(s) ---`);
    real.slice(0, 6).forEach(e => console.log(e.split('\n').slice(0, 12).join('\n')));
    process.exitCode = 1;
}
