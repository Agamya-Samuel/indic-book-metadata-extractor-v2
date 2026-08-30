# Wikibase Extension and Tooling Reference

## Overview

This document lists all extensions, gadgets, and tools installed on the local Wikibase instance, compared to wikidata.org.

---

## Installed Extensions

These extensions are loaded on the local Wikibase instance. Verify at http://localhost:8181/wiki/Special:Version

### Wikibase-Specific Extensions

| Extension | Version | Purpose |
|-----------|---------|---------|
| **WikibaseRepository** | Bundled | Core structured data (items, properties, statements) |
| **WikibaseClient** | Bundled | Client-side Wikibase integration |
| **WikibaseCirrusSearch** | Bundled | Elasticsearch integration for Wikibase entities |
| **WikibaseManifest** | Bundled | API metadata for structured data repo |
| **WikibaseLocalMedia** | Bundled | Local media file support |
| **EntitySchema** | Bundled | ShEx schema storage for entity validation |
| **WikibaseEdtf** | Bundled | Extended Date/Time Format (circa 1920, 19th century) |
| **WikibaseLexeme** | REL1_45 | Lexicographic data for multilingual content |
| **WikibaseLexemeCirrusSearch** | REL1_45 | Search integration for lexemes |
| **WikibaseQualityConstraints** | REL1_45 | Constraint checking on properties |
| **PropertySuggester** | REL1_45 | Suggests relevant properties when editing |

### MediaWiki Extensions

| Extension | Purpose |
|-----------|---------|
| **CirrusSearch** | OpenSearch/Elasticsearch full-text search |
| **Elastica** | PHP Elasticsearch client |
| **Echo** | Notifications |
| **OAuth** | OAuth consumer authorization (for QuickStatements) |
| **UniversalLanguageSelector** | Language selection and input methods |
| **Babel** | Language proficiency userboxes |
| **CLDR** | Localized language/country names |
| **VisualEditor** | WYSIWYG visual editor |
| **Scribunto** | Lua scripting in wiki pages |
| **ParserFunctions** | Logical parser functions |
| **Cite** | Citation tags |
| **CodeMirror** | Wikitext syntax highlighting |
| **DiscussionTools** | Modern talk page discussions |
| **ConfirmEdit** | CAPTCHA spam protection |
| **Nuke** | Mass-delete pages |
| **SyntaxHighlight** | Code syntax highlighting |
| **AbuseFilter** | Edit abuse heuristics |
| **AdvancedSearch** | Enhanced search UI |
| **Gadgets** | User script gadget framework |

---

## Installed Gadgets

8 curated gadgets from wikidata.org, installed via `install-gadgets.sh`:

| Gadget | Purpose |
|--------|---------|
| **Merge** | Merge duplicate items |
| **labelLister** | Show/edit labels across languages |
| **KeyShortcuts** | Keyboard shortcuts (L, D, S, I, J, A) |
| **DuplicateReferences** | Copy references across statements |
| **compact items** | More compact statement UI |
| **NarrowUI** | Responsive design for narrow screens |
| **Descriptions** | Hover to see item descriptions |
| **AuthorityControl** | Links to authority control values |

**Enable at:** http://localhost:8181/wiki/Special:Preferences#mw-prefsection-gadgets

---

## Extensions NOT Installed (and Why)

### Not Feasible for Self-Hosted

| Extension | wikidata.org Has | Why Not |
|-----------|-----------------|---------|
| **CentralAuth** | Yes | Requires multi-wiki Wikimedia infrastructure |
| **GlobalBlocking** | Yes | Requires CentralAuth |
| **GlobalCssJs** | Yes | Requires CentralAuth |
| **GlobalPreferences** | Yes | Requires CentralAuth |
| **EventBus** | Yes | Requires WMF event platform |
| **EventLogging** | Yes | Requires WMF event platform |
| **CentralNotice** | Yes | Requires multi-wiki |
| **Wikidata.org** | Yes | wikidata.org-specific config |

### Could Be Added Later

| Extension | Purpose | Complexity |
|-----------|---------|------------|
| **Translate** | Translation framework | High |
| **Collection** | Book/PDF creation | Medium |
| **Math** | LaTeX rendering | Medium |
| **Kartographer** | Maps integration | Medium |
| **CheckUser** | IP investigation | Low |
| **CategoryTree** | Category navigation | Low |

---

## External Tools

| Tool | Port | Purpose | Status |
|------|------|---------|--------|
| **QuickStatements** | 9191 | Batch item creation from TSV | Installed |
| **OpenRefine** | 3333 | Bulk data cleaning GUI | Installed |
| **WDQS (SPARQL)** | — | SPARQL query service | Not installed (saves ~4GB RAM) |

---

## Adding New Extensions

1. Add `git clone` to `docker/wikibase/Dockerfile`
2. Add `wfLoadExtension()` to `docker/wikibase/config/90-extensions.php`
3. Rebuild: `docker compose build wikibase`
4. Restart: `docker compose up -d wikibase wikibase-jobrunner`
5. Verify at Special:Version

## Adding New Gadgets

1. Add gadget page name to `fetch-gadgets.sh` GADGET_PAGES array
2. Add gadget definition to `install-gadgets.sh`
3. Rebuild: `docker compose build wikibase`
4. Run: `docker compose exec wikibase bash /install-gadgets.sh`
