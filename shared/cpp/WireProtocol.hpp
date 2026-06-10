#pragma once

// =============================================================================
// QuantForge binary wire protocol  (single source of truth for the C++ side)
// -----------------------------------------------------------------------------
// The Python gateway mirrors these exact layouts in gateway/app/protocol.py.
// Any change here MUST be reflected there. Both sides are little-endian and use
// 1-byte struct packing so the layout is identical on the wire.
//
// Prices are transmitted as INTEGER TICKS (fixed-point), never floating point.
// A tick is 1 / PRICE_SCALE of one quote-currency unit. With PRICE_SCALE = 100
// the smallest representable increment is one cent. This removes floating-point
// rounding from the matching path and lets prices be exact map keys.
// =============================================================================

#include <cstdint>

namespace quantforge::wire {

// Fixed-point scale for on-the-wire prices.
inline constexpr int64_t PRICE_SCALE = 100;

// Action byte carried in RawOrder.action.
enum class Action : char {
    NEW_LIMIT  = 'L',
    NEW_MARKET = 'M',
    CANCEL     = 'C',
};

#pragma pack(push, 1)

// Gateway -> Matching engine.  Python: "<Q16sccqQ"
struct RawOrder {
    uint64_t id;            // gateway-assigned order id
    char     symbol[16];    // ASCII, NUL-padded (NOT guaranteed NUL-terminated)
    char     side;          // 'B' (buy) or 'S' (sell)
    char     action;        // Action: 'L' limit, 'M' market, 'C' cancel
    int64_t  price_ticks;   // price in ticks (ignored for market / cancel)
    uint64_t quantity;      // order size (0 for cancel)
};

// Matching engine -> Gateway.  Python: "<Q16sccqQQQQ64s"
struct RawExecutionReport {
    uint64_t order_id;
    char     symbol[16];
    char     side;                 // 'B' or 'S'
    char     status;               // 'N','P','F','C','R'
    int64_t  price_ticks;
    uint64_t last_quantity;
    uint64_t cumulative_quantity;
    uint64_t remaining_quantity;
    uint64_t timestamp;            // engine epoch millis
    char     reject_reason[64];
};

#pragma pack(pop)

} // namespace quantforge::wire
