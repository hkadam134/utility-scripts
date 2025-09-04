import paramiko
import threading
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

USERNAME = "root"
CLIENT_A = "10.8.128.29"  # Node A
CLIENT_B = "10.8.128.30"  # Node B
TESTFILE = "concurrent_testfile"

# Arguments from CLI
PASSWORD = None
MOUNT_PATH = None
WORKERS = 1  # default workers per client


def run_cmd(host, cmd):
    """Run command on remote host via SSH."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=USERNAME, password=PASSWORD)
    logging.info(f"[{host}] CMD: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    ssh.close()
    return out, err


def client_action(host, label, iteration, worker_id, action):
    """Perform action (create/delete) on remote client."""
    file_name = f"{MOUNT_PATH}/{TESTFILE}_{iteration}"  # <-- shared file for all workers
    cmd = ""
    if action == "create":
        cmd = f"touch {file_name}"
    elif action == "delete":
        cmd = f"rm -f {file_name}"

    out, err = run_cmd(host, cmd)
    if err:
        logging.info(f"[{label}] {action.capitalize()} error (w{worker_id}): {err}")
    else:
        logging.info(f"[{label}] {action.capitalize()} OK (w{worker_id})")


def final_check(iteration):
    """Check from Client A if file exists after operations."""
    cmd = f"ls -l {MOUNT_PATH}/{TESTFILE}_{iteration} 2>/dev/null"
    out, err = run_cmd(CLIENT_A, cmd)
    logging.info(f"[Node A] Final ls (iteration {iteration}): {out or err or 'File missing'}")


def run_test(iterations):
    for i in range(1, iterations + 1):
        logging.info(f"=== Iteration {i} START ===")

        # concurrent creates
        create_threads = []
        for w in range(1, WORKERS + 1):
            create_threads.append(threading.Thread(target=client_action, args=(CLIENT_A, "Node A", i, w, "create")))
            create_threads.append(threading.Thread(target=client_action, args=(CLIENT_B, "Node B", i, w, "create")))

        for t in create_threads:
            t.start()
        for t in create_threads:
            t.join()

        # concurrent deletes
        delete_threads = []
        for w in range(1, WORKERS + 1):
            delete_threads.append(threading.Thread(target=client_action, args=(CLIENT_A, "Node A", i, w, "delete")))
            delete_threads.append(threading.Thread(target=client_action, args=(CLIENT_B, "Node B", i, w, "delete")))

        for t in delete_threads:
            t.start()
        for t in delete_threads:
            t.join()

        time.sleep(1)
        final_check(i)
        logging.info(f"=== Iteration {i} END ===\n")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(f"Usage: python {sys.argv[0]} <iterations> <mount_path> <password> <workers>")
        sys.exit(1)

    iterations = int(sys.argv[1])
    MOUNT_PATH = sys.argv[2]
    PASSWORD = sys.argv[3]
    WORKERS = int(sys.argv[4])

    run_test(iterations)

