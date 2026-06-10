#pragma once

// =============================================================================
// RedisPublisher - a tiny, dependency-free Redis PUBLISH client.
// -----------------------------------------------------------------------------
// Shared by the feed handler and the matching engine. It speaks just enough of
// the RESP protocol to issue PUBLISH commands.
//
// Crucially the publish path is *fire-and-forget*: we send the command and then
// drain any pending replies non-blocking (via select() with a zero timeout)
// instead of doing a blocking recv() after every message. That keeps the hot
// path from being pinned to Redis round-trip latency while still preventing the
// kernel receive buffer from filling with "+OK" replies.
// =============================================================================

#include <string>
#include <cstring>
#include <iostream>
#include <chrono>
#include <thread>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <netdb.h>
    #include <unistd.h>
#endif

namespace quantforge {

class RedisPublisher {
public:
#ifdef _WIN32
    using socket_t = SOCKET;
    static constexpr socket_t kInvalid = INVALID_SOCKET;
#else
    using socket_t = int;
    static constexpr socket_t kInvalid = -1;
#endif

    RedisPublisher(std::string host, int port)
        : host_(std::move(host)), port_(port) {}

    ~RedisPublisher() { closeSocket(); }

    RedisPublisher(const RedisPublisher&) = delete;
    RedisPublisher& operator=(const RedisPublisher&) = delete;

    bool connected() const { return fd_ != kInvalid; }

    // Block until connected or attempts exhausted. Returns success.
    bool connectWithRetry(int attempts = 5, int delay_seconds = 2) {
        for (int i = 0; i < attempts; ++i) {
            if (connect()) return true;
            std::this_thread::sleep_for(std::chrono::seconds(delay_seconds));
        }
        return false;
    }

    // Publish `message` to `channel`. Reconnects lazily on a dead socket.
    // Returns false if the message could not be sent (socket is then closed).
    bool publish(const std::string& channel, const std::string& message) {
        if (!connected() && !connect()) return false;

        const std::string cmd =
            "*3\r\n$7\r\nPUBLISH\r\n$" + std::to_string(channel.size()) + "\r\n" + channel +
            "\r\n$" + std::to_string(message.size()) + "\r\n" + message + "\r\n";

        if (!sendAll(cmd)) {
            closeSocket();
            return false;
        }
        drainReplies();
        return true;
    }

private:
    bool connect() {
        closeSocket();

        struct addrinfo hints, *res = nullptr;
        std::memset(&hints, 0, sizeof(hints));
        hints.ai_family = AF_INET;
        hints.ai_socktype = SOCK_STREAM;
        if (getaddrinfo(host_.c_str(), std::to_string(port_).c_str(), &hints, &res) != 0) {
            std::cerr << "[Redis] Failed to resolve " << host_ << std::endl;
            return false;
        }

        socket_t fd = ::socket(AF_INET, SOCK_STREAM, 0);
        if (fd == kInvalid) { freeaddrinfo(res); return false; }

        if (::connect(fd, res->ai_addr, static_cast<int>(res->ai_addrlen)) < 0) {
            freeaddrinfo(res);
            closeOne(fd);
            std::cerr << "[Redis] Failed to connect to " << host_ << ":" << port_ << std::endl;
            return false;
        }
        freeaddrinfo(res);

        fd_ = fd;
        std::cout << "[Redis] Connected to " << host_ << ":" << port_ << std::endl;
        return true;
    }

    bool sendAll(const std::string& data) {
        size_t sent = 0;
        while (sent < data.size()) {
            int n = ::send(fd_, data.data() + sent,
                           static_cast<int>(data.size() - sent), 0);
            if (n <= 0) return false;
            sent += static_cast<size_t>(n);
        }
        return true;
    }

    // Non-blocking: read and discard whatever replies are already buffered.
    void drainReplies() {
        char buf[512];
        for (;;) {
            fd_set rs;
            FD_ZERO(&rs);
            FD_SET(fd_, &rs);
            timeval tv{0, 0};
            int r = select(static_cast<int>(fd_) + 1, &rs, nullptr, nullptr, &tv);
            if (r <= 0 || !FD_ISSET(fd_, &rs)) break;
            int n = ::recv(fd_, buf, sizeof(buf), 0);
            if (n <= 0) { if (n == 0) closeSocket(); break; }
        }
    }

    static void closeOne(socket_t fd) {
#ifdef _WIN32
        closesocket(fd);
#else
        ::close(fd);
#endif
    }

    void closeSocket() {
        if (fd_ != kInvalid) { closeOne(fd_); fd_ = kInvalid; }
    }

    std::string host_;
    int port_;
    socket_t fd_ = kInvalid;
};

} // namespace quantforge
