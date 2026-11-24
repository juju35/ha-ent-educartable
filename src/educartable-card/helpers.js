// ── helpers (shared with the panel through window.Educartable) ─────────────────────
import { EDUCARTABLE_CARD_VERSION } from "./card-picker.js";
import { EDUCARTABLE_ACCENT, EDUCARTABLE_ICON } from "./header-icon.js";
import { EducartableI18n } from "./i18n/strings.js";

export function educartableEsc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

export function educartableFormat(text, values) {
  return String(text || '').replace(/\{(\w+)\}/g, (m, k) => (values && values[k] != null ? values[k] : m));
}

// The card's `language` option wins over the Home Assistant language; a full code the card knows (sr-Latn) is
// kept, else its base (fr-FR gives fr), else English.
export function educartableLang(hass, config) {
  var lang = String(config?.language || (hass && (hass.locale?.language || hass.language)) || navigator.language || 'en');
  if (EducartableI18n[lang]) return lang;
  lang = lang.split('-')[0];
  return EducartableI18n[lang] ? lang : 'en';
}

// Locale for Intl: plain "pt" is European Portuguese in Home Assistant but Brazilian in Intl.
export function educartableLocale(hass, config) {
  var lang = educartableLang(hass, config);
  var full = String(config?.language || (hass && (hass.locale?.language || hass.language)) || '');
  var sameScript = /-Latn\b/i.test(full) === /-Latn\b/i.test(lang);
  var locale = full && full.split('-')[0] === lang.split('-')[0] && sameScript ? full : lang;
  return locale === 'pt' ? 'pt-PT' : locale;
}

// English key by key until the language file is loaded (the split leaves `{}` in its place).
export function educartableT(hass, config) {
  return Object.assign({}, EducartableI18n.en, EducartableI18n[educartableLang(hass, config)]);
}

// False while the release's language file is still on its way (its table is still empty): reading the table
// starts the download, and the caller draws again a moment later.
export function educartableLangReady(hass, config) {
  var lang = educartableLang(hass, config);
  return lang === 'en' || Object.keys(EducartableI18n[lang] || {}).length > 0;
}

export function educartableErrorText(hass, err) {
  var fallback = String(err?.message || err || '').replace(/^Validation error: /, '');
  var key = err?.translation_key;
  if (!key || err.translation_domain !== 'educartable' || typeof hass?.loadBackendTranslation !== 'function') {
    return Promise.resolve(fallback);
  }
  return Promise.resolve(hass.loadBackendTranslation('exceptions', 'educartable'))
    .then((localize) => (localize || hass.localize)(`component.educartable.exceptions.${key}.message`, err.translation_placeholders || {}) || fallback)
    .catch(() => fallback);
}

// The Educartable portal, opened by the header button (the browser keeps its own session there).
export var EDUCARTABLE_URL = 'https://app.educartable.com';

// Sensors of the integration. Home Assistant updates hass several times a second: scanning every state each time
// cost a lot on large installations, so the ids are taken from the entity registry, read again only when it
// changes (a new object). Without a registry (tests, screenshots), every sensor is looked at.
export var educartableIdCache = { entities: null, ids: null };

export function educartableSensorIds(hass) {
  var entities = hass?.entities;
  if (!entities || !Object.keys(entities).length) return Object.keys(hass?.states || {}).filter((id) => id.indexOf('sensor.') === 0);
  if (educartableIdCache.entities !== entities) {
    educartableIdCache.entities = entities;
    educartableIdCache.ids = Object.keys(entities).filter((id) => id.indexOf('sensor.') === 0 && entities[id].platform === 'educartable');
  }
  return educartableIdCache.ids;
}

