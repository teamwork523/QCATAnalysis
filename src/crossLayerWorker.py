#!/usr/bin/env python

"""
@Author Haokun Luo
@Date   03/20/2013

Procise one-to-one mapping between TCP packet and RLC PDUs
"""
import os, sys, re
import const
import QCATEntry as qe
import PCAPPacket as pp
import PrintWrapper as pw
import retxWorker as rw
import Util as util
from datetime import datetime

DEBUG = False
DETAIL_DEBUG = False
CUR_DEBUG = False
CONFIG_DEBUG = False
DUP_DEBUG = True

############################################################################
################## Cross Layer Based on RLC Layer ##########################
############################################################################
# Map TCP / UDP packet with corresponding RLCs
# Basic idea is to track the first byte information from RLC
# and incrementally map with the existing TCP data
# until three conditions:
# 1. We match until we hit a LI PDU
# 2. We run out of current payload size
# 3. Exceeding a build-in limit
# @ASSUME: No filtering on entries, since IP packets could be sagmented
#          All the sequence number must increase by one each time!!!
# @input: list of entries, index of the TCP packet in the list, entry logID,
#         index_hint is useful if you know the starting index in the entry
# @output: 
#       1. a sequence of RLC entries that maps with the current TCP packet
#          [(entry1, index1), (entry2, index2), ...]
#       2. a list of corresponding sequnce number

def map_SDU_to_PDU(entries, tcp_index, logID, hint_index = -1):
    # search for the entires IP packets
    tcp_payload = findEntireIPPacket(entries, tcp_index)
    
    if DEBUG:
        print "#" * 40
        print "Index is %d" % tcp_index
        print "Length of real payload is %d" % len(tcp_payload)
        print entries[tcp_index].ip
        print entries[tcp_index].tcp
        # pw.printTCPEntry(entries[tcp_index])
        print "First ten bytes: %s" % tcp_payload[:10]
        print "Last ten bytes: %s" % tcp_payload[-10:]
    tcp_len = entries[tcp_index].ip["total_len"]
    # tracking which byte has been matched in the TCP payload
    cur_match_index = 0
    # max_reachable_index = min(len(entries), tcp_index + const.MAX_ENTRIES_LIST)
    max_reachable_index = len(entries)
    
    # return variable
    return_entries = []
    mapped_seq_num_list = []
    
    # default starting point is at the tcp entry
    start_index = tcp_index
    if hint_index != -1:
        start_index = max(hint_index, tcp_index)
        # start_index = hint_index
    if DEBUG:
        print "Start_index at %d" % start_index
        pw.printRLCEntry(entries[start_index], "up")
    # A sequence number tracker to make sure it compare with the next sequnece number
    priv_seq_num = None
    priv_len = None

    for i in range(start_index, max_reachable_index):
        cur_header = None
        cur_seq_num_li = None
        find_match = False
        # make sure the RLC entry is a Data PDU entry
        if entries[i].logID == logID == const.UL_PDU_ID and entries[i].ul_pdu[0]["sn"]:
            cur_header = entries[i].ul_pdu[0]["header"]
            cur_seq_num_li = entries[i].ul_pdu[0]["sn"]
            if not priv_seq_num:
                priv_seq_num = (cur_seq_num_li[0] - 1) % const.MAX_RLC_UL_SEQ_NUM
        elif entries[i].logID == logID == const.DL_PDU_ID and entries[i].dl_pdu[0]["sn"]:
            cur_header = entries[i].dl_pdu[0]["header"]
            cur_seq_num_li = entries[i].dl_pdu[0]["sn"]
            if not priv_seq_num:
                priv_seq_num = (cur_seq_num_li[0] - 1) % const.MAX_RLC_UL_SEQ_NUM
        # Reset packet will stop mapping, so block  
        elif entries[i].logID == const.DL_PDU_ID or entries[i].logID == const.DL_CTRL_PDU_ID:
            if entries[i].dl_ctrl and entries[i].dl_ctrl["reset"]:
                if cur_match_index > 0:
                    if DEBUG:
                        print "@" * 50
                        print "!!!!!! RESET !!!!!! Find RESET at index %d, return directly" % (i)
                        pw.printRLCEntry(return_entries[0][0], "up")
                        print return_entries
                    return (return_entries, mapped_seq_num_list)
            continue
        else:
            continue

        for j in range(len(cur_header)):
            # Increase multiple number of PDUs if there is a gap between PDUs
            factor = -1
            # apply this when there is a match already
            if cur_match_index > 0:
                if cur_seq_num_li[j] < priv_seq_num:
                    factor = cur_seq_num_li[j] + const.MAX_RLC_UL_SEQ_NUM - priv_seq_num - 1
                elif cur_seq_num_li[j] > priv_seq_num:
                    factor = cur_seq_num_li[j] - priv_seq_num - 1
                if factor > 0:
                    cur_match_index += factor * priv_len
            elif cur_seq_num_li[j] % const.MAX_RLC_UL_SEQ_NUM < (priv_seq_num + 1) % const.MAX_RLC_UL_SEQ_NUM:
                continue
            priv_seq_num = cur_seq_num_li[j]  
            priv_len = cur_header[j]["len"]

            if isDataMatch(cur_header[j]["data"], tcp_payload, cur_match_index):
                find_match = True
                if cur_header[j].has_key("li"):
                    # get first li result
                    cur_match_index += cur_header[j]["li"][0]
                else:
                    cur_match_index += cur_header[j]["len"]
                # find a match then append to return seq num list
                mapped_seq_num_list.append(cur_seq_num_li[j])
            else:
                find_match = False
                # if contain data then append the rest of payload
                if cur_header[j].has_key("li") and cur_header[j]["data"]:
                    cur_match_index = cur_header[j]["len"] - cur_header[j]["li"][0]
                    mapped_seq_num_list = []
                # Exceptional case: indicate that last entry, but not padding data
                # i.e. 2 li + 2 e + no data
                elif cur_header[j].has_key("li") and not cur_header[j]["data"]:
                    cur_match_index += cur_header[j]["li"][0]
                else:
                    cur_match_index = 0
                    mapped_seq_num_list = []

            if DETAIL_DEBUG:
                print "&" * 60
                print cur_header[j]
                print "cur_header position %d" % j
                print "Does match find? %s" % find_match
                print "TCP matched index %d and total length is %d" % (cur_match_index, tcp_len)

            # Check if the length matches the TCP header length
            if cur_match_index == tcp_len:
                return_entries.append((entries[i], i))
                if DEBUG:
                    print "@" * 50
                    print "!!!!!! Great!!!!!! Find match at index %d" % (i)
                    pw.printRLCEntry    (return_entries[0][0], "up")
                    print return_entries
                return (return_entries, mapped_seq_num_list)
            # reset the index if not match at the end (HE == 2)
            elif cur_header[j].has_key("he") and cur_header[j]["he"] == 2:
                cur_match_index = 0
            # handle the case where data mismatch at the length indicator entry
            elif cur_header[j].has_key("li") and not cur_header[j]["data"]:
                cur_match_index = 0
            elif cur_header[j].has_key("li") and cur_header[j]["data"]:
                cur_match_index = cur_header[j]["len"] - cur_header[j]["li"][0]
            # if the current index is longer than expected TCP length then reset
            elif cur_match_index > tcp_len:
                cur_match_index = 0

        if find_match:
            return_entries.append((entries[i], i))
        else:
            return_entries = []
        if DETAIL_DEBUG:
            print "+++" * 5
            print "At index %d" % i

    if DETAIL_DEBUG:
        print (return_entries, mapped_seq_num_list)
    if DEBUG:
        print "@@@@@@@@@@@@ NOOOOO MATCH Found @@@@@@@@@@@@"
    return (None, None)

