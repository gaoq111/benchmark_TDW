#!/bin/bash
while read line; do
    python test.py --scene box_room_2018 --name 'with_'$line --object $line 
done < core_lib.txt