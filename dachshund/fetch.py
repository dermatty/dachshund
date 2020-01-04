import asyncio 
import aiohttp


async def fetch_url(session, idx, url):
    try:
        async with session.get(url) as response:
            res = await response.read()
            return idx, res
    except Exception:
        return idx, None


async def fetch_all_urls(urllist):
    tasks = []
    async with aiohttp.ClientSession() as session:
        for idx, url in urllist:
            dl = fetch_url(session, idx, url)
            tasks.append(asyncio.create_task(dl))
        responses = await asyncio.gather(*tasks)
    return responses


def fetch_all_indexers(indexerlist, qstr):
    if not indexerlist or not qstr:
        return None
    urllist = []
    for idx in indexerlist:
        urllist.append((idx.name, idx.build_all_search_url(qstr)))
    full_res = asyncio.get_event_loop().run_until_complete(fetch_all_urls(urllist))
    short_res = [(idx, True) if res else (idx, False) for idx, res in full_res]
    return full_res, short_res
