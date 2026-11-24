// Unit tests for the card logic: the card file is evaluated with stubs, no browser needed.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import vm from 'node:vm';
import { bundle } from '../scripts/bundle.mjs';

// West of UTC: a date-only "YYYY-MM-DD" read as UTC midnight would show the day before.
process.env.TZ = 'America/New_York';

// The card file as scripts/build-frontend.mjs assembles it from its ES modules in src/educartable-card/.
const source = bundle('src/educartable-card/index.js');
const context = {
  HTMLElement: class {},
  customElements: { get: () => true, define() {} },
  window: {},
  navigator: { language: 'en' },
  document: { addEventListener() {}, removeEventListener() {} },
  console,
  Date,
  Intl,
};
vm.createContext(context);
vm.runInContext(`${source}\nthis.e = { educartableEsc, educartableLang, educartableLocale, educartableT, educartableData, educartableChanged, educartableDay, educartableDue, educartableSortedHomework, educartableWordRow, educartableHomeworkRow, educartableNewsRow, educartableFiles, educartableCanAct, educartableSign, educartableSetDone, educartableDocumentRow, educartableFileUrl, educartableAnswerSurvey, educartableBook, educartableReply, educartableWrite, educartableSignDocument, educartableTime, educartableSetTimeFormat, educartableHeaderState, EducartableI18n, EducartableCard };`, context);
const E = context.e;

const sensor = (id, state, attrs) => ({ entity_id: id, state: String(state), attributes: { config_entry_id: 'abc', ...attrs } });
const states = {
  'sensor.edu_carnet': sensor('sensor.edu_carnet', 1, { stale: [], messages: [{ id: '1', title: 'Trip', type: 'info', date: '2026-11-20', to_sign: true }, { id: '2', title: 'Pool', type: 'info', date: '2026-11-18', to_sign: false }] }),
  'sensor.edu_news': sensor('sensor.edu_news', 1, { stale: ['news'], news: [{ id: 'n1', title: 'Fair', type: 'event', date: '2026-11-19' }] }),
  'sensor.edu_alex': sensor('sensor.edu_alex', 1, { child_id: 'p1', child: 'Alex', homework: [{ id: 'h1', title: 'Poem', subject: 'French', due: '2026-11-26', done: false }] }),
  'sensor.edu_sam': sensor('sensor.edu_sam', 0, { child_id: 'p2', child: 'Sam', homework: [{ id: 'h2', title: 'Box', subject: 'Art', due: '2026-11-27', done: true }] }),
  'sensor.edu_last': sensor('sensor.edu_last', '2026-11-16T08:00:00+00:00', { stale: [], account: { name: 'Parent' }, children: [{ id: 'p1', firstname: 'Alex', name: 'Alex Doe' }, { id: 'p2', firstname: 'Sam', name: 'Sam Doe' }], panel_tabs: ['homework', 'news'], hide_header: 'off' }),
  'sensor.edu_docs': sensor('sensor.edu_docs', 1, { stale: [], documents: [{ id: 'notebook:3', kind: 'notebook', title: 'Report', year: '2026', child: 'Alex', child_id: 'p1', to_sign: true, signed: false, file: true }] }),
  'sensor.other': { entity_id: 'sensor.other', state: '3', attributes: { config_entry_id: 'zzz', messages: [] } },
};
// Values made in the card's context are compared as plain JSON (another realm's arrays are not deepEqual).
const plain = (v) => JSON.parse(JSON.stringify(v));
const registry = () => {
  const entities = { 'sensor.other': { platform: 'other' } };
  for (const id of Object.keys(states).filter((k) => k.startsWith('sensor.edu_'))) entities[id] = { platform: 'educartable' };
  return entities;
};

test('educartableEsc escapes HTML', () => {
  assert.equal(E.educartableEsc('<b a="1">\'&'), '&lt;b a=&quot;1&quot;&gt;&#39;&amp;');
  assert.equal(E.educartableEsc(null), '');
});