// The Educartable accounts found in the states: each sensor carries config_entry_id and its own attribute — the
// liaison book (`messages`), the news (`news`), one homework sensor per child (`homework`) and the last update
// (`children`, with the account's options).
export function educartableAccounts(hass) {
  var accounts = {};
  var states = hass?.states || {};
  educartableSensorIds(hass).forEach((id) => {
    var st = states[id];
    var at = st?.attributes;
    var entry = at?.config_entry_id;
    if (!entry) return;
    var acc = (accounts[entry] = accounts[entry] || { entryId: entry, homework: [] });
    if ('children' in at) acc.last = st;
    else if ('homework' in at) acc.homework.push(st);
    else if ('news' in at) acc.news = st;
    else if ('messages' in at) acc.carnet = st;
  });
  Object.keys(accounts).forEach((k) => {
    accounts[k].homework.sort((x, y) => String(x.entity_id).localeCompare(String(y.entity_id)));
  });
  return accounts;
}

export function educartableData(hass, entryId) {
  var accounts = educartableAccounts(hass);
  var acc = entryId ? accounts[entryId] : accounts[Object.keys(accounts)[0]];
  if (!acc) return null;
  var a = (st, key) => (st && Array.isArray(st.attributes?.[key]) ? st.attributes[key] : []);
  var down = (st) => !st || st.state === 'unavailable' || st.state === 'unknown';
  var last = acc.last;
  var stale = [];
  [acc.carnet, acc.news, last].forEach((st) => {
    (st?.attributes?.stale || []).forEach((s) => {
      if (stale.indexOf(s) === -1) stale.push(s);
    });
  });
  // One list for the family: each homework knows its child, and its due date as `date`.
  var homework = [];
  acc.homework.forEach((st) => {
    if (down(st)) return;
    a(st, 'homework').forEach((h) => {
      homework.push(Object.assign({}, h, { date: h.due || '', child: st.attributes.child || '', child_id: String(st.attributes.child_id || '') }));
    });
  });
  return {
    entryId: acc.entryId,
    unavailable: down(acc.carnet) && down(acc.news) && acc.homework.every(down),
    // The liaison book: `signed` once every recipient has signed it.
    words: a(acc.carnet, 'messages').map((m) => Object.assign({}, m, { signed: !m.to_sign })),
    homework: homework,
    news: a(acc.news, 'news'),
    children: a(last, 'children').map((ch) => Object.assign({}, ch, { first_name: ch.firstname || ch.name || '' })),
    account: last?.attributes?.account || {},
    url: EDUCARTABLE_URL,
    // Tabs of the panel shown (integration option); all of them before the option exists.
    panelTabs: Array.isArray(last?.attributes?.panel_tabs) ? last.attributes.panel_tabs : ['homework', 'words', 'news'],
    // Who the panel's top bar is hidden for (integration option): off, all or non_admin.
    hideHeader: last?.attributes?.hide_header || 'off',
    updated: last && !down(last) ? last.state : null,
    stale: stale,
    states: [acc.carnet, acc.news, last].concat(acc.homework),
  };
}

// True when one of the account's sensors is not the one drawn last time (a new state object, or a child more or less).
export function educartableChanged(key, last) {
  if (!key || !last) return key !== last;
  return key.length !== last.length || key.some((st, i) => st !== last[i]);
}

// "YYYY-MM-DD" is read as UTC midnight by Date.parse: give a date alone a local midnight.
export function educartableParse(raw) {
  var s = String(raw || '').trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) s += 'T00:00:00';
  return new Date(s);
}

export function educartableDayDiff(raw) {
  var d = educartableParse(raw);
  if (Number.isNaN(d.getTime())) return null;
  var a = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  var now = new Date();
  var b = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((a - b) / 86400000);
}

// Today / Tomorrow / Yesterday, else the short weekday within a week, else the date.
export function educartableDay(raw, t, locale) {
  var diff = educartableDayDiff(raw);
  if (diff === null) return '';
  if (diff === 0) return t.today;
  if (diff === 1) return t.tomorrow;
  if (diff === -1) return t.yesterday;
  var d = educartableParse(raw);
  // Within a week the weekday is enough; further away the weekday stays, with the date (Thu 26 Nov).
  var opts = Math.abs(diff) < 7 ? { weekday: 'long' } : { weekday: 'short', day: 'numeric', month: 'short' };
  try {
    return d.toLocaleDateString(locale, opts);
  } catch (_e) {
    return d.toLocaleDateString('en', opts);
  }
}

