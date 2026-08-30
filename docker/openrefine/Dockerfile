FROM eclipse-temurin:17-jre-alpine

ARG OPENREFINE_VERSION=3.10.1
ARG OPENREFINE_URL=https://github.com/OpenRefine/OpenRefine/releases/download/${OPENREFINE_VERSION}/openrefine-linux-${OPENREFINE_VERSION}.tar.gz

RUN apk add --no-cache curl bash \
    && mkdir -p /opt/openrefine /refine \
    && curl -fsSL "${OPENREFINE_URL}" | tar xz -C /opt/openrefine --strip-components=1 \
    && chmod +x /opt/openrefine/refine

ENV REFINE_PORT=3333
ENV REFINE_HOST=0.0.0.0
ENV REFINE_DIR=/refine

EXPOSE 3333

WORKDIR /opt/openrefine

CMD ["./refine", "-i", "0.0.0.0", "-p", "3333", "-d", "/refine"]