test('language and locale', () => {
  assert.equal(E.educartableLang({ locale: { language: 'fr-FR' } }), 'fr');
  assert.equal(E.educartableLang({ locale: { language: 'sr-Latn' } }), 'sr-Latn');
  assert.equal(E.educartableLang({ locale: { language: 'xx' } }), 'en');
  assert.equal(E.educartableLocale({ locale: { language: 'pt' } }), 'pt-PT');
});

test('every language has the English keys', () => {
  const en = Object.keys(E.EducartableI18n.en).filter((k) => k !== 'default_title').sort();
  for (const [lang, table] of Object.entries(E.EducartableI18n)) {
    if (lang === 'en') continue;
    assert.deepEqual(Object.keys(table).filter((k) => k !== 'default_title').sort(), en, lang);
    for (const [k, v] of Object.entries(table)) {
      assert.deepEqual((v.match(/\{\w+\}/g) || []).sort(), (E.EducartableI18n.en[k].match(/\{\w+\}/g) || []).sort(), `${lang}.${k}`);
    }
  }
  assert.equal(Object.keys(E.EducartableI18n).length, 22);
});

test('educartableData groups the sensors of one account', () => {
  // The registry lists every sensor; only those of the integration are read.
  const d = E.educartableData({ states, entities: registry() }, 'abc');
  assert.deepEqual(plain(d.words.map((w) => [w.id, w.signed])), [['1', false], ['2', true]]);
  // The homework of every child in one list, each with its child and its due date as `date`
  assert.deepEqual(plain(d.homework.map((h) => [h.id, h.child, h.child_id, h.date])), [['h1', 'Alex', 'p1', '2026-11-26'], ['h2', 'Sam', 'p2', '2026-11-27']]);
  assert.deepEqual(plain(d.children.map((ch) => ch.first_name)), ['Alex', 'Sam']);
  assert.equal(d.news.length, 1);
  assert.deepEqual([...d.stale], ['news']);
  assert.deepEqual([...d.panelTabs], ['homework', 'news']);
  assert.equal(d.url, 'https://app.educartable.com');
  assert.equal(d.updated, '2026-11-16T08:00:00+00:00');
  assert.equal(d.unavailable, false);
  assert.equal(E.educartableData({ states, entities: registry() }, 'zzz'), null, 'a sensor of another integration is ignored');
});

test('a child more or less counts as a change of the account', () => {
  const a = [1, 2];
  assert.equal(E.educartableChanged(a, a), false);
  assert.equal(E.educartableChanged([1, 2, 3], a), true);
  assert.equal(E.educartableChanged([1, 3], a), true);
  assert.equal(E.educartableChanged(null, a), true);
});

test('relative days and due labels', () => {
  const t = E.educartableT({ language: 'en' });
  const iso = (n) => {
    const d = new Date();
    d.setDate(d.getDate() + n);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };
  assert.equal(E.educartableDay(iso(0), t, 'en'), 'Today');
  assert.equal(E.educartableDay(iso(1), t, 'en'), 'Tomorrow');
  assert.equal(E.educartableDue(iso(0), t, 'en'), 'for today');
  assert.equal(E.educartableDue(iso(1), t, 'en'), 'for tomorrow');
  assert.match(E.educartableDue(iso(3), t, 'en'), /^for \w+/);
});

test('homework order: undone first by date, done hidden on request', () => {
  const list = [
    { id: 'a', date: '2026-11-20', done: true },
    { id: 'b', date: '2026-11-21', done: false },
    { id: 'c', date: '2026-11-19', done: false },
  ];
  assert.deepEqual(E.educartableSortedHomework(list, true).map((h) => h.id), ['c', 'b', 'a']);
  assert.deepEqual(E.educartableSortedHomework(list, false).map((h) => h.id), ['c', 'b']);
});

