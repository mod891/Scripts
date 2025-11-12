#!/usr/bin/env python3
# run as root

##############################################################################
#   aptDownloadOnly.py  v2.0                                                 #
#                                                                            #
#   Download a package and his dependencies or the upgradables packages      #
#   and check the sha256sum against the downloaded metadata,                 #
#       * Helps to detect tampered packages *                                #
#                                                                            #
#   Author: David Motos Olmedo                                               #       
##############################################################################

from subprocess import call, run, check_output, STDOUT
import os
import sys
import shutil
import time

pkg = ''
pkgs = []
pkgsMetadata = "/var/lib/apt/lists/deb.debian.org_debian_dists_trixie_main_binary-amd64_Packages"
pkgsUpdatesMetadata = "/var/lib/apt/lists/deb.debian.org_debian_dists_trixie-updates_main_binary-amd64_Packages"
installList=[]
#__________________________________________________________________________________________________________
def simulate(upgrade=0):
    if upgrade == 1:
        print('upgrade')
        call('apt update',shell=True)
        simulated = run(['apt','upgrade','-s'],capture_output=True, text=True).stdout
    else:
        simulated = run(['apt','install','-s',pkg],capture_output=True, text=True).stdout
    
    if len(simulated) > 0:
        lines = simulated.split('\n')
        for line in lines:
            if "Inst " in line:
                pkgs.append(line.split()[1])
#__________________________________________________________________________________________________________
def download(upgrade=0):
    if upgrade == 1:
        print('Downloading upgrades...')
        downloaded = run(['apt','upgrade','--download-only','-y'],capture_output=True, text=True)
    else:
        print('Downloading package and depencencies...')
        downloaded = run(['apt','install','--download-only','-y',pkg],capture_output=True, text=True)
    if 'Error:' in downloaded.stderr:
        print('ERROR')
        sys.exit(1)
#__________________________________________________________________________________________________________        
def writeFiles(upgrade=0):
    metadataFile = ""
    if upgrade == 1:
        metadataFile = pkgsUpdatesMetadata
    else:
        metadataFile = pkgsMetadata
    if os.path.exists(pkg):
        shutil.rmtree(pkg)
    os.mkdir(pkg)
    os.chdir(pkg)
    call('mv /var/cache/apt/archives/*.deb .',shell=True)
    files = os.listdir()
    for item in files:
        if item.split('_')[0] in pkgs:
            index = pkgs.index(item.split('_')[0])
            pkgs[index] = item
    
    with open('sha256sums','w') as f:
        print(f'checking hashes')
        for item in pkgs:
            try:
                output = check_output(f"grep -A 5 -m 1 {item} {metadataFile} | grep SHA256 | awk '{{print $2, \" {item}\" }}'",
                    shell=True, text=True).replace('\n','')
                if len(output) >0: # pkg found in file. SHOULD
                    sumResult = check_output(f"echo \"{output}\" | sha256sum --check - | cut -d: -f2", shell=True, text=True).replace('\n',' ')   
                    f.write(f'{output} : {sumResult}\n')
                else:
                    f.write(f'package {output} {item} not found in {metadataFile}\n') # libixml11t64_1%3a1.14.20-1_amd64.deb → libixml11t64_1.14.20-1_amd64.deb → 1%3a
            except Exception as e:
                f.write(f'exception: {e} SUM missmatch?\n')
    with open('install.sh','w') as f:
        f.write('#!/bin/env bash\n')
        for item in pkgs:
            f.write(f'dpkg -i {item}\n')
#__________________________________________________________________________________________________________
if os.geteuid() != 0:
    print('Run it as root')
    sys.exit(1)
if len(sys.argv) == 2:
    pkg = sys.argv[1]  
else:
    print('Usage: aptDownloadOnly.py [package|upgrade]')
    sys.exit(1)
    
ini = time.time()
opt = 0
if pkg == 'upgrade':
    opt = 1
simulate(opt)
download(opt)
writeFiles(opt)
end = time.time()            
diff = round(end-ini,2)
print(f'{pkg} downloaded in {diff}s')

