import argparse
import asyncio
import signal


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def handle(client_reader, client_writer, target_host: str, target_port: int):
    target_reader, target_writer = await asyncio.open_connection(target_host, target_port)
    await asyncio.gather(
        pipe(client_reader, target_writer),
        pipe(target_reader, client_writer),
    )


async def main():
    parser = argparse.ArgumentParser(description="Host TCP bridge for VM-facing port exposure.")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=int, required=True)
    args = parser.parse_args()

    server = await asyncio.start_server(
        lambda reader, writer: handle(reader, writer, args.target_host, args.target_port),
        args.listen_host,
        args.listen_port,
    )

    stop_event = asyncio.Event()

    def stop(*_args):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop)
        except NotImplementedError:
            pass

    async with server:
        await stop_event.wait()


if __name__ == "__main__":
    asyncio.run(main())
