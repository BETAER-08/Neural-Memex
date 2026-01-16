import asyncio
import argparse
import logging
import sys

# [Performance] Performance Tuning: Activate uvloop if available
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    print("[Performance] uvloop active", file=sys.stderr)
except ImportError:
    print("[Performance] uvloop not found, using default asyncio loop", file=sys.stderr)

from src.ingestion import IngestionServer

def main():
    # [Usability] CLI Options via argparse
    parser = argparse.ArgumentParser(description="Neural-Memex High-Performance Ingestion Layer")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=9999, help="Bind port")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()

    # Configure Logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logger = logging.getLogger("main")
    logger.info(f"Starting Neural-Memex Ingestion on {args.host}:{args.port}")
    if args.debug:
        logger.info("Debug mode enabled")

    # Start Server
    server = IngestionServer(host=args.host, port=args.port)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == "__main__":
    main()
