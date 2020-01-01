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

install_dir = os.path.dirname(os.path.realpath(__file__))
userhome = expanduser("~")
maindir = userhome + "/.dachshund/"

# check for maindir
'''if not os.path.exists(maindir):
    try:
        os.mkdir(maindir)
    except Exception as e:
        print(str(e))
        sys.exit()'''

try:
    cfg_file = maindir + "dachshund.config"
    cfg = configparser.ConfigParser()
    cfg.read(cfg_file)
except Exception as e:
    print(str(e))
    sys.exit()

searchstr = "ubuntu 18"
searchstr = urllib.parse.quote(searchstr)
url = cfg["INDEXER"]["URL"] + "/api?t=search&apikey=" + cfg["INDEXER"]["APIKEY"] + "&o=json&q=" + searchstr

# url = "https://www.nzb.su/api?t=search&apikey=15f358c78ddf57aa0557ef5dd4b9157a&o=json&q=ubuntu"
print(url)
RESULTLIST = []
hdr = {'User-Agent': 'Mozilla/5.0'}
req = urllib.request.Request(url, headers=hdr)
result = urllib.request.urlopen(req).read()
result = json.loads(result)

nr_results = result["channel"]["response"]["@attributes"]["total"]

print(nr_results + " results found")
res_items = result["channel"]["item"]
i = 1
for r in res_items:
    print("### RESULT #" + str(i))
    i += 1
    title = r["title"]
    link = r["link"]
    guid = r["guid"]
    comments = r["comments"]
    pubdate = r["pubDate"]
    category = r["category"]
    description = r["description"]
    t1 = int((time.time() - time.mktime(email.utils.parsedate(pubdate)))/(3600*24))
    title_in_resultlist = len([(ti0, t10) for ti0, t10 in RESULTLIST if ti0 == title]) > 0
    if title_in_resultlist:
        print("------- GIBTS SCHON -------")
    RESULTLIST.append((title, t1))

    enclosure = r["enclosure"]["@attributes"]
    nzburl = enclosure["url"]
    length = enclosure["length"]

    attr_categorylist = []
    attr_size = "-"
    attr_guid = "-"
    for a in r["attr"]:
        a0 = a["@attributes"]
        if a0["name"] == "category":
            attr_categorylist.append(a0["value"])
        if a0["name"] == "size":
            attr_size = a0["value"]
        if a0["name"] == "guid":
            attr_guid = a0["value"]
    
    print("Title:", title)
    print("link:", link)
    print("pubdate", pubdate)
    print("category", category)
    print("guid", guid)
    print("description:", description)
    print("Enclosure nzburl, length:", nzburl, length)
    print("category - size - guid")
    print(str(attr_categorylist) + " - " + attr_size + " + " + attr_guid)
    print("")

    print("DETAILS")
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

    print("-" * 80)


