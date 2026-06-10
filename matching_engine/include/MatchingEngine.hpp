#pragma once

#include "OrderBook.hpp"
#include <unordered_map>
#include <memory>
#include <mutex>

namespace quantforge {

// Routes orders to per-symbol order books. Each symbol has its own mutex, so
// orders for different symbols match fully in parallel; only same-symbol orders
// are serialized. A short-lived registry lock guards book creation/lookup.
class MatchingEngine {
public:
    MatchingEngine() = default;
    ~MatchingEngine() = default;

    // Route order submission.
    std::vector<Trade> submitOrder(const Order& order, std::vector<ExecutionReport>& reports);

    // Route order cancellation.
    bool cancelOrder(const std::string& symbol, uint64_t order_id, std::vector<ExecutionReport>& reports);

    // Retrieve order book depth (price ticks, quantity), best level first.
    std::vector<std::pair<PriceTicks, uint64_t>> getBidsDepth(const std::string& symbol);
    std::vector<std::pair<PriceTicks, uint64_t>> getAsksDepth(const std::string& symbol);

private:
    struct BookEntry {
        std::unique_ptr<OrderBook> book;
        std::mutex mtx;  // serializes access to this symbol's book
    };

    // Returns a stable entry pointer (books are never erased, so the pointer
    // remains valid for the process lifetime).
    BookEntry& getOrCreateEntry(const std::string& symbol);

    std::unordered_map<std::string, std::unique_ptr<BookEntry>> books_;
    std::mutex registry_mutex_;  // guards the books_ map structure only
};

} // namespace quantforge
