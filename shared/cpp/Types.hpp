#pragma once

#include <string>
#include <cstdint>

namespace quantforge {

enum class OrderSide : char {
    BUY = 'B',
    SELL = 'S'
};

enum class OrderType : char {
    LIMIT = 'L',
    MARKET = 'M',
    STOP = 'T'
};

enum class OrderStatus : char {
    NEW = 'N',
    PARTIALLY_FILLED = 'P',
    FILLED = 'F',
    CANCELLED = 'C',
    REJECTED = 'R'
};

struct Order {
    uint64_t id;
    std::string symbol;
    OrderSide side;
    OrderType type;
    double price;
    uint64_t quantity;
    uint64_t remaining_quantity;
    uint64_t timestamp;
};

struct Trade {
    std::string trade_id;
    uint64_t buy_order_id;
    uint64_t sell_order_id;
    std::string symbol;
    double price;
    uint64_t quantity;
    uint64_t timestamp;
};

struct ExecutionReport {
    uint64_t order_id;
    std::string symbol;
    OrderSide side;
    OrderStatus status;
    double price;
    uint64_t last_quantity;
    uint64_t cumulative_quantity;
    uint64_t remaining_quantity;
    uint64_t timestamp;
    std::string reject_reason;
};

} // namespace quantforge
