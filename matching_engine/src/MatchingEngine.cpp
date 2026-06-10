#include "MatchingEngine.hpp"

namespace quantforge {

MatchingEngine::BookEntry& MatchingEngine::getOrCreateEntry(const std::string& symbol) {
    std::lock_guard<std::mutex> lock(registry_mutex_);
    auto it = books_.find(symbol);
    if (it == books_.end()) {
        auto entry = std::make_unique<BookEntry>();
        entry->book = std::make_unique<OrderBook>(symbol);
        BookEntry& ref = *entry;
        books_[symbol] = std::move(entry);
        return ref;
    }
    return *(it->second);
}

std::vector<Trade> MatchingEngine::submitOrder(const Order& order, std::vector<ExecutionReport>& reports) {
    BookEntry& entry = getOrCreateEntry(order.symbol);
    std::lock_guard<std::mutex> book_lock(entry.mtx);

    if (order.type == OrderType::MARKET) {
        return entry.book->addMarketOrder(order, reports);
    }
    return entry.book->addLimitOrder(order, reports);
}

bool MatchingEngine::cancelOrder(const std::string& symbol, uint64_t order_id, std::vector<ExecutionReport>& reports) {
    BookEntry* entry = nullptr;
    {
        std::lock_guard<std::mutex> lock(registry_mutex_);
        auto it = books_.find(symbol);
        if (it == books_.end()) {
            return false;
        }
        entry = it->second.get();
    }
    std::lock_guard<std::mutex> book_lock(entry->mtx);
    return entry->book->cancelOrder(order_id, reports);
}

std::vector<std::pair<PriceTicks, uint64_t>> MatchingEngine::getBidsDepth(const std::string& symbol) {
    BookEntry* entry = nullptr;
    {
        std::lock_guard<std::mutex> lock(registry_mutex_);
        auto it = books_.find(symbol);
        if (it == books_.end()) {
            return {};
        }
        entry = it->second.get();
    }
    std::lock_guard<std::mutex> book_lock(entry->mtx);
    return entry->book->getBidsDepth();
}

std::vector<std::pair<PriceTicks, uint64_t>> MatchingEngine::getAsksDepth(const std::string& symbol) {
    BookEntry* entry = nullptr;
    {
        std::lock_guard<std::mutex> lock(registry_mutex_);
        auto it = books_.find(symbol);
        if (it == books_.end()) {
            return {};
        }
        entry = it->second.get();
    }
    std::lock_guard<std::mutex> book_lock(entry->mtx);
    return entry->book->getAsksDepth();
}

} // namespace quantforge
