#!/usr/bin/env python3

##############################################################################
#   aptscraper.py  v2.0                                                      #
#                                                                            #
#   Does web scrapping for get a package, sha256sum [and his dependencies]   #
#   for the current state of the system or another one.                      #
#                                                                            # 
#   Author: David Motos Olmedo                                               #       
##############################################################################
from bs4 import BeautifulSoup 
import sys
import os
import re
import shutil
import random

from subprocess import call, run, check_output

ARCH='amd64'
BASEURL='https://packages.debian.org'
DIST = check_output("lsb_release -c | awk '{{print $2}}'", shell=True, text=True).replace('\n','')
C_FLAG = False
N_FLAG = False
I_FLAG = False
H_FLAG = False
SEARCH = None
repeated = [
    '-c','--checksum-only',
    '-n','--no-depends',
    '-i','--installed-file',
    '-h','--help'
]  
sintaxError=False
URL = ""
curlCont=0
pkgsFile=""
indexFile=-1
pkgsInstalled = []
simulatedPkgs = []
toDownload = []
sha256sums = []
dependencies = []
visited = []

#__________________________________________________________________________________________
def showHelp():
    print("""
\033[1mSYNOPSIS\033[0m
    aptscraper.py [OPTION...] package

\033[1mDESCRIPTION\033[0m    
    By default, download a package, his dependencies and sha256sums from the web of debian
    for the current state of the system if no arguments are passed.
    
\033[1mOPTIONS\033[0m
    \033[1m-c  --checksum-only\033[0m           Only return the checksum of the specified package

    \033[1m-n  --no-depends\033[0m              Download only the searched package and sha256sum

    \033[1m-i  --installed-pkgs\033[0m          Download the package, dependencies and checksums needed for apt in 
                                  installed.pkgs file (apt list --installed > file), this file need to be passed
                                  like last argument. This options is not compatible with the others
                                
    \033[1m-h  --help\033[0m                    Print this message and exit
"""
    )
    sys.exit(0)
#__________________________________________________________________________________________
def loadPkgs(file):
    try:
        with open(file,'r',encoding='utf-8') as f:
            for line in f:
                pkgsInstalled.append(line.split('/')[0])
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)
#__________________________________________________________________________________________
def incorrectSintaxMessage():
    print('Sintax Error, run \033[1maptscraper.py -h\033[0m for get help')
    sys.exit(1)
#__________________________________________________________________________________________
def curl(url,name):
    global curlCont
    output = f'files/debs/{name}'
    if name.endswith('html'):
        output = f'files/parse/{name}'
    o1 = check_output(f"curl {url} -s -o {output}", shell=True, text=True)
    curlCont=curlCont+1
    print(url)
#__________________________________________________________________________________________
def extractDownloadInfo(soup):
    global URL
    a=soup.select('div[id="pdownload"] > table')[0].select(f'a[href*="{ARCH}"]')#/{DIST}/{ARCH}/{PACKAGE}/download
    if not a:
        a=soup.select('div[id="pdownload"] > table')[0].select(f'a[href*="all"]')#/{DIST}/all/{PACKAGE}/download
    URL=a[0]['href']
    
    curl(BASEURL+URL,'download.html')
    with open('files/parse/download.html') as downloadPage:
        soup = BeautifulSoup(downloadPage,'lxml')
    
    if not C_FLAG:
        servers = []
        leftDiv = soup.find('div',{'class':'cardleft'}).find_all('a')
        rightDiv = soup.find('div',{'class':'cardright'}).find_all('a')
        for a in leftDiv:
            servers.append(a['href'])
        for a in rightDiv:
            servers.append(a['href'])
        downloadServer = random.choice(servers)
        toDownload.append(downloadServer)
    
    SHA256 = soup.find('th',string=re.compile('SHA256')).next_sibling.next_sibling.find('tt').string
    fullNamePackage = soup.find('h3').find('kbd').string
    #print(f'{SHA256}  {fullNamePackage}')
    sha256sums.append(f'{SHA256}  {fullNamePackage}')   
#__________________________________________________________________________________________    
def aptInstallSimulated():
    global SEARCH
    simulated = run(['apt','install','-s',SEARCH],capture_output=True, text=True).stdout
    if len(simulated) > 0:
        lines = simulated.split('\n')
        for line in lines:
            if "Inst " in line:
                simulatedPkgs.append(line.split()[1])
#__________________________________________________________________________________________                    
def search():
    global SEARCH
    global dependencies
    call('bash -c "[ -d files ] || mkdir -p files/{parse,debs}"', shell=True)
    curl(BASEURL+'/search?keywords='+SEARCH,'search.html')
    with open('files/parse/search.html') as search:
        soup = BeautifulSoup(search,'lxml') 
    h2 = soup.find('h2',string='Exact hits')
    if h2 is not None:
        URL = h2.parent.find('a', {'class':'resultlink','href':re.compile(DIST)})['href']
    else:
        print('Package not found.')
        shutil.rmtree('files')
        sys.exit(1)
    call(f'bash -c "[ -d {SEARCH} ] || mkdir {SEARCH}"', shell=True)
    dependencies.append(URL)
    aptInstallSimulated()
