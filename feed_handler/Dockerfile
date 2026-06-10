# ---- build stage -----------------------------------------------------------
FROM alpine:3.19 AS builder
RUN apk add --no-cache build-base cmake
WORKDIR /app
COPY . .
RUN cmake -B build -S . -DCMAKE_BUILD_TYPE=Release -DQF_PORTABLE_BUILD=ON -DQF_NO_LTO=ON
RUN cmake --build build --target quantforge_feed_handler -j

# ---- runtime stage ---------------------------------------------------------
FROM alpine:3.19
RUN apk add --no-cache libstdc++ && adduser -D -H quant
WORKDIR /app
COPY --from=builder /app/build/bin/quantforge_feed_handler /app/quantforge_feed_handler
USER quant
EXPOSE 9002/udp
CMD ["/app/quantforge_feed_handler"]
