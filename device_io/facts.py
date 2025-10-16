def get_facts(conn, vendor):
    return conn.send_command("show version")