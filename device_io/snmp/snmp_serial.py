# file: snmp_serial.py
from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto.api import v2c
from typing import Optional, Dict

# ENTITY-MIB: Serial Number
ENT_PHYS_SERIAL_OID = (1, 3, 6, 1, 2, 1, 47, 1, 1, 1, 1, 11)

def get_serial_number(ip: str, community: str = "public") -> Optional[str]:
    """
    Zwraca serial number urządzenia z SNMP ENTITY-MIB.
    Jeśli brak seriala lub SNMP nie zwróci wartości → None.
    """
    host = (ip, 161)
    results: Dict[int, str] = {}

    def in_subtree(oid, prefix):
        return oid.asTuple()[:len(prefix)] == prefix

    def cb(dispatcher, domain, address, whole_msg):
        nonlocal results
        while whole_msg:
            rsp_msg, whole_msg = decoder.decode(whole_msg, asn1Spec=v2c.Message())
            pdu = v2c.apiMessage.get_pdu(rsp_msg)
            for oid, val in v2c.apiPDU.get_varbinds(pdu):
                if not in_subtree(oid, ENT_PHYS_SERIAL_OID):
                    dispatcher.job_finished(1)
                    return whole_msg
                idx = oid.asTuple()[-1]
                results[idx] = val.prettyPrint()
            dispatcher.job_finished(1)
        return whole_msg

    # Build GETNEXT request (walk root of ENT_PHYS_SERIAL_OID)
    req_pdu = v2c.GetNextRequestPDU()
    v2c.apiPDU.set_defaults(req_pdu)
    v2c.apiPDU.set_varbinds(req_pdu, [(v2c.ObjectIdentifier(ENT_PHYS_SERIAL_OID), v2c.Null(""))])

    req_msg = v2c.Message()
    v2c.apiMessage.set_defaults(req_msg)
    v2c.apiMessage.set_community(req_msg, community)
    v2c.apiMessage.set_pdu(req_msg, req_pdu)

    dispatcher = AsyncioDispatcher()
    dispatcher.register_recv_callback(cb)
    dispatcher.register_transport(udp.DOMAIN_NAME, udp.UdpAsyncioTransport().open_client_mode())

    dispatcher.send_message(encoder.encode(req_msg), udp.DOMAIN_NAME, host)
    dispatcher.job_started(1)
    try:
        dispatcher.run_dispatcher(timeout=3)
    except Exception:
        pass
    finally:
        dispatcher.close_dispatcher()

    # Wybieramy pierwszy sensowny numer seryjny (chassis zazwyczaj ma najmniejszy index)
    for idx in sorted(results.keys()):
        sn = results[idx]
        if sn and sn not in ("", "0", "unknown", "Not Specified"):
            return sn.strip()

    return None


# === PRZYKŁADOWE UŻYCIE ===
if __name__ == "__main__":
    serial = get_serial_number("10.0.0.12", "public")
    print("Serial number:", serial)
