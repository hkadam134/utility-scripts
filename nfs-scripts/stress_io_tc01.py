import paramiko
import logging
import time
import sys
import threading
import random

# Setup logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("nfs_metadata_stress.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Global test space
DIR_COUNT = 50
FILE_COUNT = 100
LARGE_COUNT = 20

# Hardcoded config
CLIENTS = ["10.8.128.29", "10.8.128.30"]
SERVER = "magna048.ceph.redhat.com"
EXPORT = "/ibm/scale_volume"
NFS_PORT = 2049
USER = "root"


def ssh_connect(host, user, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=user, password=password)
    return ssh


def run_cmd(ssh, cmd, desc=""):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    host = ssh.get_transport().getpeername()[0]
    logging.info(f"[{host}] CMD: {cmd}")
    if desc:
        logging.info(f"[{host}] {desc}: {out if out else 'OK'}")
    if rc != 0:
        logging.error(f"[{host}] Command failed: {err}")
    return out


def mount_nfs(ssh, server, export, mount_point, nfs_port):
    run_cmd(ssh, f"mkdir -p {mount_point}", "Create mount dir")
    run_cmd(ssh, f"mount -t nfs -o port={nfs_port} {server}:{export} {mount_point}", "Mount NFS")


def prepare_environment(ssh, mount_point):
    for i in range(1, DIR_COUNT + 1):
        run_cmd(ssh, f"mkdir -p {mount_point}/dir_{i}", f"Create dir_{i}")
    for i in range(1, FILE_COUNT + 1):
        run_cmd(ssh, f"touch {mount_point}/file_{i}", f"Create file_{i}")
    for i in range(1, LARGE_COUNT + 1):
        run_cmd(ssh, f"touch {mount_point}/large_{i}", f"Create large_{i}")


def metadata_worker(ssh, mount_point, duration):
    end_time = time.time() + duration
    while time.time() < end_time:
        fpath = f"{mount_point}/file_{random.randint(1, FILE_COUNT)}"
        dpath = f"{mount_point}/dir_{random.randint(1, DIR_COUNT)}"
        ops = [
            f"touch {fpath}",
            f"chmod 644 {fpath}",
            f"chown root:root {fpath}",
            f"ls -l {dpath} >/dev/null 2>&1",
        ]
        cmd = random.choice(ops)
        run_cmd(ssh, cmd, "Metadata op")
        time.sleep(0.5)


def antivirus_worker(ssh, mount_point, duration):
    end_time = time.time() + duration
    while time.time() < end_time:
        dpath = f"{mount_point}/dir_{random.randint(1, DIR_COUNT)}"
        run_cmd(ssh, f"find {dpath} -type f -exec stat {{}} \\; >/dev/null 2>&1", "AV scan sim")
        run_cmd(ssh, f"touch {dpath}/av_marker", "AV update marker")
        time.sleep(1)


def checksum_worker(ssh, mount_point, duration):
    end_time = time.time() + duration
    while time.time() < end_time:
        fpath = f"{mount_point}/large_{random.randint(1, LARGE_COUNT)}"
        run_cmd(ssh, f"dd if=/dev/zero of={fpath} bs=1M count=1 oflag=direct conv=fsync >/dev/null 2>&1", "Write chunk")
        run_cmd(ssh, f"md5sum {fpath} >/dev/null 2>&1", "Checksum")
        time.sleep(1)


def run_stress(node, user, password, server, export, nfs_port, mount_point, duration, workers=2, do_prepare=False):
    ssh = ssh_connect(node, user, password)
    mount_nfs(ssh, server, export, mount_point, nfs_port)

    if do_prepare:
        prepare_environment(ssh, mount_point)

    threads = []
    for _ in range(workers):
        t1 = threading.Thread(target=metadata_worker, args=(ssh, mount_point, duration))
        t2 = threading.Thread(target=antivirus_worker, args=(ssh, mount_point, duration))
        t3 = threading.Thread(target=checksum_worker, args=(ssh, mount_point, duration))
        threads.extend([t1, t2, t3])

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    run_cmd(ssh, f"umount {mount_point}", "Unmount NFS")
    ssh.close()


def main():
    if len(sys.argv) != 5:
        print("Usage: python3 nfs_metadata_stress.py <password> <duration> <mount-point> <workers>")
        sys.exit(1)

    password = sys.argv[1]
    duration = int(sys.argv[2])
    mount_point = sys.argv[3]
    workers = int(sys.argv[4])

    # 🔹 Log parsed values clearly
    logging.info("========== TEST CONFIG ==========")
    logging.info(f"Password   : {'*' * len(password)}")
    logging.info(f"Duration   : {duration} seconds")
    logging.info(f"Mount Path : {mount_point}")
    logging.info(f"Workers    : {workers} per client")
    logging.info(f"Clients    : {CLIENTS}")
    logging.info("=================================")

    # First: prepare step
    threads = []
    for node in CLIENTS:
        t = threading.Thread(target=run_stress,
                             args=(node, USER, password, SERVER,
                                   EXPORT, NFS_PORT, mount_point,
                                   5, 0, True))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    # Then: stress workload
    threads = []
    for node in CLIENTS:
        t = threading.Thread(target=run_stress,
                             args=(node, USER, password, SERVER,
                                   EXPORT, NFS_PORT, mount_point,
                                   duration, workers, False))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    logging.info("========== TEST COMPLETED ==========")


if __name__ == "__main__":
    main()

