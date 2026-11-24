// ── educartable-card ──────────────────────────────────────────────────────────────
import { EDUCARTABLE_ACCENT, EDUCARTABLE_ICON } from "./header-icon.js";
import { EDUCARTABLE_DEFAULTS } from "./i18n-helpers.js";
import { educartableAccounts, educartableCanAct, educartableChanged, educartableData, educartableErrorText, educartableEsc, educartableFormat, educartableHomeworkRow, educartableHydrate, educartableInDialog, educartableItemStyles, educartableLocale, educartableMarkRead, educartableNewsRow, educartableOpenFile, educartableRefresh, educartableSetDone, educartableSetTimeFormat, educartableSign, educartableSortedHomework, educartableT, educartableTime, educartableWordRow } from "./helpers.js";
import { EDUCARTABLE_BANNER_STYLES, EDUCARTABLE_SCHOOL_PATH, educartableHeaderState, educartableIsNight, educartableSceneSvg, educartableTextWidth } from "./illustrated-header.js";

export var educartableUid = 0;

export var EDUCARTABLE_PANEL_PATH = 'educartable';

// Shadow DOM patching: a redraw updates the nodes already on the page (text, attributes, classes) instead of replacing
// them, so that a state update never re-creates the pictures (SVG scenes, logos) nor restarts their animations, and the
// card keeps its height (a re-created card is laid out again, which can move the dashboard under the reader's eyes).
// An open <dialog> keeps its `open` state: it is driven by showModal() / close().
export function educartableMorphAttrs(cur, next) {
  for (var a of Array.from(cur.attributes)) {
    if (!next.hasAttribute(a.name) && !(a.name === 'open' && cur.localName === 'dialog')) cur.removeAttribute(a.name);
  }
  for (var b of Array.from(next.attributes)) {
    if (cur.getAttribute(b.name) === b.value) continue;
    if (b.namespaceURI) cur.setAttributeNS(b.namespaceURI, b.name, b.value);
    else cur.setAttribute(b.name, b.value);
  }
}

// A Home Assistant element given no content (<ha-icon>…) draws itself: what it adds to its own node is not ours to
// remove. It is kept as long as the attributes the HTML gives it do not change, and replaced when they do.
export function educartableMorphOwnDrawn(o, n) {
  if (!n.localName.includes('-') || n.firstChild) return false;
  var key = Array.from(n.attributes, (a) => `${a.name}=${a.value}`).join('\n');
  if (o.__morphKey === undefined && Array.from(n.attributes).every((a) => o.getAttribute(a.name) === a.value)) o.__morphKey = key;
  if (o.__morphKey !== key) {
    n.__morphKey = key;
    o.parentNode.replaceChild(n, o);
  }
  return true;
}

export function educartableMorphChildren(cur, next) {
  var old = Array.from(cur.childNodes);
  var fresh = Array.from(next.childNodes);
  fresh.forEach((n, i) => {
    var o = old[i];
    var ref = cur.childNodes[i] || null;
    if (!o || o.nodeType !== n.nodeType || o.nodeName !== n.nodeName) {
      cur.insertBefore(n, ref);
      return;
    }
    if (o !== ref) cur.insertBefore(o, ref);
    if (n.nodeType !== 1) {
      if (o.nodeValue !== n.nodeValue) o.nodeValue = n.nodeValue;
    } else if (!educartableMorphOwnDrawn(o, n)) {
      educartableMorphAttrs(o, n);
      educartableMorphChildren(o, n);
    }
  });
  while (cur.childNodes.length > fresh.length) cur.removeChild(cur.lastChild);
}

// Gives `root` (a shadow root or an element) the content of `html`, patching what is already there (a plain
// innerHTML where there is no DOM to patch, as in the unit tests' stubs).
export function educartableMorph(root, html) {
  var tpl = root.childNodes && typeof document !== 'undefined' && document.createElement?.('template');
  if (!tpl?.content) {
    root.innerHTML = html;
    return;
  }
  tpl.innerHTML = html;
  educartableMorphChildren(root, tpl.content);
}

