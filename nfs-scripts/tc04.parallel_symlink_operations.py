#!/usr/bin/env python3
import paramiko
import logging
import sys
import time
import threading

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger()

# Fixed client IPs
CLIENTS = ["10.8.128.29", "10.8.128.30"]
USERNAME = "root"

# Args from CLI
MOUNT_PATH = None
PASSWORD = None
WORKERS = 1


def run_cmd(ip, cmd):
    """Run a command on a remote host."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=USERNAME, password=PASSWORD)
    logger.info("[%s] CMD: %s", ip, cmd)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    return out.strip(), err.strip()


def symlink_workflow(ip, idx, wid):
    """One worker’s symlink create/stat/unlink workflow on shared file."""
    # Shared file per iteration
    testfile = f"{MOUNT_PATH}/symlink_cfile_{idx}"
    symlink = f"{MOUNT_PATH}/symlink_clink_{idx}"

    # create file
    run_cmd(ip, f"touch {testfile}")
    logger.info("[Node %s][w%s] File created: %s", ip, wid, testfile)

    # create symlink
    run_cmd(ip, f"ln -sf {testfile} {symlink}")
    logger.info("[Node %s][w%s] Symlink created: %s -> %s", ip, wid, symlink, testfile)

    # stat symlink
    out, err = run_cmd(ip, f"stat {symlink}")
    if out:
        logger.info("[Node %s][w%s] Stat output:\n%s", ip, wid, out)
    if err:
        logger.info("[Node %s][w%s] Stat error:\n%s", ip, wid, err)

    # unlink symlink
    run_cmd(ip, f"unlink {symlink}")
    logger.info("[Node %s][w%s] Symlink unlinked: %s", ip, wid, symlink)


def main():
    if len(sys.argv) != 5:
        print(f"Usage: python {sys.argv[0]} <iterations> <mount_path> <password> <workers>")
        sys.exit(1)

    iterations = int(sys.argv[1])
    global MOUNT_PATH, PASSWORD, WORKERS
    MOUNT_PATH = sys.argv[2]
    PASSWORD = sys.argv[3]
    WORKERS = int(sys.argv[4])

    for i in range(1, iterations + 1):
        logger.info("=== Iteration %s START ===", i)
        threads = []
        for ip in CLIENTS:
            for w in range(1, WORKERS + 1):
                t = threading.Thread(target=symlink_workflow, args=(ip, i, w))
                threads.append(t)
                t.start()

        for t in threads:
            t.join()

        time.sleep(1)
        logger.info("=== Iteration %s END ===", i)


if __name__ == "__main__":
    main()