# match the existing data with payload
def isDataMatch(dataList, payload, matching_index):
    # handle PDU no PDU entry no payload case
    if not dataList and payload:
        return False
        #return True
    payloadLen = len(payload)
    for dataIndex in range(len(dataList)):
        if matching_index + dataIndex >= payloadLen or \
           dataList[dataIndex] != payload[matching_index + dataIndex]:
            return False
    return True

# Find the entire IP packets 
def findEntireIPPacket (entries, index):
    cur_custom_seq_num = entries[index].custom_header["seq_num"]
    payload = entries[index].hex_dump["payload"][const.Payload_Header_Len:]

    # if current IP is already the last segment, then return directly
    if entries[index].custom_header["final_seg"]:
        return payload 

    index += 1
    entryLen = len(entries)
    while (entries[index].logID != const.PROTOCOL_ID) or \
          (entries[index].logID == const.PROTOCOL_ID and entries[index].custom_header["seq_num"] == cur_custom_seq_num and \
          not entries[index].custom_header["final_seg"] and index < entryLen):
        if entries[index].logID != const.PROTOCOL_ID:
            index += 1
            continue
        payload += entries[index].hex_dump["payload"][const.Payload_Header_Len:]
        index += 1
    
    # include the last segment as payload
    if entries[index].custom_header["final_seg"]:
        payload += entries[index].hex_dump["payload"][const.Payload_Header_Len:]

    return payload

############################################################################
############## Statistics Generated from Cross Layer Mapping ###############
############################################################################
# We want to know the number of RLC layer retransmission between the two TCP
# retransmission 
# @input: retxList is optional if you just want to test the combination of Retx
#         RLC entries
# @return: 
# 1. map between timestamp and transmission count
# 2. map between timestamp and transmission bytes
# 3. map between RLC seq num and transmission count
# 4. map between timestamp and entry
# 5. map between RLC seq num and entry
# 6. map between RLC seq num and average retx time (must encounter more than 2 times)
# def RLCTxMaps (entries, start_index, end_index, logID):
def RLCTxMaps (entries, orig_sn_list, logID, interval = (0,0), retxRLCEntries = None):
    start_index, end_index = interval
    if start_index < 0 or end_index < 0 or start_index >= len(entries) or \
       end_index >= len(entries):
        return None
    # Tx Count Map: {ts1: # of transmission, ts2: # of transmission, ...}
    TxCountTimeMap = {}
    # Tx Byte Map: {ts1: # of transmitted byte, ts2: # of transmitted byte}
    TxByteTimeMap = {}
    # SN Count Map: {sn1: # of transmission, sn2: # of transmission}
    TxCountSNMap = dict(zip(orig_sn_list, [0]*len(orig_sn_list)))
    # Time Entry Map: {ts1: correspond entry, ts2: correspond entry}
    TSEntryMap = {}
    # Sequence Number Map: {sn1: correspond entry, sn2: correspond entry}
    SNEntryMap = {}
    # Sequence Number Map: {sn1: avg retx time, sn2: avg retx time...}
    RLCSNRetxTimeDistMap = {}

    # A set of original list of sequence number
    orig_sn_set = set(orig_sn_list)

    listRange = range(start_index, end_index + 1)
    if retxRLCEntries:
        listRange = [i[1] for i in retxRLCEntries]
    for i in listRange:
        PDU_SNs = None
        if entries[i].logID == logID == const.UL_PDU_ID:
            PDU = entries[i].ul_pdu[0]
        elif entries[i].logID == logID == const.DL_PDU_ID:
            PDU = entries[i].dl_pdu[0]
        else:
            continue
        
        for sn_index in range(len(PDU["sn"])):
            if PDU["sn"][sn_index] in orig_sn_set:
                TxCountSNMap[PDU["sn"][sn_index]] += 1
                if SNEntryMap.has_key(PDU["sn"][sn_index]):
                    SNEntryMap[PDU["sn"][sn_index]].append(entries[i])
                else:
                    SNEntryMap[PDU["sn"][sn_index]] = [entries[i]]
                if TxCountTimeMap.has_key(entries[i].timestamp):
                    TxCountTimeMap[entries[i].timestamp] += 1
                    TxByteTimeMap[entries[i].timestamp] += PDU["size"][sn_index]
                else:
                    TSEntryMap[entries[i].timestamp] = entries[i]
                    TxCountTimeMap[entries[i].timestamp] = 1
                    TxByteTimeMap[entries[i].timestamp] = PDU["size"][sn_index]
                """
                if TxByteTimeMap.has_key(entries[i].timestamp):
                    TxByteTimeMap[entries[i].timestamp] += PDU["size"][sn_index]
                else:
                    TxByteTimeMap[entries[i].timestamp] = PDU["size"][sn_index]
                if entries[i] not in RetxEntriesList:
                    RetxEntriesList.append(entries[i])
                """
    RLCSNRetxTimeDistMap = convertSNEntryToSNAvgRetxTime(SNEntryMap)
    return (TxCountTimeMap, TxCountSNMap, TxByteTimeMap, TSEntryMap, SNEntryMap, RLCSNRetxTimeDistMap)

