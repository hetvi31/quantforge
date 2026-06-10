// =============================================================================
// QuantForge matching-engine micro-benchmark.
// -----------------------------------------------------------------------------
// Measures in-process order-submission latency (no network) so the project can
// cite a REAL, reproducible number instead of a hand-waved one. Build in Release
// (-O3) and run:  ./bin/bench_matching [num_orders]
// =============================================================================

#include "MatchingEngine.hpp"
#include "WireProtocol.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <random>
#include <vector>

using namespace quantforge;

int main(int argc, char** argv) {
    const size_t N = (argc > 1) ? std::stoul(argv[1]) : 1'000'000;

    MatchingEngine engine;
    std::mt19937_64 rng(42);
    // Two-sided quotes around 50,000.00 so orders both rest and match.
    std::uniform_int_distribution<int64_t> price_dist(
        static_cast<int64_t>(49900.0 * wire::PRICE_SCALE),
        static_cast<int64_t>(50100.0 * wire::PRICE_SCALE));
    std::uniform_int_distribution<uint64_t> qty_dist(1, 10);
    std::bernoulli_distribution buy_dist(0.5);

    std::vector<uint64_t> latencies_ns;
    latencies_ns.reserve(N);

    std::vector<ExecutionReport> reports;
    reports.reserve(16);

    for (size_t i = 0; i < N; ++i) {
        Order order;
        order.id = i + 1;
        order.symbol = "BTCUSDT";
        order.side = buy_dist(rng) ? OrderSide::BUY : OrderSide::SELL;
        order.type = OrderType::LIMIT;
        order.price = price_dist(rng);
        order.quantity = qty_dist(rng);
        order.remaining_quantity = order.quantity;
        order.timestamp = 0;

        reports.clear();
        auto t0 = std::chrono::steady_clock::now();
        engine.submitOrder(order, reports);
        auto t1 = std::chrono::steady_clock::now();
        latencies_ns.push_back(
            std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count());
    }

    std::sort(latencies_ns.begin(), latencies_ns.end());
    auto pct = [&](double p) {
        size_t idx = static_cast<size_t>(p * (latencies_ns.size() - 1));
        return latencies_ns[idx];
    };
    uint64_t sum = 0;
    for (auto v : latencies_ns) sum += v;

    std::cout << "QuantForge matching-engine benchmark\n"
              << "  orders submitted : " << N << "\n"
              << "  mean             : " << (sum / latencies_ns.size()) << " ns\n"
              << "  p50              : " << pct(0.50) << " ns\n"
              << "  p99              : " << pct(0.99) << " ns\n"
              << "  p99.9            : " << pct(0.999) << " ns\n"
              << "  max              : " << latencies_ns.back() << " ns\n"
              << "  throughput       : "
              << static_cast<uint64_t>(latencies_ns.size() / (sum / 1e9)) << " orders/sec\n";
    return 0;
}
