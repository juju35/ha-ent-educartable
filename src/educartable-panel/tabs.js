// Educartable sidebar panel: one tab per part of the family portal, Settings last. It draws its own content (no Lovelace card
// inside) and reuses the card file's helpers, translations and row renderers (window.Educartable), loaded on demand.
export var EDUCARTABLE_PANEL_TABS = ['home', 'homework', 'words', 'news', 'settings'];
export var EDUCARTABLE_TAB_KEYS = { home: 'tab_home', homework: 'tab_homework', words: 'tab_words', news: 'tab_news', settings: 'tab_settings' };
