// ── editor ────────────────────────────────────────────────────────────────────
import { EDUCARTABLE_CARD_VERSION, pickerDefine } from "./card-picker.js";
import { EDUCARTABLE_DEFAULTS, EDUCARTABLE_LANGUAGES } from "./i18n-helpers.js";
import { educartableLang, educartableT } from "./helpers.js";
import { EducartableCard } from "./card.js";
import { EducartableMiniCard } from "./mini-card.js";

export var EDUCARTABLE_EDITOR_KEYS = {
  config_entry_id: 'editor_entry',
  title: 'editor_title',
  show_title: 'editor_show_title',
  show_refresh: 'editor_show_refresh',
  show_words: 'editor_show_words',
  show_homework: 'editor_show_homework',
  show_done: 'editor_show_done',
  show_news: 'editor_show_news',
  show_empty: 'editor_show_empty',
  max_items: 'editor_max_items',
  language: 'editor_language',
  illustration: 'editor_illustration',
  illustration_theme: 'editor_illustration_theme',
};

export function educartableEditorSchema(t) {
  var bool = (name) => ({ name: name, selector: { boolean: {} } });
  return [
    { name: 'config_entry_id', selector: { config_entry: { integration: 'educartable' } } },
    { name: 'title', selector: { text: {} } },
    {
      type: 'grid',
      name: '',
      schema: ['show_title', 'show_refresh', 'show_words', 'show_homework', 'show_done', 'show_news', 'show_empty'].map(bool),
    },
    { name: 'max_items', selector: { number: { min: 1, max: 20, mode: 'box' } } },
    {
      type: 'grid',
      name: '',
      schema: [
        bool('illustration'),
        { name: 'illustration_theme', selector: { select: { mode: 'dropdown', options: ['auto', 'day', 'night'].map((v) => ({ value: v, label: t['theme_' + v] })) } } },
      ],
    },
    {
      name: 'language',
      selector: { select: { mode: 'dropdown', options: [{ value: '', label: t.editor_lang_auto }].concat(EDUCARTABLE_LANGUAGES.map((l) => ({ value: l[0], label: l[1] }))) } },
    },
  ];
}

export class EducartableCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({}, config);
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement('ha-form');
      this._form.addEventListener('value-changed', this._valueChanged.bind(this));
      this.appendChild(this._form);
    }
    var lang = educartableLang(this._hass, this._config);
    if (lang !== this._lang) {
      this._lang = lang;
      var t = educartableT(this._hass, this._config);
      this._form.schema = educartableEditorSchema(t);
      this._form.computeLabel = (field) => t[EDUCARTABLE_EDITOR_KEYS[field.name]] || field.name;
    }
    this._form.hass = this._hass;
    this._form.data = Object.assign({}, EDUCARTABLE_DEFAULTS, this._config);
  }

  _valueChanged(ev) {
    var value = Object.assign({}, ev.detail.value);
    Object.keys(EDUCARTABLE_DEFAULTS).forEach((key) => {
      if (value[key] === EDUCARTABLE_DEFAULTS[key]) delete value[key];
    });
    ['title', 'config_entry_id', 'language'].forEach((key) => {
      if (!value[key]) delete value[key];
    });
    this._config = value;
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: value }, bubbles: true, composed: true }));
  }
}

if (!customElements.get('educartable-card-editor')) pickerDefine('educartable-card-editor', EducartableCardEditor);

export var educartableDefined = false;
if (!customElements.get('educartable-card')) {
  pickerDefine('educartable-card', EducartableCard);
  educartableDefined = true;
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'educartable-card',
    name: 'Educartable',
    description: 'Liaison book to sign, homework and news of an Educartable family account.',
    preview: true,
    documentationURL: 'https://github.com/juju35/ha-ent-educartable',
  });
}
if (!customElements.get('educartable-mini-card')) {
  pickerDefine('educartable-mini-card', EducartableMiniCard);
  educartableDefined = true;
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'educartable-mini-card',
    name: 'Educartable mini',
    description: 'Homework, liaison book to sign and news counts, with a button to show the full Educartable card.',
    preview: true,
    documentationURL: 'https://github.com/juju35/ha-ent-educartable',
  });
}
if (educartableDefined) {
  console.info(`%c EDUCARTABLE-CARD %c v${EDUCARTABLE_CARD_VERSION} `, 'color:#fff;background:#f28c1e;font-weight:700', 'color:#f28c1e;background:#fff');
}
