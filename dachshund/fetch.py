from threading import Thread
import xml.etree.ElementTree as ET
import urllib


class FetchThread(Thread):
    def __init__(self, idx, url):
        Thread.__init__(self)
        self.idx = idx
        self.url = url
        self.result = None

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) '})
            self.result = urllib.request.urlopen(req).read()
        except Exception:
            self.result = None


def tfetch_all_urls(urllist):
    try:
        tasks = []
        responses = []
        for idx, url in urllist:
            fetchthread = FetchThread(idx, url)
            tasks.append(fetchthread)
            fetchthread.start()
        for fetchthread in tasks:
            fetchthread.join()
            responses.append((fetchthread.idx, fetchthread.url, fetchthread.result))
    except Exception as e:
        print(str(e))
    return responses


def tfetch_all_indexers(indexerdict, qstr, maindir, writetofile=True):
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

    full_res = tfetch_all_urls(urllist)

    for idx, url, res in full_res:
        if res:
            indexerdict[idx].search1_result = res
            indexerdict[idx].xmltree = ET.fromstring(res)
        else:
            indexerdict[idx].search1_result = None
            indexerdict[idx].xmltree = None
