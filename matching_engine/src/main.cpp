#include "MatchingEngine.hpp"
#include "WireProtocol.hpp"
#include "RedisPublisher.hpp"

#include <iostream>
#include <thread>
#include <mutex>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <string>
#include <chrono>

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
    #include <unistd.h>
    using socket_t = int;
    #define close_socket close
    #define INVALID_SOCKET -1
    #define IS_VALIDSOCKET(s) ((s) >= 0)
#endif

using namespace quantforge;
using wire::RawOrder;
using wire::RawExecutionReport;

namespace {

// Length of a NUL-padded fixed field, capped at `max` (portable strnlen).
size_t fieldLen(const char* s, size_t max) {
    size_t n = 0;
    while (n < max && s[n] != '\0') ++n;
    return n;
}

// A single Redis connection shared by all client threads, guarded by a mutex.
// Used to publish authoritative order-book snapshots so the UI shows the real
// engine book (not a fabricated one).
RedisPublisher* g_redis = nullptr;
std::mutex g_redis_mutex;

std::string ticksToString(PriceTicks ticks) {
    // Render fixed-point ticks as a decimal string (e.g. 6200000 -> "62000.00").
    const bool neg = ticks < 0;
    uint64_t mag = neg ? static_cast<uint64_t>(-(ticks + 1)) + 1 : static_cast<uint64_t>(ticks);
    uint64_t whole = mag / wire::PRICE_SCALE;
    uint64_t frac = mag % wire::PRICE_SCALE;
    std::string s = (neg ? "-" : "") + std::to_string(whole) + ".";
    std::string fs = std::to_string(frac);
    while (fs.size() < 2) fs = "0" + fs;  // PRICE_SCALE = 100 -> two decimals
    return s + fs;
}

std::string buildBookJson(MatchingEngine& engine, const std::string& symbol) {
    auto bids = engine.getBidsDepth(symbol);
    auto asks = engine.getAsksDepth(symbol);
    const size_t kMaxLevels = 15;

    auto levels = [&](const std::vector<std::pair<PriceTicks, uint64_t>>& v) {
        std::string out = "[";
        for (size_t i = 0; i < v.size() && i < kMaxLevels; ++i) {
            if (i) out += ",";
            out += "[" + ticksToString(v[i].first) + "," + std::to_string(v[i].second) + "]";
        }
        out += "]";
        return out;
    };

    uint64_t now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    return "{\"symbol\":\"" + symbol + "\",\"bids\":" + levels(bids) +
           ",\"asks\":" + levels(asks) + ",\"timestamp\":" + std::to_string(now_ms) + "}";
}

void publishBook(MatchingEngine& engine, const std::string& symbol) {
    if (!g_redis) return;
    std::string json = buildBookJson(engine, symbol);
    std::lock_guard<std::mutex> lock(g_redis_mutex);
    g_redis->publish("order_book", json);
}

char statusToChar(OrderStatus status) {
    switch (status) {
        case OrderStatus::NEW:              return 'N';
        case OrderStatus::PARTIALLY_FILLED: return 'P';
        case OrderStatus::FILLED:           return 'F';
        case OrderStatus::CANCELLED:        return 'C';
        case OrderStatus::REJECTED:         return 'R';
    }
    return 'R';
}

void sendReports(socket_t client_fd, const std::vector<ExecutionReport>& reports) {
    for (const auto& report : reports) {
        RawExecutionReport raw;
        std::memset(&raw, 0, sizeof(raw));
        raw.order_id = report.order_id;
        std::strncpy(raw.symbol, report.symbol.c_str(), sizeof(raw.symbol) - 1);
        raw.side = (report.side == OrderSide::BUY) ? 'B' : 'S';
        raw.status = statusToChar(report.status);
        raw.price_ticks = report.price;
        raw.last_quantity = report.last_quantity;
        raw.cumulative_quantity = report.cumulative_quantity;
        raw.remaining_quantity = report.remaining_quantity;
        raw.timestamp = report.timestamp;
        std::strncpy(raw.reject_reason, report.reject_reason.c_str(), sizeof(raw.reject_reason) - 1);
        send(client_fd, reinterpret_cast<const char*>(&raw), sizeof(raw), 0);
    }
}

} // namespace

