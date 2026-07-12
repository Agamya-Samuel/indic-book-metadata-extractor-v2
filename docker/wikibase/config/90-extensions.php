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

# --- Extension Configuration ---

# PropertySuggester: minimum probability threshold for suggestions
$wgPropertySuggesterMinProbability = 0.05;

# WikibaseLexeme: enable CirrusSearch integration for lexeme search
$wgLexemeEnableCirrusSearch = true;

# WikibaseQualityConstraints: check constraints on entity save and special page
$wgWBQualityConstraints['constraintCheckOnEntitySave'] = true;
$wgWBQualityConstraints['constraintCheckOnSpecialPage'] = true;
