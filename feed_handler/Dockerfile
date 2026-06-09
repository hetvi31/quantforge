FROM alpine:latest AS builder

RUN apk add --no-cache build-base cmake make g++

WORKDIR /app

# Copy the entire workspace to get shared headers and feed handler source
COPY . .

# Run CMake and build feed handler
RUN cmake -B build -S .
RUN cmake --build build --target quantforge_feed_handler

# Stage 2: Final lightweight image
FROM alpine:latest

RUN apk add --no-cache libstdc++

WORKDIR /app

# Copy compiled binary from builder stage
COPY --from=builder /app/build/bin/quantforge_feed_handler /app/quantforge_feed_handler

EXPOSE 9002

CMD ["/app/quantforge_feed_handler"]
