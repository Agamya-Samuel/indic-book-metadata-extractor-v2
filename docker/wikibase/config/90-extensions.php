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

# --- Branding ---
# Files live in the images volume so they survive container recreation.
# icon.png is the emblem, wordmark.png the text beside it, logo.png the full lockup.
$wgLogos = [
    '1x' => "$wgServer/images/indico/logo.png",
    '1.5x' => "$wgServer/images/indico/logo.png",
    '2x' => "$wgServer/images/indico/logo.png",
    'icon' => "$wgServer/images/indico/icon.png",
    // MediaWiki 1.45 requires width/height for a scalable wordmark.
    'wordmark' => [
        'src' => "$wgServer/images/indico/wordmark.png",
        'width' => 160,
        'height' => 93,
    ],
];

# --- Extension Configuration ---

# PropertySuggester: minimum probability threshold for suggestions
$wgPropertySuggesterMinProbability = 0.05;

# WikibaseLexeme: enable CirrusSearch integration for lexeme search
$wgLexemeEnableCirrusSearch = true;

# WikibaseQualityConstraints: check constraints on entity save and special page
$wgWBQualityConstraints['constraintCheckOnEntitySave'] = true;
$wgWBQualityConstraints['constraintCheckOnSpecialPage'] = true;
