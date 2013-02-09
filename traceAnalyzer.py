#!/usr/bin/env python

"""
@Author Haokun Luo
@Date   02/02/2013
This program analyze the Data Set generated from QXDM filtered log file
It could optionally map the packets from PCAP with the RRC states in the log
"""

import os, sys
import const
import QCATEntry as qe
import PCAPPacket as pp
import Util as util
from optparse import OptionParser

def init_optParser():
    extraspace = len(sys.argv[0].split('/')[-1])+10
    optParser = OptionParser(usage="./%prog [-l, --log] QCAT_LOG_PATH [-m] [-p, --pcap] inPCAPFile\n" + \
                            " "*extraspace + "[-t, --type] protocolType, [--src_ip] srcIP\n" + \
                            " "*extraspace + "[--dst_ip] dstIP, [--src_port] srcPort\n" + \
                            " "*extraspace + "[--dst_port] destPort")
    optParser.add_option("-l", "--log", dest="inQCATLogFile", default="", \
                         help="QCAT log file path")
    optParser.add_option("-m", action="store_true", default=False, dest="isMapping", \
                         help="Add this option when try to map PCAP trace with QCAT log file")
    optParser.add_option("-p", "--pcap", dest="inPCAPFile", default="", \
                         help="PCAP trace file path")
    optParser.add_option("-t", "--type", dest="protocolType", default="TCP",
                         help="Protocol Type, i.e. TCP or UDP")
    optParser.add_option("--src_ip", dest="srcIP", default=None, \
                         help="Filter out entries with source ip")
    optParser.add_option("--dst_ip", dest="dstIP", default=None, \
                         help="Filter out entries with destination ip")
    optParser.add_option("--src_port", dest="srcPort", default=None, \
                         help="Filter out entries with source port number")
    optParser.add_option("--dst_port", dest="dstPort", default=None, \
                         help="Filter out entries with destination port number")
    return optParser

def main():
    # read lines from input file
    optParser = init_optParser()
    (options, args) = optParser.parse_args()

    if options.inQCATLogFile == "":
        optParser.error("-l, --log: Empty QCAT log filepath")
    if options.isMapping == True and options.inPCAPFile == "":
        optParser.error("-p, --pcap: Empty PCAP filepath")

    QCATEntries = util.readQCATLog(options.inQCATLogFile)
    util.assignRRCState(QCATEntries)
    
    # validate ip address
    cond = {}
    if options.srcIP != None:
        if util.validateIP(option.srcIP) == None:
            optParser.error("Invalid source IP")
        else:
            cond["src_ip"] = options.srcIP
    if options.dstIP != None:
        if util.validateIP(option.dstIP) == None:
            optParser.error("Invalid destination IP")
        else:
            cond["dst_ip"] = options.dstIP
    if options.srcPort != None:
        cond["src_port"] = options.src_port
    if options.dstPort != None:
        cond["dst_port"] = options.dst_port
    if options.protocolType != None:
        cond["tlp_id"] = const.TLPtoID_MAP[options.protocolType.upper()]
    
    # TODO: add filter
    util.packetFilter(QCATEntries, cond)
    
    """
    for i in QCATEntries:
        if i.rrcID != None and i.ip["tlp_id"] != None:
            print "RRC: %d, Protocol: %d" % (i.rrcID, i.ip["tlp_id"])
    """

    # TODO: might consider not to use external traces
    if options.isMapping == True and options.inPCAPFile == "":
        optParser.error("-p, --pcap: Empty PCAP filepath")
    elif options.isMapping == True:
        outFile = "pcapResult.txt"
        os.system("pcap/main " + options.inPCAPFile + " > " + outFile)

        PCAPPackets = util.readPCAPResultFile(outFile)
        PCAPMaps = util.createTSbasedMap(PCAPPackets)
        QCATMaps = util.createTSbasedMap(QCATEntries)
        countMap = util.mapPCAPwithQCAT(PCAPMaps, QCATMaps)
        totalCount = countMap["fast"] + countMap["slow"] + countMap["same"]
        print "*"*40
        print "In total %d packets"%(len(PCAPPackets))
        print "Mapping rate is %f"%((float)(totalCount)/(float)(len(PCAPPackets)))
        print "QCAT ahead rate is %f"%((float)(countMap["fast"])/(float)(len(PCAPPackets)))
        print "QCAT same rate is %f"%((float)(countMap["same"])/(float)(len(PCAPPackets)))
        print "QCAT slow rate is %f"%((float)(countMap["slow"])/(float)(len(PCAPPackets)))
        print "DCH state rate is %f"%((float)(countMap[const.DCH_ID])/(float)(len(PCAPPackets)))
        print "FACH state rate is %f"%((float)(countMap[const.FACH_ID])/(float)(len(PCAPPackets)))
        print "PCH state rate is %f"%((float)(countMap[const.PCH_ID])/(float)(len(PCAPPackets)))
    else:
        optParser.error("Include -m is you want to map PCAP file to QCAT log file")

if __name__ == "__main__":
    main()