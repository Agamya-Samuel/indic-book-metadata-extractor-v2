<?php
# User-installed extensions (loaded from custom Dockerfile)
# This file is mounted at /var/www/html/LocalSettings.d/90-extensions.php
# and loaded after all bundled extension configs (10_ through 42_).

wfLoadExtension('PropertySuggester');
wfLoadExtension('WikibaseLexeme');
wfLoadExtension('WikibaseLexemeCirrusSearch');
wfLoadExtension('WikibaseQualityConstraints');
wfLoadExtension('AdvancedSearch');

# Bundled extensions that need explicit loading
wfLoadExtension('AbuseFilter');
wfLoadExtension('WikibaseEdtf');

# Gadgets extension (may already be loaded by MW core; wfLoadExtension is idempotent)
wfLoadExtension('Gadgets');

# --- Canonical origin ---
# The bundled image bakes $wgServer at install time, so a redeploy on a new
# domain keeps redirecting to the old host. Honour the runtime value instead.
if (getenv('MW_WG_SERVER')) {
    $wgServer = getenv('MW_WG_SERVER');
    $wgCanonicalServer = $wgServer;
}

# --- QuickStatements OAuth ---
# QuickStatements registers its own owner-only consumer on first setup.
$wgGroupPermissions['oauthbot']['mwoauthproposeconsumer'] = true;

# --- Statement indexing (WikibaseCirrusSearch) ---
# haswbstatement: only works for properties listed here. Without this,
# statement_keywords is empty in Elasticsearch and every haswbstatement
# query returns 0 hits. Local property ids: P2 = instance of, P3 = author,
# P6 = publisher, P15 = language, P31 = title.
$wgWBRepoSettings['searchIndexProperties'] = [ 'P2', 'P3', 'P6', 'P15', 'P31' ];
$wgWBRepoSettings['searchIndexTypes'] = [
    'string',
    'external-id',
    'url',
    'wikibase-item',
    'wikibase-property',
];

# --- Branding ---
# Served from /var/www/html/images/indico, bind-mounted read-only from
# docker/wikibase/images (so the logo is always the repo version).
# icon.png MUST be a perfect square (Vector renders it in a square slot; a
# non-square image is cropped). There is no wordmark image: Vector 2022 falls
# back to $wgSitename as the text beside the icon.
$wgSitename = 'Open Book Map Wikibase';
$wgLogos = [
    '1x' => "$wgServer/images/indico/logo.png",
    '1.5x' => "$wgServer/images/indico/logo.png",
    '2x' => "$wgServer/images/indico/logo.png",
    'icon' => "$wgServer/images/indico/icon.png",
];

# --- Extension Configuration ---

# PropertySuggester: minimum probability threshold for suggestions
$wgPropertySuggesterMinProbability = 0.05;

# WikibaseLexeme: enable CirrusSearch integration for lexeme search
$wgLexemeEnableCirrusSearch = true;

# WikibaseQualityConstraints: check constraints on entity save and special page
$wgWBQualityConstraints['constraintCheckOnEntitySave'] = true;
$wgWBQualityConstraints['constraintCheckOnSpecialPage'] = true;
