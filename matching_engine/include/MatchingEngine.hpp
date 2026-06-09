#pragma once

#include "OrderBook.hpp"
#include <unordered_map>
#include <memory>
#include <mutex>

namespace quantforge {

class MatchingEngine {
public:
    MatchingEngine() = default;
    ~MatchingEngine() = default;

    // Route order submission
    std::vector<Trade> submitOrder(const Order& order, std::vector<ExecutionReport>& reports);
    
    // Route order cancellation
    bool cancelOrder(const std::string& symbol, uint64_t order_id, std::vector<ExecutionReport>& reports);

    // Retrieve order book depth
    std::vector<std::pair<double, uint64_t>> getBidsDepth(const std::string& symbol);
    std::vector<std::pair<double, uint64_t>> getAsksDepth(const std::string& symbol);

private:
    std::unordered_map<std::string, std::unique_ptr<OrderBook>> order_books_;
    std::mutex engine_mutex_; // Thread safety guard for multi-threaded access

    OrderBook& getOrCreateOrderBook(const std::string& symbol);
};

} // namespace quantforge