export class EducartableCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement('educartable-card-editor');
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = Object.assign({}, EDUCARTABLE_DEFAULTS, config || {});
    this.toggleAttribute?.('hide-title', config?.show_title === false);
    this._open = this._open || {};
    if (this._hass) this._render(true);
  }

  set hass(hass) {
    var first = !this._hass;
    this._hass = hass;
    var data = educartableData(hass, this._config?.config_entry_id);
    var key = data ? data.states : null;
    // Only redraw when one of the account's sensors changed.
    var changed = first || educartableChanged(key, this._lastKey);
    if (changed) {
      this._lastKey = key;
      // A new successful update clears the error shown since the one before.
      if (this._error && data?.updated && data.updated !== this._errorAt) this._error = '';
      this._render();
    }
  }

  connectedCallback() {
    this._onOutside = this._onOutside || ((ev) => {
      var anyOpen = Object.keys(this._open || {}).length > 0;
      if ((!this._confirm && !anyOpen) || ev.composedPath().indexOf(this) !== -1 || educartableInDialog(ev)) return;
      // Like the other cards: a click elsewhere closes the popup and folds the open rows.
      this._confirm = null;
      this._open = {};
      this._render(true);
    });
    document.addEventListener('click', this._onOutside, true);
    // A new width (or the web font loaded): the status pill is fitted again, in the next frame.
    if (typeof ResizeObserver === 'function') {
      this._pillResize = this._pillResize || new ResizeObserver((entries) => {
        var w = Math.round(entries[entries.length - 1].contentRect.width);
        if (w === this._pillWidth) return;
        this._pillWidth = w;
        cancelAnimationFrame(this._pillFrame);
        this._pillFrame = requestAnimationFrame(() => this._fitPill());
      });
      this._pillResize.observe(this);
    }
    document.fonts?.ready?.then(() => this._fitPill());
  }

  disconnectedCallback() {
    document.removeEventListener('click', this._onOutside, true);
    this._pillResize?.disconnect();
    this._pillWidth = null;
    // Leaving the page (view change, conditional card hidden) closes the popup without doing anything.
    if (this._confirm || Object.keys(this._open || {}).length) {
      this._confirm = null;
      this._open = {};
      this._render(true);
    }
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 'auto' };
  }

  _t() {
    return educartableT(this._hass, this._config);
  }

  _locale() {
    return educartableLocale(this._hass, this._config);
  }

  _compact() {
    return false;
  }

  _detailButton() {
    return '';
  }

  _ensureShell() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: 'open' });
    this._root.innerHTML = '<style>' + EducartableCard._styles() + '</style><ha-card><div class="header" data-head></div><div class="popup" hidden></div><div class="body"></div></ha-card>';
    var card = this._root.querySelector('ha-card');
    card.addEventListener('click', this._onClick.bind(this));
    card.addEventListener('keydown', (ev) => {
      if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.hasAttribute?.('data-toggle')) {
        ev.preventDefault();
        this._toggleRow(ev.target.getAttribute('data-toggle'));
      } else if (ev.key === 'Enter' && ev.target.classList?.contains('signer')) {
        ev.preventDefault();
        this._doSign();
      }
    });
    card.addEventListener('input', (ev) => {
      if (this._confirm && ev.target.classList?.contains('signer')) this._confirm.name = ev.target.value;
    });
  }

  _render() {
    if (!this._config || !this._hass) return;
    this._ensureShell();
    educartableSetTimeFormat(this._hass);
    var t = this._t();
    var data = educartableData(this._hass, this._config.config_entry_id);
    this._data = data;
    this._root.querySelector('ha-card').classList.toggle('mini', this._compact());
    this._renderHeader(t, data);
    this._fitPill();
    this._renderPopup(t, data);
    var body = this._root.querySelector('.body');
    if (!data) {
      educartableMorph(body, '<div class="pad empty">' + educartableEsc(t.no_entity) + '</div>');
      return;
    }
    if (data.unavailable) {
      educartableMorph(body, '<div class="pad empty">' + educartableEsc(t.unavailable) + '</div>');
      return;
    }
    // The rows are patched in place (educartableMorph): the focused toggle keeps the focus, or gets it back if replaced.
    var focused = this._root.activeElement?.getAttribute?.('data-toggle');
    educartableMorph(body, this._renderTiles(t, data) + (this._compact() ? '' : this._renderSections(t, data)));
    if (focused && this._root.activeElement?.getAttribute?.('data-toggle') !== focused) body.querySelector(`[data-toggle="${CSS.escape(focused)}"]`)?.focus({ preventScroll: true });
    educartableHydrate(body, this._hass, data.entryId);
  }

  _time(iso) {
    return educartableTime(iso, this._locale());
  }

  // The status pill goes on the title row, right after the title, only when the whole title and the pill's whole
  // label fit there; otherwise it takes its own line under the subtitle (.pill-below) and the title keeps its row
  // (cut only when it does not fit alone). The subtitle then keeps one line (its whole text in its tooltip), and when
  // the block still runs out of the banner or into its ground strip, or the label does not fit its own line, the pill
  // keeps its dot alone (.pill-dot, the label in its tooltip and aria-label). Measured after each render and on each
  // new width, never by a fixed width, so that every language fits.
  _fitPill() {
    // Home Assistant's <ha-card> (a Lit element) shows its content only from its first update, a microtask after it
    // is connected: measured before, everything is 0 px wide and the pill lands on the wrong line. Fitted then.
    var haCard = this._root?.querySelector?.('ha-card');
    if (haCard && haCard.hasUpdated === false) {
      this._pillWait ??= (haCard.updateComplete?.then ? haCard.updateComplete : new Promise((r) => requestAnimationFrame(r))).then(() => {
        this._pillWait = null;
        this._fitPill();
      });
      return;
    }
    var t = this._root?.querySelector?.('.titles');
    var chip = t?.querySelector('.status');
    if (!chip?.getBoundingClientRect) return;
    t.classList.remove('pill-below', 'pill-dot');
    var sub = t.querySelector('.sub');
    sub?.removeAttribute('title');
    if (!chip.querySelector('.status-text')?.getClientRects().length) return;
    var avail = t.getBoundingClientRect().width;
    var gap = parseFloat(getComputedStyle(chip.parentElement).columnGap) || 0;
    var width = chip.getBoundingClientRect().width;
    if (educartableTextWidth(t.querySelector('.name')) + gap + width <= avail + 0.01) return;
    t.classList.add('pill-below');
    if (sub && sub.scrollWidth > sub.clientWidth) sub.title = sub.textContent.trim();
    var banner = t.closest('.banner');
    var box = banner?.getBoundingClientRect();
    var floor = banner?.querySelector('.eo-ground')?.getBoundingClientRect().top ?? box?.bottom;
    var r = t.getBoundingClientRect();
    var out = box && (r.top < box.top - 0.5 || r.bottom > floor + 0.5);
    if (out || width > avail + 0.01) t.classList.add('pill-dot');
  }

  _renderHeader(t, data) {
    var c = this._config;
    var header = this._root.querySelector('[data-head]');
    var title = c.title || t.default_title;
    // The children's first names say whose family portal this is.
    var who = data ? data.children.map((ch) => ch.first_name).filter(Boolean).join(' · ') : '';
    var updated = data?.updated ? educartableFormat(t.last_update, { time: this._time(data.updated) }) : '';
    // The status pill, right after the title: green (classic header) or in the header icon's colour (banner). It goes
    // on a line of its own under the subtitle when the whole title and its label do not fit side by side (see
    // _fitPill), and on a very narrow card only its dot stays (its text stays in its title and aria-label).
    var st = educartableHeaderState(data, c);
    var pill = '';
    if (data) {
      var kind = c.illustration === false ? (data.unavailable ? 'bad' : data.stale.length ? 'warn' : 'ok') : st.status;
      var text = data.unavailable ? t.offline : data.stale.length ? t.partial : t.up_to_date;
      pill = '<span class="status ' + kind + '" title="' + educartableEsc(updated || text) + '" aria-label="' + educartableEsc(text) + '"><span class="dot"></span><span class="status-text">' + educartableEsc(text) + '</span></span>';
    }
    var titles = (s) => '<div class="titles"><div class="title-row"><div class="name">' + educartableEsc(title) + '</div>' + pill + '</div>' + s + '</div>';
    var buttons = '';
    if (data && !this._compact()) {
      if (c.show_refresh) {
        buttons += '<button class="hbtn refresh-btn' + (this._refreshing ? ' spinning' : '') + '" data-action="refresh" aria-label="' + educartableEsc(t.refresh) + '" title="' + educartableEsc(t.refresh) + '"><ha-icon icon="mdi:refresh"></ha-icon></button>';
      }
      if (data.url) {
        buttons += '<button class="hbtn" data-action="open" aria-label="' + educartableEsc(t.open_ent) + '" title="' + educartableEsc(t.open_ent) + '"><ha-icon icon="mdi:open-in-new"></ha-icon></button>';
      }
    }
    var sub = this._error
      ? '<div class="sub error"><span>' + educartableEsc(this._error) + '</span><button class="dismiss" data-action="dismiss" aria-label="' + educartableEsc(t.close) + '" title="' + educartableEsc(t.close) + '"><ha-icon icon="mdi:close"></ha-icon></button></div>'
      : who ? '<div class="sub">' + educartableEsc(who) + '</div>' : '';
    if (c.illustration === false) {
      header.className = 'header';
      educartableMorph(header,
        '<div class="title"><div class="logo" aria-hidden="true">' + EDUCARTABLE_ICON + '</div>' +
        titles(sub) + '</div>' +
        (buttons ? '<div class="buttons">' + buttons + '</div>' : '') + this._detailButton(t));
      return;
    }
    // The illustrated header: the school corner at the right, the status in the icon's colour (and in the pill), the
    // buttons at the top right.
    this._uid = this._uid || ++educartableUid;
    var tools = buttons + this._detailButton(t);
    header.className = 'banner' + (educartableIsNight(this._hass, c) ? ' night' : '');
    educartableMorph(header,
      educartableSceneSvg(st, header.classList.contains('night'), this._uid, !!tools) + '<div class="eo-ground"></div>' +
      '<div class="htext"><div class="logo ' + st.status + '" title="' + educartableEsc(updated || title) + '"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="' + EDUCARTABLE_SCHOOL_PATH + '"/></svg>' +
      '<span class="brand" aria-hidden="true">' + EDUCARTABLE_ICON + '</span></div>' +
      titles(sub) + '</div>' +
      (tools ? '<div class="hbtns">' + tools + '</div>' : ''));
  }

  // Confirmation popup at the top of the card (card convention), never centered on the screen: the signer's name, as
  // the portal asks for it, prefilled with the account's name.
  _renderPopup(t, data) {
    var popup = this._root.querySelector('.popup');
    var w = this._confirm && data ? data.words.find((x) => String(x.id) === this._confirm.id) : null;
    if (!w) {
      this._confirm = null;
      popup.hidden = true;
      educartableMorph(popup, '');
      return;
    }
    var first = popup.hidden;
    popup.hidden = false;
    educartableMorph(popup,
      '<div class="popup-title">' + educartableEsc(t.sign_title) + '</div>' +
      '<div class="popup-text">' + educartableEsc(educartableFormat(t.sign_text, { title: w.title || '—' })) + '</div>' +
      '<label class="signer-label">' + educartableEsc(t.signer) + '<input class="signer" type="text" autocomplete="name" value="' + educartableEsc(this._confirm.name) + '"></label>' +
      '<div class="popup-actions"><button class="act ghost" data-action="cancel">' + educartableEsc(t.cancel) + '</button>' +
      '<button class="act" data-action="confirm"' + (this._confirm.busy ? ' disabled' : '') + '>' + educartableEsc(this._confirm.busy ? t.signing : t.sign) + '</button></div>');
    if (first) popup.querySelector('.signer')?.focus({ preventScroll: true });
  }

  _renderTiles(t, data) {
    var toSign = data.words.filter((w) => !w.signed).length;
    var todo = data.homework.filter((h) => !h.done).length;
    var news = data.news.length;
    var tile = (value, label, icon, hot, tab) =>
      '<button class="tile' + (hot ? ' hot' : '') + '" data-action="goto" data-tab="' + tab + '" aria-label="' + educartableEsc(value + ' ' + label) + '">' +
      '<span class="v"><ha-icon icon="' + icon + '"></ha-icon>' + value + '</span><span class="l">' + educartableEsc(label) + '</span></button>';
    // A count follows its section's option: hiding the homework hides its count too.
    var c = this._config;
    var tiles = [
      c.show_homework ? tile(todo, t.tile_homework, 'mdi:pencil-outline', false, 'homework') : '',
      c.show_words ? tile(toSign, t.tile_words, 'mdi:notebook-edit-outline', toSign > 0, 'words') : '',
      c.show_news ? tile(news, t.tile_news, 'mdi:newspaper-variant-outline', false, 'news') : '',
    ].filter(Boolean);
    if (!tiles.length) return '';
    return '<div class="tiles" style="grid-template-columns: repeat(' + tiles.length + ', minmax(0, 1fr))">' + tiles.join('') + '</div>';
  }

  _section(key, title, rows, empty, extra) {
    // An empty section is left out (but homework, which says "nothing to do"), unless show_empty.
    if (!rows.length && !this._config.show_empty && key !== 'homework') return '';
    return '<div class="section" data-section="' + key + '"><div class="section-title">' + educartableEsc(title) + '</div>' +
      (rows.length ? rows.join('') : '<div class="empty">' + educartableEsc(empty) + '</div>') +
      (extra ? '<div class="more">' + educartableEsc(extra) + '</div>' : '') + '</div>';
  }

  _renderSections(t, data) {
    var c = this._config;
    var max = Math.max(1, Number(c.max_items) || EDUCARTABLE_DEFAULTS.max_items);
    var locale = this._locale();
    var limit = (list) => ({ shown: list.slice(0, max), rest: Math.max(0, list.length - max) });
    var more = (n) => (n ? educartableFormat(t.more, { n: n }) : '');
    // A single child: their name is in the header, not repeated on every row.
    var child = data.children.length > 1;
    var opts = { isOpen: (key) => !!this._open[key], entryId: data.entryId, canAct: educartableCanAct(this._hass), child: child };
    var html = '';
    if (c.show_words) {
      // The messages still waiting for something (a signature, a read).
      var words = limit(data.words.filter((w) => w.achievement && !w.achieved));
      html += this._section('words', t.section_words, words.shown.map((w) => educartableWordRow(w, t, locale, opts)), t.no_words, more(words.rest));
    }
    if (c.show_homework) {
      var hw = limit(educartableSortedHomework(data.homework, c.show_done));
      html += this._section('homework', t.section_homework, hw.shown.map((h) => educartableHomeworkRow(h, t, locale, opts)), t.no_homework, more(hw.rest));
    }
    if (c.show_news) {
      var news = limit(data.news);
      html += this._section('news', t.section_news, news.shown.map((n) => educartableNewsRow(n, t, locale, opts)), t.no_news, more(news.rest));
    }
    return html;
  }

  // A count opens the panel on its tab; without the panel, the card scrolls to the section (the mini card opens).
  _goto(tab) {
    if (this._hass?.panels?.[EDUCARTABLE_PANEL_PATH]) {
      var params = new URLSearchParams({ tab: tab });
      if (this._data && Object.keys(educartableAccounts(this._hass)).length > 1) params.set('entry', this._data.entryId);
      window.history.pushState(null, '', `/${EDUCARTABLE_PANEL_PATH}?${params}`);
      window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: false } }));
      return;
    }
    if (this._compact()) this._setZoom?.(true);
    this._root.querySelector(`[data-section="${tab}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  _toggleRow(key) {
    if (this._open[key]) delete this._open[key];
    else this._open[key] = true;
    this._render(true);
  }

  _onClick(ev) {
    var toggle = ev.target.closest ? ev.target.closest('[data-toggle]') : null;
    var el = ev.target.closest ? ev.target.closest('[data-action]') : null;
    if (toggle && !el) {
      ev.stopPropagation();
      this._toggleRow(toggle.getAttribute('data-toggle'));
      return;
    }
    if (!el || !this._data) return;
    var data = this._data;
    var action = el.getAttribute('data-action');
    var word = () => data.words.find((x) => String(x.id) === el.getAttribute('data-id'));
    if (action === 'refresh') this._refresh();
    else if (action === 'open') window.open(data.url, '_blank', 'noopener');
    else if (action === 'detail') this._toggleDetail(ev);
    else if (action === 'goto') {
      ev.stopPropagation();
      this._goto(el.getAttribute('data-tab'));
    } else if (action === 'dismiss') {
      this._error = '';
      this._render(true);
    } else if (action === 'sign' && educartableCanAct(this._hass)) {
      ev.stopPropagation();
      this._confirm = { id: el.getAttribute('data-id'), name: data.account.name || '' };
      this._render(true);
    } else if (action === 'cancel') {
      this._confirm = null;
      this._render(true);
    } else if (action === 'confirm') this._doSign();
    else if (action === 'read' && word()) {
      ev.stopPropagation();
      educartableMarkRead(this._hass, data.entryId, word()).catch((err) => this._fail(err, this._t().action_failed));
    } else if (action === 'homework') {
      var item = data.homework.find((h) => String(h.id) === el.getAttribute('data-id') && String(h.child_id) === el.getAttribute('data-child'));
      if (item && educartableCanAct(this._hass)) educartableSetDone(this._hass, data.entryId, item, !item.done).catch((err) => this._fail(err, this._t().action_failed));
    } else if (action === 'file') {
      ev.stopPropagation();
      educartableOpenFile(this._hass, data.entryId, { id: el.getAttribute('data-media'), name: el.getAttribute('data-name') }).catch((err) => this._fail(err, this._t().action_failed));
    }
  }

  _doSign() {
    var w = this._confirm && this._data?.words.find((x) => String(x.id) === this._confirm.id);
    if (!w || this._confirm.busy) return;
    if (String(this._confirm.name || '').trim().length < 3) {
      this._error = this._t().signer_short;
      this._render(true);
      return;
    }
    this._confirm.busy = true;
    this._error = '';
    this._render(true);
    educartableSign(this._hass, this._data.entryId, w, this._confirm.name.trim())
      .then(() => {
        this._confirm = null;
        this._render(true);
      })
      .catch((err) => {
        this._confirm = null;
        this._fail(err, this._t().action_failed);
      });
  }

  _fail(err, prefix) {
    educartableErrorText(this._hass, err).then((text) => {
      this._error = `${prefix} ${text}`;
      this._errorAt = this._data?.updated;
      this._render(true);
    });
  }

  _refresh() {
    if (this._refreshing) return;
    this._refreshing = true;
    this._error = '';
    this._render(true);
    educartableRefresh(this._hass, this._data.entryId)
      .catch((err) => this._fail(err, this._t().refresh_failed))
      .finally(() => {
        this._refreshing = false;
        this._render(true);
      });
  }

  static _styles() {
    var A = EDUCARTABLE_ACCENT;
    return [
      ':host { display: block; }',
      ':host::before { content: ""; display: grid; grid-template-columns: minmax(0, 360px); height: 0; }',
      'ha-card { padding: 0 0 10px; overflow: hidden; container: eo-card / inline-size; }',
      '.header { display: flex; align-items: center; gap: 10px; padding: 12px 10px 8px 12px; min-height: 40px; }',
      '.title { flex: 1 1 0; min-width: calc(5ch + 50px); display: flex; align-items: center; gap: 10px; }',
      '.logo { width: 40px; height: 40px; flex: none; border-radius: 50%; display: grid; place-items: center; color: ' + A + '; background: color-mix(in srgb, ' + A + ' 16%, transparent); }',
      '.logo > svg { width: 24px; height: 24px; }',
      '.titles { flex: 1 1 0; min-width: 5ch; overflow: hidden; container: eo-titles / inline-size; }',
      ':host([hide-title]) .title-row > .name { display: none; }',
      // The title line: the title, then the status pill, when the whole title and its whole label fit there; otherwise
      // the pill goes on its own line under the subtitle (kept to one line), and when even that is too tight only its
      // dot is left (its text stays in its title and aria-label). Decided by measure (see _fitPill).
      '.title-row { display: flex; align-items: center; gap: 8px; min-width: 0; }',
      '.title-row .name { flex: 0 1 auto; min-width: 0; }',
      '.title-row .status { flex: none; max-width: none; }',
      '.titles.pill-below { display: flex; flex-direction: column; }',
      '.titles.pill-below .title-row { display: contents; }',
      '.titles.pill-below .title-row .status { order: 3; align-self: flex-start; margin-top: 3px; max-width: 100%; }',
      '.titles.pill-below .sub.error { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
      '.titles.pill-dot .title-row .status { padding: 4px; } .titles.pill-dot .status-text { display: none; }',
      '.name { font-size: 16px; font-weight: 500; line-height: 1.25; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
      '.sub { font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
      '.sub.error { display: flex; align-items: flex-start; gap: 4px; white-space: normal; color: color-mix(in srgb, var(--error-color, #db4437) 55%, var(--primary-text-color)); }',
      '.dismiss { all: unset; cursor: pointer; flex: none; display: grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; --mdc-icon-size: 14px; }',
      '.dismiss:hover { background: color-mix(in srgb, var(--error-color, #db4437) 14%, transparent); }',
      '.dismiss:focus-visible { outline: 2px solid var(--primary-color); }',
      '.status { --c: var(--success-color, #43a047); display: inline-flex; align-items: center; gap: 4px; min-width: 0; box-sizing: border-box; overflow: hidden; font-size: 11px; font-weight: 500; line-height: 16px; white-space: nowrap;' +
        ' border-radius: 12px; padding: 1px 8px; color: color-mix(in srgb, var(--c) 50%, var(--primary-text-color)); background: color-mix(in srgb, var(--c) 15%, transparent); }',
      '.status .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--c); flex: none; }',
      '.status.warn { --c: var(--warning-color, #ffa600); }',
      '.status.bad { --c: var(--error-color, #db4437); }',
      '.status-text { min-width: 0; overflow: hidden; text-overflow: ellipsis; }',
      '.buttons { display: flex; align-items: center; flex: none; }',
      // Plain round buttons (not ha-icon-button, whose inner 40 px button overflows a shrunk host and offsets the icon
      // and its hover ring).
      '.hbtn { all: unset; box-sizing: border-box; cursor: pointer; flex: none; display: grid; place-items: center; width: 28px; height: 28px;' +
        ' border-radius: 50%; color: var(--secondary-text-color); --mdc-icon-size: 16px; transition: background-color .15s, color .15s; }',
      '.hbtn ha-icon { display: flex; }',
      '.buttons .hbtn:hover { background: color-mix(in srgb, var(--secondary-text-color) 14%, transparent); color: var(--primary-text-color); }',
      '.hbtn:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }',
      '.spinning ha-icon { animation: educartable-spin 1s linear infinite; }',
      '@keyframes educartable-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }',
      '@container (max-width: 320px) { .header { gap: 4px; } .logo { display: none; } }',
      // Very narrow card: only the pill's dot stays, on the title line.
      '@container eo-card (max-width: 200px) { .title-row .status { padding: 4px; } .status-text { display: none; } }',
      '.pad { padding: 4px 16px; }',
      '.tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; padding: 0 12px; }',
      '.tile { all: unset; box-sizing: border-box; cursor: pointer; display: block; min-width: 0; padding: 8px 10px; border-radius: 12px; background: color-mix(in srgb, var(--primary-text-color) 5%, transparent); }',
      '.tile:hover { background: color-mix(in srgb, var(--primary-text-color) 9%, transparent); }',
      '.tile:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }',
      '.tile.hot:hover { background: color-mix(in srgb, ' + A + ' 20%, transparent); }',
      '.tile.hot { background: color-mix(in srgb, ' + A + ' 14%, transparent); }',
      '.tile .v { display: flex; align-items: center; gap: 6px; font-size: 22px; font-weight: 500; line-height: 1.1; color: var(--primary-text-color); --mdc-icon-size: 18px; }',
      '.tile .v ha-icon { color: var(--secondary-text-color); }',
      '.tile.hot .v ha-icon { color: ' + A + '; }',
      '.tile .l { display: block; font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
      '.section { padding: 10px 12px 0; }',
      '.section-title { font-size: 12px; font-weight: 500; color: var(--secondary-text-color); margin-bottom: 2px; }',
      '.popup { margin: 0 12px 10px; padding: 10px 12px; border-radius: 12px; border: 1px solid color-mix(in srgb, ' + A + ' 40%, transparent); background: color-mix(in srgb, ' + A + ' 6%, var(--card-background-color, #fff)); }',
      '.popup[hidden] { display: none; }',
      '.popup-title { font-weight: 500; color: var(--primary-text-color); }',
      '.popup-text { font-size: 13px; color: var(--secondary-text-color); margin-top: 2px; }',
      '.signer-label { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; font-size: 12px; color: var(--secondary-text-color); }',
      '.signer { font: inherit; font-size: 14px; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--divider-color, rgba(0,0,0,.2)); background: var(--card-background-color, #fff); color: var(--primary-text-color); }',
      '.signer:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }',
      '.popup-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }',
      '.more { font-size: 12px; color: var(--secondary-text-color); padding-top: 2px; }',
      educartableItemStyles(A),
      ':host([mini])::before { grid-template-columns: minmax(0, 260px); }',
      '.header { position: relative; }',
      '.header:has(> .detail) { padding-right: 34px; }',
      '.detail { all: unset; position: absolute; z-index: 2; top: 5px; right: 5px; cursor: pointer; width: 24px; height: 24px; border-radius: 50%;' +
        ' display: grid; place-items: center; color: var(--secondary-text-color); --mdc-icon-size: 16px; box-shadow: inset 0 0 0 1px var(--divider-color, rgba(127,127,127,.3)); }',
      '.hbtns .detail { position: static; }',
      '.detail:hover { background: color-mix(in srgb, var(--secondary-text-color) 14%, transparent); color: var(--primary-text-color); }',
      '.detail:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }',
      '@container (max-width: 320px) { ha-card.mini .logo { display: grid; } }',
      '@container (max-width: 200px) { .tiles { grid-template-columns: minmax(0, 1fr); } }',
      '@media (prefers-reduced-motion: reduce) { .spinning ha-icon { animation: none; opacity: .5; } }',
      EDUCARTABLE_BANNER_STYLES,
    ].join('\n');
  }
}