test('liaison book: Sign and Mark as read for administrators, the state for the others and once done', () => {
  const t = E.educartableT({ language: 'en' });
  const sign = { id: '1', title: 'Trip', achievement: 'sign', achieved: false, signed: false };
  assert.match(E.educartableWordRow(sign, t, 'en', { canAct: true }), /data-action="sign" data-id="1"/);
  assert.doesNotMatch(E.educartableWordRow(sign, t, 'en', { canAct: false }), /data-action=/);
  assert.match(E.educartableWordRow(sign, t, 'en', { canAct: false }), /class="chip">to sign/);
  const read = { id: '2', title: 'Pool', achievement: 'read', achieved: false };
  assert.match(E.educartableWordRow(read, t, 'en', { canAct: true }), /data-action="read" data-id="2"/);
  assert.match(E.educartableWordRow({ ...sign, achieved: true }, t, 'en', { canAct: true }), /class="chip ok">Signed/);
  assert.match(E.educartableWordRow({ ...read, achieved: true }, t, 'en', { canAct: true }), /class="chip ok">Read/);
  assert.match(E.educartableWordRow({ id: '3', title: 'Survey', achievement: 'survey', achieved: false }, t, 'en', { canAct: true }), /survey to answer/);
  assert.equal(E.educartableCanAct({ user: { is_admin: false } }), false);
  assert.equal(E.educartableCanAct({}), true, 'unknown user: the backend still refuses non-admins');
});

test('homework: a box to tick only for homework that can be ticked, greyed out for non-administrators', () => {
  const t = E.educartableT({ language: 'en' });
  const hw = { id: 'h1', title: 'Poem', subject: 'French', child: 'Alex', child_id: 'p1', date: '2026-11-26', done: false, recipient_id: 'r1' };
  assert.match(E.educartableHomeworkRow(hw, t, 'en', { canAct: true }), /data-action="homework" data-id="h1" data-child="p1">/);
  assert.match(E.educartableHomeworkRow(hw, t, 'en', { canAct: false }), /data-action="homework"[^>]*disabled/);
  assert.doesNotMatch(E.educartableHomeworkRow({ ...hw, recipient_id: '' }, t, 'en', { canAct: true }), /data-action=/);
  assert.match(E.educartableHomeworkRow(hw, t, 'en', {}), /Alex · French/);
  assert.doesNotMatch(E.educartableHomeworkRow(hw, t, 'en', { child: false }), /Alex/);
  assert.match(E.educartableHomeworkRow({ ...hw, done: true }, t, 'en', {}), /class="item hw done"/);
});

test('rows unfold to their text and attachments', () => {
  const t = E.educartableT({ language: 'en' });
  const w = { id: '1', title: 'Trip', text: 'Bring lunch', achievement: 'sign', achieved: false, medias: [{ id: '7', name: 'Map.jpg', extension: 'jpg' }, { id: '8', name: 'Slip.pdf', extension: 'pdf' }] };
  const closed = E.educartableWordRow(w, t, 'en', { isOpen: () => false, entryId: 'abc', canAct: true });
  assert.match(closed, /data-toggle="word:1"/);
  assert.doesNotMatch(closed, /Bring lunch/);
  const open = E.educartableWordRow(w, t, 'en', { isOpen: () => true, entryId: 'abc', canAct: true });
  assert.match(open, /Bring lunch/);
  assert.match(open, /<img alt="Map.jpg" data-src="1" data-media="7"/);
  assert.match(open, /data-action="file" data-media="8" data-name="Slip.pdf"/);
  // The panel shows everything, without a chevron
  assert.doesNotMatch(E.educartableWordRow(w, t, 'en', { full: true, entryId: 'abc', canAct: true }), /data-toggle/);
  // Attachments are fetched with the parent's account: names only for the others
  const others = E.educartableFiles(w.medias, t, 'abc', false);
  assert.doesNotMatch(others, /<img/);
  assert.match(others, /data-media="7"[^>]*disabled/);
});

test('actions send the account, the message and the child', async () => {
  const calls = [];
  const hass = { callWS: (m) => calls.push(m) && Promise.resolve(), callService: (...a) => calls.push(a) && Promise.resolve() };
  await E.educartableSign(hass, 'abc', { id: 7 }, 'Parent Test');
  await E.educartableSetDone(hass, 'abc', { id: 'h1', child_id: 'p1' }, true);
  assert.deepEqual(plain(calls), [
    ['educartable', 'sign', { config_entry_id: 'abc', message_id: '7', name: 'Parent Test' }],
    { type: 'educartable/homework_done', config_entry_id: 'abc', child_id: 'p1', homework_id: 'h1', done: true },
  ]);
});

