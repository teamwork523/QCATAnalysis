import math

"""
Copyright (c) 2012-2014 RobustNet Research Group, University of Michigan.
All rights reserved.

Redistribution and use in source and binary forms are permitted
provided that the above copyright notice and this paragraph are
duplicated in all such forms and that any documentation,
advertising materials, and other materials related to such
distribution and use acknowledge that the software was developed
by the RobustNet Research Group, University of Michigan.  The name of the
RobustNet Research Group, University of Michigan may not 
be used to endorse or promote products derived
from this software without specific prior written permission.
THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, WITHOUT LIMITATION, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
"""

# Timestamp accuracy, in terms of milliseconds
TS_DELTA = 1

# Map month to numerical value
MONTH_MAP = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, \
             "may": 5, "jun": 6, "jul": 7, "aug": 8, \
             "sep": 9, "oct": 10, "nov": 11, "dec": 12}

# global delimitor
DEL = "\t"

############################################################################
################################# PCAP Related #############################
############################################################################
# Link layer header type
LINKTYPE_ETHERNET = 1
LINKTYPE_RLC = 12

# Common byte length
LINK_HEADER_LEN = {LINKTYPE_ETHERNET:14,\
			   	   LINKTYPE_RLC:0}

# Upper bound for throughput
UPPER_BOUND_TP = math.pow(2, 30)

# Number of ACKs that triggers Fast retransmission
FAST_RETX_COUNT = 3

# Retx packet gap based on wireshark's implementation (in secs)
RETX_GAP = 0.003

############################################################################
################################# QCAT Related #############################
############################################################################
# QxDM log of interest summary

# General
PROTOCOL_ID = int("0x11EB", 16)

# WCDMA
RRC_ID = int("0x4125", 16)
EUL_STATS_ID = int("0x4311", 16)
DL_CONFIG_PDU_ID = int("0x4132", 16)
UL_CONFIG_PDU_ID = int("0x4133", 16)    # polling configurations included
DL_CTRL_PDU_ID = int("0x4134", 16)      # LIST/ACK info on UL RLC AM
UL_PDU_ID = int("0x413B", 16)   # UL on Link Layer info
DL_PDU_ID = int("0x418B", 16)   # DL on Link Layer info
CELL_RESELECTION_ID = int("0x4005", 16)  # Cell reselection information (power)
SIG_MSG_ID = int("0x412F", 16) # WCDMA signaling message
PRACH_PARA_ID = int("0x4160", 16) # PRACH parameters

# LTE
LTE_UL_RLC_PDU_ID = int("0xB092", 16)
LTE_DL_RLC_PUD_ID = int("0xB082", 16)
LTE_UL_CONFIG_RLC_ID = int("0xB091", 16)
LTE_DL_CONFIG_RLC_ID = int("0xB081", 16)
LTE_CELL_MEASUREMENT_ID = int("0xB180", 16)
LTE_RRC_OTA_ID = int("0xB0C0", 16)

# EVENTs
EVENT_ID = int("0x1FFB", 16)

LOGTYPE_MAP = {PROTOCOL_ID: "Protocol Services Data",
               RRC_ID: "WCDMA RRC States",
               EUL_STATS_ID: "WCDMA EUL Link Statistics", 
               UL_PDU_ID: "WCDMA UL PDU information", 
               DL_PDU_ID: "WCDMA DL PDU information",
               CELL_RESELECTION_ID: "WCDMA Signal Strength related",
               DL_CONFIG_PDU_ID: "WCDMA Downlink RLC configuration",
               UL_CONFIG_PDU_ID: "WCDMA Uplink RLC configuration",
               DL_CTRL_PDU_ID: "WCDMA Downlink control PDU",
               EVENT_ID: "Event",
               PRACH_PARA_ID: "WCDMA RACH Parameters"}

# WCDMA signaling message
CH_TYPE_OF_INTEREST = set([
    "DL_CCCH",
    "DL_DCCH",
    "UL_CCCH",
    "UL_DCCH"])

# T-Mobile
TMOBILE = "tmobile"
MSG_PHY_CH_RECONFIG = "physicalChannelReconfiguration"
MSG_PHY_CH_RECONFIG_COMPLETE = "physicalChannelReconfigurationComplete"
MSG_RADIO_BEARER_RECONFIG = "radioBearerReconfiguration"
MSG_RADIO_BEARER_RECONFIG_COMPLETE = "radioBearerReconfigurationComplete"
MSG_CELL_UP = "cellUpdate"
MSG_CELL_UP_CONFIRM = "cellUpdateConfirm"

