#!/bin/bash

file=$1
#tit=$2
gnuplot -p << EOF
# scalable
#set xdata time
#set timefmt "%s"     # unix timestamp
#set format x "%S"    # or anything else
#set term pngcairo dashed
set termoption dashed   # enable dashed line
#set autoscale
set xrange [-500:7000]
#set xtic auto                          # set xtics automatically
#set ytic auto                          # set ytics automatically
#set title '$tit Pattern'
set xlabel "Time (ms)"
set ylabel "FACH (2), DCH (3), PCH (4), \nFACH_PROMOTE(5), PCH_PROMOTE(6)"
#set grid
#set palette defined $color
set style arrow 1 head ls 4 lw 3
set style arrow 2 nohead ls 3 lw 1
set style arrow 3 nohead ls 16 lw 1

plot "$file\_TCP.txt" using 1:(0):(0):5 with vectors arrowstyle 1 title "TCP Packets", \
     "$file\_RLC.txt" using 1:(0):(0):5 with vectors arrowstyle 2 title "RLC PDUs", \
     "$file\_DUP_ACK.txt" using 1:(0):(0):5 with vectors arrowstyle 3 title "RLC Dup ACKs"
#     "$file\_state_trans.txt" using 1:2 with points ls 2 title "RRC State"
EOF
