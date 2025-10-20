from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto.api import v2c

def get(ip: str):
    host = (ip, 161)
    community = "public"

    # IF-MIB OID-y
    IFDESCR_OID = (1, 3, 6, 1, 2, 1, 2, 2, 1, 2)   # ifDescr – pełne nazwy interfejsów
    IFPHYSADDR_OID = (1, 3, 6, 1, 2, 1, 2, 2, 1, 6)  # ifPhysAddress – MAC adres

    def bulkwalk(prefix_oid):
        headVars = [v2c.ObjectIdentifier(prefix_oid)]
        reqPDU = v2c.GetBulkRequestPDU()
        v2c.apiBulkPDU.set_defaults(reqPDU)
        v2c.apiBulkPDU.set_non_repeaters(reqPDU, 0)
        v2c.apiBulkPDU.set_max_repetitions(reqPDU, 25)
        v2c.apiBulkPDU.set_varbinds(reqPDU, [(x, v2c.null) for x in headVars])

        reqMsg = v2c.Message()
        v2c.apiMessage.set_defaults(reqMsg)
        v2c.apiMessage.set_community(reqMsg, community)
        v2c.apiMessage.set_pdu(reqMsg, reqPDU)

        results = {}

        def in_subtree(oid, prefix):
            return oid.asTuple()[:len(prefix)] == prefix

        def cb(dispatcher, domain, address, wholeMsg, reqPDU=reqPDU):
            nonlocal results
            while wholeMsg:
                rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=v2c.Message())
                rspPDU = v2c.apiMessage.get_pdu(rspMsg)

                if v2c.apiBulkPDU.get_request_id(reqPDU) == v2c.apiBulkPDU.get_request_id(rspPDU):
                    table = v2c.apiBulkPDU.get_varbind_table(reqPDU, rspPDU)
                    done = False
                    for row in table:
                        for oid, val in row:
                            if not in_subtree(oid, prefix_oid) or isinstance(val, v2c.Null):
                                done = True
                                break
                            index = oid.asTuple()[-1]
                            results[index] = val.prettyPrint()
                        if done:
                            break

                    if done:
                        dispatcher.job_finished(1)
                        continue

                    v2c.apiBulkPDU.set_varbinds(reqPDU, [(x, v2c.null) for x, _ in table[-1]])
                    v2c.apiBulkPDU.set_request_id(reqPDU, v2c.getNextRequestID())
                    dispatcher.send_message(encoder.encode(reqMsg), domain, address)
            return wholeMsg

        dispatcher = AsyncioDispatcher()
        dispatcher.register_recv_callback(cb)
        dispatcher.register_transport(udp.DOMAIN_NAME, udp.UdpAsyncioTransport().open_client_mode())
        dispatcher.send_message(encoder.encode(reqMsg), udp.DOMAIN_NAME, host)
        dispatcher.job_started(1)
        dispatcher.run_dispatcher(3)
        dispatcher.close_dispatcher()
        return results


    def parse_mac(hex_string):
        if not hex_string or not hex_string.startswith("0x"):
            return None
        hex_value = hex_string[2:]
        return ":".join(hex_value[i:i+2] for i in range(0, len(hex_value), 2))


    # === Pobieramy nazwy i MAC-e ===
    names = bulkwalk(IFDESCR_OID)
    macs = bulkwalk(IFPHYSADDR_OID)

    interfaces = []
    for idx in sorted(names.keys(), key=int):
        interfaces.append(names[idx])
        # interfaces.append({
        #     "name": names[idx],
        #     "mac": parse_mac(macs.get(idx, ""))
        # })

    return  interfaces
