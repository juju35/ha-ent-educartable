// ── End of the folded top bar ──
import { EDUCARTABLE_PANEL_TABS, EDUCARTABLE_TAB_KEYS } from "./tabs.js";
import { educartablePanelFold } from "./fold.js";

export class EducartablePanel extends HTMLElement {
  constructor() {
    super();
    this._tab = this._tabFromUrl();
    this._readUrl();
    // Filters are remembered in this browser (storage can be missing or refuse: then they are not).
    var saved = {};
    try {
      saved = JSON.parse(window.localStorage.getItem('educartable-panel') || '{}') || {};
    } catch (_e) {
      saved = {};
    }
    this._hideDone = saved.hideDone === true;
    // Child chosen in the filter row (Home and Homework), '' = all of them.
    this._child = typeof saved.child === 'string' ? saved.child : '';
    // Day picked in the week strip of the home page ('' = the whole week), not remembered.
    this._day = '';
    this._entry = this._entry || '';
    // Rows unfolded on the home page, and the action being confirmed (sign, sign a document, book a slot).
    this._open = {};
    this._confirm = null;
    // What is being typed (reply, new message), kept across redraws; the conversations loaded and shown.
    this._typed = {};
    this._threads = {};
    this._threadOpen = {};
    // Survey answers being chosen, by message; the surveys reopened to change their answer.
    this._picks = {};
    this._editing = {};
    // The new message to the teacher being written.
    this._write = null;
  }

