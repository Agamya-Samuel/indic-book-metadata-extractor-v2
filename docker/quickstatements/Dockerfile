# QuickStatements v1 with the mysqli extension and the local-DB patch.
#
# The stock wikibase/quickstatements:1 image targets Wikimedia Toolforge:
#   - its PHP build has no mysqli, so every batch-DB call fails with
#     "Class mysqli not found";
#   - its ToolforgeCommon wrapper connects to tools.db.svc.wikimedia.cloud.
# This image adds mysqli (compiled from the matching official PHP image) and
# repoints the wrapper at the compose `mysql` service.
FROM php:8.3-apache AS builder
RUN docker-php-ext-install mysqli

FROM wikibase/quickstatements:1
COPY --from=builder /usr/local/lib/php/extensions/no-debug-non-zts-20230831/mysqli.so \
                    /usr/local/lib/php/extensions/no-debug-non-zts-20230831/mysqli.so
RUN printf 'extension=mysqli.so\n' > /usr/local/etc/php/conf.d/docker-php-ext-mysqli.ini \
 && sed -i 's#tools\.db\.svc\.wikimedia\.cloud#mysql#g; s#tools-readonly\.db\.svc\.wikimedia\.cloud#mysql#g' \
      /var/www/html/magnustools/public_html/php/ToolforgeCommon.php