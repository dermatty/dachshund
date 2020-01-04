#!/home/stephan/.virtualenvs/dh/bin/python
import urllib.request
from os.path import expanduser
import os
import sys
import configparser
import json
import urllib.parse
import email.utils
import time
from difflib import SequenceMatcher
from dachshund import fetch
import xml.etree.ElementTree as ET

SAMENESS_SEQU_SENS = 0.8
SAMENESS_AGE_SENS = 180
SAMENESS_LEN_SENS = 0.03


def truncate_middle(s, n):
    if len(s) <= n:
        # string is already short-enough
        s = s + " " * (n - len(s))
        return s
    # half of the size, minus the 3 .'s
    n_2 = int(int(n) / 2 - 3)
    # whatever's left
    n_1 = int(n - n_2 - 3)
    return '{0}...{1}'.format(s[:n_1], s[-n_2:])


def is_same(item1, item2):
    sequ_ratio = SequenceMatcher(None, item1["title"], item2["title"]).ratio()
    if sequ_ratio < SAMENESS_SEQU_SENS:
        return False, True
    age_diff = abs(item1["age"] - item2["age"])
    len_diff = abs(item1["length"] / item2["length"] - 1)
    is_same = False
    keepresult = True
    if age_diff < SAMENESS_AGE_SENS and len_diff < SAMENESS_LEN_SENS:
        is_same = True
        if item1["age"] < item2["age"]:
            keepresult = True
        else:
            keepresult = False
    return is_same, keepresult


class NewsSearchResult:
    def __init__(self, searchresultlist):
        self.searchresultlist = searchresultlist
        self.search2_result_raw = {}
        self.check_for_sameness_clearup()

    def check_for_sameness_clearup(self):
        searchresultlist2 = self.searchresultlist[:]
        res = []
        for s in self.searchresultlist:
            do_append = True
            for s2 in searchresultlist2:
                if s == s2:
                    continue
                issame, keepresult = is_same(s, s2)
                if issame and not keepresult:
                    do_append = False
                    break
            if do_append:
                res.append(s)
        # and sort by age
        res = sorted(res, key=lambda tup: tup["age"])

        self.searchresultlist = res

    def print_search_results(self):
        res = ""
        for i, s in enumerate(self.searchresultlist):
            nr = i + 1
            ell_nr = truncate_middle("[" + str(nr) + "]", 5)
            ell_title = truncate_middle(s["title"], 60)
            ell_idx = truncate_middle(s["indexer"], 12)
            ell_age = truncate_middle(str(s["age"]) + "d", 5)
            size = s["length"]
            if size < 1024:
                ell_size = str(size) + "B"
            elif size < 1024 * 1024:
                ell_size = int(size / 1024) + "K"
            elif size < 1024 * 1024 * 1024:
                ell_size = "%.1f" % (size / (1024 * 1024)) + "M"
            else:
                ell_size = "%.2f" % (size / (1024 * 1024 * 1024)) + "G"
            end = "\n" if nr < len(self.searchresultlist) else ""
            res += ell_nr + ell_idx + " " + ell_title + " / " + ell_age + " / " + ell_size + end
        return res