test('news rows say what they are: event, parent meeting or news', () => {
  const t = E.educartableT({ language: 'en' });
  assert.match(E.educartableNewsRow({ title: 'Fair', type: 'event' }, t, 'en'), /mdi:calendar-star.*Event/s);
  assert.match(E.educartableNewsRow({ title: 'Evening', type: 'meeting' }, t, 'en'), /Parent meeting/);
  assert.match(E.educartableNewsRow({ title: 'Menu', type: 'advert' }, t, 'en'), /News/);
  assert.match(E.educartableNewsRow({ title: 'Other', type: 'whatever' }, t, 'en'), /mdi:newspaper-variant-outline/);
});

test('the header picture: the liaison book to sign first, then the homework, else all done', () => {
  const all = { show_homework: true, show_words: true };
  const data = (words, homework) => ({ words, homework, stale: [], unavailable: false });
  assert.deepEqual(JSON.parse(JSON.stringify(E.educartableHeaderState(data([{ signed: false }], [{ done: false }]), all))), { kind: 'msg', status: 'active', unread: 1 });
  assert.equal(E.educartableHeaderState(data([{ signed: true }], [{ done: false }]), all).kind, 'hw');
  assert.equal(E.educartableHeaderState(data([], [{ done: true }]), all).kind, 'done');
  assert.equal(E.educartableHeaderState(data([{ signed: false }], []), { show_words: false, show_homework: true }).kind, 'done');
  assert.equal(E.educartableHeaderState(null, all).kind, 'off');
});

test('time follows the 12 / 24 h setting of the profile', () => {
  const raw = '2026-11-20T09:05:00';
  E.educartableSetTimeFormat({ locale: { time_format: '24' } });
  assert.doesNotMatch(E.educartableTime(raw, 'en-US'), /AM|PM/);
  E.educartableSetTimeFormat({ locale: { time_format: '12' } });
  assert.match(E.educartableTime(raw, 'fr'), /AM|PM|am|pm/i);
  E.educartableSetTimeFormat({ locale: { time_format: 'language' } });
  assert.match(E.educartableTime(raw, 'en-US'), /AM/);
});

test('far dates keep the weekday', () => {
  const t = E.educartableT({ language: 'en' });
  const d = new Date();
  d.setDate(d.getDate() + 10);
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const weekday = d.toLocaleDateString('en', { weekday: 'short' });
  assert.ok(E.educartableDay(iso, t, 'en').includes(weekday));
});

test('the banner follows the theme alone: night with a dark theme, day with a light one even after sunset', () => {
  const night = vm.runInContext('educartableIsNight', context);
  const hass = (sun, darkMode) => ({ states: sun ? { 'sun.sun': { state: sun } } : {}, themes: { darkMode } });
  assert.equal(night(hass('below_horizon', false), {}), false);
  assert.equal(night(hass('above_horizon', true), {}), true);
  assert.equal(night(hass('above_horizon', false), {}), false);
  assert.equal(night(hass('unavailable', true), {}), true);
  assert.equal(night(hass(null, false), {}), false);
  assert.equal(night(hass('above_horizon', true), { illustration_theme: 'day' }), false);
  assert.equal(night(hass('below_horizon', true), { illustration_theme: 'day' }), false);
  assert.equal(night(hass('above_horizon', false), { illustration_theme: 'night' }), true);
});

