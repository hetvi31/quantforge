# ---- build stage -----------------------------------------------------------
FROM alpine:3.19 AS builder
RUN apk add --no-cache build-base cmake
WORKDIR /app
COPY . .
# Portable release build (no -march=native: build and run hosts may differ).
RUN cmake -B build -S . -DCMAKE_BUILD_TYPE=Release -DQF_PORTABLE_BUILD=ON -DQF_NO_LTO=ON
RUN cmake --build build --target quantforge_matching_engine -j

# ---- runtime stage ---------------------------------------------------------
FROM alpine:3.19
RUN apk add --no-cache libstdc++ && adduser -D -H quant
WORKDIR /app
COPY --from=builder /app/build/bin/quantforge_matching_engine /app/quantforge_matching_engine
USER quant
EXPOSE 9001
CMD ["/app/quantforge_matching_engine"]