// "for today", "for tomorrow", else "for" and the day.
export function educartableDue(raw, t, locale) {
  var diff = educartableDayDiff(raw);
  if (diff === 0) return t.due_today;
  if (diff === 1) return t.due_tomorrow;
  return educartableFormat(t.due, { day: educartableDay(raw, t, locale) });
}

// The time format of the user's Home Assistant profile: '12', '24', or the language's ('language' / 'system').
export var educartableHour12;

export function educartableSetTimeFormat(hass) {
  var f = hass?.locale?.time_format;
  educartableHour12 = f === '12' ? true : f === '24' ? false : undefined;
}

export function educartableTime(raw, locale) {
  var d = educartableParse(raw);
  if (Number.isNaN(d.getTime())) return '';
  var opts = { hour: '2-digit', minute: '2-digit' };
  if (educartableHour12 !== undefined) opts.hour12 = educartableHour12;
  try {
    return d.toLocaleTimeString(locale, opts);
  } catch (_e) {
    return d.toLocaleTimeString('en', opts);
  }
}

export function educartableRefresh(hass, entryId) {
  return hass.callService('educartable', 'refresh', { config_entry_id: entryId });
}

// Signing, marking read, ticking homework and fetching attachments act on the portal with the parent's account:
// administrators only (a child's Home Assistant account must not sign their own liaison book). True while unknown.
export function educartableCanAct(hass) {
  return hass?.user?.is_admin !== false;
}

export function educartableSign(hass, entryId, message, name) {
  return hass.callService('educartable', 'sign', { config_entry_id: entryId, message_id: String(message.id), name: String(name || '') });
}

export function educartableMarkRead(hass, entryId, message) {
  return hass.callService('educartable', 'mark_read', { config_entry_id: entryId, message_id: String(message.id) });
}

export function educartableSetDone(hass, entryId, item, done) {
  return hass.callWS({ type: 'educartable/homework_done', config_entry_id: entryId, child_id: String(item.child_id), homework_id: String(item.id), done: !!done });
}

// Attachments are fetched through Home Assistant (the browser has no portal session) with a signed URL, signed for an
// hour and reused for 50 minutes; images and PDFs shown in the page are drawn from a blob: URL, kept for the page's life.
export var educartableSigned = {};
export var EDUCARTABLE_SIGN_REUSE = 50 * 60 * 1000;
export var educartableBlobs = {};

export function educartableFileUrl(hass, entryId, media) {
  var key = entryId + ' ' + media.id;
  var hit = educartableSigned[key];
  if (hit && Date.now() - hit.at < EDUCARTABLE_SIGN_REUSE) return hit.promise;
  var path = `/api/educartable/file/${entryId}?media=${encodeURIComponent(media.id)}&name=${encodeURIComponent(media.name || '')}`;
  var entry = { at: Date.now() };
  entry.promise = hass.callWS({ type: 'auth/sign_path', path: path, expires: 3600 }).then((res) => res.path);
  entry.promise.catch(() => {
    if (educartableSigned[key] === entry) delete educartableSigned[key];
  });
  educartableSigned[key] = entry;
  return entry.promise;
}

export function educartableFileBlob(hass, entryId, media) {
  var key = entryId + ' ' + media.id;
  if (educartableBlobs[key]) return educartableBlobs[key].promise;
  var entry = { url: '' };
  entry.promise = educartableFileUrl(hass, entryId, media)
    .then((url) => fetch(url, { credentials: 'same-origin' }))
    .then((res) => (res.ok ? res.blob() : Promise.reject(new Error(`HTTP ${res.status}`))))
    .then((blob) => {
      entry.url = URL.createObjectURL(blob);
      return entry.url;
    });
  entry.promise.catch(() => {
    if (educartableBlobs[key] === entry) delete educartableBlobs[key];
  });
  educartableBlobs[key] = entry;
  return entry.promise;
}