// The status pill: right after the title only when the whole title and its whole label fit, else under the subtitle,
// else only its dot; decided by measure (no width threshold left in the stylesheet).
test('the status pill is placed by measure, the title whole first', () => {
  assert.doesNotMatch(source, /@container eo-titles|pill-line|max-width: 260px\) \{ \.title-row/);
  assert.match(source, /\.titles\.pill-below \.title-row \{ display: contents; \}/);
  const el = (w, extra = {}) => {
    const cls = new Set();
    return {
      _w: w,
      classList: {
        add: (...c) => {
          for (const x of c) cls.add(x);
        },
        remove: (...c) => {
          for (const x of c) cls.delete(x);
        },
        has: (c) => cls.has(c),
      },
      getClientRects: () => [1],
      getBoundingClientRect: () => ({ width: w, top: 10, bottom: 60 }),
      removeAttribute() {},
      closest: () => null,
      ...extra,
    };
  };
  const place = (titleW, pillW, blockW) => {
    const name = el(titleW);
    const chip = el(pillW, { querySelector: () => el(pillW - 20) });
    chip.parentElement = {};
    const t = el(blockW, { querySelector: (sel) => ({ '.status': chip, '.name': name, '.sub': null })[sel] });
    context.getComputedStyle = () => ({ columnGap: '8px' });
    context.document.createRange = () => ({ selectNodeContents(n) { this.n = n; }, getBoundingClientRect() { return { width: this.n._w }; } });
    const card = Object.create(E.EducartableCard.prototype);
    card._root = { querySelector: () => t };
    card._fitPill();
    return ['pill-below', 'pill-dot'].filter((c) => t.classList.has(c));
  };
  assert.deepEqual(place(100, 60, 200), [], 'whole title and pill fit: side by side');
  assert.deepEqual(place(150, 60, 200), ['pill-below'], 'the title would be cut: the pill under the subtitle');
  assert.deepEqual(place(150, 220, 200), ['pill-below', 'pill-dot'], 'the label does not fit its own line: only the dot');
});

