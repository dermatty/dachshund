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


class Indexer:
    def __init__(self, name, url, apikey):
        self.name = name
        self.url = url
        self.apikey = apikey
        self.all_search_url = ""
        self.details_url = ""
        self.search1_result = None
        self.search2_result = None

    def build_all_search_url(self, qstr):
        # self.all_search_url = self.url + "/api?t=search&apikey=" + self.apikey + "&o=json&q=" + qstr
        self.all_search_url = self.url + "/api?t=search&apikey=" + self.apikey + "&q=" + qstr
        return self.all_search_url

    def build_details_url(self, qstr):
        # self.details_url = self.url + "/api?t=details&apikey=" + self.apikey + "&o=json&id=" + qstr
        self.details_url = self.url + "/api?t=details&apikey=" + self.apikey + "&id=" + qstr
        return self.details_url

    def search_firstpass(self, session, querystr):
        querystr_rfc = urllib.parse.quote(querystr)
        url = self.search_url + querystr_rfc
        # req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        # result = urllib.request.urlopen(req).read()
        #async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as response:
        #    self.search1_result = await response.read()
        # self.search1_result = json.loads(result)

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
    indexerlist = []
    while True:
        try:
            idxstr = "INDEXER" + str(idx)
            idx_name = cfg[idxstr]["name"]
            idx_url = cfg[idxstr]["url"]
            idx_apikey = cfg[idxstr]["apikey"]
            indexer = Indexer(idx_name, idx_url, idx_apikey)
            indexerlist.append(indexer)
        except Exception:
            break
        idx += 1
    return indexerlist


def run():
    install_dir = os.path.dirname(os.path.realpath(__file__))
    userhome = expanduser("~")
    maindir = userhome + "/.dachshund/"

    cfg_file = maindir + "dachshund.config"
    indexerlist = read_config(cfg_file)
    if not indexerlist:
        print("no indexers set up, exiting!")
        return -1

    qstr = "ubuntu 18"
    getfromfile = True
    filedic = {}
    treelist = []
    for idx in indexerlist:
        filedic[idx.name] = maindir + idx.name + "_" + qstr + ".xml"

    if not getfromfile:
        print("downloading xml results ...")
        qstr0 = qstr[:]
        full_res, short_res = fetch.fetch_all_indexers(indexerlist, qstr0)
        for f, s in zip(full_res, short_res):
            idx, res = f
            if res:
                with open(filedic[idx], "wb") as xmlfile:
                    xmlfile.write(res)
                treelist.append((idx, ET.fromstring(res)))
    else:
        print("getting xml results from files ...")
        treelist = []
        for idx, f in filedic.items():
            treelist.append((idx, ET.parse(f).getroot()))

    for tidx, troot in treelist:
        print(tidx)
        print(troot)
        print(troot.tag, troot.attrib)
        for item in troot.iter("item"):
            print("***", item.tag)
            for d in item:
                if d.tag in ["title", "link", "pubDate", "guid", "category", "description", "comments"]:
                    print("-->", d.tag + " - " + d.text)
                elif d.tag == "enclosure":
                    enclosure = d.attrib
                    print("--> enclosure:")
                    print("          url: " + enclosure["url"])
                    print("       length: " + enclosure["length"])
                    print("         type: " + enclosure["type"])
                elif "attributes/}attr" in d.tag:
                    print("--> attributes:")
                    for key, elem in d.attrib.items():
                        print("            ", key, elem)
                    # print("          size")"+ " - " + str(d.attrib))
        print("-" * 100)
            
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
