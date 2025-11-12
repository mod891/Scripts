##############################################################################
#   aptscraper_v1.py                                                         #
#   Download and verify integrity of a debian package and his dependencies   #
#   with the current system or a external one scrapping the web              #
#                                                                            #
#   Author: David Motos Olmedo                                               #       
##############################################################################
from bs4 import BeautifulSoup 
import sys
import re
import urllib.request
import time
import random
from subprocess import call, run, check_output

baseUrl='https://packages.debian.org'
DIST = 'trixie' # 'bookworm' # lsb_release -c
ARCH='amd64'
IMPORT=False
SEARCH=None
depsList = []
toDownloadList = []
sumsList = []
pkgChecked = []
pkgs = []
installedSet = set()
installedVerboseSet = set()
inOrder= [] # [BUG] installation sibbling order could fail
lvDic = {}
ngt=''
gt=-1
#__________________________________________________________________________________________
def getHtml(url,name):
    ini = time.time()
    opener = urllib.request.build_opener() # [1]
    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(url,'files/parse/'+name)
    end = time.time() 
    diff = round(end-ini,2)
    print(f'get: {url}: {diff}s')
#__________________________________________________________________________________________
def savePkg(url,sha256):  
    ini = time.time()
    pkg = url.split('/')[-1]
    opener = urllib.request.build_opener() 
    opener.addheaders = [('User-agent', 'Mozilla/5.0')]
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(url,'files/debs/'+pkg)
    end = time.time() 
    print(f'get: {url}: {round(end-ini,2)}s')
    sum = run(['sha256sum','files/debs/'+pkg], capture_output=True, text=True).stdout
    sum = sum.replace("\n","")
    if sum.split(' ')[0] == sha256:
        sumsList.append(f'{sum}\tOK')
    else:
        sumsList.append(f'{sum}\tERROR')
#__________________________________________________________________________________________
def loadPkgs(file):
    try:
        with open(file,'r',encoding='utf-8') as f: # 
            for line in f:
                installedSet.add(line.split('/')[0])
                installedVerboseSet.add(line.strip())
    except FileNotFoundError:
        print(f'file {file} doesn\'t exists')
#__________________________________________________________________________________________
if len(sys.argv) == 2:
    SEARCH=sys.argv[1]
elif len(sys.argv) == 3:
    SEARCH=sys.argv[1]
    IMPORT=True
    loadPkgs(sys.argv[2])
else:
    print('usage: python3 aptscraper.py package [apt list --installed file]')
    sys.exit()
call('bash -c "[ -d files ] || mkdir -p files/{parse,debs}"', shell=True)
call('bash -c "[ -f files/debs/deb-sums.txt ] || touch files/debs/deb-sums.txt"', shell=True)
getHtml(baseUrl+'/search?keywords='+SEARCH,'search.html')
with open('files/parse/search.html') as search:
    soup = BeautifulSoup(search,'lxml')
href = soup.find_all('a', {'class':'resultlink','href':re.compile(DIST)})
###debug
href = soup.find_all('a', {'class':'resultlink','href':'trixie'})
print(href)
input()
###debug
if len(href) == 0: # CASE no existent pkg
    print('Package not found.')
    sys.exit()
href=href[0]['href']  
depsList.append(baseUrl+href)
lvDic[href.split('/')[-1]]=0

while len(depsList) > 0:
    html = depsList.pop()
    getHtml(html,'pkgdepsarch.html')
    with open('files/parse/pkgdepsarch.html') as depends:
        soup = BeautifulSoup(depends,'lxml')
    uls = soup.find_all('ul',{'class':'uldep'})[1:]  # CASE nested pkg no depends
    for ul in uls:
        dts=ul.find_all('dt') # leave minVer if exists
        pkgs = []
        for i in dts:
            pkg = i.find('a')
            if pkg != None:
                pkg = pkg['href'].split('/')[-1]
                pkgs.append(pkg)
        for dt in reversed(dts):
            href=dt.find('a')
            if href != None: # CASE: Package not available
                href=href['href']
                if "or " not in dt.text: # CASE or other-pkg: slow OPT:A(select) B(skip) # 
                    pkg = href.split('/')[-1]
                    if pkg not in pkgChecked:   
                        pkgChecked.append(pkg)
                        if IMPORT:
                            if pkg not in installedSet:
                                if baseUrl+href not in depsList:
                                    lvDic[pkg]=lvDic[html.split('/')[-1]]+1
                                    depsList.append(baseUrl+href)
                        else: 
                            result = run(['dpkg-query','-s',pkg], capture_output=True, text=True).stdout
                            if not result: # pkg not installed  
                                if baseUrl+href not in depsList:
                                    depsList.append(baseUrl+href) 
                                    lvDic[href.split('/')[-1]]=lvDic[html.split('/')[-1]]+1
    a=soup.select('div[id="pdownload"] > table')[0].select(f'a[href*="{ARCH}"]')
    if not a:
        a=soup.select('div[id="pdownload"] > table')[0].select(f'a[href*="all"]')
    href=a[0]['href']
    downloadUrl = baseUrl+a[0]['href']
    toDownloadList.append(downloadUrl)
while len(toDownloadList) > 0:
    downloadUrl = toDownloadList.pop()
    getHtml(downloadUrl,'download.html')
    with open('files/parse/download.html') as download:
        soup = BeautifulSoup(download,'lxml')
    leftDiv = soup.find('div',{'class':'cardleft'}).find_all('a')
    rightDiv = soup.find('div',{'class':'cardright'}).find_all('a')
    servers = []
    for a in leftDiv:
        servers.append(a['href'])
    for a in rightDiv:
        servers.append(a['href'])
    downloadServer = random.choice(servers)   # 503 in some servers, implement timeout & retry other server 
    lvDic[downloadServer.split('/')[-1]]=lvDic.pop(downloadServer.split('/')[-1].split('_')[0])
    SHA256 = soup.find('th',string=re.compile('SHA256')).next_sibling.next_sibling.find('tt').string
    savePkg(downloadServer,SHA256)

while len(lvDic) > 0:
    for key, val in lvDic.items():
        if val > gt:
            gt=val
            ngt=key
    inOrder.append(ngt) # orden vertical ok, horizontal no [fix]
    del lvDic[ngt]
    gt=-1
with open('files/debs/deb-sums.txt','w') as f:
    f.writelines(f"{line}\n" for line in sumsList)
    
with open('files/debs/install.sh','w') as f:
    f.write('#!/bin/env bash\n')
    f.writelines(f"dpkg -i {line}\n" for line in inOrder)
call(f'bash -c "[ -d {SEARCH} ] || mkdir {SEARCH} && mv files/debs/* {SEARCH} && rm -rf files"', shell=True) 

