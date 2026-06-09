#include "MatchingEngine.hpp"

namespace quantforge {

OrderBook& MatchingEngine::getOrCreateOrderBook(const std::string& symbol) {
    auto it = order_books_.find(symbol);
    if (it == order_books_.end()) {
        auto book = std::make_unique<OrderBook>(symbol);
        OrderBook& book_ref = *book;
        order_books_[symbol] = std::move(book);
        return book_ref;
    }
    return *(it->second);
}

std::vector<Trade> MatchingEngine::submitOrder(const Order& order, std::vector<ExecutionReport>& reports) {
    std::lock_guard<std::mutex> lock(engine_mutex_);
    OrderBook& book = getOrCreateOrderBook(order.symbol);
    
    if (order.type == OrderType::MARKET) {
        return book.addMarketOrder(order, reports);
    } else {
        return book.addLimitOrder(order, reports);
    }
}

bool MatchingEngine::cancelOrder(const std::string& symbol, uint64_t order_id, std::vector<ExecutionReport>& reports) {
    std::lock_guard<std::mutex> lock(engine_mutex_);
    auto it = order_books_.find(symbol);
    if (it == order_books_.end()) {
        return false;
    }
    return it->second->cancelOrder(order_id, reports);
}

std::vector<std::pair<double, uint64_t>> MatchingEngine::getBidsDepth(const std::string& symbol) {
    std::lock_guard<std::mutex> lock(engine_mutex_);
    auto it = order_books_.find(symbol);
    if (it == order_books_.end()) {
        return {};
    }
    return it->second->getBidsDepth();
}

std::vector<std::pair<double, uint64_t>> MatchingEngine::getAsksDepth(const std::string& symbol) {
    std::lock_guard<std::mutex> lock(engine_mutex_);
    auto it = order_books_.find(symbol);
    if (it == order_books_.end()) {
        return {};
    }
    return it->second->getAsksDepth();
}

} // namespace quantforge
