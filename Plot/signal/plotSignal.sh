#!/bin/bash

input=$1
legend=$2
gnuplot -p <<EOF
# Data columns:X Min 1stQuartile Median 3rdQuartile Max
set bars 4.0
set style fill empty
plot '$input.txt' using 1:3:2:6:5 with candlesticks lt 4 title '$legend', \
     ''                 using 1:4:4:4:4 with candlesticks lt 3 notitle, \
     ''                 using 1:4       with linespoints  notitle
EOF
