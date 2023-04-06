#!/home/stephan/.virtualenvs/dh/bin/python
from os.path import expanduser
import re
import configparser
import email.utils
import time
from furl import furl
from dachshund import fetch, nzbget_status, is_same, make_pretty_bytes, truncate_middle, nzbget_history,\
    nzbget_getbyid
import xml.etree.ElementTree as ET
import xmlrpc.client
from telegram import Bot
import telegram.error
import json
import asyncio
import shutil
import logging
import logging.handlers

__version__ = "1.1"
global tgbd
global TERMINATED


class DHException(Exception):
    pass


class TelegramBotData:
    def __init__(self, cfg_file, maindir, logger):
        try:
            self.logger = logger
            self.cfg_file = cfg_file
            self.indexerdict, self.cfg = read_config(self.cfg_file, logger)
            self.maindir = maindir
            self.running = False
            self.token = self.cfg["TELEGRAM"]["TOKEN"]
            self.furl = furl()
            self.furl.host = self.cfg["NZBGET"]["HOST"]
            self.furl.scheme = "http"
            self.furl.port = int(self.cfg["NZBGET"]["PORT"])
            self.furl.username = self.cfg["NZBGET"]["USERNAME"]
            self.furl.password = self.cfg["NZBGET"]["PASSWORD"]
            self.furl.path.add("xmlrpc")
            self.chatids = json.loads(self.cfg.get("TELEGRAM", "CHATIDS"))
            self.motd = 'd <nr>: details / dl <nr>: download nzb / l: list / s "...": search\n'
            self.motd += "t: toggle search / e!: exit / st: nzbget status / h history\n"
            self.motd += "c <nzbid> eltern/kinder <newname>: copy to plex\n"
            self.initok = True
            self.nsr = None
            self.errstr = ""
        except Exception as e:
            self.initok = False
            self.errstr = str(e)


class NewsSearchResult:
    def __init__(self, searchresultlist, maindir, logger):
        self.logger = logger
        self.searchresultlist = searchresultlist
        self.maindir = maindir
        self.search2_result_raw = {}
        # 1 .. by age asc.
        # 2 .. by age desc.
        # 3 .. by size asc.
        # 4 .. by size desc.
        # 5 .. by indexer
        # 6 .. by title
        self.sort_toggle = 1
        self.rcodelist = []
        self.check_for_sameness_clearup()

    def sort_search_results(self):
        if self.sort_toggle == 1:
            self.searchresultlist = sorted(self.searchresultlist, key=lambda tup: tup["age"])
        elif self.sort_toggle == 2:
            self.searchresultlist = sorted(self.searchresultlist, key=lambda tup: tup["age"], reverse=True)
        elif self.sort_toggle == 3:
            self.searchresultlist = sorted(self.searchresultlist, key=lambda tup: tup["length"])
        elif self.sort_toggle == 4:
            self.searchresultlist = sorted(self.searchresultlist, key=lambda tup: tup["length"], reverse=True)
        elif self.sort_toggle == 5:
            self.searchresultlist = sorted(self.searchresultlist, key=lambda tup: tup["indexer"])
        elif self.sort_toggle == 6:
            self.searchresultlist = sorted(self.searchresultlist, key=lambda tup: tup["title"])

    def toggle_sort(self):
        self.sort_toggle = self.sort_toggle + 1
        if self.sort_toggle > 6:
            self.sort_toggle = 1
        self.sort_search_results()
        return self.print_search_results()

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
        self.searchresultlist = res[:]
        try:
            self.sort_search_results()
        except Exception as e:
            self.logger.error(str(e) + ": error in check_for_sameness_clearup")

    def nzb_details(self, nzbnr0):
        try:
            nzbnr = int(nzbnr0)
        except Exception:
            return None
        if nzbnr < 1 or nzbnr > len(self.searchresultlist):
            return -1
        nzb = self.searchresultlist[nzbnr-1]
        return (nzb["title"])

    def download_nzb(self, nzbnr0, furl):
        try:
            nzbnr = int(nzbnr0)
        except Exception as e:
            self.logger.error(str(e) + ": error in getting NZBID!")
            return ""
        if nzbnr < 1 or nzbnr > len(self.searchresultlist):
            return ""
        nzb = self.searchresultlist[nzbnr-1]
        f = furl
        try:
            title = nzb["title"]
            rpc = xmlrpc.client.ServerProxy(f.tostr())
            if not nzb["title"].endswith(".nzb"):
                title += ".nzb"
            rcode = rpc.append(title, nzb["url"], "", 0, False, False, "", 0, "SCORE", [])
            self.rcodelist.append((nzb["title"], rcode))
            self.logger.info("Downloading " + nzb["title"])
            return nzb["title"]
        except Exception as e:
            self.logger.error(str(e) + ": error in downloading NZB!")
            return ""

    def print_search_results(self, maxage=0, maxnr=0):
        ell_nr = "#"
        ell_title = "NZB NAME"
        ell_idx = "INDEXER"
        ell_age = "AGE"
        ell_size = "SIZE"
        if self.sort_toggle == 1:
            ell_age += ">"
        elif self.sort_toggle == 2:
            ell_age += "<"
        elif self.sort_toggle == 3:
            ell_size += ">"
        elif self.sort_toggle == 4:
            ell_size += "<"
        elif self.sort_toggle == 5:
            ell_idx += ">"
        elif self.sort_toggle == 6:
            ell_title += ">"
        ell_nr = truncate_middle(ell_nr, 5)
        ell_title = truncate_middle(ell_title, 40)
        ell_idx = truncate_middle(ell_idx, 12)
        ell_age = truncate_middle(ell_age, 5)
        res = ell_nr + ell_idx + " " + ell_title + " / " + ell_age + " / " + ell_size
        for i, s in enumerate(self.searchresultlist):
            nr = i + 1
            if 0 < maxnr < nr:
                res = res[:-2]
                break
            if 0 < maxage < s["age"]:
                continue
            res += "\n"
            ell_nr = truncate_middle("[" + str(nr) + "]", 5)
            ell_title = truncate_middle(s["title"], 40)
            ell_idx = truncate_middle(s["indexer"], 12)
            ell_age = truncate_middle(str(s["age"]) + "d", 5)
            size = s["length"]
            ell_size = make_pretty_bytes(size)
            res += ell_nr + ell_idx + " " + ell_title + " / " + ell_age + " / " + ell_size
            if nr > 30:
                break
        if res[:-1] == "\n":
            res = res[:-2]
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


