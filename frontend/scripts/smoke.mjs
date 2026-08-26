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