# A wrapper function to combine information between TCP/RLC retx time map and TCP -> RLC map
# Retrun aggregated five maps between TCP and RLC
def TCP_RLC_Retx_Mapper (QCATEntries, entryIndexMap, retxTimeMap, pduID):
    # top level maps
    # {"TCP": [map1, map2], "RLC": [map1, map2....]} # index between TCP and RLC is one-to-one
    countTimeTopMap = {"TCP":[], "RLC":[]}
    byteTimeTopMap = {"TCP":[], "RLC":[]}
    countSNTopMap = {"TCP": None, "RLC":[]}
    entryTimeTopMap = {"TCP":[], "RLC":[]}
    entrySNTopMap = {"TCP": None, "RLC": []}
    RetxTimeDistSNTopMap = {"TCP": [], "RLC": []}

    for key in sorted(retxTimeMap.keys()):
        # Three Time based Maps for TCP to find the retransmission value and timestamp
        TCPcountTimeMap = {}
        TCPbyteTimeMap = {}
        TCPentryTimeMap = {}
        TCPRetxTimeDistMap = {}
        
        keyChain = []
        origTCPPacket = retxTimeMap[key][0][0]
        # map with original packet
        mapped_RLCs, orig_mapped_sn = map_SDU_to_PDU(QCATEntries, entryIndexMap[origTCPPacket], pduID)

        if not mapped_RLCs:
            if DEBUG:
                print "Fail to find a match for the original TCP packet!!!"
            continue
        
        TCPcountTimeMap[origTCPPacket.timestamp] = 1
        TCPbyteTimeMap[origTCPPacket.timestamp] = origTCPPacket.ip["total_len"]
        TCPentryTimeMap[origTCPPacket.timestamp] = origTCPPacket
        TCPRetxTimeDistMap[origTCPPacket.tcp["seq_num"]] = []

        if DEBUG:
            print "# of retransmission is %d" % len(retxTimeMap[key][0])
            print "Original TCP mapped Sequnce number is "
            print orig_mapped_sn
        # consider multiple retransmission
        privTime = origTCPPacket.timestamp

        # Determine the ending index for each RLC retx
        endPointIndices = []
        for retxEntry in retxTimeMap[key][0][1:]:
            TCPRetxTimeDistMap[origTCPPacket.tcp["seq_num"]].append(retxEntry.timestamp - privTime)
            privTime = retxEntry.timestamp
            # TODO: detection anything wrong here
            temp_list, mapped_sn = map_SDU_to_PDU(QCATEntries, entryIndexMap[retxEntry], pduID, hint_index = mapped_RLCs[-1][1])
            # temp_list, mapped_sn = map_SDU_to_PDU(QCATEntries, entryIndexMap[retxEntry], pduID)
            if temp_list:
                # add the first RLC in the map list as a break point, the last
                # break point is used for the divider to count retransmission
                endPointIndices.append(temp_list[0][1])
                mapped_RLCs += temp_list
                TCPcountTimeMap[retxEntry.timestamp] = 1
                TCPbyteTimeMap[retxEntry.timestamp] = retxEntry.ip["total_len"]
                TCPentryTimeMap[retxEntry.timestamp] = retxEntry
            else:
                if DEBUG:
                    print "NO!!!"
                    print "Try to find the match!!!"
        # Map until the one entry after the last retransmission
        entryAfterLastRetx = retxTimeMap[key][1]
        if entryAfterLastRetx:
            if mapped_RLCs:
                lastMapped_list, mapped_sn = map_SDU_to_PDU(QCATEntries, entryIndexMap[entryAfterLastRetx], pduID, hint_index = mapped_RLCs[-1][1])
            else:
                lastMapped_list, mapped_sn = map_SDU_to_PDU(QCATEntries, entryIndexMap[entryAfterLastRetx], pduID, hint_index = mapped_RLCs[-1][1])
        # use the first matched RLC as the ending mapping indicator

        if lastMapped_list:
            mapped_RLCs.append(lastMapped_list[0])

        if mapped_RLCs:
            #RLCcountTimeMap, RLCcountSNMap, RLCbyteTimeMap, RLCentryTimeMap, RLCentrySNMap, RLCSNRetxTimeDistMap \
            # = RLCTxMaps(QCATEntries, mapped_RLCs[0][1], mapped_RLCs[-1][1], pduID, retxRLCEntries = mapped_RLCs)
            #RLCcountTimeMap, RLCcountSNMap, RLCbyteTimeMap, RLCentryTimeMap, RLCentrySNMap, RLCSNRetxTimeDistMap \
            # = RLCTxMaps(QCATEntries, mapped_RLCs[0][1], mapped_RLCs[-1][1], pduID)
            endPoint = mapped_RLCs[-1][1]
            if endPointIndices:
                endPoint = endPointIndices[-1]         

            RLCcountTimeMap, RLCcountSNMap, RLCbyteTimeMap, RLCentryTimeMap, RLCentrySNMap, RLCSNRetxTimeDistMap \
             = RLCTxMaps(QCATEntries, orig_mapped_sn, pduID, interval = (mapped_RLCs[0][1], endPoint))
            #RLCcountTimeMap, RLCcountSNMap, RLCbyteTimeMap, RLCentryTimeMap, RLCentrySNMap, RLCSNRetxTimeDistMap \
            # = RLCTxMaps(QCATEntries, orig_mapped_sn, pduID, interval = (mapped_RLCs[0][1], mapped_RLCs[-1][1]), retxRLCEntries = mapped_RLCs)
            if DEBUG:
                # pick the maximum number of retransmissions in the map
                print "Retransmission count is %d" % (max(RLCcountSNMap.values() + [0]))
                print RLCcountTimeMap
                print RLCcountSNMap
                print RLCbyteTimeMap
                print RLCentryTimeMap
                print RLCentrySNMap
                print RLCSNRetxTimeDistMap

        countTimeTopMap["TCP"].append(TCPcountTimeMap)
        byteTimeTopMap["TCP"].append(TCPbyteTimeMap)
        entryTimeTopMap["TCP"].append(TCPentryTimeMap)
        RetxTimeDistSNTopMap["TCP"].append(TCPRetxTimeDistMap)
        if DETAIL_DEBUG:
            print "Current RLCcountTimeMap is"
            print RLCcountTimeMap
        countTimeTopMap["RLC"].append(RLCcountTimeMap)
        byteTimeTopMap["RLC"].append(RLCbyteTimeMap)
        countSNTopMap["RLC"].append(RLCcountSNMap)
        entryTimeTopMap["RLC"].append(RLCentryTimeMap)
        entrySNTopMap["RLC"].append(RLCentrySNMap)
        RetxTimeDistSNTopMap["RLC"].append(RLCSNRetxTimeDistMap)
        
    if CUR_DEBUG:
        print "^.^\n" * 5
        print countTimeTopMap["RLC"]
        maxIndex = findBestMappedIndex(countTimeTopMap["RLC"], countTimeTopMap["TCP"], entryTimeTopMap["RLC"], countSNTopMap["RLC"])
        print "Find Max retx index is %d\n Avg transmission is %d" % (maxIndex, util.meanValue(countTimeTopMap["RLC"][maxIndex].values()))
        print countTimeTopMap["RLC"][maxIndex]
    
    return {"ts_count": countTimeTopMap, "ts_byte": byteTimeTopMap, \
            "ts_entry": entryTimeTopMap, "sn_count": countSNTopMap, \
            "sn_entry": entrySNTopMap, "sn_retx_time_dist": RetxTimeDistSNTopMap}

############################################################################
###################### Context & Configuration #############################
############################################################################
# return a configuration map
# A map between RRC state, RLC configuration and their count
def getContextInfo(retxMap, logID): 
    total_configs = rw.initFullRRCMap(None)
    for retxEntries in retxMap.values():
        for entry in retxEntries[0]:
            target_config = None
            if logID == const.DL_CONFIG_PDU_ID:
                target_config = str(entry.dl_config)
            elif logID == const.UL_CONFIG_PDU_ID:
                target_config = str(entry.ul_config)
            # insert into the retransmission entry
            if total_configs[entry.rrcID]:
                if target_config in total_configs[entry.rrcID]:
                    total_configs[entry.rrcID][target_config] += 1
                else:
                    total_configs[entry.rrcID][target_config] = 1.0
            else:
                total_configs[entry.rrcID] = {}
                total_configs[entry.rrcID][target_config] = 1.0

    return total_configs