def read_config(cfg_file, logger):
    try:
        cfg = configparser.ConfigParser()
        cfg.read(cfg_file)
    except Exception as e:
        logger.error(str(e) + ": error in read_config!")
        return None, None
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
    return indexerdict, cfg


class SigHandler:
    def __init__(self, logger, tgram):
        self.logger = logger
        self.tgram = tgram

    def sighandler(self, a, b):
        self.logger.info("Received SIGINT/SIGTERM, terminating ...")
        self.tgram.running = False


def dhandler(msg0):
    global tgbd
    getfromfile = False
    msg = msg0.lstrip()
    rep = ""
    if len(msg) < 1:
        rep = "You have to enter a command!"
        return rep
    if msg[:2] == "dl" and tgbd.nsr:
        nzbnr = msg[2:].lstrip().rstrip()
        rep += "downloading " + str(nzbnr) + "\n"
        rep += tgbd.nsr.download_nzb(nzbnr, tgbd.furl) + "\n"
    elif msg[:1] == "t" and tgbd.nsr:
        rep += tgbd.nsr.toggle_sort() + "\n"
    elif msg[:1] == "d" and tgbd.nsr:
        nzbnr = msg[2:].lstrip().rstrip()
        rep += tgbd.nsr.nzb_details(nzbnr) + "\n"
    elif msg[:2] == "e!":
        tgbd.running = False
    elif msg[:2] == "st":
        rep += nzbget_status(tgbd.maindir, tgbd.furl, tgbd.logger)
    elif msg[:1] == "c" and tgbd.nsr:
        # c <NZBID> eltern/kinder <newname>
        try:
            strlist = msg[2:].lstrip().rstrip()
            strlist = strlist.split(" ")
            nzbid = int(strlist[0])
            ek = strlist[1].lstrip().rstrip()
            if ek not in ["eltern", "kinder"]:
                raise DHException("target1 must be 'eltern' or 'kinder'")
            newname = strlist[2].lstrip().rstrip()
            src = nzbget_getbyid(nzbid, tgbd.furl, tgbd.logger)
            if not src:
                raise DHException("could not query this NZBID!")
            # here: rename biggest file!!

            if ek == "eltern":
                dst = "/media/cifs/filme/" + ek + "/Filme/Diverse/" + newname
            else:
                dst = "/media/cifs/filme/" + ek + "/Filme/" + newname
            tgbd.logger.info("Copying " + src + " to " + dst + " ...")
            shutil.copytree(src, dst)
            tgbd.logger.info("Copy done!")
            rep += "copy done!\n"
        except Exception as e:
            rep += "cannot copy: " + str(e) + "\n"
    elif msg[:1] == "s":
        try:
            qstr = re.findall(r'"([^"]*)"', msg[1:])[0]
            if not getfromfile:
                try:
                    fetch.tfetch_all_indexers(tgbd.indexerdict, qstr, tgbd.maindir, writetofile=True)
                except Exception as e:
                    tgbd.logger.error(str(e) + ": error in usenet search / indexer fetch!")
            else:
                for idx_name, idx_obj in tgbd.indexerdict.items():
                    filename = tgbd.maindir + idx_name + "_" + qstr + ".xml"
                    idx_obj.get_xmltree_from_file(filename)
            # merge into ONE search result list (of dict)
            searchresult1 = []
            #print(tgbd.indexerdict.items())
            for idx_name, idx_obj in tgbd.indexerdict.items():
                try:
                    idx_obj.analyze_search1()
                    searchresult1.extend(idx_obj.search1_list)
                except Exception:
                    pass
            tgbd.nsr = NewsSearchResult(searchresult1, tgbd.maindir, tgbd.logger)
            resstr = tgbd.nsr.print_search_results()
            rep += resstr
        except Exception as e:
            tgbd.logger.error(str(e) + ": error in usenet search / etc. !")
    elif msg[:1] == "l" and tgbd.nsr:
        resstr = tgbd.nsr.print_search_results()
        rep += resstr
    elif msg[:1] == "h" and tgbd.nsr:
        rep += nzbget_history(tgbd.nsr.rcodelist, tgbd.furl, tgbd.logger)
    elif not tgbd.nsr:
        rep += "cannot execute as no search results available \n"
    else:
        rep += ("unknown command " + msg[:2] + "\n")
    if msg[:2] != "e!":
        rep += ("-" * 80 + "\n")
        rep += tgbd.motd
    return rep


