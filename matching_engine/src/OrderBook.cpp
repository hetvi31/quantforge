#include "OrderBook.hpp"
#include <atomic>
#include <chrono>
#include <algorithm>
#include <iostream>
#include <limits>

namespace quantforge {

OrderBook::OrderBook(const std::string& symbol)
    : symbol_(symbol) {}

std::vector<Trade> OrderBook::addLimitOrder(Order order, std::vector<ExecutionReport>& reports) {
    // 1. Generate NEW report for the incoming order
    ExecutionReport new_report;
    new_report.order_id = order.id;
    new_report.symbol = symbol_;
    new_report.side = order.side;
    new_report.status = OrderStatus::NEW;
    new_report.price = order.price;
    new_report.last_quantity = 0;
    new_report.cumulative_quantity = 0;
    new_report.remaining_quantity = order.quantity;
    new_report.timestamp = order.timestamp > 0 ? order.timestamp : std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    reports.push_back(new_report);

    // 2. Perform matching
    std::vector<Trade> trades = matchOrder(order, reports);

    // 3. If remaining quantity > 0, insert into book
    if (order.remaining_quantity > 0) {
        if (order.side == OrderSide::BUY) {
            auto& order_list = bids_[order.price];
            order_list.push_back(order);
            auto it = std::prev(order_list.end());
            order_lookup_[order.id] = it;
            order_meta_[order.id] = OrderMeta{order.price, OrderSide::BUY};
        } else {
            auto& order_list = asks_[order.price];
            order_list.push_back(order);
            auto it = std::prev(order_list.end());
            order_lookup_[order.id] = it;
            order_meta_[order.id] = OrderMeta{order.price, OrderSide::SELL};
        }
    }

    return trades;
}

std::vector<Trade> OrderBook::addMarketOrder(Order order, std::vector<ExecutionReport>& reports) {
    // Market order must match immediately; set price thresholds to cross anything in the book.
    // A buy crosses any ask (max price), a sell crosses any bid (min price).
    order.price = (order.side == OrderSide::BUY)
        ? std::numeric_limits<PriceTicks>::max()
        : std::numeric_limits<PriceTicks>::min();

    ExecutionReport new_report;
    new_report.order_id = order.id;
    new_report.symbol = symbol_;
    new_report.side = order.side;
    new_report.status = OrderStatus::NEW;
    new_report.price = 0.0; // Market order has no limit price
    new_report.last_quantity = 0;
    new_report.cumulative_quantity = 0;
    new_report.remaining_quantity = order.quantity;
    new_report.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    reports.push_back(new_report);

    std::vector<Trade> trades = matchOrder(order, reports);

    // If remaining quantity > 0, we must cancel the remainder since market orders cannot rest in the book
    if (order.remaining_quantity > 0) {
        ExecutionReport cancel_report;
        cancel_report.order_id = order.id;
        cancel_report.symbol = symbol_;
        cancel_report.side = order.side;
        cancel_report.status = OrderStatus::CANCELLED;
        cancel_report.price = 0.0;
        cancel_report.last_quantity = 0;
        cancel_report.cumulative_quantity = order.quantity - order.remaining_quantity;
        cancel_report.remaining_quantity = 0;
        cancel_report.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        cancel_report.reject_reason = "Unfilled market order balance cancelled";
        reports.push_back(cancel_report);
    }

    return trades;
}

bool OrderBook::cancelOrder(uint64_t order_id, std::vector<ExecutionReport>& reports) {
    auto lookup_it = order_lookup_.find(order_id);
    if (lookup_it == order_lookup_.end()) {
        return false;
    }

    auto list_it = lookup_it->second;
    auto meta = order_meta_[order_id];

    // Create cancel report
    ExecutionReport cancel_report;
    cancel_report.order_id = order_id;
    cancel_report.symbol = symbol_;
    cancel_report.side = meta.side;
    cancel_report.status = OrderStatus::CANCELLED;
    cancel_report.price = list_it->price;
    cancel_report.last_quantity = 0;
    cancel_report.cumulative_quantity = list_it->quantity - list_it->remaining_quantity;
    cancel_report.remaining_quantity = 0;
    cancel_report.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    reports.push_back(cancel_report);

    // Remove from the book map
    if (meta.side == OrderSide::BUY) {
        auto bids_it = bids_.find(meta.price);
        if (bids_it != bids_.end()) {
            bids_it->second.erase(list_it);
            if (bids_it->second.empty()) {
                bids_.erase(bids_it);
            }
        }
    } else {
        auto asks_it = asks_.find(meta.price);
        if (asks_it != asks_.end()) {
            asks_it->second.erase(list_it);
            if (asks_it->second.empty()) {
                asks_.erase(asks_it);
            }
        }
    }

    // Clean up lookup maps
    order_lookup_.erase(lookup_it);
    order_meta_.erase(order_id);

    return true;
}

std::vector<Trade> OrderBook::matchOrder(Order& order, std::vector<ExecutionReport>& reports) {
    std::vector<Trade> trades;
    uint64_t now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    static std::atomic<uint64_t> global_trade_counter{0};

    if (order.side == OrderSide::BUY) {
        while (!asks_.empty() && order.remaining_quantity > 0) {
            auto best_ask_price = asks_.begin()->first;
            if (order.price < best_ask_price) {
                break; // Limit price not met
            }

            auto& ask_list = asks_.begin()->second;
            while (!ask_list.empty() && order.remaining_quantity > 0) {
                auto& book_order = ask_list.front();
                uint64_t match_qty = std::min(order.remaining_quantity, book_order.remaining_quantity);

                order.remaining_quantity -= match_qty;
                book_order.remaining_quantity -= match_qty;

                // Create Trade record
                Trade trade;
                trade.trade_id = symbol_ + "_" + std::to_string(now_ms) + "_" + std::to_string(++global_trade_counter);
                trade.buy_order_id = order.id;
                trade.sell_order_id = book_order.id;
                trade.symbol = symbol_;
                trade.price = best_ask_price; // Execute at resting limit price
                trade.quantity = match_qty;
                trade.timestamp = now_ms;
                trades.push_back(trade);

                // Report for book order (SELL)
                ExecutionReport book_report;
                book_report.order_id = book_order.id;
                book_report.symbol = symbol_;
                book_report.side = OrderSide::SELL;
                book_report.status = (book_order.remaining_quantity == 0) ? OrderStatus::FILLED : OrderStatus::PARTIALLY_FILLED;
                book_report.price = trade.price;
                book_report.last_quantity = match_qty;
                book_report.cumulative_quantity = book_order.quantity - book_order.remaining_quantity;
                book_report.remaining_quantity = book_order.remaining_quantity;
                book_report.timestamp = now_ms;
                reports.push_back(book_report);

                // Report for incoming order (BUY)
                ExecutionReport incoming_report;
                incoming_report.order_id = order.id;
                incoming_report.symbol = symbol_;
                incoming_report.side = OrderSide::BUY;
                incoming_report.status = (order.remaining_quantity == 0) ? OrderStatus::FILLED : OrderStatus::PARTIALLY_FILLED;
                incoming_report.price = trade.price;
                incoming_report.last_quantity = match_qty;
                incoming_report.cumulative_quantity = order.quantity - order.remaining_quantity;
                incoming_report.remaining_quantity = order.remaining_quantity;
                incoming_report.timestamp = now_ms;
                reports.push_back(incoming_report);

                if (book_order.remaining_quantity == 0) {
                    order_lookup_.erase(book_order.id);
                    order_meta_.erase(book_order.id);
                    ask_list.pop_front();
                }
            }

            if (ask_list.empty()) {
                asks_.erase(asks_.begin());
            }
        }
    } else { // SELL order
        while (!bids_.empty() && order.remaining_quantity > 0) {
            auto best_bid_price = bids_.begin()->first;
            if (order.price > best_bid_price) {
                break; // Limit price not met
            }

            auto& bid_list = bids_.begin()->second;
            while (!bid_list.empty() && order.remaining_quantity > 0) {
                auto& book_order = bid_list.front();
                uint64_t match_qty = std::min(order.remaining_quantity, book_order.remaining_quantity);

                order.remaining_quantity -= match_qty;
                book_order.remaining_quantity -= match_qty;

                // Create Trade record
                Trade trade;
                trade.trade_id = symbol_ + "_" + std::to_string(now_ms) + "_" + std::to_string(++global_trade_counter);
                trade.buy_order_id = book_order.id;
                trade.sell_order_id = order.id;
                trade.symbol = symbol_;
                trade.price = best_bid_price; // Execute at resting limit price
                trade.quantity = match_qty;
                trade.timestamp = now_ms;
                trades.push_back(trade);

                // Report for book order (BUY)
                ExecutionReport book_report;
                book_report.order_id = book_order.id;
                book_report.symbol = symbol_;
                book_report.side = OrderSide::BUY;
                book_report.status = (book_order.remaining_quantity == 0) ? OrderStatus::FILLED : OrderStatus::PARTIALLY_FILLED;
                book_report.price = trade.price;
                book_report.last_quantity = match_qty;
                book_report.cumulative_quantity = book_order.quantity - book_order.remaining_quantity;
                book_report.remaining_quantity = book_order.remaining_quantity;
                book_report.timestamp = now_ms;
                reports.push_back(book_report);

                // Report for incoming order (SELL)
                ExecutionReport incoming_report;
                incoming_report.order_id = order.id;
                incoming_report.symbol = symbol_;
                incoming_report.side = OrderSide::SELL;
                incoming_report.status = (order.remaining_quantity == 0) ? OrderStatus::FILLED : OrderStatus::PARTIALLY_FILLED;
                incoming_report.price = trade.price;
                incoming_report.last_quantity = match_qty;
                incoming_report.cumulative_quantity = order.quantity - order.remaining_quantity;
                incoming_report.remaining_quantity = order.remaining_quantity;
                incoming_report.timestamp = now_ms;
                reports.push_back(incoming_report);

                if (book_order.remaining_quantity == 0) {
                    order_lookup_.erase(book_order.id);
                    order_meta_.erase(book_order.id);
                    bid_list.pop_front();
                }
            }

            if (bid_list.empty()) {
                bids_.erase(bids_.begin());
            }
        }
    }

    return trades;
}

std::vector<std::pair<PriceTicks, uint64_t>> OrderBook::getBidsDepth() const {
    std::vector<std::pair<PriceTicks, uint64_t>> levels;
    for (const auto& [price, order_list] : bids_) {
        uint64_t total_qty = 0;
        for (const auto& order : order_list) {
            total_qty += order.remaining_quantity;
        }
        levels.push_back({price, total_qty});
    }
    return levels;
}

std::vector<std::pair<PriceTicks, uint64_t>> OrderBook::getAsksDepth() const {
    std::vector<std::pair<PriceTicks, uint64_t>> levels;
    for (const auto& [price, order_list] : asks_) {
        uint64_t total_qty = 0;
        for (const auto& order : order_list) {
            total_qty += order.remaining_quantity;
        }
        levels.push_back({price, total_qty});
    }
    return levels;
}

} // namespace quantforge
