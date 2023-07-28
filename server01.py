#!/usr/bin/env python3
# Blog: https://www.technopolis.tv/blog/2023/07/24/LoRa-Writing-our-own-Protocol-Part-2-Hardware/

import socket
import json
import base64
from binascii import hexlify, unhexlify

PROTO_SIZE = 12
PROTO_VERSION = b"\x02"
PUSH_DATA = b"\x00"
PUSH_ACK = b"\x01"
PULL_DATA = b"\x02"
PULL_RESP = b"\x03"
PULL_ACK = b"\x04"
TX_ACK = b"\x05"

local_ip = "0.0.0.0"
local_port = 1700
buffer_size = 1024
downlink = False
tx = {"txpk": {"imme": True, "freq": None, "rfch": 0, "powe": 14, "modu": "LORA", "datr": "SF8BW125", "codr": "4/6", "ipol": True, "prea": 8, "size": 0, "data": None}}


def parse_lorawan(data):
    for rx in data["rxpk"]:
        if rx["modu"] == "LORA":
            if rx["stat"] == 1:
                send_downlink(rx)

            try:
                print(f"[*] LoRaWAN Packet received")
                print(f"    RX Time: {rx['time']}")
                # print(f"    RX Timestamp: {rx['tmms']}")
                print(f"    RX finished: {rx['tmst']}")
                print(f"    CRC Status: {rx['stat']}")
                print(f"    Frequency: {rx['freq']}MHz")
                print(f"    Channel: {rx['chan']}")
                print(f"    RF Chain: {rx['rfch']}")
                print(f"    Coding Rate: {rx['codr']}")
                print(f"    Data Rate: {rx['datr']}")
                print(f"    RSSI: {rx['rssi']}dBm")
                print(f"    SNR: {rx['lsnr']}dB")
                print(f"    Size: {rx['size']} bytes")
                print(f"    Data: {hexlify(base64.b64decode(rx['data']))}")
            except:
                print(f"[!] No valid JSON: {rx}")


def parse_stats(gateway, data):
    print(f"[*] Gateway Statistics received")
    print(f"    ID: {hexlify(gateway)}")
    print(f"    Time: {data['stat']['time']}")
    print(f"    Packets received: {data['stat']['rxnb']}")
    print(f"    Packets received (valid): {data['stat']['rxok']}")
    print(f"    Packets forwarded: {data['stat']['rxfw']}")
    print(f"    Acknowledged upstream: {data['stat']['ackr']}%")
    print(f"    Downlink received: {data['stat']['dwnb']}")
    print(f"    Packets emitted: {data['stat']['txnb']}")


def send_downlink(data):
    global downlink

    tx["txpk"]["freq"] = data['freq']
    tx["txpk"]["data"] = data['data']
    tx["txpk"]["size"] = data['size'] 

    downlink = True


if __name__ == "__main__":
    server = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    server.bind((local_ip, local_port))

    print(f"[*] Starting LoRaWAN UDP Server {local_ip}:{local_port}")

    try:  
        while(True):
            data, addr = server.recvfrom(buffer_size)

            if len(data) >= PROTO_SIZE:
                token = data[1:3]
                identifier = data[3].to_bytes(1, "little")
                gateway = data[4:12]

                # print(f"token: {token} id: {identifier} gateway: {hexlify(gateway)} data: {data[12:]}")

                if identifier == PUSH_DATA:
                    try:
                        json_payload = json.loads(data[12:])
                        if "rxpk" in json_payload:
                            parse_lorawan(json_payload)
                        else:
                            parse_stats(gateway, json_payload)
                    except:
                        print(f"[!] No valid JSON: {data[12:]}")

                    # Send PUSH_ACK
                    payload = PROTO_VERSION
                    payload += token
                    payload += PUSH_ACK

                    server.sendto(payload, addr)
                    
                elif identifier == PULL_DATA:
                    # Send PULL_ACK
                    payload = PROTO_VERSION
                    payload += token
                    payload += PULL_ACK

                    server.sendto(payload, addr)

                    if downlink:
                        print(f"[*] Echoing packet back")

                        payload = PROTO_VERSION
                        payload += token
                        payload += PULL_RESP

                        server.sendto(payload + json.dumps(tx).encode("utf-8"), addr)
                        downlink = False
                
                elif identifier == TX_ACK:
                    if len(data[12:]) == 0:
                        print(f"[*] Received acknowledge token {hexlify(token)} from {hexlify(gateway)}")
                    else:
                        print(f"[*] Received error token {hexlify(token)} from {hexlify(gateway)}")
                        print(f"    Error message: {data[12:]}")
                
                else:
                    print(f"[!] Unknown UDP Packet: {hexlify(data)}")
                
            else:
                print(f"[!] Wrong UDP Packet size: {len(data)}")
            
    except KeyboardInterrupt:
        print(" [*] Shutting down LoRaWAN UDP Server...")
        
    finally:
        server.close()