#__________________________________________________________________________________________
def extractDependencies(mode=0): # 0 : depends, 1 : suggested
    global URL
    global dependencies
    while len(dependencies) > 0:
        URL = dependencies.pop()
        curl(BASEURL+URL,'detailsPage.html') 
        with open('files/parse/detailsPage.html') as detailsPage:
            soup = BeautifulSoup(detailsPage,'lxml')
        uls = soup.select('ul[class=uldep]')[1:]
        hrefs = []
        for ul in uls:
            hrefs.extend(a['href'] for a in ul.find_all('a'))
        for href in hrefs:
            if href not in visited:
                visited.append(href)
                dp = href.split('/')[-1]
                if I_FLAG:
                    if dp not in pkgsInstalled:
                        dependencies.append(href)
                else:
                    stcode = call(f'bash -c "dpkg-query -s {dp} &> /dev/null"',shell=True)
                    if stcode == 1:
                        dependencies.append(href) 
        extractDownloadInfo(soup)

        if N_FLAG:
            dependencies = []
            
       # extraer los dt's, algunas dependencias tiene paquetes 'or' para ver que variedad instalar. Virtual packages tampoco testeados
#__________________________________________________________________________________________    
def download():
    for url in toDownload:
        curl(url,url.split('/')[-1])
#__________________________________________________________________________________________    
def writeFiles():  
    global sha256sums
    aux = []
    if os.path.exists(SEARCH):
        shutil.rmtree(SEARCH)
    os.mkdir(SEARCH)
    if not C_FLAG:
        call(f'bash -c "mv files/debs/* {SEARCH}"', shell=True) 
    os.chdir(SEARCH)
    
    with open('sha256.sums','w') as f:
        f.writelines(f"{line}\n" for line in sha256sums)
        
    for line in reversed(sha256sums):
        aux.append(f'dpkg -i {line.split(" ")[-1]}') 
    sha256sums =list(aux)    
    aux = []
    if len(simulatedPkgs) > 0:
        for pkg in simulatedPkgs:
            index = [i for i, s in enumerate(sha256sums) if pkg in s]
            if len(index) > 0:
                aux.append(f'dpkg -i {sha256sums[index[0]].split(" ")[-1]}')
        if len(aux) == len(sha256sums):
            sha256sums = aux    

    with open('install.sh','w') as f:
        f.write('#!/bin/env bash\n')
        for line in sha256sums:
            pkg = line.split(' ')[-1]
            f.write(f'dpkg -i {pkg}\n') ## dpkg -i dpkg -i if sha256sums == aux
    shutil.rmtree('../files')
#__________________________________________________________________________________________
if len(sys.argv) < 2:
    incorrectSintaxMessage()
for arg in enumerate(sys.argv[1:]):
    if arg[1] in ('-c','--checksum-only') and C_FLAG==False: 
        C_FLAG = True
    elif arg[1] in ('-n','--no-depends') and N_FLAG==False:
        N_FLAG = True    
    elif arg[1] in ('-i','--installed-pkgs') and I_FLAG==False:
        I_FLAG = True
        indexFile=arg[0]+2
    elif arg[1] in ('-h','--help') and H_FLAG==False and arg[1] == sys.argv[-1]:
        H_FLAG = True
    elif arg[1] == sys.argv[-1] and not arg[1].startswith('-'):
        if len(sys.argv) == 2:
            SEARCH = arg[1]
        if len(sys.argv) == 3 and ('-c' in sys.argv[arg[0]] or '-n' in sys.argv[arg[0]]):
            SEARCH = arg[1]
        if len(sys.argv) == 4 and '-i' in sys.argv[arg[0]-1]:
            SEARCH = arg[1]
        if len(sys.argv) == 4 and ('-c' in sys.argv[arg[0]-1] or '-n' in sys.argv[arg[0]-1]) \
                                and ('-c' in sys.argv[arg[0]] or '-n' in sys.argv[arg[0]]):
            SEARCH = arg[1]
    elif arg[1] == sys.argv[-1] and arg[1].startswith('-'):
        sintaxError = True
    elif arg[1] in repeated:
         sintaxError = True
    elif (arg[1].startswith('--') and arg[1][2:] not in ('installed-pkgs','no-depends','checksum-only','help') ) \
        or ( arg[1].startswith('-') and arg[1][1:] not in ('i','n','c','h') ):# 'cn','nc' 
        sintaxError = True
if SEARCH == None and H_FLAG == False:
    sintaxError = True
if I_FLAG and (N_FLAG or H_FLAG or C_FLAG):
    sintaxError == True
if H_FLAG and (N_FLAG or I_FLAG or C_FLAG): 
    sintaxError == True
if sintaxError == True:
    incorrectSintaxMessage()
    
if H_FLAG:
    showHelp()
if I_FLAG:
    loadPkgs(sys.argv[indexFile])

search()
extractDependencies()
download()
writeFiles()
