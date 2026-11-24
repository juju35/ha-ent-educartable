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

// Shared row renderers: the card and the panel draw the same rows. This release only reads the portal: the rows show
// the state of each item (to sign, signed, done) without buttons that would act on it.
export function educartableWordRow(w, t, locale) {
  var meta = [w.child, educartableDay(w.date, t, locale)].filter(Boolean).join(' · ');
  return '<div class="item word' + (w.signed ? ' done' : '') + '">' +
    '<ha-icon class="item-icon" icon="' + (w.signed ? 'mdi:check-circle-outline' : 'mdi:notebook-edit-outline') + '"></ha-icon>' +
    '<div class="item-main"><div class="item-title">' + educartableEsc(w.title || '—') + '</div>' +
    '<div class="item-meta">' + educartableEsc(meta) + '</div></div>' +
    '<span class="chip' + (w.signed ? ' ok' : '') + '">' + educartableEsc(w.signed ? t.signed : t.tile_words) + '</span></div>';
}

// opts.child: the child's first name in the meta line (left out where a single child is shown).
export function educartableHomeworkRow(h, t, locale, opts) {
  var meta = [opts?.child === false ? '' : h.child, h.subject, educartableDue(h.date, t, locale)].filter(Boolean).join(' · ');
  return '<div class="item hw' + (h.done ? ' done' : '') + '">' +
    '<ha-icon class="item-icon state" icon="' + (h.done ? 'mdi:checkbox-marked-outline' : 'mdi:checkbox-blank-outline') + '" aria-label="' + educartableEsc(h.done ? t.done : t.to_do) + '"></ha-icon>' +
    '<div class="item-main"><div class="item-title">' + educartableEsc(h.title || h.subject || '—') + '</div>' +
    '<div class="item-meta">' + educartableEsc(meta) + '</div></div></div>';
}

// News, events and parent meetings: the icon and the label say which.
export var EDUCARTABLE_NEWS_KINDS = {
  event: ['mdi:calendar-star', 'kind_event'],
  meeting: ['mdi:account-group-outline', 'kind_meeting'],
  advert: ['mdi:newspaper-variant-outline', 'kind_advert'],
};

export function educartableNewsRow(n, t, locale) {
  var kind = EDUCARTABLE_NEWS_KINDS[n.type] || EDUCARTABLE_NEWS_KINDS.advert;
  return '<div class="item news">' +
    '<ha-icon class="item-icon" icon="' + kind[0] + '"></ha-icon>' +
    '<div class="item-main"><div class="item-title">' + educartableEsc(n.title || '—') + '</div>' +
    '<div class="item-meta">' + educartableEsc([t[kind[1]], educartableDay(n.date, t, locale)].filter(Boolean).join(' · ')) + '</div></div></div>';
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
  sortedHomework: educartableSortedHomework,
  rows: { word: educartableWordRow, homework: educartableHomeworkRow, news: educartableNewsRow },
  itemStyles: educartableItemStyles,
};
