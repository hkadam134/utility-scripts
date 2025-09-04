import paramiko
import logging
import time
import sys

# Setup logging to file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("nfs_delete_lock_test.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

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
    logging.info(f"[{ssh.get_transport().getpeername()[0]}] CMD: {cmd}")
    if desc:
        logging.info(f"{desc}: {out if out else 'OK'}")
    if rc != 0 and not desc.startswith("[Node B] Delete attempt"):
        logging.error(f"Command failed: {err}")
    return out, rc

def main(iterations, mount_point, password):
    nodeA = "magna029.ceph.redhat.com"
    nodeB = "magna030.ceph.redhat.com"
    user = "root"

    ssh_A = ssh_connect(nodeA, user, password)
    ssh_B = ssh_connect(nodeB, user, password)

    for i in range(1, iterations + 1):
        test_file = f"{mount_point}/lock_testfile_del{i}"
        logging.info(f"=== Iteration {i} START ===")

        # Create test file
        run_cmd(ssh_A, f"touch {test_file}", "[Node A] File created")

        # Node A acquires lock for 20s
        run_cmd(
            ssh_A,
            f"nohup sh -c \"flock -x {test_file} -c 'sleep 20'\" >/dev/null 2>&1 &",
            "[Node A] Lock acquired for 20s"
        )

        time.sleep(2)  # ensure lock is active

        # Node B delete attempt during lock
        out, rc = run_cmd(
            ssh_B,
            f"timeout 5 rm -f {test_file} && echo DELETE_ALLOWED || echo DELETE_BLOCKED",
            "[Node B] Delete attempt during lock"
        )

        # Verify existence after delete attempt
        run_cmd(
            ssh_B,
            f"ls {test_file} >/dev/null 2>&1 && echo FILE_EXISTS || echo FILE_MISSING",
            "[Node B] File status after delete attempt"
        )

        # Wait for lock release
        logging.info("Waiting for lock release...")
        time.sleep(22)

        # Node B delete attempt after lock release
        out, rc = run_cmd(
            ssh_B,
            f"timeout 5 rm -f {test_file} && echo DELETE_ALLOWED || echo DELETE_BLOCKED",
            "[Node B] Delete attempt after lock release"
        )

        # Verify existence after delete
        run_cmd(
            ssh_B,
            f"ls {test_file} >/dev/null 2>&1 && echo FILE_EXISTS || echo FILE_MISSING",
            "[Node B] File status after final delete"
        )

        logging.info(f"=== Iteration {i} END ===\n")

    ssh_A.close()
    ssh_B.close()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: python {sys.argv[0]} <iterations> <mount_path> <ssh_password>")
        sys.exit(1)

    iterations = int(sys.argv[1])
    mount_path = sys.argv[2]
    password = sys.argv[3]

    main(iterations, mount_path, password)

