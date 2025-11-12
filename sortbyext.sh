#!/bin/env bash

# script for sort by extension files recovered from PhotoRec Data Recovery Utility

recupDirs=()
for i in */; do
	recupDirs+=("$i")
done
[ ! -d sortedByExt ] && mkdir sortedByExt
for dir in  "${recupDirs[@]}"; do
	cd $dir
	printf "sorting: $dir\n"
	ext="$(ls -1 | head -n1 | cut -d . -f2 )"
	while [ -n "$ext" ]; do 
		[ ! -d ../sortedByExt/$ext ] && printf "ext: $ext\n" && mkdir ../sortedByExt/$ext
		mv *.$ext ../sortedByExt/$ext
		ext="$(ls -1 | head -n1 | cut -d . -f2 )"
	done
	cd ..
done
