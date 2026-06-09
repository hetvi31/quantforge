#include "MatchingEngine.hpp"
#include <iostream>
#include <thread>
#include <vector>
#include <cstring>

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

#pragma pack(push, 1)
struct RawOrder {
    uint64_t id;
    char symbol[16];
    char side; // 'B' or 'S'
    char type; // 'L' or 'M'
    double price;
    uint64_t quantity;
};

struct RawExecutionReport {
    uint64_t order_id;
    char symbol[16];
    char side;
    char status; // 'N', 'P', 'F', 'C', 'R'
    double price;
    uint64_t last_quantity;
    uint64_t cumulative_quantity;
    uint64_t remaining_quantity;
    uint64_t timestamp;
    char reject_reason[64];
};
#pragma pack(pop)

void handleClient(socket_t client_fd, MatchingEngine& engine) {
    std::cout << "[Engine] Client connected!" << std::endl;
    char buffer[4096];
    size_t buffer_offset = 0;

    while (true) {
        int bytes_received = recv(client_fd, buffer + buffer_offset, sizeof(buffer) - buffer_offset, 0);
        if (bytes_received <= 0) {
            std::cout << "[Engine] Client disconnected or read error." << std::endl;
            break;
        }

        size_t total_bytes = buffer_offset + bytes_received;
        size_t processed_bytes = 0;

        while (total_bytes - processed_bytes >= sizeof(RawOrder)) {
            RawOrder* raw_order = reinterpret_cast<RawOrder*>(buffer + processed_bytes);
            
            // Convert to engine structures
            Order order;
            order.id = raw_order->id;
            order.symbol = std::string(raw_order->symbol);
            order.side = (raw_order->side == 'B') ? OrderSide::BUY : OrderSide::SELL;
            order.type = (raw_order->type == 'M') ? OrderType::MARKET : OrderType::LIMIT;
            order.price = raw_order->price;
            order.quantity = raw_order->quantity;
            order.remaining_quantity = raw_order->quantity;
            order.timestamp = 0; // Filled by orderbook

            std::cout << "[Engine] Received Order ID: " << order.id 
                      << ", Symbol: " << order.symbol 
                      << ", Side: " << raw_order->side 
                      << ", Price: " << order.price 
                      << ", Qty: " << order.quantity << std::endl;

            std::vector<ExecutionReport> reports;
            engine.submitOrder(order, reports);

            // Send reports back to client
            for (const auto& report : reports) {
                RawExecutionReport raw_report;
                std::memset(&raw_report, 0, sizeof(RawExecutionReport));
                raw_report.order_id = report.order_id;
                std::strncpy(raw_report.symbol, report.symbol.c_str(), sizeof(raw_report.symbol) - 1);
                raw_report.side = (report.side == OrderSide::BUY) ? 'B' : 'S';
                
                switch (report.status) {
                    case OrderStatus::NEW: raw_report.status = 'N'; break;
                    case OrderStatus::PARTIALLY_FILLED: raw_report.status = 'P'; break;
                    case OrderStatus::FILLED: raw_report.status = 'F'; break;
                    case OrderStatus::CANCELLED: raw_report.status = 'C'; break;
                    case OrderStatus::REJECTED: raw_report.status = 'R'; break;
                }
                
                raw_report.price = report.price;
                raw_report.last_quantity = report.last_quantity;
                raw_report.cumulative_quantity = report.cumulative_quantity;
                raw_report.remaining_quantity = report.remaining_quantity;
                raw_report.timestamp = report.timestamp;
                std::strncpy(raw_report.reject_reason, report.reject_reason.c_str(), sizeof(raw_report.reject_reason) - 1);

                send(client_fd, reinterpret_cast<const char*>(&raw_report), sizeof(RawExecutionReport), 0);
            }

            processed_bytes += sizeof(RawOrder);
        }

        // Shift remaining data to start of buffer
        if (processed_bytes > 0) {
            size_t remaining = total_bytes - processed_bytes;
            if (remaining > 0) {
                std::memmove(buffer, buffer + processed_bytes, remaining);
            }
            buffer_offset = remaining;
        } else {
            buffer_offset = total_bytes;
        }
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
    address.sin_port = htons(9001); // Engine listens on Port 9001

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
            std::cerr << "[Engine] Accept connection failed." << std::endl;
            continue;
        }

        std::thread client_thread(handleClient, client_fd, std::ref(engine));
        client_thread.detach();
    }

    close_socket(server_fd);
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
