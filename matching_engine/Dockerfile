FROM alpine:latest AS builder

RUN apk add --no-cache build-base cmake make g++

WORKDIR /app

# Copy the entire workspace to get shared headers and matching engine source
COPY . .

# Run CMake and build matching engine
RUN cmake -B build -S .
RUN cmake --build build --target quantforge_matching_engine

# Stage 2: Final lightweight image
FROM alpine:latest

RUN apk add --no-cache libstdc++

WORKDIR /app

# Copy compiled binary from builder stage
COPY --from=builder /app/build/bin/quantforge_matching_engine /app/quantforge_matching_engine

EXPOSE 9001

CMD ["/app/quantforge_matching_engine"]
