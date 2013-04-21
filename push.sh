#!/bin/bash

USAGE="./push.sh -{o,e}"
OPTION=$1
if [ $# -ne 1 ]
then
    echo $USAGE
    exit 1
fi

owl_folder=/home/haokun/RRC_Analysis_UDP/QCATAnalysis
ep2_folder=/home/haokun/QCATAnalysis
if [ $OPTION = '-o' ]
then
    #scp -r Data/UDP/* haokun@owl.eecs.umich.edu:$owl_folder/Data/UDP/
    scp -r pcap/UDP/seq/* haokun@owl.eecs.umich.edu:$owl_folder/pcap/UDP/seq/
elif [ $OPTION = '-e' ]
then
    scp -r pcap/UDP/seq/* haokun@ep2.eecs.umich.edu:$ep2_folder/pcap/UDP/seq/
else
    echo $USAGE
    exit 1
fi

