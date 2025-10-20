from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto.api import v2c
import device_io.snmp.utils as utils
from models import Facts, DetectPlatform
from parsers.ai_parser import parse_cli_to_model
from . import snmp_interfaces

def get(ip: str) -> Facts:
    host = (ip, 161)
    COMMUNITY = "public"

    SYSNAME_OID     = (1, 3, 6, 1, 2, 1, 1, 5, 0)
    SYSDESCR_OID    = (1, 3, 6, 1, 2, 1, 1, 1, 0)
    SYSOBJECTID_OID = (1, 3, 6, 1, 2, 1, 1, 2, 0)

    reqPDU = v2c.GetRequestPDU()
    v2c.apiPDU.set_defaults(reqPDU)
    v2c.apiPDU.set_varbinds(
        reqPDU, [(v2c.ObjectIdentifier(oid), v2c.null)
                 for oid in (SYSNAME_OID, SYSDESCR_OID, SYSOBJECTID_OID)]
    )

    reqMsg = v2c.Message()
    v2c.apiMessage.set_defaults(reqMsg)
    v2c.apiMessage.set_community(reqMsg, COMMUNITY)
    v2c.apiMessage.set_pdu(reqMsg, reqPDU)

    result = {"hostname": None, "sysDescr": None, "sysObjectID": None}

    def cbRecvFun(dispatcher, domain, address, wholeMsg, reqPDU=reqPDU):
        # <<< USUŃ 'global result' >>>
        while wholeMsg:
            rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=v2c.Message())
            rspPDU = v2c.apiMessage.get_pdu(rspMsg)

            if v2c.apiPDU.get_request_id(reqPDU) == v2c.apiPDU.get_request_id(rspPDU):
                err = v2c.apiPDU.get_error_status(rspPDU)
                if err and err != 2:
                    print(f"SNMP error: {err.prettyPrint()}")
                    dispatcher.job_finished(1)
                    break

                for oid, val in v2c.apiPDU.get_varbinds(rspPDU):
                    ot = oid.asTuple()
                    if ot == SYSNAME_OID:
                        result["hostname"] = val.prettyPrint()
                    elif ot == SYSDESCR_OID:
                        result["sysDescr"] = utils.decode_snmp_octetstring(val.prettyPrint())
                    elif ot == SYSOBJECTID_OID:
                        result["sysObjectID"] = val.prettyPrint()

                dispatcher.job_finished(1)
        return wholeMsg

    dispatcher = AsyncioDispatcher()
    dispatcher.register_recv_callback(cbRecvFun)
    dispatcher.register_transport(udp.DOMAIN_NAME, udp.UdpAsyncioTransport().open_client_mode())
    dispatcher.send_message(encoder.encode(reqMsg), udp.DOMAIN_NAME, host)
    dispatcher.job_started(1)
    dispatcher.run_dispatcher(3)
    dispatcher.close_dispatcher()

    print(result)
    platform_detect = parse_cli_to_model(result.get("sysDescr"), DetectPlatform)

    interfaces = snmp_interfaces.get(ip, core_only=True)

    for iface in interfaces:
        print(f"{iface}")
        # print(f"{iface['name']:25}  {iface['mac']}")

    return Facts(
        hostname=result["hostname"] or "",
        interfaces=interfaces,
        vendor="",
        model="",
        platform=platform_detect.platform,
        serial="",
        os_version="",
        mgmt_ip="",
    )
