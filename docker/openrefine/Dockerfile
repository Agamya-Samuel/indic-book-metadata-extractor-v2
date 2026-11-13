FROM eclipse-temurin:17-jre-alpine

ARG OPENREFINE_VERSION=3.10.1
ARG OPENREFINE_URL=https://github.com/OpenRefine/OpenRefine/releases/download/${OPENREFINE_VERSION}/openrefine-linux-${OPENREFINE_VERSION}.tar.gz

# The deploy host downloads this tarball over a throttled path (~40 KB/s to
# GitHub's CDN) and the transfer stalls without erroring, which is what hung two
# deployments indefinitely. So: resume across attempts (-C -), abort a stalled
# transfer (--speed-time/--speed-limit) instead of waiting forever, and loop
# until the archive is actually complete rather than until curl exits cleanly.
RUN apk add --no-cache curl bash \
    && mkdir -p /opt/openrefine /refine \
    && for attempt in $(seq 1 12); do \
         if tar -tzf /tmp/openrefine.tar.gz >/dev/null 2>&1; then \
           echo "archive complete after ${attempt} attempt(s)"; break; \
         fi; \
         echo "attempt ${attempt}: resuming download"; \
         curl -fL --http1.1 -C - \
              --speed-time 30 --speed-limit 2048 --max-time 1500 \
              -o /tmp/openrefine.tar.gz "${OPENREFINE_URL}" \
           || echo "attempt ${attempt} interrupted (exit $?), resuming"; \
       done \
    && tar -tzf /tmp/openrefine.tar.gz >/dev/null \
    && tar xzf /tmp/openrefine.tar.gz -C /opt/openrefine --strip-components=1 \
    && rm -f /tmp/openrefine.tar.gz \
    && chmod +x /opt/openrefine/refine

ENV REFINE_PORT=3333
ENV REFINE_HOST=0.0.0.0
ENV REFINE_DIR=/refine

EXPOSE 3333

WORKDIR /opt/openrefine

CMD ["./refine", "-i", "0.0.0.0", "-p", "3333", "-d", "/refine"]
