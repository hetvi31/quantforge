#include "OrderBook.hpp"
#include "WireProtocol.hpp"
#include <iostream>
#include <cassert>

using namespace quantforge;

// Helper: convert a decimal price to integer ticks for test readability.
static constexpr PriceTicks T(double price) {
    return static_cast<PriceTicks>(price * wire::PRICE_SCALE + (price < 0 ? -0.5 : 0.5));
}

void testLimitOrderMatching() {
    std::cout << "[Test] Running testLimitOrderMatching..." << std::endl;
    OrderBook book("BTCUSDT");
    std::vector<ExecutionReport> reports;

    // 1. Submit a sell limit order: 10 BTC at 50,000
    Order sell_order1{1, "BTCUSDT", OrderSide::SELL, OrderType::LIMIT, T(50000.0), 10, 10, 0};
    auto trades = book.addLimitOrder(sell_order1, reports);
    assert(trades.empty());
    assert(reports.size() == 1);
    assert(reports[0].status == OrderStatus::NEW);
    assert(reports[0].remaining_quantity == 10);
    reports.clear();

    // 2. Submit a buy limit order: 5 BTC at 49,900 (should not match, resting in book)
    Order buy_order1{2, "BTCUSDT", OrderSide::BUY, OrderType::LIMIT, T(49900.0), 5, 5, 0};
    trades = book.addLimitOrder(buy_order1, reports);
    assert(trades.empty());
    assert(reports.size() == 1);
    assert(reports[0].status == OrderStatus::NEW);
    reports.clear();

    // 3. Submit a buy limit order: 12 BTC at 50,000 (should match 10 BTC at 50,000, 2 BTC remains resting)
    Order buy_order2{3, "BTCUSDT", OrderSide::BUY, OrderType::LIMIT, T(50000.0), 12, 12, 0};
    trades = book.addLimitOrder(buy_order2, reports);
    assert(trades.size() == 1);
    assert(trades[0].price == T(50000.0));
    assert(trades[0].quantity == 10);
    assert(trades[0].buy_order_id == 3);
    assert(trades[0].sell_order_id == 1);

    // There should be 3 reports:
    // Report 1: Buy order 3 is NEW
    // Report 2: Sell order 1 is FILLED (book order)
    // Report 3: Buy order 3 is PARTIALLY_FILLED (incoming order)
    assert(reports.size() == 3);
    assert(reports[0].order_id == 3 && reports[0].status == OrderStatus::NEW);
    assert(reports[1].order_id == 1 && reports[1].status == OrderStatus::FILLED);
    assert(reports[2].order_id == 3 && reports[2].status == OrderStatus::PARTIALLY_FILLED);
    assert(reports[2].remaining_quantity == 2);
    reports.clear();

    std::cout << "[Test] testLimitOrderMatching PASSED!" << std::endl;
}

void testFIFOAndPricePriority() {
    std::cout << "[Test] Running testFIFOAndPricePriority..." << std::endl;
    OrderBook book("ETHUSDT");
    std::vector<ExecutionReport> reports;

    // Sell orders:
    // Order 1: 5 ETH at 3,000 (submitted first)
    // Order 2: 5 ETH at 3,000 (submitted second, same price)
    // Order 3: 5 ETH at 2,990 (submitted third, lower price)
    Order s1{101, "ETHUSDT", OrderSide::SELL, OrderType::LIMIT, T(3000.0), 5, 5, 0};
    Order s2{102, "ETHUSDT", OrderSide::SELL, OrderType::LIMIT, T(3000.0), 5, 5, 0};
    Order s3{103, "ETHUSDT", OrderSide::SELL, OrderType::LIMIT, T(2990.0), 5, 5, 0};

    book.addLimitOrder(s1, reports);
    book.addLimitOrder(s2, reports);
    book.addLimitOrder(s3, reports);
    reports.clear();

    // Submit a Buy Limit Order: 12 ETH at 3,010
    // Price Priority: Should match Order 3 first (2,990 is cheaper than 3,000)
    // FIFO Priority: Should match Order 1 second (submitted before Order 2 at same price)
    // Total matched: 5 ETH from s3, 5 ETH from s1, 2 ETH from s2
    Order b1{201, "ETHUSDT", OrderSide::BUY, OrderType::LIMIT, T(3010.0), 12, 12, 0};
    auto trades = book.addLimitOrder(b1, reports);

    assert(trades.size() == 3);
    // First match: Order 103 (s3)
    assert(trades[0].sell_order_id == 103 && trades[0].price == T(2990.0) && trades[0].quantity == 5);
    // Second match: Order 101 (s1)
    assert(trades[1].sell_order_id == 101 && trades[1].price == T(3000.0) && trades[1].quantity == 5);
    // Third match: Order 102 (s2)
    assert(trades[2].sell_order_id == 102 && trades[2].price == T(3000.0) && trades[2].quantity == 2);

    std::cout << "[Test] testFIFOAndPricePriority PASSED!" << std::endl;
}

void testOrderCancellation() {
    std::cout << "[Test] Running testOrderCancellation..." << std::endl;
    OrderBook book("SOLUSDT");
    std::vector<ExecutionReport> reports;

    Order s1{301, "SOLUSDT", OrderSide::SELL, OrderType::LIMIT, T(150.0), 10, 10, 0};
    book.addLimitOrder(s1, reports);
    reports.clear();

    // Cancel the order
    bool cancelled = book.cancelOrder(301, reports);
    assert(cancelled);
    assert(reports.size() == 1);
    assert(reports[0].status == OrderStatus::CANCELLED);
    assert(reports[0].order_id == 301);
    reports.clear();

    // Try to match against it (should fail since it's cancelled)
    Order b1{302, "SOLUSDT", OrderSide::BUY, OrderType::LIMIT, T(150.0), 10, 10, 0};
    auto trades = book.addLimitOrder(b1, reports);
    assert(trades.empty());

    std::cout << "[Test] testOrderCancellation PASSED!" << std::endl;
}

void testMarketOrderSweepsBook() {
    std::cout << "[Test] Running testMarketOrderSweepsBook..." << std::endl;
    OrderBook book("BTCUSDT");
    std::vector<ExecutionReport> reports;

    // Rest two asks at different prices.
    Order a1{401, "BTCUSDT", OrderSide::SELL, OrderType::LIMIT, T(50000.0), 3, 3, 0};
    Order a2{402, "BTCUSDT", OrderSide::SELL, OrderType::LIMIT, T(50100.0), 3, 3, 0};
    book.addLimitOrder(a1, reports);
    book.addLimitOrder(a2, reports);
    reports.clear();

    // Market buy 4 should sweep best price first (3 @ 50000) then 1 @ 50100.
    Order m{403, "BTCUSDT", OrderSide::BUY, OrderType::MARKET, 0, 4, 4, 0};
    auto trades = book.addMarketOrder(m, reports);
    assert(trades.size() == 2);
    assert(trades[0].price == T(50000.0) && trades[0].quantity == 3);
    assert(trades[1].price == T(50100.0) && trades[1].quantity == 1);

    std::cout << "[Test] testMarketOrderSweepsBook PASSED!" << std::endl;
}

int main() {
    testLimitOrderMatching();
    testFIFOAndPricePriority();
    testOrderCancellation();
    testMarketOrderSweepsBook();
    std::cout << "[Test] All C++ OrderBook unit tests passed successfully!" << std::endl;
    return 0;
}