// ── DOM patching (layout shift): a redraw keeps the nodes on the page ───────────────────────────────────────────
// A tiny DOM, enough for the patch helper: elements with attributes and children, and text nodes.
class FakeNode {
  constructor(type, name, value = null) {
    this.nodeType = type;
    this.nodeName = name.toUpperCase();
    this.localName = name.toLowerCase();
    this.nodeValue = value;
    this.childNodes = [];
    this.parentNode = null;
    this.attrs = new Map();
  }
  get attributes() {
    return [...this.attrs].map(([name, value]) => ({ name, value, namespaceURI: null }));
  }
  hasAttribute(n) {
    return this.attrs.has(n);
  }
  getAttribute(n) {
    return this.attrs.has(n) ? this.attrs.get(n) : null;
  }
  setAttribute(n, v) {
    this.attrs.set(n, String(v));
  }
  removeAttribute(n) {
    this.attrs.delete(n);
  }
  get lastChild() {
    return this.childNodes[this.childNodes.length - 1] || null;
  }
  insertBefore(n, ref) {
    if (n.parentNode) n.parentNode.removeChild(n);
    const i = ref ? this.childNodes.indexOf(ref) : this.childNodes.length;
    this.childNodes.splice(i, 0, n);
    n.parentNode = this;
    return n;
  }
  removeChild(n) {
    this.childNodes.splice(this.childNodes.indexOf(n), 1);
    n.parentNode = null;
    return n;
  }
  replaceChild(n, o) {
    this.insertBefore(n, o);
    return this.removeChild(o);
  }
  get firstChild() {
    return this.childNodes[0] || null;
  }
}
const fakeEl = (name, attrs = {}, ...kids) => {
  const e = new FakeNode(1, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  for (const k of kids) e.insertBefore(typeof k === "string" ? new FakeNode(3, "#text", k) : k, null);
  return e;
};

test("a redraw patches the card in place: pictures, images and texts keep their nodes", () => {
  const patch = vm.runInContext("educartableMorphChildren", context);
  const img = fakeEl("img", { src: "logo.svg", alt: "" });
  const svg = fakeEl("svg", { class: "scene" }, fakeEl("path", { d: "M0 0" }));
  const label = fakeEl("span", { class: "t" }, "3 min");
  const root = fakeEl("div", {}, fakeEl("div", { class: "banner st-ok", "data-wrap": "" }, svg, img), label, fakeEl("p", {}, "gone"));
  const next = fakeEl("div", {}, fakeEl("div", { class: "banner st-late" }, fakeEl("svg", { class: "scene" }, fakeEl("path", { d: "M0 0" })), fakeEl("img", { src: "logo.svg", alt: "" })), fakeEl("span", { class: "t" }, "2 min"));
  const banner = root.childNodes[0];
  const text = label.childNodes[0];
  patch(root, next);
  // The same nodes, updated: no picture or image is re-created (they would be laid out again)
  assert.equal(root.childNodes[0], banner);
  assert.equal(banner.childNodes[0], svg);
  assert.equal(banner.childNodes[1], img);
  assert.equal(root.childNodes[1], label);
  assert.equal(label.childNodes[0], text);
  assert.equal(text.nodeValue, "2 min");
  assert.equal(banner.getAttribute("class"), "banner st-late");
  assert.equal(banner.hasAttribute("data-wrap"), false);
  // What the new HTML no longer has is removed
  assert.equal(root.childNodes.length, 2);
});

test("a redraw replaces only the nodes whose element changed, and keeps an open dialog open", () => {
  const patch = vm.runInContext("educartableMorphChildren", context);
  const dlg = fakeEl("dialog", { id: "zoom", open: "" });
  const keep = fakeEl("div", { class: "a" });
  const root = fakeEl("div", {}, keep, fakeEl("span", {}, "x"), dlg);
  const fresh = fakeEl("button", { class: "b" });
  patch(root, fakeEl("div", {}, fakeEl("div", { class: "a" }), fresh, fakeEl("dialog", { id: "zoom" })));
  assert.deepEqual(root.childNodes.map((n) => n.localName), ["div", "button", "dialog"]);
  assert.equal(root.childNodes[0], keep);
  assert.equal(root.childNodes[1], fresh);
  assert.equal(root.childNodes[2], dlg);
  // `open` belongs to showModal() / close(), not to the HTML
  assert.equal(dlg.hasAttribute("open"), true);
});

test("a hass update that changes no sensor of the account does not redraw the card; one of its sensors does", () => {
  const entities = registry();
  const card = Object.create(E.EducartableCard.prototype);
  card._config = {};
  let renders = 0;
  card._render = () => renders++;
  card.hass = { states, entities };
  assert.equal(renders, 1);
  // Another entity changes: the card is not touched (no DOM change, nothing laid out again)
  card.hass = { states: { ...states, 'sensor.other': { ...states['sensor.other'], state: '4' } }, entities };
  assert.equal(renders, 1);
  card.hass = { states: { ...states, 'sensor.edu_carnet': sensor('sensor.edu_carnet', 0, { messages: [] }) }, entities };
  assert.equal(renders, 2);
  // A child's homework sensor counts too
  card.hass = { states: { ...states, 'sensor.edu_sam': sensor('sensor.edu_sam', 1, { child_id: 'p2', homework: [] }) }, entities };
  assert.equal(renders, 3);
});

test("a redraw keeps what a Home Assistant element drew in itself, and replaces it when its attributes change", () => {
  const patch = vm.runInContext("educartableMorphChildren", context);
  // <ha-icon> draws its own content (and may style its own node): the redraw leaves it alone
  const icon = fakeEl("ha-icon", { icon: "mdi:refresh", style: "display: inline-flex" }, fakeEl("svg"));
  const root = fakeEl("div", {}, icon);
  patch(root, fakeEl("div", {}, fakeEl("ha-icon", { icon: "mdi:refresh" })));
  assert.equal(root.childNodes[0], icon);
  assert.equal(icon.childNodes.length, 1);
  assert.equal(icon.getAttribute("style"), "display: inline-flex");
  // Another icon: a new element, which draws the new icon
  patch(root, fakeEl("div", {}, fakeEl("ha-icon", { icon: "mdi:check" })));
  assert.notEqual(root.childNodes[0], icon);
  assert.equal(root.childNodes[0].getAttribute("icon"), "mdi:check");
  // An element we fill ourselves (<ha-card>) is patched like any other
  const card = fakeEl("ha-card", { class: "mini" }, fakeEl("div", {}, "a"));
  const host = fakeEl("div", {}, card);
  patch(host, fakeEl("div", {}, fakeEl("ha-card", {}, fakeEl("div", {}, "b"))));
  assert.equal(host.childNodes[0], card);
  assert.equal(card.hasAttribute("class"), false);
  assert.equal(card.childNodes[0].childNodes[0].nodeValue, "b");
});

// Home Assistant's <ha-card> is a Lit element: it lays out its content from its first update only, a microtask after it
// is connected. Measured before, the title and the pill are 0 px wide and the pill lands on the wrong line for a frame:
// the card waits for that update (updateComplete), then measures once.
test("the status pill is measured only once <ha-card> has drawn its content", async () => {
  const card = Object.create(E.EducartableCard.prototype);
  const asked = [];
  let drawn;
  const haCard = { hasUpdated: false, updateComplete: new Promise((done) => (drawn = done)) };
  const root = {
    querySelector: (sel) => (sel === "ha-card" ? haCard : (asked.push(sel), null)),
    querySelectorAll: (sel) => (asked.push(sel), []),
  };
  card._root = root;
  card._fitPill();
  card._fitPill();
  await null;
  assert.deepEqual(asked, [], "nothing measured before <ha-card>'s first update");
  haCard.hasUpdated = true;
  drawn(true);
  await haCard.updateComplete;
  await null;
  assert.ok(asked.length > 0, "measured once it is drawn");
  const once = asked.length;
  card._fitPill();
  assert.equal(asked.length, once * 2, "then measured right away, with no wait");
});

test('the livret: its documents in the data, Sign and the PDF for administrators', () => {
  const d = E.educartableData({ states, entities: registry() }, 'abc');
  assert.deepEqual(plain(d.documents.map((x) => x.id)), ['notebook:3']);
  const t = E.educartableT({});
  const row = E.educartableDocumentRow(d.documents[0], t, { canAct: true });
  assert.match(row, /data-action="doc-sign" data-id="notebook:3"/);
  assert.match(row, /data-action="doc-file" data-doc="notebook:3"/);
  const other = E.educartableDocumentRow(d.documents[0], t, { canAct: false });
  assert.doesNotMatch(other, /doc-sign/);
  assert.match(other, /disabled/);
  assert.match(E.educartableDocumentRow({ ...d.documents[0], signed: true, to_sign: false }, t, { canAct: true }), /chip ok/);
});

test('a livret PDF is fetched by its document id, never by a file path', async () => {
  const calls = [];
  const hass = { callWS: (msg) => { calls.push(msg); return Promise.resolve({ path: msg.path + '&authSig=x' }); } };
  await E.educartableFileUrl(hass, 'abc', { document: 'notebook:3', name: 'Report 2026.pdf' });
  assert.equal(calls[0].path, '/api/educartable/file/abc?document=notebook%3A3&name=Report%202026.pdf');
});

test('replies, new messages, surveys, appointments and livret signatures call their actions', async () => {
  const calls = [];
  const hass = { callService: (d, s, data) => { calls.push([d, s, data]); return Promise.resolve(); } };
  await E.educartableReply(hass, 'abc', 5, 'Hello');
  await E.educartableWrite(hass, 'abc', [1, 'p2'], 'Absence', 'Ill');
  await E.educartableAnswerSurvey(hass, 'abc', 'c5', { q1: ['a'] });
  await E.educartableBook(hass, 'abc', 51, '');
  await E.educartableSignDocument(hass, 'abc', 'notebook:3', 'Pat Doe');
  assert.deepEqual(plain(calls), [
    ['educartable', 'reply', { config_entry_id: 'abc', message_id: '5', text: 'Hello' }],
    ['educartable', 'write_message', { config_entry_id: 'abc', children: ['1', 'p2'], title: 'Absence', text: 'Ill' }],
    ['educartable', 'answer_survey', { config_entry_id: 'abc', message_id: 'c5', answers: { q1: ['a'] } }],
    ['educartable', 'book_appointment', { config_entry_id: 'abc', slot_id: '51' }],
    ['educartable', 'sign_document', { config_entry_id: 'abc', document_id: 'notebook:3', name: 'Pat Doe' }],
  ]);
});