############################################################################
#################### Dup ACK and RLC Fast Retransmision ####################
############################################################################
# Find the duplicate ACKs for a given range
#   {ack_#1:[list of index with same ack], ack_#2:[...], ...}
def detectDupACK (QCATEntries, beginIndex , endIndex):
    dup_ack_map = {}
    # search for duplicate ack
    for index in range(beginIndex, endIndex+1):
        cur_ack = QCATEntries[index].dl_ctrl["ack"]
        if cur_ack:
            if cur_ack in dup_ack_map:
                dup_ack_map[cur_ack].append(index)
            else:
                dup_ack_map[cur_ack] = [index]
    # eliminate non-dup ack
    for key, value in dup_ack_map.items():
        if len(value) <= 1:
            del dup_ack_map[key]
    return dup_ack_map

# Calculate the dup ack ratio and bitmap of retx indices
# Return:
# 1. RATIO of Duplicate ACK # / Total retransmission #
# 2. A bit Map that indicate whether a index is in the retransmission range
def cal_dup_ack_ratio_and_fast_retx_benefit (QCATEntries, entryIndexMap, crossMap):
    count_dup_ack = 0.0
    retx_bit_map = [False] * len(QCATEntries)

    # use the TCP and RLC cross mapping to implement this
    for mapindex in range(len(crossMap["ts_entry"]["TCP"])):
        firstKey = sorted(crossMap["ts_entry"]["TCP"][mapindex].keys())[0]
        lastKey = sorted(crossMap["ts_entry"]["RLC"][mapindex].keys())[-1]
        beginIndex = entryIndexMap[crossMap["ts_entry"]["TCP"][mapindex][firstKey]]
        endIndex = entryIndexMap[crossMap["ts_entry"]["RLC"][mapindex][lastKey]]
        
        dup_ack_map = detectDupACK(QCATEntries, beginIndex, endIndex)
        
        if dup_ack_map:
            count_dup_ack += 1

        if DUP_DEBUG:
            print "First index is %d, Last index is %d" % (beginIndex, endIndex)
        
        retx_bit_map[beginIndex:endIndex+1] = [True] * (endIndex + 1 - beginIndex)

        # TODO: check if all retransmission could save all of them

    dup_ack_ratio = 0
    if len(crossMap["ts_entry"]["TCP"]):
        dup_ack_ratio = count_dup_ack / float(len(crossMap["ts_entry"]["TCP"]))
    
    return dup_ack_ratio, count_dup_ack, float(len(crossMap["ts_entry"]["TCP"])), retx_bit_map

