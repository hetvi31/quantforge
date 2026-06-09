import socket
import time
import struct
import random

# Tickers config
SYMBOLS = [b"BTCUSDT", b"ETHUSDT", b"SOLUSDT", b"NIFTY"]
PRICES = {
    b"BTCUSDT": 62000.00,
    b"ETHUSDT": 3100.00,
    b"SOLUSDT": 150.00,
    b"NIFTY": 22500.00
}

def run_simulator(host="localhost", port=9002):
    print(f"[Simulator] Starting Market Simulator sending to {host}:{port} via UDP...")
    
    # Resolve host
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        ip = "127.0.0.1"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Struct format: 16s (symbol), d (price), Q (qty), Q (timestamp), c (side)
    # Total size = 16 + 8 + 8 + 8 + 1 = 41 bytes
    struct_format = "<16sdQQc"
    
    while True:
        # Choose a random symbol
        symbol = random.choice(SYMBOLS)
        base_price = PRICES[symbol]
        
        # Fluctuate price slightly
        change_pct = random.uniform(-0.001, 0.001)
        base_price *= (1 + change_pct)
        PRICES[symbol] = base_price
        
        qty = random.randint(1, 15)
        timestamp = int(time.time() * 1000)
        side = random.choice([b'B', b'A'])
        
        # Pack the binary packet
        packet = struct.pack(
            struct_format,
            symbol,
            base_price,
            qty,
            timestamp,
            side
        )
        
        # Send via UDP
        try:
            sock.sendto(packet, (ip, port))
        except Exception as e:
            print(f"[Simulator] Socket Send Error: {e}")
            
        time.sleep(0.05) # 20 events per second

if __name__ == "__main__":
    import sys
    target_host = "localhost"
    if len(sys.argv) > 1:
        target_host = sys.argv[1]
    run_simulator(host=target_host)