# AT&T 3G + ALL LTE
ATT = "att"
VERIZON = "verizon"
MSG_CONNECT_REQUEST = "rrcConnectionRequest"
MSG_CONNECT_SETUP = "rrcConnectionSetup"
MSG_CONNECT_SETUP_COMPLETE = "rrcConnectionSetupComplete"
MSG_CONNECT_RELEASE = "rrcConnectionRelease"
MSG_CONNECT_RELEASE_COMPLETE = "rrcConnectionReleaseComplete"
MSG_CONNCT_RECONFIG = "rrcConnectionReconfiguration"
MSG_CONNCT_RECONFIG_COMPLETE = "rrcConnectionReconfigurationComplete"
MSG_SECURITY_COMMAND = "securityModeCommand"
MSG_SECURITY_COMPLETE = "securityModeComplete"

MSG_TYPE_OF_INTEREST = set([
    MSG_PHY_CH_RECONFIG,
    MSG_PHY_CH_RECONFIG_COMPLETE,
    MSG_CELL_UP,
    MSG_CELL_UP_CONFIRM,
    MSG_RADIO_BEARER_RECONFIG,
    MSG_RADIO_BEARER_RECONFIG_COMPLETE,
    MSG_CONNECT_REQUEST,
    MSG_CONNECT_SETUP,
    MSG_CONNECT_SETUP_COMPLETE,
    MSG_CONNECT_RELEASE,
    MSG_CONNECT_RELEASE_COMPLETE,
    MSG_CONNCT_RECONFIG,
    MSG_CONNCT_RECONFIG_COMPLETE,
    MSG_SECURITY_COMMAND,
    MSG_SECURITY_COMPLETE])

MSG_OF_INTEREST = set([
    "rrc-StateIndicator", # from DL_DCCH
    "cellUpdateCause"]) # from UL_DCCH

# Network types
WCDMA = "wcdma"
LTE = "lte"

####################################
######### Flow Analysis ############
####################################
FLOW_TIME_WIN = 10  # unit is second

####################################
############## HTTP ################
####################################
HTTP_DST_PORT = 80
HTTP_LINE_DEL = "\r\n"
HTTP_FIELD_DEL = ": "
MAX_PAIR_TIME_DIFF = 20 # unit of seconds
MAX_USER_DELAY_SEC = 10

HOST_OF_INTEREST = set([
    "www.yahoo.com",
    "instagram.com",
    "www.google.com",
    "www.djaverages.com",
    "m.youtube.com",
    "m.kayak.com",
    "www.amazon.com",
    "www.cnn.com",
    "m.espn.go.com",
    "m.accuweather.com"])

####################################
############### UDP ################
####################################
UDP_RTT_LIMIT = 5
UDP_Header_Len = 8
# instrumented index value
UDP_WAIT_LIMIT = 32
UDP_GRAN_LIMIT = 1024

# Include data configuration settings
# TODO: hard configured, to be changed
DATA_LOGIC_CHANNEL_ID = 19

# DNS related
DNS_PORT = 53
DNS_QUERY = 0
DNS_RESPONSE = 1

####################################
############ RRC State #############
####################################
# map between RRC id and RRC state
DISCONNECTED_ID = 0
CONNECTING_ID = 1
FACH_ID = 2
DCH_ID = 3
PCH_ID = 4
# 3G TMobile RRC transition
FACH_TO_DCH_ID = 5
PCH_TO_FACH_ID = 6
DCH_TO_FACH_ID = 7
FACH_TO_PCH_ID = 8

TMOBILE_3G_RRC_TRANSITION_ID_GROUP = \
    set([FACH_TO_DCH_ID, \
         PCH_TO_FACH_ID, \
         DCH_TO_FACH_ID, \
         FACH_TO_PCH_ID])

# 3G ATT promotion transition
DISCONNECTED_TO_DCH_ID = 9
DCH_TO_DISCONNECTED_ID = 10

ATT_3G_RRC_TRANSITION_ID_GROUP = \
    set([DISCONNECTED_TO_DCH_ID, \
         DCH_TO_DISCONNECTED_ID])

