import asyncio 
import aiohttp
import xml.etree.ElementTree as ET
import urllib


async def fetch_url(session, idx, url):
    try:
        async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            res = await response.read()
            return idx, url, res
    except Exception as e:
        # print("****", str(e), idx)
        return idx, url, None


async def fetch_all_urls(urllist):
    tasks = []
    async with aiohttp.ClientSession() as session:
        for idx, url in urllist:
            dl = fetch_url(session, idx, url)
            tasks.append(asyncio.create_task(dl))
        responses = await asyncio.gather(*tasks)
    return responses


def fetch_all_indexers(indexerdict, qstr, maindir, writetofile=True):
    if not indexerdict or not qstr:
        return None
    urllist = []
    for idx, idx_obj in indexerdict.items():
        indexerdict[idx].search1_result = None
        indexerdict[idx].xmltree = None
        indexerdict[idx].search1_list = []
        qstr0 = qstr[:]
        qstr0_rfc = urllib.parse.quote(qstr0)
        urllist.append((idx, idx_obj.build_all_search_url(qstr0_rfc)))
    full_res = asyncio.get_event_loop().run_until_complete(fetch_all_urls(urllist))
    for idx, url, res in full_res:
        indexerdict[idx].search1_result = res
        indexerdict[idx].xmltree = ET.fromstring(res)
        # for dev write xmltree to file
        if writetofile:
            filename = maindir + idx + "_" + qstr + ".xml"
            with open(filename, "wb") as xmlfile:
                xmlfile.write(res)


def fetch_all_guids(nsr, indexerdict):
    urllist = []
    for s in nsr.searchresultlist:
        idx_name = s["indexer"]
        idx_obj = indexerdict[idx_name]
        url = idx_obj.build_details_url(s["guid"])
        #print(url)
        urllist.append((idx_name, url))
    finished = False
    i = 1
    while not finished:
        full_res = asyncio.get_event_loop().run_until_complete(fetch_all_urls(urllist))
        newurllist = []
        for idx, url, res in full_res:
            if not res:
                newurllist.append((idx, url))
        if newurllist:
            urllist = newurllist
        else:
            finished = True
        i += 1
        if i > 5:
            break

    for idx, url, res in full_res:
        print(idx)
        if res:
            nsr.search2_result_raw[idx] = ET.fromstring(res)
        else:
            nsr.search2_result_raw[idx] = None
