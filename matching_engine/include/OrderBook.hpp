#pragma once

#include "Types.hpp"
#include <map>
#include <list>
#include <unordered_map>
#include <vector>
#include <memory>

namespace quantforge {

class OrderBook {
public:
    explicit OrderBook(const std::string& symbol);
    ~OrderBook() = default;

    // Core Matching Operations
    std::vector<Trade> addLimitOrder(Order order, std::vector<ExecutionReport>& reports);
    std::vector<Trade> addMarketOrder(Order order, std::vector<ExecutionReport>& reports);
    bool cancelOrder(uint64_t order_id, std::vector<ExecutionReport>& reports);

    // Getters for book info
    const std::string& getSymbol() const { return symbol_; }
    
    // Depth representation (Price, Quantity)
    std::vector<std::pair<double, uint64_t>> getBidsDepth() const;
    std::vector<std::pair<double, uint64_t>> getAsksDepth() const;

private:
    std::string symbol_;

    // Bids: Sorted high to low (highest bid has priority)
    std::map<double, std::list<Order>, std::greater<double>> bids_;
    
    // Asks: Sorted low to high (lowest ask has priority)
    std::map<double, std::list<Order>, std::less<double>> asks_;

    // Quick lookup from order ID to list iterator
    std::unordered_map<uint64_t, std::list<Order>::iterator> order_lookup_;
    
    // Quick lookup for order meta details (price, side)
    struct OrderMeta {
        double price;
        OrderSide side;
    };
    std::unordered_map<uint64_t, OrderMeta> order_meta_;

    // Helper functions for matching
    std::vector<Trade> matchOrder(Order& order, std::vector<ExecutionReport>& reports);
};

} // namespace quantforge
