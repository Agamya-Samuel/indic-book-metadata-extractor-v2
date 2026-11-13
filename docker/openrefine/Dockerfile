FROM eclipse-temurin:17-jre-alpine

ARG OPENREFINE_VERSION=3.10.1
ARG OPENREFINE_URL=https://github.com/OpenRefine/OpenRefine/releases/download/${OPENREFINE_VERSION}/openrefine-linux-${OPENREFINE_VERSION}.tar.gz

# The deploy host's egress resets long-lived HTTP/2 streams mid-download
# (observed: "HTTP/2 stream reset by server" after 37 minutes, which left tar
# with a short read and failed the build). Fetch to a file over HTTP/1.1 with
# retries, then extract, so a reset is retried instead of corrupting the stream.
RUN apk add --no-cache curl bash \
    && mkdir -p /opt/openrefine /refine \
    && curl -fsSL --http1.1 --retry 5 --retry-delay 5 --retry-all-errors \
         -o /tmp/openrefine.tar.gz "${OPENREFINE_URL}" \
    && tar xzf /tmp/openrefine.tar.gz -C /opt/openrefine --strip-components=1 \
    && rm -f /tmp/openrefine.tar.gz \
    && chmod +x /opt/openrefine/refine

ENV REFINE_PORT=3333
ENV REFINE_HOST=0.0.0.0
ENV REFINE_DIR=/refine

EXPOSE 3333

WORKDIR /opt/openrefine

CMD ["./refine", "-i", "0.0.0.0", "-p", "3333", "-d", "/refine"]