# Detect all duplicate ACKs within a window.
# In detail, we calculate the benefit by transmit the retransmission packets ahead
# OR we retransmit before TCP RTO
# Three cases:
#   1. RLC fast retx occur within the TCP retransmission -- win
#   2. RLC fast retx occur follow by NACK, without TCP retx -- draw
#       2.1 packets will be retrans later -- draw_plus
#   3. RLC fast retx occur follow by an ACK (or a larger NACK), without TCP retx -- lose (real overhead)
# @ return
#   1. break down fraction for each case
#   2. index list of duplicate ACK and retransmitted PDU within the range for each case
#      e.g. {"win":[{"dup_ack":[], "rlc":[], "sn":[]}, {...}], "draw":[...], "draw_plus":[...] "loss":[...]}
#      NOTE: we capture the rlc upto the next ctrl ACK
#   3. Benefit time (the last Dup ACK to the next retx time)
#      e.g. {"win":[], "draw":[]}
def rlc_fast_retx_overhead_analysis(QCATEntries, entryIndexMap, win_size, retx_bit_map, dup_ack_threshold, all_retx_map, draw_percent):
    dup_ack_count = 0.0
    # Dup Acks falls outside the retx intervals
    dup_ack_overhead_count = 0.0
    entry_len = len(QCATEntries)
    # skip over some of the entries
    next_target = None
    # calculate the time in between dup ACKs (deprecated)
    dup_ack_time_intervals = {"non_retx":[], "retx":[]}
    # the whole retransmission map
    rlc_fast_retx_map = {"win":[], "draw":[], "draw_plus":[], "loss":[]}
    # transmission benefit/cost map
    trans_time_benefit_cost_map = {"win":[], "draw_plus":[], "draw":[], "loss":[]}
    # RTT benefit/cost map
    rtt_benefit_cost_time_map = {"win":[], "draw_plus":[], "draw":[], "loss":[]}
    # RTT benefit/cost count map
    rtt_benefit_cost_count_map = {"win":[], "draw_plus":[], "draw":[], "loss":[]}
    # sorted retransmission keys
    sortedKeys = sorted(all_retx_map.keys())

    if DUP_DEBUG:
        print "Duplicate ACK threshold is %d" % dup_ack_threshold

    # add all the index pair into a set
    for entry_index in range(entry_len):
        if next_target and entry_index < next_target:
            continue
        if QCATEntries[entry_index].dl_ctrl["chan"]:
            cur_ack_num = QCATEntries[entry_index].dl_ctrl["ack"]
            temp_count = 0
            dup_ack_index_temp_buffer = []
            dup_ack_temp_time_interval = []

            for j in range(entry_index, min(entry_index+win_size, entry_len)):
                if QCATEntries[j].dl_ctrl["ack"] and QCATEntries[j].dl_ctrl["ack"] == cur_ack_num:
                    temp_count += 1
                    dup_ack_index_temp_buffer.append(j)
                # detect of fast retransmission
                if temp_count >= dup_ack_threshold:
                    # STRICT RULE: 
                    # if any of the index doesn't belong to the retx range
                    # then count as overhead
                    test_overhead = False
                    local_bit_map = []
                    tmp_rlc_sum = {"dup_ack":[], "rlc":[]}
                    benefit_time = 0.0

                    for tmp_index in range(1,len(dup_ack_index_temp_buffer)):
                        cur_entry = QCATEntries[dup_ack_index_temp_buffer[tmp_index]]
                        priv_entry = QCATEntries[dup_ack_index_temp_buffer[tmp_index-1]]
                        dup_ack_temp_time_interval.append(cur_entry.timestamp - priv_entry.timestamp)

                    for index in dup_ack_index_temp_buffer:
                        if not retx_bit_map[index]:
                            test_overhead = True
                           
                        local_bit_map.append(retx_bit_map[index])
 
                    # Next ctrl ACK and Next list (nack)
                    cur_dup_ack = QCATEntries[dup_ack_index_temp_buffer[0]].dl_ctrl["ack"]
                    # TODO: this might be larger than expected
                    next_ctrl_ack_index = findNextCtrlMsg(QCATEntries, dup_ack_index_temp_buffer[-1], "ack", cur_dup_ack)
                    next_list_index = findNextCtrlMsg(QCATEntries, dup_ack_index_temp_buffer[-1], "list", cur_dup_ack)

                    # don't count due to inaccurate info
                    if not next_ctrl_ack_index or not next_list_index:
                        break

                    next_list = QCATEntries[next_list_index].dl_ctrl["list"][0][0]
                    dup_ack_index_temp_buffer += findDupAckInRange(QCATEntries, dup_ack_index_temp_buffer[-1] + 1, next_list_index, cur_dup_ack)
                    tmp_rlc_sum["dup_ack"] = dup_ack_index_temp_buffer
                    
                    firstACKindex = dup_ack_index_temp_buffer[0]
                    lastIndex = max(next_list_index, next_ctrl_ack_index)
                    tmp_rlc_sum["rlc"] = find_RLC_PDU_within_interval(QCATEntries, firstACKindex, lastIndex)

                    if DUP_DEBUG:
                        print "Current sequence number is %d, next Ctrl index is %d, next list index is %d" % (cur_dup_ack, next_ctrl_ack_index, next_list_index)
                    # draw / loss case
                    if test_overhead:
                        dup_ack_overhead_count += 1
                        dup_ack_time_intervals["non_retx"].append(dup_ack_temp_time_interval)
                        
                        # loss case
                        # judge by index order or time order
                        if next_ctrl_ack_index < next_list_index or next_list > cur_dup_ack:
                            rlc_fast_retx_map["loss"].append(tmp_rlc_sum)
                            startTime = QCATEntries[dup_ack_index_temp_buffer[0]].timestamp
                            endTime = QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]].timestamp
                            # the whole section duplication period is the overhead
                            trans_time_benefit_cost_map["loss"].append(endTime-startTime)
                            # To calculate the RTT delay overhead, calculate the number of PDUs in btw the Dup ACKs
                            # Total overhead is that RTT of last STATUS * the number of PDUs
                            count_PDUs = 0.0
                            for index in range(dup_ack_index_temp_buffer[0], dup_ack_index_temp_buffer[dup_ack_threshold-1]+1):
                                if QCATEntries[index].logID == const.UL_PDU_ID:
                                    count_PDUs += len(QCATEntries[index].ul_pdu[0]["sn"])
                            est_rtt = QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]].rtt["rlc"]
                            if est_rtt:
                                rtt_benefit_cost_time_map["loss"].append(est_rtt)
                                rtt_benefit_cost_count_map["loss"].append(count_PDUs)
                        # draw case
                        else:
                            sn_to_index_map_within_dup_acks = find_SN_within_interval(QCATEntries, firstACKindex, dup_ack_index_temp_buffer[dup_ack_threshold-1])
                            retx_seq_num_li = sn_to_index_map_within_dup_acks.keys()
                            # we want to calculate until the next ACK
                            sn_to_index_map_after_dup_acks = find_SN_within_interval(QCATEntries, dup_ack_index_temp_buffer[dup_ack_threshold-1], next_ctrl_ack_index)
                            target_seq_num_li = sn_to_index_map_after_dup_acks.keys()

                            if DUP_DEBUG:
                                print "Retx SN %s" % set(retx_seq_num_li)
                                print "rest SN %s" % set(target_seq_num_li)
                            
                            last_dup_ack_rtt = QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]].rtt["rlc"]
                            rtt_request_index = dup_ack_index_temp_buffer[dup_ack_threshold-1] - 1
                            while not last_dup_ack_rtt and rtt_request_index >= 0:
                                last_dup_ack_rtt = QCATEntries[rtt_request_index].rtt["rlc"]
                                rtt_request_index -= 1

                            draw_benefit_time = 0.0
                            draw_cost_time = 0.0
                            
                            # RTT cost / benefit calculation
                            benefit_count = 0.0
                            cost_count = 0.0
                            for sn in retx_seq_num_li:
                                if sn not in set(target_seq_num_li):
                                    sn_index = sn_to_index_map_within_dup_acks[sn]
                                    if QCATEntries[sn_index].rtt["rlc"]:
                                        # draw_cost_time += QCATEntries[sn_index].rtt["rlc"]
                                        draw_cost_time += last_dup_ack_rtt
                                        cost_count += 1
                                else:
                                    sn_index = sn_to_index_map_after_dup_acks[sn]
                                    # only append positive time here
                                    if QCATEntries[sn_index].rtt["rlc"] and QCATEntries[sn_index].rtt["rlc"] > last_dup_ack_rtt:
                                        draw_benefit_time += (QCATEntries[sn_index].rtt["rlc"] - last_dup_ack_rtt)
                                        benefit_count += 1
                            if DUP_DEBUG:
                                print "Draw_benefit_time is %f" % (draw_benefit_time)
                                print "Draw_cost_time is %f" % (draw_cost_time)

                            # Draw plus case
                            # TODO: verify beneficial
                            # if draw_benefit_time > draw_cost_time:
                            if util.set_partial_belongs_to(set(retx_seq_num_li), set(target_seq_num_li), draw_percent):
                            # all the previous packets has been retransmit before 
                            #if util.set_belongs_to(set(retx_seq_num_li), set(target_seq_num_li)):
                                rlc_fast_retx_map["draw_plus"].append(tmp_rlc_sum)
                                retx_after_dup_ack_index = find_sn_of_interest(QCATEntries, dup_ack_index_temp_buffer[dup_ack_threshold-1], next_ctrl_ack_index, cur_dup_ack)
                                if retx_after_dup_ack_index:
                                    benefit_time = QCATEntries[retx_after_dup_ack_index].timestamp - QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]].timestamp
                                    trans_time_benefit_cost_map["draw_plus"].append(benefit_time)
                                    if DUP_DEBUG:
                                        print "Draw_plus benefit time is %f" % benefit_time
                                    if benefit_count > 0:
                                        rtt_benefit_cost_time_map["draw_plus"].append(draw_benefit_time/benefit_count)
                                        rtt_benefit_cost_count_map["draw_plus"].append(benefit_count)
                            # Draw case
                            else:
                                rlc_fast_retx_map["draw"].append(tmp_rlc_sum)
                                benefit_trans_set = set.intersection(set(retx_seq_num_li), set(target_seq_num_li))
                                count_draw_overhead = 0.0
                                for a in retx_seq_num_li:
                                    if a not in benefit_trans_set:
                                        count_draw_overhead += 1
                                startTime = QCATEntries[dup_ack_index_temp_buffer[0]].timestamp
                                endTime = QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]].timestamp
                                total_fast_rest_len = float(len(retx_seq_num_li))
                                real_overhead = 2*count_draw_overhead - total_fast_rest_len
                                draw_overhead_delay = 0
                                if total_fast_rest_len:
                                    draw_overhead_delay = real_overhead / total_fast_rest_len * (endTime - startTime)
                                    if DUP_DEBUG:
                                        print "Draw: overhead ratio is %f" % (real_overhead / total_fast_rest_len)
                                # The fraction of over-retransmission part is the overhead
                                trans_time_benefit_cost_map["draw"].append(draw_overhead_delay)
                                # retransmission cost
                                if cost_count > 0:
                                    rtt_benefit_cost_time_map["draw"].append((draw_cost_time - draw_benefit_time)/cost_count)
                                    rtt_benefit_cost_count_map["draw"].append(cost_count)
                    # win case
                    else:
                        dup_ack_time_intervals["retx"].append(dup_ack_temp_time_interval)
                        rlc_fast_retx_map["win"].append(tmp_rlc_sum)
                        # TODO: fix the inaccurate TCP retransmission lookup
                        lastDupACKEntry = QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]]
                        # using binary search to find the closest retransmission ahead of timestamp
                        retxEntryTS = util.binary_search_largest_smaller_value(lastDupACKEntry.timestamp, sortedKeys)

                        if DUP_DEBUG:
                            for i in sortedKeys:
                                result = util.convert_ts_in_human(i)
                                result += "-> " + util.convert_ts_in_human(all_retx_map[i][1].timestamp)
                                print result
                                # original mapped RLC
                                first_mapped_RLC_index = entryIndexMap[all_retx_map[i][0][0]]
                                last_mapped_RLC_index = entryIndexMap[all_retx_map[i][0][-1]]
                                first_mapped_RLCs, first_mapped_sn = map_SDU_to_PDU(QCATEntries, first_mapped_RLC_index, const.UL_PDU_ID)
                                last_mapped_RLCs, last_mapped_sn = map_SDU_to_PDU(QCATEntries, last_mapped_RLC_index, const.UL_PDU_ID)
                                tcp_index = entryIndexMap[all_retx_map[i][-1]]
                                post_mapped_RLCs, post_mapped_sn = map_SDU_to_PDU(QCATEntries, tcp_index, const.UL_PDU_ID)
                                if post_mapped_RLCs and first_mapped_RLCs:
                                    print "Post mapped result is %d"
                                    index_result = str(entryIndexMap[all_retx_map[i][0][0]]) + " -> " + str(first_mapped_RLCs[0][1]) + " -> " + str(post_mapped_RLCs[0][1])
                                    print index_result
                                    if first_mapped_RLCs[0][1] > post_mapped_RLCs[0][1]:
                                        print ":" * 50 + " Debugging required Start " + ":" * 50
                                        print "First entry detail: "
                                        pw.printTCPEntry(all_retx_map[i][0][0])
                                        print "Signature: %s" % all_retx_map[i][0][0].ip["signature"]
                                        print "First Mapped RLC detail: "
                                        pw.printRLCEntry(first_mapped_RLCs[0][0], "up")
                                        print "Last entry detail: "
                                        pw.printTCPEntry(all_retx_map[i][0][-1])
                                        print "Signature: %s" % all_retx_map[i][0][-1].ip["signature"]
                                        print "Last Mapped RLC detail: "
                                        pw.printRLCEntry(last_mapped_RLCs[0][0], "up")
                                        print "Next to Last entry detail: "
                                        print "Signature: %s" % all_retx_map[i][0][0].ip["signature"]
                                        pw.printTCPEntry(all_retx_map[i][-1])
                                        print "Last Mapped RLC detail: "
                                        pw.printRLCEntry(post_mapped_RLCs[0][0], "up")
                                        print "=" * 50 + " Debugging required end " + "="*50
                            print "Last dup ack entry is %s" % lastDupACKEntry.timestamp
                            print "Position of the dup ack is %d" % sortedKeys.index(retxEntryTS)

                        retx_after_dup_ack_index = None

                        if retxEntryTS:
                            # find the second retransmission and calculate the gain
                            first_retx_index = entryIndexMap[all_retx_map[retxEntryTS][0][1]]       
                            # TODO: assume uplink here
                            mapped_RLCs, mapped_sn = map_SDU_to_PDU(QCATEntries, first_retx_index, const.UL_PDU_ID)

                            if mapped_RLCs:
                                benefit_time = mapped_RLCs[0][0].timestamp - QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]].timestamp
                                first_mapped_RLC_index = entryIndexMap[all_retx_map[retxEntryTS][0][0]]
                                last_mapped_RLC_index = entryIndexMap[all_retx_map[retxEntryTS][0][-1]]
                                first_mapped_RLCs, first_mapped_sn = map_SDU_to_PDU(QCATEntries, first_mapped_RLC_index, const.UL_PDU_ID)
                                last_mapped_RLCs, last_mapped_sn = map_SDU_to_PDU(QCATEntries, last_mapped_RLC_index, const.UL_PDU_ID)

                                # TODO: inaccurate benefit_time calculation
                                # create a range to constrain the benefit_time
                                # maximum = retransmission time
                                tcp_upper_limit = all_retx_map[retxEntryTS][0][-1].timestamp - all_retx_map[retxEntryTS][0][0].timestamp
                                rlc_upper_limit = 999
                                if first_mapped_RLCs and last_mapped_RLCs:
                                    rlc_upper_limit = last_mapped_RLCs[0][0].timestamp - first_mapped_RLCs[0][0].timestamp
                                    if rlc_upper_limit < 0:
                                        rlc_upper_limit = 999
                                print "Win benefit time is %f" % benefit_time
                                print ">>> TCP benefit upper bound is %f" % tcp_upper_limit
                                print ">>> RLC benefit upper bound is %f" % rlc_upper_limit
                                if benefit_time < 0:
                                    benefit_time = 999
                                benefit_time = min(rlc_upper_limit, benefit_time)
                                    
                                # benefit calculation
                                trans_time_benefit_cost_map["win"].append(benefit_time)
                                # Count the number of PDUs has been tran
                                count_PDUs = 0.0
                                for index in range(dup_ack_index_temp_buffer[0], dup_ack_index_temp_buffer[dup_ack_threshold-1]+1):
                                    if QCATEntries[index].logID == const.UL_PDU_ID:
                                        count_PDUs += len(QCATEntries[index].ul_pdu[0]["sn"])
                                if count_PDUs:
                                    rtt_benefit_cost_time_map["win"].append(tcp_upper_limit / count_PDUs)
                                    rtt_benefit_cost_count_map["win"].append(count_PDUs)

                                if DUP_DEBUG:
                                    # TODO: delete after testing
                                    post_retx_first_index = entryIndexMap[all_retx_map[retxEntryTS][1]]
                                    post_mapped_RLCs, post_mapped_sn = map_SDU_to_PDU(QCATEntries, post_retx_first_index, const.UL_PDU_ID)
                                    if post_mapped_RLCs:
                                        post_TCP_benefit_time = post_mapped_RLCs[0][0].timestamp - QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]].timestamp
                                        start = entryIndexMap[all_retx_map[retxEntryTS][0][0]]
                                        end = post_mapped_RLCs[-1][1]
                                        print "Before 30: %s" % retx_bit_map[start-30:start]
                                        print retx_bit_map[start:end+1]
                                        print "After 100: %s" % retx_bit_map[end:end+100]
                                        print "Last entry's benefit is %f" % post_TCP_benefit_time
                                        print ">"*5+"Post Mapped Last RLC is "
                                        pw.printRLCEntry(post_mapped_RLCs[-1][0], "up")

                                    print "TCP retransmission  is " + const.LOGTYPE_MAP[mapped_RLCs[0][0].logID]
                                    print "Last ACK entry log is " + const.LOGTYPE_MAP[QCATEntries[dup_ack_index_temp_buffer[dup_ack_threshold-1]].logID]
                                    print ">"*5+"Retx TCP:"
                                    pw.printTCPEntry(QCATEntries[first_retx_index])
                                    print ">"*5+"Lower bound TCP:"
                                    pw.printTCPEntry(QCATEntries[post_retx_first_index])
                                    print ">"*5+"Mapped First RLC entry:"
                                    pw.printRLCEntry(mapped_RLCs[0][0], "up")
                                    print ">"*5+"Mapped Last RLC entry:"
                                    pw.printRLCEntry(mapped_RLCs[-1][0], "u p")
                                    print ">"*5+"Dup ACK RLC entry:"
                                    pw.printRLCEntry(lastDupACKEntry, "up")
                        
                        if DUP_DEBUG:
                            start = dup_ack_index_temp_buffer[dup_ack_threshold-1]
                            print "Nearest twenty packets is %s" % retx_bit_map[start:start+20]

                    dup_ack_count += 1
                    next_target = lastIndex+1
                    totalRetxMap = []

                    # print duplicate ACKs
                    if DUP_DEBUG:
                        print "Index list is: " + str(dup_ack_index_temp_buffer)
                        print "Retx table is %s" % local_bit_map
                        for temp_index in dup_ack_index_temp_buffer:
                            pw.printRLCEntry(QCATEntries[temp_index], "down_ctrl")
                        print "$"*100
                    break
        
    return (dup_ack_count, rlc_fast_retx_map, trans_time_benefit_cost_map, rtt_benefit_cost_time_map, rtt_benefit_cost_count_map)

