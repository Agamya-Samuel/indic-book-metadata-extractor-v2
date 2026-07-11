-- Create wikibase database and user if they don't exist
-- This runs on first MariaDB container start (docker-entrypoint-initdb.d)
CREATE DATABASE IF NOT EXISTS `wikibase`;
CREATE USER IF NOT EXISTS 'wikibase'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON `wikibase`.* TO 'wikibase'@'%';
FLUSH PRIVILEGES;