class Indexer:
    def __init__(self, name, url, apikey):
        self.name = name
        self.url = url
        self.apikey = apikey
        self.all_search_url = ""
        self.details_url = ""
        self.search1_result = None
        self.search1_list = []
        self.xmltree = None

    def build_all_search_url(self, qstr):
        self.all_search_url = self.url + "/api?t=search&apikey=" + self.apikey + "&q=" + qstr
        return self.all_search_url

    def build_details_url(self, qstr):
        self.details_url = self.url + "/api?t=details&apikey=" + self.apikey + "&id=" + qstr
        return self.details_url

    def get_xmltree_from_file(self, filename):
        self.xmltree = ET.parse(filename).getroot()
        return self.xmltree

    def analyze_search1(self):
        troot = self.xmltree
        # sort into list of dicts(per title)
        for item in troot.iter("item"):
            itemdict = {}
            itemdict["indexer"] = self.name
            itemdict["categories"] = []
            for d in item:
                if d.tag == "pubDate":
                    pubdate = d.text
                    itemdict["age"] = int((time.time() - time.mktime(email.utils.parsedate(pubdate)))/(3600*24))
                elif d.tag in ["title", "link", "guid", "category", "description", "comments"]:
                    itemdict[d.tag] = d.text
                elif d.tag == "enclosure":
                    enclosure = d.attrib
                    itemdict["url"] = enclosure["url"]
                    itemdict["length"] = int(enclosure["length"])
                    itemdict["type"] = enclosure["type"]
                elif "attributes/}attr" in d.tag:
                    if d.attrib["name"] == "size":
                        itemdict[d.attrib["name"]] = int(d.attrib["value"])
                    elif d.attrib["name"] == "category":
                        itemdict["categories"].append(d.attrib["value"])
                    else:
                        itemdict[d.attrib["name"]] = d.attrib["value"]
            # search for duplicates and remove older
            itemdict["guid"] = itemdict["guid"].split("details/")[-1]
            search_list1_copy = self.search1_list[:]
            keepresult = True
            for s in self.search1_list:
                issame, keepresult = is_same(itemdict, s)
                if issame and keepresult:
                    search_list1_copy.remove(s)
                elif issame and not keepresult:
                    break
            self.search1_list = search_list1_copy
            if keepresult:
                self.search1_list.append(itemdict)

    def search_2ndpass(self):
        if not self.search1_result:
            return None
        resultlist = []
        try:
            res_items = self.search1_result["channel"]["item"]
        except Exception:
            res_items = self.search1_result["item"]
        res_count = 0
        for r in res_items:
            result = {}
            title = r["title"]
            try:
                enclosure = r["enclosure"]["@attributes"]
                nzburl = enclosure["url"]
                length = int(enclosure["length"])
            except Exception:
                enclosure = r["enclosure"]
                nzburl = enclosure["_url"]
                length = int(enclosure["_length"])
            age = int((time.time() - time.mktime(email.utils.parsedate(r["pubDate"])))/(3600*24))

            # check for sameness
            resultlist_copy = resultlist[:]
            keepresult = True
            for r0 in resultlist:
                c = SequenceMatcher(None, title, r0["title"]).ratio()
                age_diff = abs(age - (r0["age"]))
                len_diff = abs(length / r0["length"] - 1)
                if c > 0.80 and age_diff < 180 and len_diff < 0.03:
                    if age < r0["age"]:
                        resultlist_copy.remove(r0)
                    else:
                        keepresult = False
            resultlist = resultlist_copy[:]
            if not keepresult:
                continue

            res_count += 1
            result["title"] = r["title"]
            result["age"] = int((time.time() - time.mktime(email.utils.parsedate(r["pubDate"])))/(3600*24))
            result["description"] = r["description"]
            result["nzburl"] = nzburl
            result["length"] = length

            try:
                # nzb.su
                attrs = r["attr"] 
                result["categorylist"] = []
                result["size"] = "-"
                result["guid"] = "-"
                result["hash"] = "-"
                for a in attrs:
                    a0 = a["@attributes"]
                    if a0["name"] == "category":
                        result["categorylist"].append(a0["value"])
                    if a0["name"] == "size":
                        result["size"] = int(a0["value"])
                    if a0["name"] == "guid":
                        result["guid"] = a0["value"]
                    if a0["name"] == "hash":
                        result["hash"] = a0["value"]
            except Exception:
                # drunkenslug
                attrs = r["newznab:attr"]
                result["categorylist"] = []
                result["size"] = "-"
                result["guid"] = "-"
                result["hash"] = "-"
                for a in attrs:
                    if a["_name"] == "category":
                        result["categorylist"].append(a["_value"])
                    if a["_name"] == "size":
                        result["size"] = int(a["_value"])
                result["guid"] = r["guid"]["text"].split("details/")[-1]
            resultlist.append(result)
        return res_count, resultlist


def read_config(cfg_file):
    try:
        cfg = configparser.ConfigParser()
        cfg.read(cfg_file)
    except Exception as e:
        print(str(e))
        return None
    idx = 1
    indexerdict = {}
    while True:
        try:
            idxstr = "INDEXER" + str(idx)
            idx_name = cfg[idxstr]["name"]
            idx_url = cfg[idxstr]["url"]
            idx_apikey = cfg[idxstr]["apikey"]
            indexer = Indexer(idx_name, idx_url, idx_apikey)
            indexerdict[idx_name] = indexer
        except Exception:
            break
        idx += 1
    return indexerdict


