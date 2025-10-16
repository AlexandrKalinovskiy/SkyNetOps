from puresnmp import Client

client = Client("127.0.0.1", "public", version=2)  # SNMPv2c
sys_contact  = client.get("1.3.6.1.2.1.1.4.0")
sys_location = client.get("1.3.6.1.2.1.1.6.0")

print("sysContact.0 =", sys_contact)
print("sysLocation.0 =", sys_location)