# overall benefit calculation
# TODO: only consider uplink right now
# @return: RTT benefit total time map + RTT benefit total count map
def rlc_fast_retx_overall_benefit( rtt_benefit_cost_time_list, rtt_benefit_cost_count_list):   
    all_kw = ["win", "draw_plus", "draw", "loss"]
    benefit_kw = all_kw[:2]
    overhead_kw = all_kw[2:]
    rtt_benefit_cost_time_map = dict(zip(all_kw, [0.0]*len(all_kw)))
    rtt_benefit_cost_count_map = dict(zip(all_kw, [0.0]*len(all_kw)))
    
    # reduced rtt calculation
    for kw in benefit_kw:
        for index in range(len(rtt_benefit_cost_time_list[kw])):
            avg_time = rtt_benefit_cost_time_list[kw][index]
            count = rtt_benefit_cost_count_list[kw][index]
            rtt_benefit_cost_time_map[kw] += avg_time * count
            rtt_benefit_cost_count_map[kw] += count

    # overhead rtt calculation
    for kw in overhead_kw:
        for index in range(len(rtt_benefit_cost_count_list[kw])):
            avg_time = rtt_benefit_cost_time_list[kw][index]
            count = rtt_benefit_cost_count_list[kw][index]
            rtt_benefit_cost_time_map[kw] += avg_time * count
            rtt_benefit_cost_count_map[kw] += count

    return rtt_benefit_cost_time_map, rtt_benefit_cost_count_map
        