// Opens an attachment in a new tab (PDF and images shown by the browser, other files downloaded).
export function educartableOpenFile(hass, entryId, media) {
  var tab = window.open('', '_blank');
  return educartableFileUrl(hass, entryId, media)
    .then((url) => {
      if (tab) tab.location.href = url;
      else window.location.href = url;
    })
    .catch((err) => {
      if (tab) tab.close();
      throw err;
    });
}

export function educartableIsImage(media) {
  return /^(png|jpe?g|gif|webp)$/.test(String(media.extension || '').toLowerCase());
}

// Attachments of an unfolded row: image thumbnails (shown once fetched, see educartableHydrate) and file buttons.
// Fetched with the parent's account: administrators only, the others see the names.
export function educartableFiles(medias, t, entryId, canAct) {
  if (!medias?.length) return '';
  var attrs = (m) => ' data-media="' + educartableEsc(m.id) + '" data-name="' + educartableEsc(m.name) + '"';
  var images = canAct ? medias.filter(educartableIsImage) : [];
  var others = medias.filter((m) => images.indexOf(m) === -1);
  var blob = (m) => educartableBlobs[entryId + ' ' + m.id]?.url || '';
  return '<div class="atts" role="group" aria-label="' + educartableEsc(t.attachments) + '">' +
    (images.length ? '<div class="att-images">' + images.map((m) =>
      '<button class="att-img" data-action="file"' + attrs(m) + ' title="' + educartableEsc(m.name) + '"><img alt="' + educartableEsc(m.name) + '" data-src="1"' + attrs(m) + (blob(m) ? ' src="' + educartableEsc(blob(m)) + '"' : '') + '></button>').join('') + '</div>' : '') +
    (others.length ? '<div class="files">' + others.map((m) =>
      '<button class="file" data-action="file"' + attrs(m) + (canAct ? '' : ' disabled') + ' title="' + educartableEsc(m.name) + '"><ha-icon icon="' + (m.extension === 'pdf' ? 'mdi:file-pdf-box' : 'mdi:paperclip') + '"></ha-icon><span>' + educartableEsc(m.name) + '</span></button>').join('') + '</div>' : '') +
    '</div>';
}

// Gives the drawn thumbnails their sources.
export function educartableHydrate(root, hass, entryId) {
  root.querySelectorAll('img[data-src]:not([src])').forEach((img) => {
    educartableFileBlob(hass, entryId, { id: img.getAttribute('data-media'), name: img.getAttribute('data-name') })
      .then((url) => {
        if (!img.getAttribute('src')) img.setAttribute('src', url);
      })
      .catch(() => img.closest('.att-img')?.classList.add('broken'));
  });
}

// A click inside a Home Assistant dialog (more-info, editor) is not a click outside the card.
export function educartableInDialog(ev) {
  return ev.composedPath().some((el) => el?.tagName && /^(HA-DIALOG|HA-MORE-INFO-DIALOG|HUI-DIALOG-EDIT-CARD)$/.test(el.tagName));
}

// Undone homework first by due date, done homework after (when shown).
export function educartableSortedHomework(items, showDone) {
  return items
    .filter((h) => showDone || !h.done)
    .slice()
    .sort((x, y) => (x.done === y.done ? String(x.date).localeCompare(String(y.date)) : x.done ? 1 : -1));
}

// Shared row renderers: the card and the panel draw the same rows. A row with more to read (text, attachments) gets a
// chevron and data-toggle; opts.isOpen(key) unfolds it, opts.full (the panel's tabs) always shows it.
export function educartableToggle(key, open, hasMore) {
  if (!hasMore) return { attrs: '', chevron: '' };
  return {
    attrs: ' data-toggle="' + educartableEsc(key) + '" role="button" tabindex="0" aria-expanded="' + !!open + '"',
    chevron: '<ha-icon class="chevron' + (open ? '' : ' closed') + '" icon="mdi:chevron-down"></ha-icon>',
  };
}

