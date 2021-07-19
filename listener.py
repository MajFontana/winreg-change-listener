import winreg
import contextlib
import itertools
import time
import datetime

def subkeys(hkey, path, flags=0):
    with contextlib.suppress(WindowsError), winreg.OpenKey(hkey, path, 0, winreg.KEY_READ | flags) as key:
        for i in itertools.count():
            yield winreg.EnumKey(key, i)

class Tree:
    def __init__(self, hkey, path="", keys=None, maxdepth=10, debug=False):
        if debug:
            t1 = time.perf_counter()
        
        self.hkey = hkey
        self.path = path

        hkeyid = getattr(winreg, hkey)
        try:
            with winreg.OpenKey(hkeyid, path, 0, winreg.KEY_READ) as key:
                self.modified = winreg.QueryInfoKey(key)[2]
            self.restricted = False
        except PermissionError:
            self.modified = None
            self.restricted = True

        if not path:
            parent = ""
        else:
            parent = path + "\\"

        self.children = None
        if maxdepth > 0:
            if not self.restricted:
                self.children = {}
                self.complete = True
                if keys == None:
                    keys = subkeys(hkeyid, path)
                for key in keys:
                    subpath = parent + key
                    self.children[key] = Tree(hkey, subpath, maxdepth=maxdepth - 1)
                    if not self.children[key].complete:
                        self.complete = False
            else:
                self.complete = True
        else:
            self.complete = False

        if debug:
            t2 = time.perf_counter()

            inf = self.info()
            print("%i nodes, %i restricted" % (inf["nodes"], inf["restricted"]))
            
            print("Generation time: %.2f ms" % ((t2 - t1) * 1000))
            if self.complete:
                print("Tree is complete, max depth: %i" % inf["maxdepth"])
            else:
                print("Tree is not complete (%i unexpanded nodes)" % inf["unexpanded"])
        
    def display(self, level=0):
        off = "  " * level
        if self.children != None:
            for name, child in self.children.items():
                print(off + name)
                child.display(level + 1)
        else:
            if self.restricted:
                print(off + "RESTRICTED")
            else:
                print(off + "NOT EXPANDED")

    def __getitem__(self, name):
        return self.children[name]
    
    def difference(self, tree, depth=0):
        diff = []
        
        if self.modified != tree.modified:
            seconds = max(self.modified, tree.modified) / 10000000
            delta = datetime.timedelta(seconds=seconds)
            dt = (datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc) + delta).astimezone()
            diff.append(("MODIFIED_KEY", [self.path, dt]))

        if type(self.children) != type(tree.children):
            diff.append(("NONMATCHING_EXPANSION", [depth]))
        elif self.children != None:
            c1 = set(self.children.keys())
            c2 = set(tree.children.keys())
            for name in c1 - c2:
                diff.append(("MISSING_KEY", [self[name].path]))
            for name in c2 - c1:
                diff.append(("NEW_KEY", [tree[name].path]))
            for name in c1 & c2:
                diff += self[name].difference(tree[name], depth + 1)

        return diff

    def info(self, depth=0):
        inf = {"nodes": 1, "maxdepth": depth, "restricted": 0, "unexpanded": 0}
        if self.restricted:
            inf["restricted"] = 1
        elif self.children == None:
            inf["unexpanded"] = 1
        
        if self.children:
            for child in self.children.values():
                subinf = child.info(depth + 1)
                inf["nodes"] += subinf["nodes"]
                inf["restricted"] += subinf["restricted"]
                inf["unexpanded"] += subinf["unexpanded"]
                inf["maxdepth"] = max(inf["maxdepth"], subinf["maxdepth"])

        return inf
            
if __name__ == "__main__":
    old = Tree("HKEY_LOCAL_MACHINE", r"", ["SYSTEM"], 20, debug=True)
    #old.display()
    print()

    while True:
        new = Tree("HKEY_LOCAL_MACHINE", r"", ["SYSTEM"], 20)
        d = new.difference(old)
        if d:
            old = new
            print("-" * 10)
            for item in d:
                print(item)
                print()
        else:
            print("no change")