############################################################################
######################## Analysis of Err Demotion ##########################
############################################################################
# Determine ratio of retransmission period experience the three state transission
# Also the short demotion FACH state index to determine the gap
# FACH -> PCH -> FACH
# @return
#   1. Ratio of total_num_short_FACH_demotion / total_num_retx
#   2. list of index with problematic short FACH demotion timer
def err_demotion_analysis(QCATEntries, entryIndexMap, topLevelMaps):
    totalRetx = len(topLevelMaps["ts_entry"]["TCP"])
    err_demote_count = 0.0
    checkStates = [const.FACH_ID, const.PCH_ID, const.FACH_ID]
    err_demotion_FACH_index_list = []

    for i in range(len(topLevelMaps["ts_entry"]["TCP"])):

        # TODO: delete later
        if DUP_DEBUG:
            print "TCP entry length %d, vs RLC entry length %d" % (len(topLevelMaps["ts_entry"]["TCP"]), len(topLevelMaps["ts_entry"]["RLC"]))

        firstKey = sorted(topLevelMaps["ts_entry"]["TCP"][i])[0]
        firstIndex = entryIndexMap[topLevelMaps["ts_entry"]["TCP"][i][firstKey]]
        lastKey = sorted(topLevelMaps["ts_entry"]["TCP"][i])[-1]
        lastIndex = entryIndexMap[topLevelMaps["ts_entry"]["TCP"][i][lastKey]]
        if DUP_DEBUG:
            print topLevelMaps["ts_entry"]["RLC"][i]
        rlcLastKey = sorted(topLevelMaps["ts_entry"]["RLC"][i])[-1]
        # TODO: debug variable, delete later
        lastEntry = topLevelMaps["ts_entry"]["TCP"][i][lastKey]
        if rlcLastKey > lastKey:
            lastIndex = entryIndexMap[topLevelMaps["ts_entry"]["RLC"][i][rlcLastKey]]
            lastEntry = topLevelMaps["ts_entry"]["RLC"][i][rlcLastKey]
        
        # check if the pattern of FACH -> PCH -> FACH exist
        checkIndex = 0
        first_FACH_index = 0
        for index in range(firstIndex, lastIndex+1):
            if checkIndex >= len(checkStates):
                break
            if QCATEntries[index].logID == const.RRC_ID:
                if QCATEntries[index].rrcID == checkStates[checkIndex]:
                    if checkIndex == 0:
                        first_FACH_index = index
                    checkIndex += 1
                else:
                    # reset the cases where first FACH promote
                    # i.e. FACH -> DCH -> PCH -> FACH
                    checkIndex = 0
        if checkIndex >= len(checkStates):
            if DEBUG:
                entry = topLevelMaps["ts_entry"]["TCP"][i][firstKey]
                print "FACH error corresponding TCP entry time %s with index %d" % (util.convert_ts_in_human(entry.timestamp), firstIndex)
                print "The last entry time is %s with index %d" % (util.convert_ts_in_human(lastEntry.timestamp), lastIndex)
            err_demotion_FACH_index_list.append(first_FACH_index)
            err_demote_count += 1

    ratio = 0
    if totalRetx:
        ratio = err_demote_count/totalRetx
    if DEBUG:
        print "Total error pattern %d, and total pattern is %d" % (err_demote_count, totalRetx)
        print "FACH->PCH->FACH pattern ratio (totalPattern/totalRetx) is %f" % (ratio)
    return (ratio, err_demotion_FACH_index_list)

# analyze the best poll_timer configuration to fix the best retransmission
# @return
#   {time:[time_between_poll_err_fatch, ...], poll_timer:[whether_poll_timer_enabled, ...], ...}

def figure_out_best_timer(QCATEntries, FACH_state_list, logID):
    extra_timer = {"time":[], "poll_timer":[]}

    for index in FACH_state_list:
        match_index = search_prev_polling_bit(QCATEntries, index, logID)
        entryConfig = None
        if QCATEntries[match_index].logID == const.UL_PDU_ID:
            entryConfig = QCATEntries[match_index].ul_config
        elif QCATEntries[match_index].logID == const.DL_PDU_ID:
            entryConfig = QCATEntries[match_index].dl_config
        if match_index:
            time_diff = QCATEntries[index].timestamp - QCATEntries[match_index].timestamp
            extra_timer["time"].append(time_diff)
            extra_timer["poll_timer"].append((entryConfig["poll"]["poll_timer"] > 0))

            if CONFIG_DEBUG:
                print "poll timer is %d, and poll period is %d" % (entryConfig["poll"]["poll_timer"], entryConfig["poll"]["poll_periodic_timer"])
                print "Time diff is %f with FACH time %s" % (time_diff, util.convert_ts_in_human(QCATEntries[index].timestamp))
                print "The corresponding index is %d" % (index)

    return extra_timer