function educartableMore(item, key, opts) {
  var open = !!(opts?.full || opts?.isOpen?.(key));
  var tg = opts?.full ? { attrs: '', chevron: '' } : educartableToggle(key, open, !!item.text || (item.medias || []).length > 0);
  var body = open ? (item.text ? '<div class="item-text' + (opts?.full ? '' : ' clamp') + '">' + educartableEsc(item.text) + '</div>' : '') + educartableFiles(item.medias, opts.t, opts.entryId, opts.canAct) : '';
  return { tg: tg, body: body };
}

// The action a liaison-book message waits for: Sign (opens the confirmation) or Mark as read, for administrators;
// its state for the others and once done.
export function educartableWordAction(w, t, canAct) {
  if (w.achieved || !w.achievement) return w.achievement ? '<span class="chip ok">' + educartableEsc(w.achievement === 'sign' ? t.signed : t.read_done) + '</span>' : '';
  if (canAct && w.achievement === 'sign') return '<button class="act" data-action="sign" data-id="' + educartableEsc(w.id) + '">' + educartableEsc(t.sign) + '</button>';
  if (canAct && w.achievement === 'read') return '<button class="act" data-action="read" data-id="' + educartableEsc(w.id) + '">' + educartableEsc(t.mark_read) + '</button>';
  return '<span class="chip">' + educartableEsc(t['ach_' + w.achievement] || t.tile_words) + '</span>';
}

export function educartableWordRow(w, t, locale, opts) {
  var meta = [w.child, w.author, educartableDay(w.date, t, locale)].filter(Boolean).join(' · ');
  var m = educartableMore(w, 'word:' + w.id, Object.assign({ t: t }, opts));
  var pending = w.achievement && !w.achieved;
  return '<div class="item word' + (pending ? '' : ' done') + '">' +
    '<ha-icon class="item-icon" icon="' + (pending ? (w.achievement === 'sign' ? 'mdi:notebook-edit-outline' : 'mdi:email-alert-outline') : 'mdi:check-circle-outline') + '"></ha-icon>' +
    '<div class="item-main"' + m.tg.attrs + '><div class="item-title">' + educartableEsc(w.title || '—') + '</div>' +
    '<div class="item-meta">' + educartableEsc(meta) + '</div>' + m.body + '</div>' + m.tg.chevron +
    educartableWordAction(w, t, opts?.canAct) + '</div>';
}

// opts.child: the child's first name in the meta line (left out where a single child is shown). The box ticks a
// homework that asks to be done (administrators); one that asks something else shows its state only.
export function educartableHomeworkRow(h, t, locale, opts) {
  var meta = [opts?.child === false ? '' : h.child, h.subject, educartableDue(h.date, t, locale)].filter(Boolean).join(' · ');
  var label = h.done ? t.mark_todo : t.mark_done;
  var icon = '<ha-icon icon="' + (h.done ? 'mdi:checkbox-marked-outline' : 'mdi:checkbox-blank-outline') + '"></ha-icon>';
  var box = h.recipient_id
    ? '<button class="check" role="checkbox" aria-checked="' + !!h.done + '" aria-label="' + educartableEsc(label) + '" title="' + educartableEsc(label) + '" data-action="homework" data-id="' + educartableEsc(h.id) + '" data-child="' + educartableEsc(h.child_id) + '"' + (opts?.canAct === false ? ' disabled' : '') + '>' + icon + '</button>'
    : '<span class="check static" aria-label="' + educartableEsc(h.done ? t.done : t.to_do) + '">' + icon + '</span>';
  var m = educartableMore(h, 'homework:' + h.child_id + ':' + h.id, Object.assign({ t: t }, opts));
  return '<div class="item hw' + (h.done ? ' done' : '') + '">' + box +
    '<div class="item-main"' + m.tg.attrs + '><div class="item-title">' + educartableEsc(h.title || h.subject || '—') + '</div>' +
    '<div class="item-meta">' + educartableEsc(meta) + '</div>' + m.body + '</div>' + m.tg.chevron + '</div>';
}

