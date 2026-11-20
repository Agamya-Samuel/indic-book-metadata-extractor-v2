-- QuickStatements v1 batch database for the self-hosted compose.
-- The QS image's Toolforge DB wrapper is patched to use the `mysql` service
-- and the existing `wikibase` MySQL user; these schemas back batch mode.
CREATE DATABASE IF NOT EXISTS wikibase__quickstatements_p CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS wikibase__quickstatements_auth CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON wikibase__quickstatements_p.* TO 'wikibase'@'%';
GRANT ALL PRIVILEGES ON wikibase__quickstatements_auth.* TO 'wikibase'@'%';
FLUSH PRIVILEGES;

USE wikibase__quickstatements_p;
SOURCE /docker-entrypoint-initdb.d/lib/quickstatements-schema.sql;

USE wikibase__quickstatements_auth;
SOURCE /docker-entrypoint-initdb.d/lib/quickstatements-schema.sql;