from furl import furl
import xmlrpc.client
from difflib import SequenceMatcher

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


def nzbget_getbyid(nzbid, nzbget):
    f = furl()
    f.host = nzbget["host"]
    f.scheme = "http"
    f.port = nzbget["port"]
    f.username = nzbget["username"]
    f.password = nzbget["password"]
    f.path.add("xmlrpc")
    rpc = xmlrpc.client.ServerProxy(f.tostr())
    history = rpc.history()
    fn = ""
    for h in history:
        if nzbid == h["NZBID"]:
            fn = h["DestDir"]
    return fn


def nzbget_history(rcodelist, nzbget):
    f = furl()
    f.host = nzbget["host"]
    f.scheme = "http"
    f.port = nzbget["port"]
    f.username = nzbget["username"]
    f.password = nzbget["password"]
    f.path.add("xmlrpc")
    rpc = xmlrpc.client.ServerProxy(f.tostr())
    history = rpc.history()
    rep = ""
    for h in history:
        nzbid = h["NZBID"]
        matches = [title for title, rcode in rcodelist if nzbid == rcode]
        found_in_rcodelist = len(matches) > 0
        if found_in_rcodelist:
            rep += "[" + str(nzbid) + "] " + h["Name"] + " / " + h["Status"] + " / " + h["DestDir"] + "\n"
    if rep:
        rep = rep[:-2]
    return rep


def nzbget_status(maindir, nzbget):
    f = furl()
    f.host = nzbget["host"]
    f.scheme = "http"
    f.port = nzbget["port"]
    f.username = nzbget["username"]
    f.password = nzbget["password"]
    f.path.add("xmlrpc")
    rpc = xmlrpc.client.ServerProxy(f.tostr())
    status = rpc.status()
    groups = rpc.listgroups(0)
    with open(maindir + "nzbget.status", "w") as sf:
        sf.write(str(status))
    with open(maindir + "nzbget.groups", "w") as gf:
        gf.write(str(groups))
    res = ""
    res += "Overall remaining: " + str(make_pretty_bytes(status["RemainingSizeLo"])) + "\n"
    dlr = "%.1f" % ((status["DownloadRate"] / (1024 * 1024)) * 8) + " MBit"
    res += "Download rate:     " + dlr + "\n"
    for i, g in enumerate(groups):
        size = str(g["FileSizeMB"]) + "M"
        rem = str(g["RemainingSizeMB"] - g["PausedSizeMB"]) + "M"
        nr = truncate_middle("[" + str(i+1) + "]", 5)
        res += nr + truncate_middle(g["NZBFilename"], 40) + " (" + g["Status"] + ") / " + rem + " of "  + size + "\n"
    return res


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


def make_pretty_bytes(size):
    if size < 1024:
        ell_size = str(size) + "B"
    elif size < 1024 * 1024:
        ell_size = str(int(size / 1024)) + "K"
    elif size < 1024 * 1024 * 1024:
        ell_size = "%.1f" % (size / (1024 * 1024)) + "M"
    else:
        ell_size = "%.2f" % (size / (1024 * 1024 * 1024)) + "G"
    return ell_size
