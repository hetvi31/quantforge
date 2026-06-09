#include <iostream>
#include <thread>
#include <string>
#include <cstring>
#include <chrono>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
    using socket_t = SOCKET;
    #define close_socket closesocket
    #define INVALID_SOCKET -1
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

#pragma pack(push, 1)
struct RawTick {
    char symbol[16];
    double price;
    uint64_t quantity;
    uint64_t timestamp;
    char side; // 'B' (Bid) or 'A' (Ask) / 'T' (Trade)
};
#pragma pack(pop)

socket_t connectToRedis(const std::string& host, int port) {
    socket_t redis_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (!IS_VALIDSOCKET(redis_fd)) {
        std::cerr << "[FeedHandler] Failed to create Redis socket" << std::endl;
        return INVALID_SOCKET;
    }

    sockaddr_in server_addr;
    std::memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);

    // Resolve host
    struct addrinfo hints, *res;
    std::memset(&hints, 0, sizeof(hints));
    hints.sin_family = AF_INET;
    hints.sin_socktype = SOCK_STREAM;
    if (getaddrinfo(host.c_str(), std::to_string(port).c_str(), &hints, &res) != 0) {
        std::cerr << "[FeedHandler] Failed to resolve Redis host: " << host << std::endl;
        close_socket(redis_fd);
        return INVALID_SOCKET;
    }

    if (connect(redis_fd, res->ai_addr, res->ai_addrlen) < 0) {
        std::cerr << "[FeedHandler] Failed to connect to Redis at " << host << ":" << port << std::endl;
        freeaddrinfo(res);
        close_socket(redis_fd);
        return INVALID_SOCKET;
    }

    freeaddrinfo(res);
    std::cout << "[FeedHandler] Connected to Redis successfully" << std::endl;
    return redis_fd;
}

void publishToRedis(socket_t redis_fd, const std::string& channel, const std::string& message) {
    if (!IS_VALIDSOCKET(redis_fd)) return;
    
    std::string cmd = "*3\r\n$7\r\nPUBLISH\r\n$" + std::to_string(channel.length()) + "\r\n" + channel + 
                      "\r\n$" + std::to_string(message.length()) + "\r\n" + message + "\r\n";
                      
    send(redis_fd, cmd.c_str(), cmd.length(), 0);
    
    // Read the reply (RESP format) to clean the socket buffer
    char reply_buf[256];
    int bytes = recv(redis_fd, reply_buf, sizeof(reply_buf) - 1, 0);
    if (bytes <= 0) {
        std::cerr << "[FeedHandler] Redis connection lost during publish" << std::endl;
    }
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

    // Determine host settings
    std::string redis_host = "127.0.0.1";
    char* env_redis_host = std::getenv("REDIS_HOST");
    if (env_redis_host) {
        redis_host = env_redis_host;
    }

    int redis_port = 6379;
    char* env_redis_port = std::getenv("REDIS_PORT");
    if (env_redis_port) {
        redis_port = std::stoi(env_redis_port);
    }

    // Connect to Redis with retry mechanism
    socket_t redis_fd = INVALID_SOCKET;
    for (int i = 0; i < 5; ++i) {
        redis_fd = connectToRedis(redis_host, redis_port);
        if (IS_VALIDSOCKET(redis_fd)) break;
        std::this_thread::sleep_for(std::chrono::seconds(2));
    }

    // Set up UDP socket for feed intake
    socket_t udp_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (!IS_VALIDSOCKET(udp_fd)) {
        std::cerr << "[FeedHandler] Failed to create UDP socket" << std::endl;
        return 1;
    }

    sockaddr_in server_addr;
    std::memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(9002); // UDP port 9002

    if (bind(udp_fd, reinterpret_cast<sockaddr*>(&server_addr), sizeof(server_addr)) < 0) {
        std::cerr << "[FeedHandler] Failed to bind UDP to port 9002" << std::endl;
        close_socket(udp_fd);
        return 1;
    }

    std::cout << "[FeedHandler] Listening for UDP market data ticks on port 9002..." << std::endl;

    char buffer[2048];
    while (true) {
        sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int bytes = recvfrom(udp_fd, buffer, sizeof(buffer), 0, reinterpret_cast<sockaddr*>(&client_addr), &client_len);
        
        if (bytes < static_cast<int>(sizeof(RawTick))) {
            continue;
        }

        int processed = 0;
        while (bytes - processed >= static_cast<int>(sizeof(RawTick))) {
            RawTick* tick = reinterpret_cast<RawTick*>(buffer + processed);

            // Construct JSON payload
            std::string json_msg = "{\"symbol\":\"" + std::string(tick->symbol) + 
                                   "\",\"price\":" + std::to_string(tick->price) + 
                                   ",\"quantity\":" + std::to_string(tick->quantity) + 
                                   ",\"side\":\"" + std::string(1, tick->side) + 
                                   "\",\"timestamp\":" + std::to_string(tick->timestamp) + "}";

            // Publish to Redis
            if (IS_VALIDSOCKET(redis_fd)) {
                publishToRedis(redis_fd, "market_data", json_msg);
            } else {
                // Retry connecting
                redis_fd = connectToRedis(redis_host, redis_port);
            }

            processed += sizeof(RawTick);
        }
    }

    close_socket(udp_fd);
    if (IS_VALIDSOCKET(redis_fd)) {
        close_socket(redis_fd);
    }
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