// News, events and parent meetings: the icon and the label say which.
export var EDUCARTABLE_NEWS_KINDS = {
  event: ['mdi:calendar-star', 'kind_event'],
  meeting: ['mdi:account-group-outline', 'kind_meeting'],
  advert: ['mdi:newspaper-variant-outline', 'kind_advert'],
};

export function educartableNewsRow(n, t, locale, opts) {
  var kind = EDUCARTABLE_NEWS_KINDS[n.type] || EDUCARTABLE_NEWS_KINDS.advert;
  var m = educartableMore(n, 'news:' + n.id, Object.assign({ t: t }, opts));
  return '<div class="item news">' +
    '<ha-icon class="item-icon" icon="' + kind[0] + '"></ha-icon>' +
    '<div class="item-main"' + m.tg.attrs + '><div class="item-title">' + educartableEsc(n.title || '—') + '</div>' +
    '<div class="item-meta">' + educartableEsc([t[kind[1]], n.author, educartableDay(n.date, t, locale)].filter(Boolean).join(' · ')) + '</div>' + m.body + '</div>' + m.tg.chevron + '</div>';
}

// Styles of the rows and chips, shared by the card and the panel.
export function educartableItemStyles(accent) {
  return [
    '.item { display: flex; align-items: flex-start; gap: 10px; padding: 6px 0; border-top: 1px solid var(--divider-color, rgba(0,0,0,.12)); }',
    '.item:first-child, .section-title + .item, h2 + .item, h3 + .item { border-top: none; }',
    '.item-icon { flex: none; color: var(--secondary-text-color); --mdc-icon-size: 20px; margin-top: 1px; }',
    '.word:not(.done) .item-icon { color: ' + accent + '; }',
    '.hw.done .item-icon { color: var(--success-color, #43a047); }',
    '.item-main { flex: 1; min-width: 0; }',
    '.item-title { font-weight: 500; color: var(--primary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
    '.item.done .item-title { color: var(--secondary-text-color); font-weight: 400; }',
    '.hw.done .item-title { text-decoration: line-through; }',
    '.item-meta { font-size: 12px; color: var(--secondary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
    '.link { color: color-mix(in srgb, ' + accent + ' 65%, var(--primary-text-color)); font-weight: 500; text-decoration: none; }',
    '.link:hover { text-decoration: underline; }',
    '.chip { flex: none; font-size: 11px; font-weight: 500; border-radius: 12px; padding: 2px 8px; white-space: nowrap;' +
      ' color: color-mix(in srgb, ' + accent + ' 55%, var(--primary-text-color)); background: color-mix(in srgb, ' + accent + ' 15%, transparent); }',
    '.chip.ok { color: color-mix(in srgb, var(--success-color, #43a047) 55%, var(--primary-text-color)); background: color-mix(in srgb, var(--success-color, #43a047) 15%, transparent); }',
    '.empty { padding: 4px 0; font-size: 13px; color: var(--secondary-text-color); }',
    '.item-text { font-size: 13px; color: var(--primary-text-color); white-space: pre-line; margin-top: 4px; overflow-wrap: anywhere; }',
    '.item-text.clamp { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 4; line-clamp: 4; overflow: hidden; }',
    '[data-toggle] { cursor: pointer; }',
    '[data-toggle]:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; border-radius: 4px; }',
    // Collapsed: chevron to the right; open: down (like the other cards).
    '.chevron { flex: none; align-self: flex-start; margin-top: 10px; color: var(--secondary-text-color); --mdc-icon-size: 20px; transition: transform .2s ease; }',
    '.chevron.closed { transform: rotate(-90deg); }',
    // 40 px touch target around the 20 px box, without moving the row's text.
    '.check { all: unset; cursor: pointer; flex: none; display: grid; place-items: center; width: 40px; height: 40px; margin: -8px -8px -8px -10px; border-radius: 10px; color: var(--secondary-text-color); --mdc-icon-size: 20px; }',
    '.check:hover { background: color-mix(in srgb, var(--primary-text-color) 6%, transparent); }',
    '.check:disabled, .check.static { cursor: default; background: none; }',
    '.check:disabled { opacity: .6; }',
    '.hw.done .check { color: var(--success-color, #43a047); }',
    '.check:focus-visible, .act:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }',
    // Outlined, never filled (card convention): accent text on an accent hairline.
    '.act { flex: none; font: inherit; font-size: 12px; font-weight: 500; cursor: pointer; padding: 3px 10px; border-radius: 10px; background: transparent;' +
      ' color: color-mix(in srgb, ' + accent + ' 60%, var(--primary-text-color)); border: 1px solid color-mix(in srgb, ' + accent + ' 50%, transparent); }',
    '.act:hover { background: color-mix(in srgb, ' + accent + ' 10%, transparent); }',
    '.act:disabled { opacity: .6; cursor: default; }',
    '.act.ghost { color: var(--secondary-text-color); border-color: var(--divider-color, rgba(0,0,0,.2)); }',
    '.atts { display: flex; flex-direction: column; gap: 6px; margin-top: 6px; }',
    '.att-images { display: flex; flex-wrap: wrap; gap: 6px; }',
    // White under the image: a transparent PNG drawn in black (a poster, a scan) disappears on a dark theme.
    '.att-img { all: unset; cursor: zoom-in; display: block; border-radius: 8px; overflow: hidden; border: 1px solid var(--divider-color, rgba(0,0,0,.12)); background: #fff; }',
    '.att-img img { display: block; height: 72px; width: auto; max-width: 160px; object-fit: cover; }',
    '.att-img.broken { display: none; }',
    '.att-img:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }',
    '.files { display: flex; flex-wrap: wrap; gap: 6px; }',
    '.file { all: unset; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; max-width: 100%; font-size: 12px; padding: 3px 10px 3px 6px; border-radius: 12px;' +
      ' border: 1px solid var(--divider-color, rgba(0,0,0,.2)); color: var(--primary-text-color); --mdc-icon-size: 16px; }',
    '.file span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }',
    '.file ha-icon { color: ' + accent + '; flex: none; }',
    '.file:hover { background: color-mix(in srgb, ' + accent + ' 10%, transparent); }',
    '.file:disabled { cursor: default; background: none; }',
    '.file:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 1px; }',
    '@media (prefers-reduced-motion: reduce) { .chevron { transition: none; } }',
    '.error-text { color: color-mix(in srgb, var(--error-color, #db4437) 55%, var(--primary-text-color)); font-size: 13px; }',
  ].join('\n');
}

window.Educartable = {
  version: EDUCARTABLE_CARD_VERSION,
  accent: EDUCARTABLE_ACCENT,
  icon: EDUCARTABLE_ICON,
  i18n: EducartableI18n,
  t: educartableT,
  langReady: educartableLangReady,
  lang: educartableLang,
  locale: educartableLocale,
  esc: educartableEsc,
  format: educartableFormat,
  errorText: educartableErrorText,
  accounts: educartableAccounts,
  data: educartableData,
  changed: educartableChanged,
  day: educartableDay,
  time: educartableTime,
  setTimeFormat: educartableSetTimeFormat,
  refresh: educartableRefresh,
  canAct: educartableCanAct,
  sign: educartableSign,
  markRead: educartableMarkRead,
  setDone: educartableSetDone,
  openFile: educartableOpenFile,
  hydrate: educartableHydrate,
  sortedHomework: educartableSortedHomework,
  rows: { word: educartableWordRow, homework: educartableHomeworkRow, news: educartableNewsRow },
  itemStyles: educartableItemStyles,
};
