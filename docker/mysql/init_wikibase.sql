-- Ensure wikibase database exists (backup for first-init)
-- MariaDB docker-entrypoint creates MYSQL_DATABASE automatically,
-- but this script runs as a safety net.
CREATE DATABASE IF NOT EXISTS `wikibase`;
