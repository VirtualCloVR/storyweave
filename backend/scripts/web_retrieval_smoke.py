import asyncio

from app.web import search_and_fetch


async def main() -> None:
    results = await search_and_fetch("日本 交通事故 事故類型 統計 警察庁")
    for result in results:
        print(f"provider={result.provider} url={result.url} chars={len(result.text)}")
    if not results:
        raise SystemExit("No web page body could be retrieved")


if __name__ == "__main__":
    asyncio.run(main())