############################################################################
############################# Helper functions #############################
############################################################################
# RLC_FAST_RETX_ANALYSIS
# find the nearest control message of ACK or NACK
# @input: 
#   1. ctrl_type: "ack" or "list" (nack)
# @output:
#   1. "index" of target entry
#   2. "None" if not found
def findNextCtrlMsg (QCATEntries, startIndex, ctrl_type, cur_seq):
    entry_len = len(QCATEntries)
    for index in range(startIndex, entry_len):
        if QCATEntries[index].dl_ctrl["chan"]:
            if ctrl_type == "ack":
                if QCATEntries[index].dl_ctrl["ack"] > cur_seq:
                    return index
            elif ctrl_type == "list":
                if QCATEntries[index].dl_ctrl["list"]:
                    list_seq = QCATEntries[index].dl_ctrl["list"][-1][0]
                    if list_seq >= cur_seq:
                        return index
    return None

# RLC_FAST_RETX_ANALYSIS
# find the other duplicate ack in the range
# @ return: a list of duplicate ack index in the original list
def findDupAckInRange (QCATEntries, startIndex, endIndex, cur_seq):
    listDupAck = []
    if endIndex > len(QCATEntries):
        return []
    for index in range(startIndex, endIndex):
        if QCATEntries[index].dl_ctrl["chan"]:
            if QCATEntries[index].dl_ctrl["ack"] and QCATEntries[index].dl_ctrl["ack"] == cur_seq:
                listDupAck.append(index)
    return listDupAck

# RLC_FAST_RETX_ANALYSIS
# find all the RLC packets within the range
# @ return: a list of RLC log index within range
def find_RLC_PDU_within_interval (QCATEntries, startIndex, endIndex):
    listOfRLC = []
    if endIndex > len(QCATEntries):
        return []
    for index in range(startIndex, endIndex):
        if QCATEntries[index].logID == const.UL_PDU_ID:
            listOfRLC.append(index)

    return listOfRLC            

# RLC_FAST_RETX_ANALYSIS
# return a map between sequence number on corresponding entry index
def find_SN_within_interval (QCATEntries, startIndex, endIndex):
    sn_to_entryIndex_map = {}
    if endIndex > len(QCATEntries):
        return []
    for index in range(startIndex, endIndex):
        sn_list = QCATEntries[index].ul_pdu[0]["sn"]
        if QCATEntries[index].logID == const.UL_PDU_ID and sn_list:
            for sn in sn_list:
                sn_to_entryIndex_map[sn] = index
    return sn_to_entryIndex_map    

# RLC_FAST_RETX_ANALYSIS
# Select the largest duplicate ACK number 
# @ input:
#   li = {"win":[{"dup_ack":[], "rlc":[]}, {...}], "draw":[...], "draw_plus":[...] "loss":[...]}
#   li["win"]
# @ return: index of interest entry in the list
def findLongestRLCSeq (fast_retx_map_list):
    maxLen = 0
    maxIndex = 0
    for index in range(len(fast_retx_map_list)):
        cur_len = len(fast_retx_map_list[index]["dup_ack"])
        if cur_len > maxLen:
            maxLen = cur_len
            maxIndex = index
    return maxIndex

# RLC_FAST_RETX_ANALYSIS
# Select the smallest number of RLC entry
# @ input:
#   li = {"win":[{"dup_ack":[], "rlc":[]}, {...}], "draw":[...], "draw_plus":[...] "loss":[...]}
#   li["win"]
# @ return: index of interest entry in the list
def findShortestRLCSeq (fast_retx_map_list):
    minLen = 99999
    minIndex = 0
    for index in range(len(fast_retx_map_list)):
        cur_len = len(fast_retx_map_list[index]["rlc"])
        if cur_len < minLen:
            minLen = cur_len
            minIndex = index
    return minIndex

# RLC_FAST_RETX_ANALYSIS
# find the target fast retx packet for a given range
def find_sn_of_interest (QCATEntries, startIndex, endIndex, seq_num):
    for index in range(startIndex, endIndex):
        if QCATEntries[index].logID == const.UL_PDU_ID and QCATEntries[index].ul_pdu[0]["sn"] \
           and seq_num in QCATEntries[index].ul_pdu[0]["sn"]:
            return index
    return None

# RLC_FAST_RETX_ANALYSIS
# Find the end of TCP retx section in the bit_map
# @ return the last index of TCP retx
def find_end_TCP_retx (bit_map, startIndex):
    for index in range(startIndex, len(bit_map)):
        if not bit_map[index]:
            return index - 1
    return None

# RLC_FAST_RETX_ANALYSIS
# Find the end of TCP retx section in the bit_map
# @ return the last index of TCP retx
def find_end_TCP_retx (bit_map, startIndex):
    for index in range(startIndex, len(bit_map)):
        if not bit_map[index]:
            return index - 1
    return None

# RLC_FAST_RETX_ANALYSIS
# Find the end of TCP retx section in the bit_map
# @ return the last index of TCP retx
def find_begin_TCP_retx (bit_map, startIndex):
    for index in range(startIndex, len(bit_map)):
        if not bit_map[index]:
            return index - 1
    return None

# Select a group with best for demo purpose 
# return the best mapped TCP entry
def findBestMappedIndex(RLCList, TCPList, EntryList, SNCountList):
    maxValue = -1
    maxIndex = -1
    indexOfInterest = []
    # filter out the duplicated sequence number entries    
    for i in range(len(RLCList)):
        if max(RLCList[i].keys()) > max(TCPList[i].keys()):
            indexOfInterest.append(i)
        if util.meanValue([j.rrcID for j in EntryList[i].values()]) > const.DCH_ID:
            indexOfInterest.append(i)
    if not indexOfInterest:
        indexOfInterest = range(len(RLCList))
        print "No entries of interest"
        # return -1

    # the best of the mean * length product
    for i in indexOfInterest:
        mean = util.meanValue(RLCList[i].values())
        # MAX = max(RLCList[i].values() + [0])
        length = len(RLCList[i])
        #maxCount = max(SNCountList[i].values())
        #maxTCPCount = max(TCPList[i].values())
        #if MAX * length > maxValue:
        if mean * length > maxValue:
        #if maxCount > maxValue:
        #if maxTCPCount > maxValue:
            maxIndex = i
            #maxValue = MAX * length
            maxValue = mean * length
            #maxValue = maxCount
            #maxValue = maxTCPCount
    print "Max Product is %d" % maxValue
    return maxIndex

# convert SNEntryMap into SNAvgRetxTime
def convertSNEntryToSNAvgRetxTime (SNEntryMap):
    RLCSNRetxTimeDistMap = {}
    for sn, entries in SNEntryMap.items():
        privTime = entries[0].timestamp
        RLCSNRetxTimeDistMap[sn] = []
        for entry in entries[1:]:
            RLCSNRetxTimeDistMap[sn].append(entries[-1].timestamp - privTime)
            privTime = entry.timestamp
        
    return RLCSNRetxTimeDistMap

# find the previous RLC with polling bit enabled
def search_prev_polling_bit(QCATEntries, startIndex, logID):
    endIndex = max(-1, startIndex - const.MAX_LOOK_AHEAD_INDEX)

    for i in range(startIndex, endIndex, -1):
        if QCATEntries[i].logID == logID == const.UL_PDU_ID:
            for header in QCATEntries[i].ul_pdu[0]["header"][::-1]:
                if header["p"] == 1:
                    return i

    return None