void handleClient(socket_t client_fd, MatchingEngine& engine) {
    std::cout << "[Engine] Client connected." << std::endl;
    char buffer[8192];
    size_t buffer_offset = 0;

    while (true) {
        int bytes_received = recv(client_fd, buffer + buffer_offset,
                                  static_cast<int>(sizeof(buffer) - buffer_offset), 0);
        if (bytes_received <= 0) {
            std::cout << "[Engine] Client disconnected." << std::endl;
            break;
        }

        size_t total_bytes = buffer_offset + bytes_received;
        size_t processed_bytes = 0;

        while (total_bytes - processed_bytes >= sizeof(RawOrder)) {
            RawOrder* raw = reinterpret_cast<RawOrder*>(buffer + processed_bytes);
            processed_bytes += sizeof(RawOrder);

            // NUL-safe symbol decode: the field is NUL-padded but a full 16-byte
            // symbol carries no terminator, so bound the length explicitly.
            std::string symbol(raw->symbol, fieldLen(raw->symbol, sizeof(raw->symbol)));

            std::vector<ExecutionReport> reports;

            if (raw->action == static_cast<char>(wire::Action::CANCEL)) {
                std::cout << "[Engine] Cancel order id=" << raw->id
                          << " symbol=" << symbol << std::endl;
                engine.cancelOrder(symbol, raw->id, reports);
            } else {
                Order order;
                order.id = raw->id;
                order.symbol = symbol;
                order.side = (raw->side == 'B') ? OrderSide::BUY : OrderSide::SELL;
                order.type = (raw->action == static_cast<char>(wire::Action::NEW_MARKET))
                                 ? OrderType::MARKET : OrderType::LIMIT;
                order.price = raw->price_ticks;
                order.quantity = raw->quantity;
                order.remaining_quantity = raw->quantity;
                order.timestamp = 0;  // stamped by the order book

                std::cout << "[Engine] Order id=" << order.id << " symbol=" << symbol
                          << " side=" << raw->side << " action=" << raw->action
                          << " price_ticks=" << order.price << " qty=" << order.quantity << std::endl;

                engine.submitOrder(order, reports);
            }

            sendReports(client_fd, reports);
            publishBook(engine, symbol);
        }

        // Shift any partial trailing frame to the front of the buffer.
        size_t remaining = total_bytes - processed_bytes;
        if (processed_bytes > 0 && remaining > 0) {
            std::memmove(buffer, buffer + processed_bytes, remaining);
        }
        buffer_offset = remaining;
    }

    close_socket(client_fd);
}

int main() {
    std::cout << "[Engine] Starting QuantForge Matching Engine..." << std::endl;

#ifdef _WIN32
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        std::cerr << "[Engine] WSAStartup failed." << std::endl;
        return 1;
    }
#endif

    // Connect to Redis for order-book snapshot publishing (best-effort).
    std::string redis_host = std::getenv("REDIS_HOST") ? std::getenv("REDIS_HOST") : "127.0.0.1";
    int redis_port = std::getenv("REDIS_PORT") ? std::stoi(std::getenv("REDIS_PORT")) : 6379;
    static RedisPublisher redis(redis_host, redis_port);
    if (redis.connectWithRetry()) {
        g_redis = &redis;
    } else {
        std::cerr << "[Engine] Warning: Redis unavailable; order-book snapshots disabled." << std::endl;
    }

    MatchingEngine engine;
    socket_t server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (!IS_VALIDSOCKET(server_fd)) {
        std::cerr << "[Engine] Socket creation failed." << std::endl;
        return 1;
    }

    int opt = 1;
#ifdef _WIN32
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char*>(&opt), sizeof(opt));
#else
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
#endif

    sockaddr_in address;
    std::memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(9001);

    if (bind(server_fd, reinterpret_cast<sockaddr*>(&address), sizeof(address)) < 0) {
        std::cerr << "[Engine] Bind to port 9001 failed." << std::endl;
        close_socket(server_fd);
        return 1;
    }

    if (listen(server_fd, 10) < 0) {
        std::cerr << "[Engine] Listen failed." << std::endl;
        close_socket(server_fd);
        return 1;
    }

    std::cout << "[Engine] Matching Engine listening on port 9001..." << std::endl;

    while (true) {
        sockaddr_in client_address;
        socklen_t client_len = sizeof(client_address);
        socket_t client_fd = accept(server_fd, reinterpret_cast<sockaddr*>(&client_address), &client_len);

        if (!IS_VALIDSOCKET(client_fd)) {
            std::cerr << "[Engine] Accept failed." << std::endl;
            continue;
        }

        std::thread(handleClient, client_fd, std::ref(engine)).detach();
    }

    close_socket(server_fd);
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