# LTE Tmobile transition state
IDLE_CAMPED_to_CONNECTED_ID = 11
CONNECTED_TO_IDLE_CAMPED_ID = 12

LTE_RRC_TRANSITION_ID_GROUP = \
    set([IDLE_CAMPED_to_CONNECTED_ID, \
         CONNECTED_TO_IDLE_CAMPED_ID])

RRC_MAP = {DISCONNECTED_ID: "DISCONNECTED", \
           CONNECTING_ID: "CONNECTING", \
           FACH_ID: "FACH", \
           DCH_ID: "DCH", \
           PCH_ID: "PCH", \
           FACH_TO_DCH_ID: "FACH_TO_DCH", \
           PCH_TO_FACH_ID: "PCH_TO_FACH", \
           DCH_TO_FACH_ID: "DCH_TO_FACH", \
           FACH_TO_PCH_ID: "FACH_TO_PCH", \
           DISCONNECTED_TO_DCH_ID: "DISCONNECTED_TO_DCH", \
           DCH_TO_DISCONNECTED_ID: "DCH_TO_DISCONNECTED", \
           IDLE_CAMPED_to_CONNECTED_ID: "IDLE_CAMPED_to_CONNECTED", \
           CONNECTED_TO_IDLE_CAMPED_ID: "CONNECTED_TO_IDLE_CAMPED"}

# Generic RRC states in UMTS w/o Arteficial RRC State
RRC_ORIG_MAP = {FACH_ID: "CELL_FACH", \
                DCH_ID: "CELL_DCH", \
                PCH_ID: "CELL_PCH"}

# For WCDMA signaling message parsing
RRC_REVERSE_MAP = {
    "cell-PCH": PCH_ID,
    "cell-FACH": FACH_ID,
    "cell-DCH": DCH_ID}

# 1 sec for DCH promotion, and 0.2 sections for PCH promotion
TIMER = { FACH_TO_DCH_ID: 1, \
          PCH_TO_FACH_ID: 0.2}

# transport layer protocol map
IP_ID = int("0x01", 16) # QCAT protocol id
TCP_ID = 6
UDP_ID = 17
IDtoTLP_MAP = {TCP_ID: "TCP",
               UDP_ID: "UDP"}
TLPtoID_MAP = {"TCP": TCP_ID,
               "UDP": UDP_ID}
               
# QCAT Entry constant
Payload_Header_Len = 8
IP_Header_Len = 20
TCP_Header_Len = 20 + 12 # include option

####################################
############### RLC ################
####################################
RLC_LI_THRESHOLD = 126 # If the current PDU size is greater than 126, then LI length is 15 bits (2 bytes including E bit)
RLC_LI_LIMIT = 32677

# Retransmission mapping (heuristics)
MAX_ENTRIES_LIST = 10000
MIN_MAPPING_THRESHOLD = 0.5

# maximum lookup ahead in search for the polling bit
MAX_LOOK_AHEAD_INDEX = 200

# RLC DL retransmission
RETX_PERIOD_THRESHOLD = 5
MIN_SN_PERIOD = 20

# Maximum RLC UL sequence number
MAX_RLC_UL_SEQ_NUM = 4096

####################################
############# Physical #############
####################################
# PRACH message
PRACH_KEY_TO_ID_MAP = {"ABORT": 4,\
                       "DONE": 1}
PRACH_ABORT = 4
PRACH_DONE = 1
PRACH_AICH_STATUS_SET = set([
    PRACH_ABORT, \
    PRACH_DONE])

############################################################################
################################# Log Message ##############################
############################################################################
# Non-unique cross-layer mapping
NON_UNIQUE_MAPPING_WARNING = "WARNING: Non-unique Mapping"

############################################################################
################################# Profile ##################################
############################################################################
EXTEND_SECONDS = 10
PROFILE_FILENAME = "profile.txt"

############################################################################
################################## QoE #####################################
############################################################################
# Video
MEDIA_PLAYER_TAG = "MediaPlayer"
MEDIA_PLAYER_WARNING_TAG = "info/warning"
MEDIA_PLAYER_STALL_START = 701
MEDIA_PLAYER_STALL_END = 702
MEDIA_PLAYER_STALL_BANDWIDTH_LOW = 703
MEDIA_PLAYER_BUFFERING = "buffering"

TIME_SYC_TAG = "sync_time"

# Facebook
QOE_TIME_OFFSET = 0.3