def run():
    install_dir = os.path.dirname(os.path.realpath(__file__))
    userhome = expanduser("~")
    maindir = userhome + "/.dachshund/"

    cfg_file = maindir + "dachshund.config"
    indexerdict = read_config(cfg_file)
    if not indexerdict:
        print("no indexers set up, exiting!")
        return -1

    # search and get xmltree
    qstr = "ubuntu 18"
    getfromfile = True

    if not getfromfile:
        fetch.fetch_all_indexers(indexerdict, qstr, maindir, writetofile=True)
    else:
        for idx_name, idx_obj in indexerdict.items():
            filename = maindir + idx_name + "_" + qstr + ".xml"
            idx_obj.get_xmltree_from_file(filename)

    # merge into ONE search result list (of dict)
    searchresult1 = []
    for idx_name, idx_obj in indexerdict.items():
        idx_obj.analyze_search1()
        searchresult1.extend(idx_obj.search1_list)
    nsr = NewsSearchResult(searchresult1)

    # now get details of details
    # fetch.fetch_all_guids(nsr, indexerdict)
    resstr = nsr.print_search_results()
    print(resstr)
    


    # print(treelist)

    #query_str = "ubuntu 18"
    #for indexer in indexerlist:
    #    indexer.search_firstpass(query_str)
    #    res1_count, results1 = indexer.search_2ndpass()
    #    print(indexer.name + ": " + str(res1_count) + " found!")
    #    for r in results1:
    #        length = str(int(r["length"] / (1024 * 1024))) + " MB"
    #        size0 = str(int(r["size"] / (1024 * 1024))) + " MB"
    #        print(r["title"] + "/ " + str(r["age"]) + " days" + " / " + length + " / " + size0)
    #    print("-" * 80)

    '''print("DETAILS")
    # http://servername.com/api?t=details&apikey=xxxxx&guid=xxxxxxxxx
    url2 = cfg["INDEXER"]["URL"] + "/api?t=details&apikey=" + cfg["INDEXER"]["APIKEY"] + "&o=json&id=" + attr_guid
    print(url2)
    hdr2 = {'User-Agent': 'Mozilla/5.0'}
    req2 = urllib.request.Request(url2, headers=hdr2)
    result2 = urllib.request.urlopen(req2).read()
    result2 = json.loads(result2)
    r1 = result2["channel"]["item"]
    title2 = r1["title"]
    link2 = r1["link"]
    guid2 = r1["guid"]
    comments2 = r1["comments"]
    pubdate2 = r1["pubDate"]
    category2 = r1["category"]
    description2 = r1["description"]
    enclosure2 = r1["enclosure"]["@attributes"]
    nzburl2 = enclosure2["url"]
    length2 = enclosure2["length"]
    attr_categorylist2 = []
    attr_size2 = "-"
    attr_guid2 = "-"
    attr_grabs2 ="0"
    attr_files2 = "-"
    attr_poster2 = "-"
    attr_group2 = "-"
    attr_usenetdate2 = "-"
    attr_comments2 = "-"
    attr_password2 = "-"
    for a11 in r1["attr"]:
        a0 = a11["@attributes"]
        if a0["name"] == "category":
            attr_categorylist2.append(a0["value"])
        if a0["name"] == "size":
            attr_size2 = a0["value"]
        if a0["name"] == "guid":
            attr_guid2 = a0["value"]
        if a0["name"] == "grabs":
            attr_grabs2 = a0["value"]
        if a0["name"] == "files":
            attr_files2 = a0["value"]
        if a0["name"] == "poster":
            attr_poster2 = a0["value"]
        if a0["name"] == "group":
            attr_group2 = a0["value"]
        if a0["name"] == "usenetdate":
            attr_usenetdate2 = a0["value"]
        if a0["name"] == "comments":
            attr_comments2 = a0["value"]
        if a0["name"] == "password":
            attr_password2 = a0["value"]
    print("Title:", title2)
    print("link:", link2)
    print("pubdate", pubdate2)
    print("category", category2)
    print("description:", description)
    print("Enclosure nzburl, length:", nzburl2, length2)
    print("Attr Categories:", attr_categorylist2)
    print("Attr Size:", attr_size2)
    print("Attr Guid:", attr_guid2)
    print("Attr Grabs:", attr_grabs2)
    print("Attr Files:", attr_files2)
    print("Attr Poster:", attr_poster2)
    print("Attr Group:", attr_group2)
    print("Attr usenetdate:", attr_usenetdate2)
    print("Attr Comments.", attr_comments2)
    print("Attr_password:", attr_password2)

    print("")
    t2 = int((time.time() - time.mktime(email.utils.parsedate(attr_usenetdate2)))/(3600*24))

    print("pub Age", t1)
    print("Use Age", t2)

    print("-" * 80)'''

    return 1
