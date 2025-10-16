# pip install pysnmp pyasn1
from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto.api import v2c

HOST = ("172.28.0.17", 161)
COMMUNITY = "public"

# SNMP OID-y
SYSNAME_OID     = (1, 3, 6, 1, 2, 1, 1, 5, 0)  # hostname
SYSDESCR_OID    = (1, 3, 6, 1, 2, 1, 1, 1, 0)  # opis systemu
SYSOBJECTID_OID = (1, 3, 6, 1, 2, 1, 1, 2, 0)  # vendor id

def decode_snmp_octetstring(value: str) -> str:
    """
    Jeśli prettyPrint() zwróci '0x....' (hex), zdekoduj do tekstu.
    W innym wypadku zwróć oryginał.
    """
    if isinstance(value, str) and value.startswith("0x"):
        hexstr = value[2:]
        try:
            return bytes.fromhex(hexstr).decode("utf-8", errors="replace")
        except Exception:
            return bytes.fromhex(hexstr).decode("latin-1", errors="replace")
    return value

# --- przygotuj GET request ---
oids = [SYSNAME_OID, SYSDESCR_OID, SYSOBJECTID_OID]

reqPDU = v2c.GetRequestPDU()
v2c.apiPDU.set_defaults(reqPDU)
v2c.apiPDU.set_varbinds(reqPDU, [(v2c.ObjectIdentifier(oid), v2c.null) for oid in oids])

reqMsg = v2c.Message()
v2c.apiMessage.set_defaults(reqMsg)
v2c.apiMessage.set_community(reqMsg, COMMUNITY)
v2c.apiMessage.set_pdu(reqMsg, reqPDU)

result = {"hostname": None, "sysDescr": None, "sysObjectID": None}

def cbRecvFun(dispatcher, domain, address, wholeMsg, reqPDU=reqPDU):
    global result
    while wholeMsg:
        rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=v2c.Message())
        rspPDU = v2c.apiMessage.get_pdu(rspMsg)

        if v2c.apiPDU.get_request_id(reqPDU) == v2c.apiPDU.get_request_id(rspPDU):
            err = v2c.apiPDU.get_error_status(rspPDU)
            if err and err != 2:
                print(f"SNMP error: {err.prettyPrint()}")
                dispatcher.job_finished(1)
                break

            for (oid, val) in v2c.apiPDU.get_varbinds(rspPDU):
                oid_tuple = oid.asTuple()
                if oid_tuple == SYSNAME_OID:
                    result["hostname"] = val.prettyPrint()
                elif oid_tuple == SYSDESCR_OID:
                    # <<< tu dekodujemy ewentualny hex >>>
                    result["sysDescr"] = decode_snmp_octetstring(val.prettyPrint())
                elif oid_tuple == SYSOBJECTID_OID:
                    result["sysObjectID"] = val.prettyPrint()

            dispatcher.job_finished(1)
    return wholeMsg

dispatcher = AsyncioDispatcher()
dispatcher.register_recv_callback(cbRecvFun)
dispatcher.register_transport(udp.DOMAIN_NAME, udp.UdpAsyncioTransport().open_client_mode())
dispatcher.send_message(encoder.encode(reqMsg), udp.DOMAIN_NAME, HOST)
dispatcher.job_started(1)
dispatcher.run_dispatcher(3)
dispatcher.close_dispatcher()

print(result)
# przykład:
# {'hostname': 'R12.lab.local',
#  'sysDescr': 'Cisco IOS Software, 7200 Software (C7200-ADV...); ...',
#  'sysObjectID': '1.3.6.1.4.1.9.1.222'}
