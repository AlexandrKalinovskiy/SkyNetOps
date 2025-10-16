from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto.api import v2c

HOST = ("172.28.0.11", 161)
COMMUNITY = "public"

# IF-MIB::ifName
IFNAME_OID = (1, 3, 6, 1, 2, 1, 31, 1, 1, 1, 1)
headVars = [v2c.ObjectIdentifier(IFNAME_OID)]

reqPDU = v2c.GetBulkRequestPDU()
v2c.apiBulkPDU.set_defaults(reqPDU)
v2c.apiBulkPDU.set_non_repeaters(reqPDU, 0)
v2c.apiBulkPDU.set_max_repetitions(reqPDU, 25)
v2c.apiBulkPDU.set_varbinds(reqPDU, [(x, v2c.null) for x in headVars])

reqMsg = v2c.Message()
v2c.apiMessage.set_defaults(reqMsg)
v2c.apiMessage.set_community(reqMsg, COMMUNITY)
v2c.apiMessage.set_pdu(reqMsg, reqPDU)

interfaces = []

def in_subtree(oid, prefix):
    t = oid.asTuple()
    return t[:len(prefix)] == prefix

def cbRecvFun(dispatcher, domain, address, wholeMsg, reqPDU=reqPDU):
    while wholeMsg:
        rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=v2c.Message())
        rspPDU = v2c.apiMessage.get_pdu(rspMsg)

        if v2c.apiBulkPDU.get_request_id(reqPDU) == v2c.apiBulkPDU.get_request_id(rspPDU):
            table = v2c.apiBulkPDU.get_varbind_table(reqPDU, rspPDU)
            err = v2c.apiBulkPDU.get_error_status(rspPDU)
            if err and err != 2:
                dispatcher.job_finished(1)
                break

            end = False
            for row in table:
                for oid, val in row:
                    if not in_subtree(oid, IFNAME_OID) or isinstance(val, v2c.Null):
                        end = True
                        break
                    interfaces.append(val.prettyPrint())
                if end:
                    break

            if end:
                dispatcher.job_finished(1)
                continue

            v2c.apiBulkPDU.set_varbinds(reqPDU, [(x, v2c.null) for x, y in table[-1]])
            v2c.apiBulkPDU.set_request_id(reqPDU, v2c.getNextRequestID())
            dispatcher.send_message(encoder.encode(reqMsg), domain, address)

    return wholeMsg

dispatcher = AsyncioDispatcher()
dispatcher.register_recv_callback(cbRecvFun)
dispatcher.register_transport(udp.DOMAIN_NAME, udp.UdpAsyncioTransport().open_client_mode())
dispatcher.send_message(encoder.encode(reqMsg), udp.DOMAIN_NAME, HOST)
dispatcher.job_started(1)
dispatcher.run_dispatcher(3)
dispatcher.close_dispatcher()

print("\n".join(interfaces))