async def dhecho(bot, update_id):
    updates = await bot.get_updates(offset=update_id, timeout=10)
    txt0 = ""
    for update in updates:
        next_update_id = update.update_id + 1
        if update.message and update.message.text:
            txt0 = update.message.text
            rep = dhandler(txt0)
            await update.message.reply_text(rep)     # update.message.text)
        return next_update_id, txt0
    return update_id, ""


async def runbot():
    global tgbd
    async with Bot(tgbd.token) as bot:
        try:
            rep = "Welcome to dachshund V" + str(__version__) + " - usenet search telegram bot\n"
            rep += tgbd.motd
            for c in tgbd.chatids:
                await bot.send_message(chat_id=c, text=rep)
            try:
                update_id = (await bot.get_updates())[0].update_id + 1
            except IndexError:
                update_id = None

            tgbd.running = True
            while tgbd.running:
                try:
                    update_id, txt0 = await dhecho(bot, update_id)
                except telegram.error.NetworkError:
                    await asyncio.sleep(1)
                except telegram.error.Forbidden:
                    # The user has removed or blocked the bot.
                    update_id += 1
                except Exception as e:
                    print(str(e))
                    break
            rep = "Shutting down Dachshund by >e!< command "
            for c in tgbd.chatids:
                await bot.send_message(chat_id=c, text=rep)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            rep = "Shutting down Dachshund by SIGTERM/systemctl stop"
            for c in tgbd.chatids:
                await bot.send_message(chat_id=c, text=rep)
                await asyncio.sleep(1)
        except Exception as e:
            tgbd.logger.error(str(e) + " :error in running runbot, exiting ...")


def run():
    # install_dir = os.path.dirname(os.path.realpath(__file__))
    userhome = expanduser("~")
    maindir = userhome + "/.dachshund/"
    global tgbd

    # Init Logger
    logger = logging.getLogger("dh")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(maindir + "dachshund.log", mode="w")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info("Dachshund " + __version__ + " started!")

    try:
        cfg_file = maindir + "dachshund.config"
        tgbd = TelegramBotData(cfg_file, maindir, logger)
        if not tgbd.initok:
            logger.error(tgbd.errstr + " :cannot set up telegram bot thread, exiting ...")
            print(tgbd.errstr + " :cannot set up telegram bot thread, exiting ...")
            return -1
        asyncio.run(runbot())
        logger.info("Telegram bot stopped, probably control command")
    except Exception as e:
        logger.error(str(e) + " :cannot set up telegram bot thread, exiting ...")
        print(str(e))
        return -1
    logger.info("Telegram bot stopped, exiting Dachshund ...")
    return 1

