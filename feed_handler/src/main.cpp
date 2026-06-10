#include "RedisPublisher.hpp"

#include <iostream>
#include <string>
#include <cstring>
#include <cstdlib>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
    using socket_t = SOCKET;
    #define close_socket closesocket
    #define IS_VALIDSOCKET(s) ((s) != INVALID_SOCKET)
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    using socket_t = int;
    #define close_socket close
    #define INVALID_SOCKET -1
    #define IS_VALIDSOCKET(s) ((s) >= 0)
#endif

using namespace quantforge;

#pragma pack(push, 1)
struct RawTick {
    char symbol[16];
    double price;
    uint64_t quantity;
    uint64_t timestamp;
    char side; // 'B' (Bid) / 'A' (Ask) / 'T' (Trade)
};
#pragma pack(pop)

// Length of a NUL-padded fixed field, capped at `max`.
static size_t fieldLen(const char* s, size_t max) {
    size_t n = 0;
    while (n < max && s[n] != '\0') ++n;
    return n;
}

int main() {
    std::cout << "[FeedHandler] Starting QuantForge Feed Handler..." << std::endl;

#ifdef _WIN32
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        std::cerr << "[FeedHandler] WSAStartup failed" << std::endl;
        return 1;
    }
#endif

    std::string redis_host = std::getenv("REDIS_HOST") ? std::getenv("REDIS_HOST") : "127.0.0.1";
    int redis_port = std::getenv("REDIS_PORT") ? std::stoi(std::getenv("REDIS_PORT")) : 6379;

    RedisPublisher redis(redis_host, redis_port);
    if (!redis.connectWithRetry()) {
        std::cerr << "[FeedHandler] Could not reach Redis; will keep retrying lazily." << std::endl;
    }

    // UDP socket for market-data intake.
    socket_t udp_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (!IS_VALIDSOCKET(udp_fd)) {
        std::cerr << "[FeedHandler] Failed to create UDP socket" << std::endl;
        return 1;
    }

    sockaddr_in server_addr;
    std::memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(9002);

    if (bind(udp_fd, reinterpret_cast<sockaddr*>(&server_addr), sizeof(server_addr)) < 0) {
        std::cerr << "[FeedHandler] Failed to bind UDP to port 9002" << std::endl;
        close_socket(udp_fd);
        return 1;
    }

    std::cout << "[FeedHandler] Listening for UDP market data ticks on port 9002..." << std::endl;

    char buffer[2048];
    while (true) {
        int bytes = recvfrom(udp_fd, buffer, sizeof(buffer), 0, nullptr, nullptr);
        if (bytes < static_cast<int>(sizeof(RawTick))) {
            continue;
        }

        int processed = 0;
        while (bytes - processed >= static_cast<int>(sizeof(RawTick))) {
            RawTick* tick = reinterpret_cast<RawTick*>(buffer + processed);
            processed += sizeof(RawTick);

            std::string symbol(tick->symbol, fieldLen(tick->symbol, sizeof(tick->symbol)));

            std::string json_msg =
                "{\"symbol\":\"" + symbol +
                "\",\"price\":" + std::to_string(tick->price) +
                ",\"quantity\":" + std::to_string(tick->quantity) +
                ",\"side\":\"" + std::string(1, tick->side) +
                "\",\"timestamp\":" + std::to_string(tick->timestamp) + "}";

            // Fire-and-forget; the publisher reconnects lazily if Redis drops.
            redis.publish("market_data", json_msg);
        }
    }

    close_socket(udp_fd);
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
