import socket
from typing import Optional, Dict, List

from netmiko import ConnectHandler
from netmiko.ssh_autodetect import SSHDetect
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

def connect_ssh(host, username, password, device_type):
    netmiko_device = {
        "device_type": device_type,   
        "host": host,
        "username": username,
        "password": password,
        "fast_cli": True,
        "ssh_config_file": "~/.ssh/config"
    }

    return ConnectHandler(**netmiko_device)

def run_command(conn, command):
    if isinstance(command, str):
        # pojedyncza komenda
        return conn.send_command(command)

    elif isinstance(command, (list, tuple)):
        # kilka komend - uruchom po kolei
        outputs = []
        for cmd in command:
            out = conn.send_command(cmd)
            outputs.append(f"\n### COMMAND: {cmd}\n{out}")
        return "\n".join(outputs)

    else:
        raise ValueError(f"Nieprawidłowy typ komendy: {type(command)}")

def disable_paging(conn, device_type: str):
    dt = device_type.lower()
    try:
        if "cisco_ios" in dt or "arista" in dt:
            conn.send_command("terminal length 0")
        elif "dell_os10" in dt or "os10" in dt:
            conn.send_command("terminal length 0")  # OS10 akceptuje
            # alternatywnie: do pojedynczej komendy dodawaj "| no-more"
        elif "juniper" in dt or "junos" in dt:
            conn.send_command("set cli screen-length 0")
        elif "huawei" in dt or "vrp" in dt or "comware" in dt:
            conn.send_command("screen-length 0 temporary")
        elif "forti" in dt:
            pass  # zwykle nie wymaga
    except Exception:
        pass  # niektóre platformy nie mają tej komendy

def grab_ssh_banner(ip: str, port: int = 22, timeout: float = 3.0) -> Optional[str]:
    try:
        with socket.create_connection((ip, port), timeout=timeout) as s:
            s.settimeout(timeout)
            # próbujemy odczytać banner (często urządzenia odsyłają np. "SSH-2.0-Cisco-1.25")
            banner = s.recv(256)
            return banner.decode(errors="ignore").strip()
    except Exception:
        return None

def detect_with_sshdetect(ip: str, username: str, password: str, port: int = 22, timeout: int = 10) -> Optional[str]:
    """Używa Netmiko SSHDetect -> zwraca najlepiej dopasowany device_type (string) lub None."""
    try:
        detector = SSHDetect(device_type="autodetect", ip=ip, username=username, password=password, port=port, timeout=timeout)
        best_match = detector.autodetect()
        return best_match  # np. "cisco_ios", "arista_eos", "dell_os10", ...
    except (NetmikoAuthenticationException, NetmikoTimeoutException):
        raise
    except Exception:
        return None

def try_connect_by_list(ip: str, username: str, password: str, candidates: List[str], port: int = 22, timeout: int = 8) -> Optional[Dict]:
    """
    Próbujemy po kolei próbować połączeń z różnymi device_type. Jeśli się połączy i
    np. wykonamy 'show version' (jeśli działa) — zwracamy device_type i snippet outputu.
    """
    for devtype in candidates:
        try:
            conn = ConnectHandler(device_type=devtype, host=ip, username=username, password=password, port=port, timeout=timeout)
            # próbujemy wykonać prostą komendę; komenda może być vendor-specific, tutaj ogólne 'show version'
            try:
                output = conn.send_command("show version", expect_string=r"#|>|$")
            except Exception:
                # nie wszystkie platformy rozumieją 'show version' — próbujemy pobrać prompt
                output = conn.find_prompt()
            conn.disconnect()
            return {"device_type": devtype, "probe_output": output}
        except NetmikoAuthenticationException:
            # złe dane, nie kontynuujemy dla innych device_type z tymi credentialami?
            # -> często warto spróbować dalej, bo różne devtype mogą różnie reagować
            continue
        except NetmikoTimeoutException:
            continue
        except Exception:
            continue
    return None

def detect_device(ip: str, username: str, password: str):
    # 1) banner grabbing
    banner = grab_ssh_banner(ip, port=8722)
    print("Banner:", banner)

    # 2) SSHDetect (szybki, jeśli mamy creds)
    try:
        guess = detect_with_sshdetect(ip, port=8722, username=username, password=password)
        print("SSHDetect guess:", guess)
    except NetmikoAuthenticationException:
        print("Auth failed for SSHDetect")
    except NetmikoTimeoutException:
        print("Timeout for SSHDetect")

    # 3) Fallback - próba z listą najbardziej typowych device_type
    candidates = ["cisco_ios", "cisco_nxos", "arista_eos", "dell_os10", "dell_force10", "juniper", "fortinet",
                  "hp_procurve", "huawei", "linux"]
    result = try_connect_by_list(ip, username, password, candidates)
    print("Fallback result:", result)