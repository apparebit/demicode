#!/usr/bin/env bash

# Note: This script also works with zsh, which does not support read's -p
# (prompt) option. Also, see
# https://unix.stackexchange.com/questions/88296/get-vertical-cursor-position/183121

rainbow_flag="\xf0\x9f\x8f\xb3\xef\xb8\x8f\xe2\x80\x8d\xf0\x9f\x8c\x88"
echo -en "${rainbow_flag}\x1b[6n"
IFS=';' read -sdR row col; echo -en "\x1b[$((col+1))G▌▍▎▏\n"
printf '━%0.s' $(seq 1 $col)
echo "▶︎ ${col}"