  set panel(panel) {
    this._panel = panel;
    this._loadShared();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._root) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!window.Educartable) {
      this._loadShared();
      return;
    }
    var E = window.Educartable;
    var data = E.data(hass, this._entry);
    var key = data ? data.states : null;
    // The settings form is not redrawn by sensor updates: that would wipe what is being typed.
    if (this._tab === 'settings' && this._root && this._lang === E.lang(hass)) return;
    if (!this._lastKey || !key || E.changed(key, this._lastKey) || this._lang !== E.lang(hass)) {
      this._lastKey = key;
      this._render();
    }
  }

  connectedCallback() {
    if (!this._fold && this.shadowRoot?.querySelector?.(".banner")) this._attachFold();
    this._onPop = this._onPop || (() => {
      this._tab = this._tabFromUrl();
      this._readUrl();
      this._render();
    });
    window.addEventListener('popstate', this._onPop);
    if (this._hass && window.Educartable) this._render();
  }

  disconnectedCallback() {
    window.removeEventListener('popstate', this._onPop);
    this._fold?.detach();
    this._fold = null;
    this._confirm = null;
  }

  // The account, from the address (the card's counts add it when there are several).
  _readUrl() {
    var params = new URLSearchParams(window.location.search);
    if (params.get('entry')) this._entry = params.get('entry');
  }

  _tabFromUrl() {
    var tab = new URLSearchParams(window.location.search).get('tab');
    return EDUCARTABLE_PANEL_TABS.indexOf(tab) !== -1 ? tab : 'home';
  }

  // The card file holds the shared code: it is already there when a dashboard loaded it, else imported here.
  _loadShared() {
    if (window.Educartable || this._loading) return;
    var url = this._panel?.config?.card_url || '/educartable_static/educartable-card.js';
    this._loading = import(url)
      .catch(() => null)
      .then(() => {
        this._loading = null;
        if (this._hass && window.Educartable) this._render();
      });
  }

  _saveFilters() {
    try {
      window.localStorage.setItem('educartable-panel', JSON.stringify({ hideDone: this._hideDone, child: this._child }));
    } catch (_e) {
      /* private mode, quota: not remembered */
    }
  }

  _setTab(tab) {
    if (tab === this._tab) return;
    this._tab = tab;
    this._confirm = null;
    var params = new URLSearchParams(window.location.search);
    params.set('tab', tab);
    window.history.pushState(null, '', `${window.location.pathname}?${params}`);
    if (tab === 'settings') this._settings = null;
    this._render();
  }

  _ensureShell() {
    if (this._root) return;
    this._root = this.attachShadow({ mode: 'open' });
    var E = window.Educartable;
    // The illustrated header of the card (school corner, ground bar, status in the icon's colour), across the page.
    this._root.innerHTML =
      '<style>' + (E.banner ? E.banner.styles : '') + EducartablePanel._styles(E.accent) + E.itemStyles(E.accent) + '</style>' +
      '<div class="banner"><div class="scene"></div><div class="eo-ground"></div><div class="htext"><ha-menu-button></ha-menu-button><div class="hinfo"></div></div>' +
      '<div class="hbtns"></div></div><div class="tabbar"><div class="tabs" role="tablist"></div><div class="tb-side"></div></div><div class="content"></div>';
    this._root.addEventListener('click', this._onClick.bind(this));
    this._root.addEventListener('change', this._onChange.bind(this));
    // What is typed is kept as it is typed: a redraw (a sensor update) draws it back.
    this._root.addEventListener('input', (ev) => {
      var key = ev.target.getAttribute?.('data-draft');
      if (key) this._typed[key] = ev.target.value;
    });
    this._root.addEventListener('keydown', (ev) => {
      if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.hasAttribute?.('data-toggle')) {
        ev.preventDefault();
        ev.target.click();
      } else if (ev.key === 'Enter' && ev.target.classList?.contains('signer') && this._data) {
        ev.preventDefault();
        this._doSign(this._data);
      } else if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey) && ev.target.matches?.('textarea[data-draft^="reply:"]') && this._data) {
        ev.preventDefault();
        this._doReply(this._data, ev.target.getAttribute('data-draft').slice(6));
      }
    });
    // Tabs: arrows, Home and End move between them (WAI-ARIA tabs pattern).
    this._root.querySelector('.tabs').addEventListener('keydown', (ev) => {
      var tabs = this._shownTabs || EDUCARTABLE_PANEL_TABS;
      var i = tabs.indexOf(this._tab);
      var next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[ev.key];
      if (next === undefined) return;
      ev.preventDefault();
      this._setTab(tabs[(next + tabs.length) % tabs.length]);
      this._root.querySelector('.tab.on')?.focus();
    });
    this._attachFold();
  }

  /** The top bar folds on scroll into one bar with the tabs as icon pills (see educartablePanelFold). */
  _attachFold() {
    this._fold?.detach();
    this._fold = educartablePanelFold(this, {
      top: ".banner",
      tabs: ".tabbar",
      tab: ".tab",
      key: (b) => b.dataset.tab,
      icons: {
        home: "mdi:home-outline",
        homework: "mdi:pencil-outline",
        words: "mdi:notebook-edit-outline",
        news: "mdi:newspaper-variant-outline",
        documents: "mdi:file-certificate-outline",
        settings: "mdi:cog",
      },
      badge: ".badge",
      name: ".banner .name",
      sub: ".banner .sub",
      icon: ".banner .logo",
      status: ".banner .status",
      acts: ".banner .hbtns > *",
      side: ".tb-side",
      accent: window.Educartable?.accent || "#f28c1e",
      menu: () => ({ hass: this._hass, narrow: this._narrow, show: true }),
    });
  }

  _render() {
    if (!this._hass || !window.Educartable) return;
    this._ensureShell();
    var E = window.Educartable;
    E.setTimeFormat(this._hass);
    var t = E.t(this._hass);
    this._lang = E.lang(this._hass);
    // The panel is not among the cards the language loader redraws: draw again once the language file is in.
    if (!E.langReady(this._hass) && !this._langRetry) {
      this._langRetry = setTimeout(() => {
        this._langRetry = null;
        if (this._tab === 'settings') this._settings = null;
        this._render();
      }, 250);
    }
    var menu = this._root.querySelector('ha-menu-button');
    menu.hass = this._hass;
    menu.narrow = this._narrow;
    var accounts = E.accounts(this._hass);
    var ids = Object.keys(accounts);
    if (this._entry && ids.indexOf(this._entry) === -1) this._entry = '';
    var data = E.data(this._hass, this._entry || ids[0]);
    this._data = data;
    // Tabs hidden in the options are left out, with their part of the home page.
    var shown = EDUCARTABLE_PANEL_TABS.filter((tab) => tab === 'home' || tab === 'settings' || !data || data.panelTabs.indexOf(tab) !== -1);
    // The top bar hidden (option): the tabs stay, with the menu button at their left and the buttons at their right.
    var mode = data?.hideHeader || 'off';
    var bare = mode === 'all' || (mode === 'non_admin' && this._hass.user?.is_admin === false);
    this._root.host.toggleAttribute('bare', bare);
    var tabbar = this._root.querySelector('.tabbar');
    if (bare && menu.parentElement !== tabbar) tabbar.prepend(menu);
    else if (!bare && menu.parentElement === tabbar) this._root.querySelector('.htext').prepend(menu);
    this._renderHeader(t, data, shown);
    var hbtns = this._root.querySelector('.hbtns');
    this._root.querySelector('.tb-side').innerHTML = (bare ? hbtns.innerHTML : '') + (ids.length > 1
      ? '<select class="account" aria-label="' + E.esc(t.account) + '">' +
        ids.map((id) => {
          var d = E.data(this._hass, id);
          var name = d.account.name || d.children.map((ch) => ch.first_name).filter(Boolean).join(' · ') || id;
          return '<option value="' + E.esc(id) + '"' + (id === (data?.entryId) ? ' selected' : '') + '>' + E.esc(name) + '</option>';
        }).join('') + '</select>'
      : '');
    if (bare) hbtns.innerHTML = '';
    this._shownTabs = shown;
    if (shown.indexOf(this._tab) === -1) this._tab = 'home';
    this._root.querySelector('.tabs').innerHTML = shown.map((tab) => {
      var count = data ? this._count(tab, data) : 0;
      var on = tab === this._tab;
      return '<button role="tab" class="tab' + (on ? ' on' : '') + '" aria-selected="' + on + '" tabindex="' + (on ? 0 : -1) + '" data-tab="' + tab + '">' +
        E.esc(t[EDUCARTABLE_TAB_KEYS[tab]]) + (count ? ' <span class="badge">' + count + '</span>' : '') + '</button>';
    }).join('');
    var content = this._root.querySelector('.content');
    if (this._tab === 'settings') {
      this._renderSettings(content, t);
      return;
    }
    if (!data) {
      content.innerHTML = '<div class="page"><div class="empty">' + E.esc(t.no_account) + '</div></div>';
      return;
    }
    if (data.unavailable) {
      content.innerHTML = '<div class="page"><div class="empty">' + E.esc(t.unavailable) + '</div></div>';
      return;
    }
    var html = { home: this._home, homework: this._homework, words: this._words, news: this._news, documents: this._documents }[this._tab].call(this, t, data);
    // The signer's name being typed survives the redraw (the input is drawn again), and so does the focus.
    var typed = content.querySelector('.signer');
    if (typed && this._confirm) this._confirm.name = typed.value;
    var active = this._root.activeElement;
    var focus = active?.getAttribute?.('data-draft') || (active?.classList?.contains('signer') ? 'signer' : '');
    var caret = focus && typeof active.selectionStart === 'number' ? [active.selectionStart, active.selectionEnd] : null;
    content.innerHTML = '<div class="page">' + (this._error ? '<div class="error-text errbar">' + E.esc(this._error) + '</div>' : '') + this._popup(t, data) + html + '</div>';
    E.hydrate(content, this._hass, data.entryId);
    if (focus) {
      var again = focus === 'signer' ? content.querySelector('.signer') : content.querySelector('[data-draft="' + CSS.escape(focus) + '"]');
      if (again) {
        again.focus({ preventScroll: true });
        if (caret) again.setSelectionRange?.(caret[0], caret[1]);
      }
    }
  }

  _count(tab, data) {
    if (tab === 'words') return data.words.filter((w) => !w.signed).length;
    if (tab === 'homework') return data.homework.filter((h) => !h.done).length;
    if (tab === 'documents') return data.documents.filter((d) => d.to_sign).length;
    return 0;
  }

  _time(iso) {
    return window.Educartable.time(iso, window.Educartable.locale(this._hass));
  }

  _box(title, body, wide) {
    return '<section class="box' + (wide ? ' wide' : '') + '">' + (title ? '<h2>' + window.Educartable.esc(title) + '</h2>' : '') + body + '</section>';
  }

  _list(rows, empty) {
    return rows.length ? rows.join('') : '<div class="empty">' + window.Educartable.esc(empty) + '</div>';
  }

  // The card's illustrated header: the school corner and its ground bar, the school icon in the status colour with
  // the Educartable book as badge, the title with its status pill, the children's names, and round glass buttons.
  _renderHeader(t, data, shown) {
    var E = window.Educartable;
    var B = E.banner;
    var banner = this._root.querySelector('.banner');
    var night = B ? B.isNight(this._hass, {}) : false;
    banner.classList.toggle('night', night);
    var on = (tab) => shown.indexOf(tab) !== -1;
    var st = B ? B.state(data, { show_homework: on('homework'), show_words: on('words') }) : { status: 'idle', kind: 'done', unread: 0 };
    this._uid = this._uid || 'p' + Math.floor(Math.random() * 1e6);
    banner.querySelector('.scene').innerHTML = B ? B.scene(st, night, this._uid, false) : '';
    var title = t.default_title;
    var updated = data?.updated ? E.format(t.last_update, { time: this._time(data.updated) }) : '';
    var who = data ? data.children.map((ch) => ch.first_name).filter(Boolean).join(' · ') : '';
    var pill = '';
    if (data) {
      var text = data.unavailable ? t.offline : data.stale.length ? t.partial : t.up_to_date;
      pill = '<span class="status ' + st.status + '" title="' + E.esc(updated || text) + '"><span class="dot"></span>' + E.esc(text) + '</span>';
    }
    banner.querySelector('.hinfo').innerHTML =
      '<div class="logo ' + st.status + '" title="' + E.esc(updated || title) + '"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="' + (B ? B.schoolPath : '') + '"/></svg>' +
      '<span class="brand" aria-hidden="true">' + E.icon + '</span></div>' +
      '<div class="titles"><div class="title-row"><div class="name">' + E.esc(title) + '</div>' + pill + '</div>' +
      '<div class="sub">' + E.esc([who, updated].filter(Boolean).join(' · ')) + '</div></div>';
    banner.querySelector('.hbtns').innerHTML =
      (data ? '<button class="hbtn' + (this._refreshing ? ' spinning' : '') + '" data-action="refresh" aria-label="' + E.esc(t.refresh) + '" title="' + E.esc(t.refresh) + '"><ha-icon icon="mdi:refresh"></ha-icon></button>' : '') +
      (data?.url ? '<button class="hbtn" data-action="open" aria-label="' + E.esc(t.open_ent) + '" title="' + E.esc(t.open_ent) + '"><ha-icon icon="mdi:open-in-new"></ha-icon></button>' : '');
  }

  // Children of the account, the chosen one dropped when it is gone.
  _children(data) {
    var kids = data.children.filter((ch) => ch.id || ch.first_name);
    if (this._child && !kids.some((ch) => String(ch.id) === this._child)) this._child = '';
    return kids;
  }

  // The filter row: All, then one chip per child (initial, first name, homework left). Only with 2+ children.
  _childChips(t, data) {
    var E = window.Educartable;
    var kids = this._children(data);
    if (kids.length < 2) return '';
    var left = (id) => data.homework.filter((h) => !h.done && (!id || h.child_id === id)).length;
    var chip = (id, label, i) => {
      var n = left(id);
      return '<button class="kid' + (this._child === id ? ' on' : '') + '" data-child="' + E.esc(id) + '" aria-pressed="' + (this._child === id) + '">' +
        (id ? '<span class="avatar c' + (i % 4) + '">' + E.esc((label || '?').charAt(0).toUpperCase()) + '</span>' : '') +
        E.esc(label) + (n ? '<span class="badge">' + n + '</span>' : '') + '</button>';
    };
    return '<div class="kids">' + chip('', t.all, 0) + kids.map((ch, i) => chip(String(ch.id), ch.first_name || ch.last_name, i)).join('') + '</div>';
  }

  // The homework of the child chosen in the filter row (all of it for All).
  _myHomework(data) {
    return data.homework.filter((h) => !this._child || h.child_id === this._child);
  }

  // The school week: Monday to Friday (Saturday and Sunday when something falls on them), the next week from
  // Saturday on. Each day carries the homework left for it; a click keeps only that day.
  _week(t, data) {
    var E = window.Educartable;
    var locale = E.locale(this._hass);
    var iso = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    var now = new Date();
    var today = iso(now);
    var monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7) + (now.getDay() === 6 || now.getDay() === 0 ? 7 : 0));
    var days = [];
    for (var i = 0; i < 7; i++) {
      var d = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i);
      var key = iso(d);
      var hw = this._myHomework(data).filter((h) => !h.done && String(h.date).slice(0, 10) === key).length;
      if (i < 5 || hw) days.push({ key: key, d: d, hw: hw });
    }
    if (this._day && !days.some((x) => x.key === this._day)) this._day = '';
    var label = (d) => {
      try {
        return d.toLocaleDateString(locale, { weekday: 'short', day: 'numeric' });
      } catch (_e) {
        return d.toDateString().slice(0, 10);
      }
    };
    return '<div class="week" role="group" aria-label="' + E.esc(t.this_week) + '">' + days.map((x) =>
      '<button class="wday' + (x.hw ? ' hw' : '') + (x.key === today ? ' today' : '') + (x.key === this._day ? ' on' : '') + (x.key < today ? ' past' : '') + '" data-day="' + x.key + '" aria-pressed="' + (x.key === this._day) + '">' +
      '<span class="wl">' + E.esc(label(x.d)) + '</span>' + (x.hw ? '<span class="wn">' + x.hw + '</span>' : '') + '</button>').join('') + '</div>';
  }

  // A tile of the chart: neutral surface, round tinted pastille (count as badge), name and a coloured state line.
  _tile(tab, icon, color, name, state, count) {
    var E = window.Educartable;
    return '<button class="tile ' + (count ? color : 'rest') + '" data-tab="' + tab + '"><span class="pastille"><ha-icon icon="' + icon + '"></ha-icon>' +
      (count ? '<span class="pbadge">' + (count > 99 ? '99+' : count) + '</span>' : '') + '</span>' +
      '<span class="tl"><span class="tn">' + E.esc(name) + '</span><span class="ts">' + E.esc(state) + '</span></span></button>';
  }

  _home(t, data) {
    var E = window.Educartable;
    var locale = E.locale(this._hass);
    var R = E.rows;
    var opts = { isOpen: (key) => !!this._open[key], entryId: data.entryId, canAct: E.canAct(this._hass), extra: (item) => this._extras(item, t, data) };
    var on = (tab) => data.panelTabs.indexOf(tab) !== -1;
    // The week strip counts homework: left out with the Homework tab, its day filter cleared.
    if (!on('homework')) this._day = '';
    var day = this._day;
    var several = this._children(data).length > 1;
    var toSign = data.words.filter((w) => !w.signed);
    var pending = data.words.filter((w) => w.achievement && !w.achieved);
    var todo = E.sortedHomework(this._myHomework(data), false).filter((h) => !day || String(h.date).slice(0, 10) === day);
    var latest = data.news[0];
    var docs = data.documents.filter((d) => d.to_sign);
    var tiles = [
      on('words') ? this._tile('words', 'mdi:notebook-edit-outline', 'red', t.section_words, toSign.length ? toSign.length + ' ' + t.tile_words : t.no_words, toSign.length) : '',
      on('homework') ? this._tile('homework', 'mdi:pencil-outline', 'amber', t.section_homework, todo.length ? todo.length + ' ' + t.tile_homework : t.no_homework, todo.length) : '',
      on('news') ? this._tile('news', 'mdi:newspaper-variant-outline', 'blue', t.section_news, latest ? [latest.title, E.day(latest.date, t, locale)].filter(Boolean).join(' · ') : t.no_news, 0) : '',
      on('documents') && data.documents.length ? this._tile('documents', 'mdi:file-certificate-outline', 'violet', t.section_documents, docs.length ? docs.length + ' ' + t.tile_documents : t.doc_all_signed, docs.length) : '',
    ].filter(Boolean);
    var see = (tab) => (on(tab) ? '<button class="see" data-tab="' + tab + '">' + E.esc(t.see_all) + ' ›</button>' : '');
    var todoRows = (on('words') ? pending.map((w) => R.word(w, t, locale, opts)) : [])
      .concat(on('homework') ? todo.slice(0, 6).map((h) => R.homework(h, t, locale, Object.assign({}, opts, { child: several && !this._child }))) : [])
      .concat(on('documents') ? docs.slice(0, 3).map((d) => R.document(d, t, { canAct: opts.canAct, child: several })) : []);
    var newsRows = data.news.slice(0, 5).map((n) => R.news(n, t, locale, opts));
    var box = (cls, title, side, rows, empty) =>
      '<section class="box ' + cls + '"><div class="bh"><h2>' + E.esc(title) + '</h2>' + side + '</div>' + this._list(rows, empty) + '</section>';
    return this._childChips(t, data) + (on('homework') ? this._week(t, data) : '') +
      (tiles.length ? '<div class="tiles" style="grid-template-columns: repeat(' + tiles.length + ', minmax(0, 1fr))">' + tiles.join('') + '</div>' : '') +
      '<div class="dgrid">' +
      (on('words') || on('homework') || on('documents') ? box('todo-box', t.section_todo, see(on('homework') ? 'homework' : 'words'), todoRows, t.nothing_to_do) : '') +
      (on('news') ? box('read-box', t.section_news, see('news'), newsRows, t.no_news) : '') +
      '</div>';
  }

  // Homework: the child chips, then one box per due day with how much of it is done.
  _homework(t, data) {
    var E = window.Educartable;
    var locale = E.locale(this._hass);
    var several = this._children(data).length > 1;
    var chips = '<div class="filters">' + this._childChips(t, data) +
      '<label class="toggle"><input type="checkbox" data-action="hide-done"' + (this._hideDone ? ' checked' : '') + '> ' + E.esc(t.hide_done) + '</label></div>';
    var days = [];
    this._myHomework(data).slice().sort((a, b) => String(a.date).localeCompare(String(b.date))).forEach((h) => {
      var last = days[days.length - 1];
      if (!last || last.date !== h.date) days.push({ date: h.date, all: [h] });
      else last.all.push(h);
    });
    var tiles = days.map((d) => {
      var done = d.all.filter((h) => h.done).length;
      var items = E.sortedHomework(d.all, !this._hideDone);
      if (!items.length) return '';
      var full = done === d.all.length;
      return '<section class="box day' + (full ? ' full' : '') + '"><div class="bh"><h2>' + E.esc(d.date ? E.day(d.date, t, locale) : '—') + '</h2><span class="ratio">' + done + ' / ' + d.all.length + '</span></div>' +
        '<div class="bar"><span style="width:' + Math.round((done / d.all.length) * 100) + '%"></span></div>' +
        items.map((h) => E.rows.homework(h, t, locale, { child: several && !this._child, full: true, entryId: data.entryId, canAct: E.canAct(this._hass) })).join('') + '</section>';
    }).join('');
    return chips + (tiles ? '<div class="days">' + tiles + '</div>' : this._box('', '<div class="empty">' + E.esc(t.no_homework) + '</div>', true));
  }

  // Liaison book: the messages still to sign first, then the signed ones.
  // Liaison book: New message (to the teacher) above the messages still to sign first, then the signed ones.
  _words(t, data) {
    var E = window.Educartable;
    var locale = E.locale(this._hass);
    var words = data.words.slice().sort((a, b) => (a.signed === b.signed ? 0 : a.signed ? 1 : -1));
    var opts = { full: true, entryId: data.entryId, canAct: E.canAct(this._hass), extra: (item) => this._extras(item, t, data) };
    var write = opts.canAct && !this._write && this._children(data).length
      ? '<div class="toolbar"><button class="act" data-action="write"><ha-icon icon="mdi:email-edit-outline"></ha-icon>' + E.esc(t.new_message) + '</button></div>'
      : '';
    return write + this._box('', this._list(words.map((w) => E.rows.word(w, t, locale, opts)), t.no_words), true);
  }

  _news(t, data) {
    var E = window.Educartable;
    var locale = E.locale(this._hass);
    var opts = { full: true, entryId: data.entryId, canAct: E.canAct(this._hass), extra: (item) => this._extras(item, t, data) };
    return this._box('', this._list(data.news.map((n) => E.rows.news(n, t, locale, opts)), t.no_news), true);
  }

  // The livret: one box per child (one list with a single child), the documents to sign first.
  _documents(t, data) {
    var E = window.Educartable;
    var canAct = E.canAct(this._hass);
    var kids = this._children(data);
    if (!data.documents.length) return this._box('', '<div class="empty">' + E.esc(t.no_documents) + '</div>', true);
    if (kids.length < 2) return this._box('', data.documents.map((d) => E.rows.document(d, t, { canAct: canAct, child: false })).join(''), true);
    var known = kids.map((ch) => String(ch.id));
    var groups = kids.map((ch) => [ch.first_name, data.documents.filter((d) => d.child_id === String(ch.id))]);
    groups.push(['', data.documents.filter((d) => known.indexOf(d.child_id) === -1)]);
    return '<div class="grid">' + groups.filter((g) => g[1].length).map((g) =>
      this._box(g[0], g[1].map((d) => E.rows.document(d, t, { canAct: canAct, child: false })).join(''))).join('') + '</div>';
  }

  // The children a message concerns (all of them when it does not say).
  _concerned(item, data) {
    var kids = this._children(data);
    var ids = (item.children || []).map(String);
    var some = kids.filter((ch) => ids.indexOf(String(ch.id)) !== -1);
    return some.length ? some : kids;
  }

  // Under an unfolded message: its survey, its appointment slots and its conversation with the teacher.
  _extras(item, t, data) {
    var can = window.Educartable.canAct(this._hass);
    var html = '';
    if (item.survey) html += this._surveyBlock(item, t, data, can);
    if (item.slots?.length) html += this._slotsBlock(item, t, data, can);
    if (can && (item.commentable || item.achievement === 'comment')) html += this._threadBlock(item, t, data);
    return html ? '<div class="extras">' + html + '</div>' : '';
  }

  _closed(survey) {
    if (!survey.deadline) return false;
    var end = window.Educartable.parse ? window.Educartable.parse(survey.deadline) : new Date(survey.deadline);
    end = new Date(end.getFullYear(), end.getMonth(), end.getDate() + 1);
    return end < new Date();
  }

  _surveyBlock(item, t, data, can) {
    var E = window.Educartable;
    var locale = E.locale(this._hass);
    var s = item.survey;
    var kids = this._concerned(item, data);
    var answered = kids.filter((ch) => s.answers[String(ch.id)]);
    var closed = this._closed(s);
    var form = can && !closed && (answered.length < kids.length || this._editing[item.id]);
    var current = this._picks[item.id] || (answered[0] ? s.answers[String(answered[0].id)] : {});
    var meta = [closed ? t.survey_closed : s.deadline ? E.format(t.survey_until, { day: E.day(s.deadline, t, locale) }) : '', s.anonymous ? t.survey_anonymous : ''].filter(Boolean).join(' · ');
    var questions = s.questions.map((q) =>
      '<div class="q"><div class="ql">' + E.esc(q.label) + (q.multiple ? ' <span class="qm">' + E.esc(t.survey_multiple) + '</span>' : '') + '</div><div class="opts" role="group" aria-label="' + E.esc(q.label) + '">' +
      q.options.map((o) => {
        var on = (current[q.id] || []).indexOf(o.id) !== -1;
        return '<button class="opt' + (on ? ' on' : '') + '" role="' + (q.multiple ? 'checkbox' : 'radio') + '" aria-checked="' + on + '" data-action="survey-opt" data-msg="' + E.esc(item.id) + '" data-q="' + E.esc(q.id) + '" data-o="' + E.esc(o.id) + '"' + (form ? '' : ' disabled') + '>' + E.esc(o.label) + '</button>';
      }).join('') + '</div></div>').join('');
    var foot = (answered.length ? '<span class="chip ok">' + E.esc(E.format(t.survey_answered, { children: answered.map((ch) => ch.first_name).join(', ') })) + '</span>' : '') +
      (form
        ? '<button class="act" data-action="survey-send" data-msg="' + E.esc(item.id) + '">' + E.esc(t.survey_send) + '</button>'
        : can && !closed && answered.length ? '<button class="act ghost" data-action="survey-change" data-msg="' + E.esc(item.id) + '">' + E.esc(t.survey_change) + '</button>' : '');
    return '<div class="xblock"><div class="xh"><ha-icon icon="mdi:poll"></ha-icon>' + E.esc(t.survey) + (meta ? '<span class="xmeta">' + E.esc(meta) + '</span>' : '') + '</div>' + questions +
      (foot ? '<div class="xfoot">' + foot + '</div>' : '') + '</div>';
  }

  _slotLabel(slot, t) {
    var E = window.Educartable;
    var locale = E.locale(this._hass);
    return [E.day(slot.start, t, locale), [E.time(slot.start, locale), slot.end ? E.time(slot.end, locale) : ''].filter(Boolean).join('–')].filter(Boolean).join(' · ');
  }

  _slotsBlock(item, t, data, can) {
    var E = window.Educartable;
    var kids = this._concerned(item, data);
    var names = {};
    kids.forEach((ch) => {
      names[String(ch.id)] = ch.first_name;
    });
    var booked = item.slots.filter((x) => x.booked);
    var free = item.slots.filter((x) => !x.booked);
    var waiting = kids.filter((ch) => !booked.some((x) => x.child_id === String(ch.id)));
    var rows = booked.map((x) =>
      '<div class="booked"><ha-icon icon="mdi:calendar-check"></ha-icon><span>' + E.esc([E.format(t.slot_booked, { child: names[x.child_id] || '' }), this._slotLabel(x, t), x.location].filter(Boolean).join(' · ')) + '</span>' +
      (can ? '<button class="act ghost" data-action="slot-cancel" data-slot="' + E.esc(x.id) + '">' + E.esc(t.slot_cancel) + '</button>' : '') + '</div>').join('');
    var pick = '';
    if (waiting.length) {
      // The free slots day by day: the day once, then its times.
      var locale = E.locale(this._hass);
      var days = [];
      free.forEach((x) => {
        var day = E.day(x.start, t, locale);
        if (!days.length || days[days.length - 1].day !== day) days.push({ day: day, slots: [] });
        days[days.length - 1].slots.push(x);
      });
      pick = free.length
        ? (can ? '<div class="xsub">' + E.esc(t.slot_pick) + '</div>' : '') + days.map((d) =>
          '<div class="slot-day"><span class="sd">' + E.esc(d.day) + '</span><div class="opts">' + d.slots.map((x) =>
            '<button class="opt" data-action="slot" data-slot="' + E.esc(x.id) + '" data-msg="' + E.esc(item.id) + '"' + (can ? '' : ' disabled') + '>' +
            E.esc([E.time(x.start, locale), x.end ? E.time(x.end, locale) : ''].filter(Boolean).join('–')) + '</button>').join('') + '</div></div>').join('')
        : '<div class="empty">' + E.esc(t.slot_none) + '</div>';
    }
    return '<div class="xblock"><div class="xh"><ha-icon icon="mdi:calendar-clock"></ha-icon>' + E.esc(t.slots) + '</div>' + rows + pick + '</div>';
  }

  _threadBlock(item, t, data) {
    var E = window.Educartable;
    var locale = E.locale(this._hass);
    var open = !!this._threadOpen[item.id];
    var th = this._threads[item.id];
    var label = item.comments ? E.format(t.conversation_count, { n: item.comments }) : t.conversation;
    var head = '<button class="xh link-like" data-action="thread" data-msg="' + E.esc(item.id) + '" aria-expanded="' + open + '"><ha-icon icon="mdi:forum-outline"></ha-icon>' + E.esc(label) +
      '<ha-icon class="chevron' + (open ? '' : ' closed') + '" icon="mdi:chevron-down"></ha-icon></button>';
    if (!open) return '<div class="xblock">' + head + '</div>';
    var body;
    if (!th || th.loading) body = '<div class="empty">' + E.esc(t.loading) + '</div>';
    else if (th.error) body = '<div class="error-text">' + E.esc(th.error) + '</div>';
    else if (!th.comments.length) body = '<div class="empty">' + E.esc(t.conversation_empty) + '</div>';
    else {
      body = '<div class="thread">' + th.comments.map((c) =>
        '<div class="bubble' + (c.mine ? ' mine' : '') + (c.deleted ? ' deleted' : '') + '"><div class="bm">' + E.esc([c.mine ? t.me : c.author, c.date ? E.day(c.date, t, locale) : ''].filter(Boolean).join(' · ')) + '</div>' +
        (c.deleted ? '<div class="bt">' + E.esc(t.deleted) + '</div>' : c.text ? '<div class="bt">' + E.esc(c.text) + '</div>' : '') +
        E.rows.files(c.medias, t, data.entryId, true) + '</div>').join('') + '</div>';
    }
    var key = 'reply:' + item.id;
    var busy = th?.sending;
    var reply = '<div class="reply"><textarea data-draft="' + E.esc(key) + '" rows="2" aria-label="' + E.esc(t.reply_placeholder) + '" placeholder="' + E.esc(t.reply_placeholder) + '"' + (busy ? ' disabled' : '') + '>' + E.esc(this._typed[key] || '') + '</textarea>' +
      '<button class="act" data-action="reply-send" data-msg="' + E.esc(item.id) + '"' + (busy ? ' disabled' : '') + '>' + E.esc(busy ? t.sending : t.reply_send) + '</button></div>';
    return '<div class="xblock">' + head + body + reply + '</div>';
  }

  _loadThread(data, id) {
    var E = window.Educartable;
    var th = (this._threads[id] = Object.assign(this._threads[id] || {}, { loading: true, error: '' }));
    this._render();
    E.comments(this._hass, data.entryId, id)
      .then((comments) => {
        th.comments = comments;
      })
      .catch((err) => E.errorText(this._hass, err).then((text) => {
        th.error = text;
      }))
      .finally(() => {
        th.loading = false;
        this._render();
      });
  }

  _doReply(data, id) {
    var E = window.Educartable;
    var key = 'reply:' + id;
    var text = String(this._typed[key] || '').trim();
    var th = this._threads[id] || (this._threads[id] = { comments: [] });
    if (!text || th.sending) return;
    th.sending = true;
    this._error = '';
    this._render();
    E.reply(this._hass, data.entryId, id, text)
      .then(() => {
        delete this._typed[key];
        th.sending = false;
        this._loadThread(data, id);
      })
      .catch((err) => {
        th.sending = false;
        this._fail(err);
      });
  }

  _doSurvey(data, id) {
    var E = window.Educartable;
    var t = E.t(this._hass);
    var item = data.words.concat(data.news).find((x) => String(x.id) === id);
    if (!item?.survey) return;
    var kids = this._concerned(item, data);
    var answered = kids.filter((ch) => item.survey.answers[String(ch.id)]);
    var picks = this._picks[id] || (answered[0] ? item.survey.answers[String(answered[0].id)] : {});
    if (item.survey.questions.some((q) => !(picks[q.id] || []).length)) {
      this._error = t.survey_incomplete;
      this._render();
      return;
    }
    this._error = '';
    E.answerSurvey(this._hass, data.entryId, id, picks)
      .then(() => {
        delete this._picks[id];
        delete this._editing[id];
        this._render();
      })
      .catch((err) => this._fail(err));
  }

  // A new message to the teacher, at the top of the Liaison book: the children (those whose teacher paused messages
  // cannot be picked), a subject and the text.
  _writePopup(t, data) {
    var E = window.Educartable;
    var w = this._write;
    var kids = this._children(data);
    var boxes = kids.map((ch) => {
      var id = String(ch.id);
      var paused = ch.writable === false;
      return '<label class="wchild' + (paused ? ' paused' : '') + '"><input type="checkbox" data-action="write-child" value="' + E.esc(id) + '"' + (w.children.indexOf(id) !== -1 ? ' checked' : '') + (paused ? ' disabled' : '') + '> ' +
        E.esc(ch.first_name || ch.name) + (paused ? ' <span class="qm">' + E.esc(t.write_paused) + '</span>' : '') + '</label>';
    }).join('');
    return '<div class="popup write"><div class="popup-title">' + E.esc(t.write_title) + '</div>' +
      '<div class="wkids" role="group" aria-label="' + E.esc(t.write_children) + '"><span class="signer-label">' + E.esc(t.write_children) + '</span>' + boxes + '</div>' +
      '<label class="signer-label wide">' + E.esc(t.write_subject) + '<input class="winput" type="text" maxlength="255" data-draft="write:title" value="' + E.esc(this._typed['write:title'] || '') + '"></label>' +
      '<label class="signer-label wide">' + E.esc(t.write_text) + '<textarea class="winput" rows="5" data-draft="write:text">' + E.esc(this._typed['write:text'] || '') + '</textarea></label>' +
      '<div class="popup-actions"><button class="act ghost" data-action="write-cancel">' + E.esc(t.cancel) + '</button>' +
      '<button class="act" data-action="write-send"' + (w.busy ? ' disabled' : '') + '>' + E.esc(w.busy ? t.sending : t.write_send) + '</button></div></div>';
  }

  _doWrite(data) {
    var E = window.Educartable;
    var t = E.t(this._hass);
    var w = this._write;
    var title = String(this._typed['write:title'] || '').trim();
    var text = String(this._typed['write:text'] || '').trim();
    if (!w || w.busy) return;
    if (!w.children.length || !title || !text) {
      this._error = t.write_incomplete;
      this._render();
      return;
    }
    w.busy = true;
    this._error = '';
    this._render();
    E.write(this._hass, data.entryId, w.children, title, text)
      .then(() => {
        this._write = null;
        delete this._typed['write:title'];
        delete this._typed['write:text'];
      })
      .catch((err) => {
        w.busy = false;
        this._fail(err);
      })
      .finally(() => this._render());
  }

  // Signing a liaison-book message: a confirmation at the top of the page with the signer's name (as the portal asks
  // for it), prefilled with the account's name.
  _popup(t, data) {
    var E = window.Educartable;
    if (this._write && this._tab === 'words') return this._writePopup(t, data);
    var c = this._confirm;
    if (c?.kind === 'book') return this._bookPopup(t, data);
    var w = !c ? null : c.kind === 'doc' ? data.documents.find((x) => x.id === c.id) : data.words.find((x) => String(x.id) === c.id);
    if (!w) return '';
    var doc = c.kind === 'doc';
    return '<div class="popup"><div class="popup-title">' + E.esc(doc ? t.doc_sign_title : t.sign_title) + '</div>' +
      '<div class="popup-text">' + E.esc(E.format(doc ? t.doc_sign_text : t.sign_text, { title: [w.title, doc ? w.year : ''].filter(Boolean).join(' ') || '—' })) + '</div>' +
      '<label class="signer-label">' + E.esc(t.signer) + '<input class="signer" type="text" autocomplete="name" value="' + E.esc(this._confirm.name) + '"></label>' +
      '<div class="popup-actions"><button class="act ghost" data-action="cancel">' + E.esc(t.cancel) + '</button>' +
      '<button class="act" data-action="confirm"' + (this._confirm.busy ? ' disabled' : '') + '>' + E.esc(this._confirm.busy ? t.signing : t.sign) + '</button></div></div>';
  }

  // Booking a slot: when it is, and for which child (a choice when several still wait for theirs).
  _bookPopup(t, data) {
    var E = window.Educartable;
    var c = this._confirm;
    var item = data.words.concat(data.news).find((x) => String(x.id) === c.msg);
    var slot = item?.slots?.find((x) => x.id === c.id);
    if (!slot) return '';
    var waiting = this._concerned(item, data).filter((ch) => !item.slots.some((x) => x.booked && x.child_id === String(ch.id)));
    if (!waiting.some((ch) => String(ch.id) === c.child)) c.child = waiting[0] ? String(waiting[0].id) : '';
    var who = waiting.length > 1
      ? '<label class="signer-label">' + E.esc(t.book_for) + '<select class="signer book-child">' + waiting.map((ch) =>
        '<option value="' + E.esc(ch.id) + '"' + (String(ch.id) === c.child ? ' selected' : '') + '>' + E.esc(ch.first_name) + '</option>').join('') + '</select></label>'
      : '';
    var name = waiting.find((ch) => String(ch.id) === c.child)?.first_name || '';
    return '<div class="popup"><div class="popup-title">' + E.esc(t.book_title) + '</div>' +
      '<div class="popup-text">' + E.esc([item.title, this._slotLabel(slot, t), slot.location, waiting.length > 1 ? '' : name].filter(Boolean).join(' · ')) + '</div>' + who +
      '<div class="popup-actions"><button class="act ghost" data-action="cancel">' + E.esc(t.cancel) + '</button>' +
      '<button class="act" data-action="confirm"' + (c.busy ? ' disabled' : '') + '>' + E.esc(c.busy ? t.sending : t.book) + '</button></div></div>';
  }

  _doBook(data) {
    var E = window.Educartable;
    var c = this._confirm;
    if (!c || c.busy) return;
    c.busy = true;
    this._error = '';
    this._render();
    E.book(this._hass, data.entryId, c.id, c.child)
      .catch((err) => this._fail(err))
      .finally(() => {
        this._confirm = null;
        this._render();
      });
  }

  _doSign(data) {
    var E = window.Educartable;
    var t = E.t(this._hass);
    if (this._confirm?.kind === 'book') {
      this._doBook(data);
      return;
    }
    var input = this._root.querySelector('.signer');
    if (input) this._confirm.name = input.value;
    var doc = this._confirm.kind === 'doc';
    var w = doc ? data.documents.find((x) => x.id === this._confirm.id) : data.words.find((x) => String(x.id) === this._confirm.id);
    if (!w || this._confirm.busy) return;
    if (String(this._confirm.name || '').trim().length < 3) {
      this._error = t.signer_short;
      this._render();
      return;
    }
    this._confirm.busy = true;
    this._error = '';
    this._render();
    (doc ? E.signDocument(this._hass, data.entryId, w.id, this._confirm.name.trim()) : E.sign(this._hass, data.entryId, w, this._confirm.name.trim()))
      .catch((err) => this._fail(err))
      .finally(() => {
        this._confirm = null;
        this._render();
      });
  }

  _fail(err) {
    var E = window.Educartable;
    E.errorText(this._hass, err).then((text) => {
      this._error = `${E.t(this._hass).action_failed} ${text}`;
      this._render();
    });
  }

  _renderSettings(content, t) {
    var E = window.Educartable;
    if (!this._settings) {
      this._settings = { loading: true };
      content.innerHTML = '<div class="page"><ha-circular-progress indeterminate></ha-circular-progress></div>';
      this._hass
        .callWS({ type: 'educartable/settings' })
        .then((res) => {
          this._settings = res;
          this._drafts = {};
          this._render();
        })
        .catch((err) => {
          this._settings = { error: String(err?.message || err) };
          this._render();
        });
      return;
    }
    if (this._settings.loading) return;
    if (this._settings.error) {
      content.innerHTML = '<div class="page"><div class="error-text">' + E.esc(this._settings.error) + '</div></div>';
      return;
    }
    var s = this._settings;
    if (!s.accounts.length) {
      content.innerHTML = '<div class="page"><div class="empty">' + E.esc(t.no_account) + '</div></div>';
      return;
    }
    // Home Assistant's own form, with the selectors of the options flow: same look and checks as everywhere else.
    content.innerHTML = '<div class="page">' + (s.admin ? '' : '<div class="empty">' + E.esc(t.admin_only) + '</div>') +
      s.accounts.map((acc) => this._box(acc.title,
        '<div class="form" data-entry="' + E.esc(acc.entry_id) + '"></div>' +
        (s.admin ? '<div class="popup-actions"><span class="msg"></span><button class="act" data-action="save" data-entry="' + E.esc(acc.entry_id) + '">' + E.esc(t.save) + '</button></div>' : ''),
        true)).join('') + '</div>';
    var labels = { scan_interval: t.settings_scan, homework_days: t.settings_days, notify_services: t.settings_notify, show_panel: t.settings_panel, panel_tabs: t.settings_tabs, hide_header: t.settings_hide_header };
    var helpers = { scan_interval: t.settings_scan_hint, notify_services: t.settings_notify_hint, hide_header: t.settings_hide_header_hint };
    s.accounts.forEach((acc) => {
      var form = document.createElement('ha-form');
      var notify = s.notify_services.concat((acc.options.notify_services || []).filter((n) => s.notify_services.indexOf(n) === -1));
      form.hass = this._hass;
      form.disabled = !s.admin;
      form.schema = [
        { name: 'scan_interval', selector: { number: { min: 10, max: 360, step: 5, mode: 'box', unit_of_measurement: 'min' } } },
        { name: 'homework_days', selector: { number: { min: 1, max: 60, step: 1, mode: 'box', unit_of_measurement: 'd' } } },
        { name: 'notify_services', selector: { select: { multiple: true, custom_value: true, mode: 'dropdown', options: notify } } },
        { name: 'show_panel', selector: { boolean: {} } },
        {
          name: 'panel_tabs',
          selector: {
            select: {
              multiple: true,
              mode: 'list',
              options: ['homework', 'words', 'news', 'documents'].map((tab) => ({ value: tab, label: t[EDUCARTABLE_TAB_KEYS[tab]] })),
            },
          },
        },
        {
          name: 'hide_header',
          selector: { select: { mode: 'list', options: ['off', 'all', 'non_admin'].map((v) => ({ value: v, label: t['hide_header_' + v] })) } },
        },
      ];
      form.data = this._drafts[acc.entry_id] || acc.options;
      form.computeLabel = (field) => labels[field.name] || field.name;
      form.computeHelper = (field) => helpers[field.name] || '';
      form.addEventListener('value-changed', (ev) => {
        this._drafts[acc.entry_id] = ev.detail.value;
        form.data = ev.detail.value;
      });
      content.querySelector(`.form[data-entry="${CSS.escape(acc.entry_id)}"]`).appendChild(form);
    });
  }

  _save(button) {
    var E = window.Educartable;
    var t = E.t(this._hass);
    var entry = button.getAttribute('data-entry');
    var acc = this._settings.accounts.find((a) => a.entry_id === entry);
    var options = Object.assign({}, acc.options, this._drafts[entry] || {});
    var msg = button.parentElement.querySelector('.msg');
    this._hass
      .callWS({
        type: 'educartable/settings/update',
        entry_id: entry,
        options: {
          scan_interval: Number(options.scan_interval),
          homework_days: Number(options.homework_days),
          notify_services: options.notify_services || [],
          show_panel: !!options.show_panel,
          panel_tabs: options.panel_tabs || [],
          hide_header: options.hide_header || 'off',
        },
      })
      .then((res) => {
        acc.options = res.options;
        delete this._drafts[entry];
        msg.className = 'msg ok';
        msg.textContent = t.saved;
      })
      .catch((err) => {
        msg.className = 'msg error-text';
        msg.textContent = String(err?.message || err);
      });
  }

  _onChange(ev) {
    var el = ev.target;
    if (el.classList?.contains('account')) {
      this._entry = el.value;
      this._render();
    } else if (el.classList?.contains('book-child') && this._confirm) {
      this._confirm.child = el.value;
    } else if (el.getAttribute?.('data-action') === 'write-child' && this._write) {
      var picked = this._write.children.filter((id) => id !== el.value);
      if (el.checked) picked.push(el.value);
      this._write.children = picked;
    } else if (el.getAttribute?.('data-action') === 'hide-done') {
      this._hideDone = el.checked;
      this._saveFilters();
      this._render();
    }
  }

  _onClick(ev) {
    var E = window.Educartable;
    var toggle = ev.target.closest('[data-toggle]');
    if (toggle && !ev.target.closest('[data-action], a, .extras')) {
      var key = toggle.getAttribute('data-toggle');
      if (this._open[key]) delete this._open[key];
      else this._open[key] = true;
      this._render();
      return;
    }
    var childEl = ev.target.closest('[data-child]:not([data-action])');
    if (childEl) {
      this._child = childEl.getAttribute('data-child');
      this._saveFilters();
      this._render();
      return;
    }
    var dayEl = ev.target.closest('[data-day]');
    if (dayEl) {
      var picked = dayEl.getAttribute('data-day');
      this._day = this._day === picked ? '' : picked;
      this._render();
      return;
    }
    var tabEl = ev.target.closest('[data-tab]');
    if (tabEl) {
      this._setTab(tabEl.getAttribute('data-tab'));
      return;
    }
    var el = ev.target.closest('[data-action]');
    if (!el) return;
    var data = this._data;
    var action = el.getAttribute('data-action');
    if (action === 'save') {
      ev.preventDefault();
      this._save(el);
    } else if (!data) {
      return;
    } else if (action === 'refresh') this._refresh(data);
    else if (action === 'open') window.open(data.url, '_blank', 'noopener');
    else if (action === 'sign' && E.canAct(this._hass)) {
      this._confirm = { id: el.getAttribute('data-id'), name: data.account.name || '' };
      this._render();
      this._root.querySelector('.popup')?.scrollIntoView?.({ block: 'nearest' });
      this._root.querySelector('.signer')?.focus?.({ preventScroll: true });
    } else if (action === 'cancel') {
      this._confirm = null;
      this._render();
    } else if (action === 'confirm') this._doSign(data);
    else if (action === 'read') {
      var w = data.words.find((x) => String(x.id) === el.getAttribute('data-id'));
      if (w && E.canAct(this._hass)) E.markRead(this._hass, data.entryId, w).catch((err) => this._fail(err));
    } else if (action === 'homework') {
      var item = data.homework.find((h) => String(h.id) === el.getAttribute('data-id') && String(h.child_id) === el.getAttribute('data-child'));
      if (item && E.canAct(this._hass)) E.setDone(this._hass, data.entryId, item, !item.done).catch((err) => this._fail(err));
    } else if (action === 'file') E.openFile(this._hass, data.entryId, { id: el.getAttribute('data-media'), name: el.getAttribute('data-name') }).catch((err) => this._fail(err));
    else if (action === 'doc-file') E.openFile(this._hass, data.entryId, { document: el.getAttribute('data-doc'), name: el.getAttribute('data-name') }).catch((err) => this._fail(err));
    else if (!E.canAct(this._hass)) return;
    else if (action === 'doc-sign') {
      this._confirm = { kind: 'doc', id: el.getAttribute('data-id'), name: data.account.name || '' };
      this._render();
      this._root.querySelector('.popup')?.scrollIntoView?.({ block: 'nearest' });
      this._root.querySelector('.signer')?.focus?.({ preventScroll: true });
    } else if (action === 'slot') {
      this._confirm = { kind: 'book', id: el.getAttribute('data-slot'), msg: el.getAttribute('data-msg'), child: '' };
      this._render();
      this._root.querySelector('.popup')?.scrollIntoView?.({ block: 'nearest' });
    } else if (action === 'slot-cancel') E.cancelBooking(this._hass, data.entryId, el.getAttribute('data-slot')).catch((err) => this._fail(err));
    else if (action === 'survey-opt') this._pick(data, el.getAttribute('data-msg'), el.getAttribute('data-q'), el.getAttribute('data-o'));
    else if (action === 'survey-send') this._doSurvey(data, el.getAttribute('data-msg'));
    else if (action === 'survey-change') {
      this._editing[el.getAttribute('data-msg')] = true;
      this._render();
    } else if (action === 'thread') {
      var id = el.getAttribute('data-msg');
      this._threadOpen[id] = !this._threadOpen[id];
      if (this._threadOpen[id] && !this._threads[id]?.comments) this._loadThread(data, id);
      else this._render();
    } else if (action === 'reply-send') this._doReply(data, el.getAttribute('data-msg'));
    else if (action === 'write') {
      this._write = { children: this._children(data).filter((ch) => ch.writable !== false).slice(0, 1).map((ch) => String(ch.id)), busy: false };
      this._render();
      this._root.querySelector('.winput')?.focus?.({ preventScroll: true });
    } else if (action === 'write-cancel') {
      this._write = null;
      this._render();
    } else if (action === 'write-send') this._doWrite(data);
  }

  // A survey option clicked: the only one of its question, or one more (or less) when several are allowed.
  _pick(data, id, qid, oid) {
    var item = data.words.concat(data.news).find((x) => String(x.id) === id);
    var q = item?.survey?.questions.find((x) => x.id === qid);
    if (!q) return;
    var kids = this._concerned(item, data);
    var answered = kids.find((ch) => item.survey.answers[String(ch.id)]);
    var picks = this._picks[id] || JSON.parse(JSON.stringify(answered ? item.survey.answers[String(answered.id)] : {}));
    var now = picks[qid] || [];
    picks[qid] = q.multiple ? (now.indexOf(oid) === -1 ? now.concat([oid]) : now.filter((x) => x !== oid)) : [oid];
    this._picks[id] = picks;
    this._render();
  }

  _refresh(data) {
    var E = window.Educartable;
    if (this._refreshing) return;
    this._refreshing = true;
    this._error = '';
    this._render();
    E.refresh(this._hass, data.entryId)
      .catch((err) =>
        E.errorText(this._hass, err).then((text) => {
          this._error = `${E.t(this._hass).refresh_failed} ${text}`;
        }),
      )
      .finally(() => {
        this._refreshing = false;
        this._render();
      });
  }

  static _styles(A) {
    return [
      ':host { display: block; min-height: 100vh; background: var(--primary-background-color); color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, inherit); }',
      // Illustrated header (the card's banner, see window.Educartable.banner.styles), across the page.
      // The round buttons at the right edge, as on the other ha-* panels; the school corner just left of them.
      '.banner { margin: 0; --eo-scene-w: min(260px, 38%); --eo-btns: 0px; }',
      '.banner:has(.hbtns .hbtn) { --eo-btns: 54px; }',
      '.banner:has(.hbtns .hbtn + .hbtn) { --eo-btns: 94px; }',
      '.banner .eo-scene { right: var(--eo-btns); }',
      '.scene { display: contents; }',
      '.htext { left: 8px; right: calc(var(--eo-scene-w) + var(--eo-btns) + 16px); top: 0; gap: 8px; }',
      '.hinfo { display: flex; align-items: center; gap: 16px; min-width: 0; }',
      'ha-menu-button { flex: none; color: var(--eo-text); }',
      '.banner .logo { width: 44px; height: 44px; flex: none; border-radius: 50%; display: grid; place-items: center; margin-left: 4px; }',
      '.banner .logo > svg { width: 26px; height: 26px; }',
      '.titles { min-width: 0; }',
      '.title-row { display: flex; align-items: center; gap: 8px; min-width: 0; }',
      '.name { font-size: 20px; font-weight: 500; line-height: 1.25; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }',
      '.sub { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }',
      '.status { --c: var(--success-color, #43a047); flex: none; display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 500; line-height: 16px; white-space: nowrap; border-radius: 12px; padding: 1px 8px; }',
      '.status .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--c); }',
      '.banner .status.warn { --c: var(--warning-color, #ffa600); } .banner .status.bad { --c: var(--error-color, #db4437); }',
      // Glass round buttons at the right edge, centred on the sky (the card's glass, at the panels' 34 px)
      '.hbtns { top: calc((100% - var(--eo-g)) / 2 - 17px); right: 12px; gap: 6px; }',
      '.hbtn { all: unset; box-sizing: border-box; cursor: pointer; display: grid; place-items: center; --mdc-icon-size: 20px; }',
      '.hbtns .hbtn { width: 34px; height: 34px; }',
      '.hbtns .hbtn:hover { background: rgba(255,255,255,.82); }',
      '.night .hbtns .hbtn:hover { background: rgba(255,255,255,.22); }',
      '.hbtn ha-icon { display: flex; }',
      '.hbtn:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }',
      '.spinning ha-icon { animation: educartable-spin 1s linear infinite; }',
      '@keyframes educartable-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }',
      // Text tabs under the header, the active one underlined; the account choice at their right.
      // Top bar hidden: the tabs alone, the menu button at their left (shown by Home Assistant on a narrow screen).
      ':host([bare]) .banner { display: none; }',
      '.tabbar ha-menu-button { flex: none; margin-left: -8px; color: var(--primary-text-color); }',
      '.tb-side { display: flex; align-items: center; gap: 4px; }',
      '.tb-side .hbtn { width: 36px; height: 36px; border-radius: 50%; color: var(--secondary-text-color); }',
      '.tb-side .hbtn:hover { background: color-mix(in srgb, var(--secondary-text-color) 14%, transparent); color: var(--primary-text-color); }',
      // The page's own background: the theme's header colour (blue in the default light theme) would put grey tab text on blue.
      '.tabbar { display: flex; align-items: center; gap: 8px; padding: 0 12px; border-bottom: 1px solid var(--divider-color, rgba(0,0,0,.12)); background: var(--primary-background-color); position: sticky; top: 0; z-index: 2; }',
      '.tabs { flex: 1; min-width: 0; display: flex; gap: 4px; overflow-x: auto; }',
      '.tb-side { flex: none; }',
      '.account { font: inherit; font-size: 13px; padding: 4px 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }',
      '.tab { all: unset; cursor: pointer; padding: 12px 10px 10px; font-size: 14px; font-weight: 500; white-space: nowrap; color: var(--secondary-text-color); border-bottom: 2px solid transparent; }',
      '.tab.on { color: var(--primary-text-color); border-bottom-color: ' + A + '; }',
      '.tab:focus-visible { outline: 2px solid var(--primary-color); outline-offset: -2px; }',
      '.badge { display: inline-block; min-width: 18px; padding: 1px 5px; margin-left: 4px; border-radius: 9px; font-size: 11px; text-align: center; box-sizing: border-box;' +
        ' color: color-mix(in srgb, ' + A + ' 60%, var(--primary-text-color)); background: color-mix(in srgb, ' + A + ' 16%, transparent); }',
      '.page { max-width: 1100px; margin: 0 auto; padding: 16px; display: flex; flex-direction: column; gap: 14px; }',
      '.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; align-items: start; }',
      '.box { background: var(--card-background-color, #fff); border-radius: var(--ha-card-border-radius, 12px); border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, #e0e0e0)); padding: 12px 16px; min-width: 0; }',
      '.box h2 { margin: 0 0 6px; font-size: 14px; font-weight: 500; color: var(--secondary-text-color); }',
      '.box h3 { margin: 12px 0 2px; font-size: 13px; font-weight: 500; color: var(--secondary-text-color); }',
      '.box h3:first-child { margin-top: 0; }',
      '.bh { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }',
      '.see { all: unset; cursor: pointer; font-size: 12px; color: var(--secondary-text-color); }',
      '.see:hover { color: var(--primary-text-color); } .see:focus-visible { outline: 2px solid var(--primary-color); }',
      // Child filter: All, then a chip per child with its initial.
      '.kids { display: flex; flex-wrap: wrap; gap: 8px; }',
      '.kid { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 8px; min-height: 32px; padding: 0 12px; border-radius: 18px; font-size: 13px;' +
        ' color: var(--secondary-text-color); background: var(--card-background-color, #fff); border: 1px solid var(--divider-color, #e0e0e0); box-sizing: border-box; }',
      '.kid:has(.avatar) { padding-left: 3px; }',
      '.kid.on { color: var(--primary-text-color); border: 1.5px solid ' + A + '; }',
      '.kid:focus-visible { outline: 2px solid var(--primary-color); }',
      '.kid .badge { margin-left: 0; }',
      '.avatar { --c: ' + A + '; width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; font-size: 12px; font-weight: 500;' +
        ' color: color-mix(in srgb, var(--c) 60%, var(--primary-text-color)); background: color-mix(in srgb, var(--c) 18%, transparent); }',
      '.avatar.c1 { --c: #8e6bd8; } .avatar.c2 { --c: #1d9e75; } .avatar.c3 { --c: #2f80ed; }',
      // Week strip: Monday to Friday, homework left in amber, a dot for an event, today outlined.
      '.week { display: flex; gap: 6px; }',
      '.wday { all: unset; cursor: pointer; flex: 1; min-width: 0; position: relative; display: flex; align-items: center; justify-content: center; gap: 6px; padding: 7px 4px; border-radius: 10px;' +
        ' font-size: 12px; color: var(--secondary-text-color); background: var(--card-background-color, #fff); border: 1px solid var(--divider-color, #e0e0e0); box-sizing: border-box; }',
      '.wday .wl { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
      '.wday.past { opacity: .6; }',
      '.wday.today { color: var(--primary-text-color); border: 1.5px solid ' + A + '; }',
      '.wday.hw { --c: #f5a623; color: color-mix(in srgb, var(--c) 55%, var(--primary-text-color)); background: color-mix(in srgb, var(--c) 14%, var(--card-background-color, #fff)); }',
      '.wday .wn { font-weight: 500; }',
      '.wday.on { box-shadow: 0 0 0 2px ' + A + '; }',
      '.wday:focus-visible { outline: 2px solid var(--primary-color); }',
      // Tiles of the chart: neutral surface, round tinted pastille with the count as badge, name + coloured state line.
      '.tiles { display: grid; gap: 12px; }',
      '.tile { all: unset; box-sizing: border-box; cursor: pointer; display: flex; align-items: center; gap: 12px; min-width: 0; padding: 12px 14px; border-radius: 12px;' +
        ' background: var(--card-background-color, #fff); border: 1px solid var(--divider-color, #e0e0e0); --c: #8a96a3; }',
      '.tile:not(.static):hover { border-color: color-mix(in srgb, var(--c) 55%, var(--divider-color, #e0e0e0)); }',
      '.tile:focus-visible { outline: 2px solid var(--primary-color); }',
      '.tile.static { cursor: default; }',
      '.tile.red { --c: var(--error-color, #e5484d); } .tile.amber { --c: #f5a623; } .tile.blue { --c: #2f80ed; } .tile.violet { --c: #8e6bd8; }',
      '.pastille { position: relative; flex: none; width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; --mdc-icon-size: 22px;' +
        ' color: var(--c); background: color-mix(in srgb, var(--c) 16%, transparent); }',
      '.pbadge { position: absolute; top: -3px; right: -5px; min-width: 18px; height: 18px; padding: 0 4px; box-sizing: border-box; border-radius: 9px; font-size: 11px; font-weight: 600;' +
        ' line-height: 18px; text-align: center; color: #fff; background: var(--c); box-shadow: 0 0 0 2px var(--card-background-color, #fff); }',
      '.tl { display: flex; flex-direction: column; min-width: 0; }',
      '.tn { font-size: 14px; font-weight: 500; color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
      '.ts { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: color-mix(in srgb, var(--c) 65%, var(--primary-text-color)); }',
      '.tile.rest .ts { color: var(--secondary-text-color); }',
      // Home: To do (two columns wide) and To read, the calendar under them.
      '.dgrid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; align-items: start; }',
      '.dgrid .todo-box { grid-column: span 2; } .dgrid .agenda-box { grid-column: 1 / -1; }',
      // Homework: one tile per day, its progress under the title.
      '.days { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; align-items: start; }',
      '.ratio { font-size: 12px; font-weight: 500; color: color-mix(in srgb, #f5a623 60%, var(--primary-text-color)); }',
      '.day.full .ratio { color: color-mix(in srgb, var(--success-color, #43a047) 60%, var(--primary-text-color)); }',
      '.bar { height: 4px; border-radius: 2px; margin: 2px 0 6px; background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); overflow: hidden; }',
      '.bar span { display: block; height: 100%; border-radius: 2px; background: #f5a623; }',
      '.day.full .bar span { background: var(--success-color, #43a047); }',
      '.filters { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }',
      '.filter { all: unset; cursor: pointer; font-size: 13px; padding: 4px 12px; border-radius: 14px; border: 1px solid var(--divider-color, #e0e0e0); color: var(--secondary-text-color); }',
      '.filter.on { color: color-mix(in srgb, ' + A + ' 60%, var(--primary-text-color)); border-color: color-mix(in srgb, ' + A + ' 50%, transparent); background: color-mix(in srgb, ' + A + ' 10%, transparent); }',
      '.toggle { margin-left: auto; font-size: 13px; color: var(--secondary-text-color); display: flex; align-items: center; gap: 6px; }',
      '.item-title { white-space: normal; }',
      '.popup { padding: 12px 16px; border-radius: 12px; border: 1px solid color-mix(in srgb, ' + A + ' 40%, transparent); background: color-mix(in srgb, ' + A + ' 6%, var(--card-background-color, #fff)); }',
      '.popup-title { font-weight: 500; }',
      '.popup-text { font-size: 13px; color: var(--secondary-text-color); margin-top: 2px; }',
      '.signer-label { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; font-size: 12px; color: var(--secondary-text-color); max-width: 360px; }',
      '.signer { font: inherit; font-size: 14px; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--divider-color, rgba(0,0,0,.2)); background: var(--card-background-color, #fff); color: var(--primary-text-color); }',
      // Settings: the Save button, outlined (never filled), its message at its left.
      '.popup-actions { display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-top: 8px; }',
      '.errbar { padding: 8px 12px; border-radius: 8px; background: color-mix(in srgb, var(--error-color, #db4437) 10%, transparent); }',
      '.msg { font-size: 13px; margin-right: auto; }',
      // New message: its button above the liaison book; the form in the popup.
      '.toolbar { display: flex; justify-content: flex-end; }',
      '.toolbar .act, .act:has(ha-icon) { display: inline-flex; align-items: center; gap: 6px; --mdc-icon-size: 16px; }',
      '.wkids { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; margin-top: 8px; }',
      '.wkids .signer-label { margin: 0; flex-basis: 100%; max-width: none; }',
      '.wchild { font-size: 13px; display: inline-flex; align-items: center; gap: 4px; }',
      '.wchild.paused { color: var(--secondary-text-color); }',
      '.signer-label.wide { max-width: none; }',
      '.winput:focus-visible, .reply textarea:focus-visible, .signer:focus-visible { outline: 2px solid ' + A + '; outline-offset: 0; border-color: transparent; }',
      '.winput, .reply textarea { font: inherit; font-size: 14px; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--divider-color, rgba(0,0,0,.2)); background: var(--card-background-color, #fff); color: var(--primary-text-color); resize: vertical; }',
      // Survey, appointment slots and conversation under an unfolded message.
      '.extras { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }',
      '.xblock { border-radius: 10px; padding: 8px 12px; background: color-mix(in srgb, var(--primary-text-color) 4%, transparent); display: flex; flex-direction: column; gap: 6px; }',
      '.xh { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; color: var(--primary-text-color); --mdc-icon-size: 18px; }',
      '.xh > ha-icon:first-child { color: ' + A + '; }',
      '.xh .chevron { margin: 0 0 0 auto; }',
      '.link-like { all: unset; cursor: pointer; display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 500; --mdc-icon-size: 18px; }',
      '.link-like:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; border-radius: 4px; }',
      '.xmeta, .xsub { font-size: 12px; font-weight: 400; color: var(--secondary-text-color); }',
      '.xmeta { margin-left: auto; }',
      '.q { display: flex; flex-direction: column; gap: 4px; }',
      '.ql { font-size: 13px; }',
      '.qm { font-size: 11px; color: var(--secondary-text-color); }',
      '.opts { display: flex; flex-wrap: wrap; gap: 6px; }',
      '.opt { all: unset; cursor: pointer; font-size: 12px; padding: 4px 12px; border-radius: 14px; border: 1px solid var(--divider-color, rgba(0,0,0,.2)); color: var(--primary-text-color); background: var(--card-background-color, #fff); }',
      '.opt:hover:not(:disabled) { border-color: color-mix(in srgb, ' + A + ' 50%, transparent); }',
      '.opt.on { color: color-mix(in srgb, ' + A + ' 60%, var(--primary-text-color)); border-color: ' + A + '; background: color-mix(in srgb, ' + A + ' 12%, var(--card-background-color, #fff)); }',
      '.opt:disabled { cursor: default; opacity: .7; }',
      '.opt:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }',
      '.xfoot { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }',
      '.xfoot .chip { margin-right: auto; }',
      '.slot-day { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }',
      '.sd { flex: none; min-width: 110px; font-size: 12px; font-weight: 500; color: var(--secondary-text-color); }',
      '.booked { display: flex; align-items: center; gap: 6px; font-size: 13px; --mdc-icon-size: 18px; }',
      '.booked > ha-icon { color: var(--success-color, #43a047); flex: none; }',
      '.booked span { flex: 1; min-width: 0; }',
      '.thread { display: flex; flex-direction: column; gap: 6px; max-height: 360px; overflow-y: auto; }',
      '.bubble { max-width: 85%; align-self: flex-start; padding: 6px 10px; border-radius: 12px 12px 12px 4px; background: var(--card-background-color, #fff); border: 1px solid var(--divider-color, rgba(0,0,0,.12)); }',
      '.bubble.mine { align-self: flex-end; border-radius: 12px 12px 4px 12px; background: color-mix(in srgb, ' + A + ' 12%, var(--card-background-color, #fff)); border-color: color-mix(in srgb, ' + A + ' 30%, transparent); }',
      '.bubble.deleted .bt { font-style: italic; color: var(--secondary-text-color); }',
      '.bm { font-size: 11px; color: var(--secondary-text-color); }',
      '.bt { font-size: 13px; white-space: pre-line; overflow-wrap: anywhere; }',
      '.reply { display: flex; gap: 8px; align-items: flex-end; }',
      '.reply textarea { flex: 1; min-width: 0; }',
      '.msg.ok { color: color-mix(in srgb, var(--success-color, #43a047) 55%, var(--primary-text-color)); }',
      '@media (max-width: 900px) { .dgrid { grid-template-columns: 1fr; } .dgrid .todo-box { grid-column: auto; } .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; } }',
      '@media (max-width: 600px) { .page { padding: 12px; } .banner { --eo-scene-w: 0px; } .eo-scene { display: none; } .htext { right: calc(var(--eo-btns) + 12px); } .name { font-size: 17px; }' +
        ' .hbtns { right: 12px; } .status { display: none; } .wday .wl { font-size: 11px; } .week { gap: 4px; } }',
      '@media (prefers-reduced-motion: reduce) { .spinning ha-icon { animation: none; opacity: .5; } }',
    ].join('\n');
  }
}

if (!customElements.get('educartable-panel')) customElements.define('educartable-panel', EducartablePanel);
