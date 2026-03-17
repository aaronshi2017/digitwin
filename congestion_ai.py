# digitwin/congestion_ai.py
import docker
from ns import ns
import time

# ==============================
# Docker Setup (Physical Asset)
# ==============================
def start_docker_client(host_ip: str, container_name="iperf-client"):
    """
    Launches a Docker iperf3 client container to connect to host IP.
    Returns the container object.
    """
    client = docker.from_env()

    # Remove existing container if it exists
    try:
        old = client.containers.get(container_name)
        print(f"Stopping and removing existing container '{container_name}'...")
        old.stop(timeout=3)
        old.remove()
    except docker.errors.NotFound:
        pass
    except docker.errors.APIError as e:
        print(f"Warning: Could not remove container: {e}")

    # Launch container with NET_ADMIN capability for 'tc'
    container = client.containers.run(
        "iperf3-tc-client",
        command=f"iperf3 -c {host_ip} -t 3600",
        name=container_name,
        network="bridge",
        detach=True,
        cap_add=["NET_ADMIN"]
    )

    # Wait until container is running
    for _ in range(50):  # max 5 seconds
        container.reload()
        if container.status == "running":
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Docker container did not start in time")

    print(">>> Docker client container is now running")
    return container

# ==============================
# Helper functions to read container stats
# ==============================
def get_container_rate(container):
    """Measure Tx rate (Mbps) of container's eth0 over 1 second"""
    cmd = "cat /sys/class/net/eth0/statistics/tx_bytes"
    _, out1 = container.exec_run(cmd)
    b1 = int(out1.decode().strip())
    time.sleep(1)
    _, out2 = container.exec_run(cmd)
    b2 = int(out2.decode().strip())
    rate = (b2 - b1) * 8 / 1e6  # Mbps
    return rate

def get_rtt(container):
    """Ping host from container to measure RTT (ms)"""
    cmd = "ping -c 3 8.8.8.8"
    _, out = container.exec_run(cmd)
    text = out.decode()
    if "avg" in text:
        avg = text.split("/")[-3]
        return float(avg)
    return None

# ==============================
# AI Agent (Digital Twin Controller)
# ==============================
def create_ai_agent(container, devices):
    congestion_applied = False  # prevent multiple throttles

    def AI_Agent():
        nonlocal congestion_applied
        current_time = ns.Simulator.Now().GetSeconds()
        print(f"[{current_time:.1f}s] Agent tick")

        real_rate = get_container_rate(container)
        real_rtt = get_rtt(container)
        print(f"REAL RATE: {real_rate:.3f} Mbps, REAL RTT: {real_rtt}")

        # Trigger congestion once at >=5s
        if current_time >= 5.0 and not congestion_applied:
            print(f"[{current_time:.1f}s] DIGITAL TWIN: Congestion Detected")

            # Update DIGITAL twin model
            devices.Get(0).SetAttribute("DataRate", ns.StringValue("1Mbps"))

            # Update PHYSICAL asset (Docker container) via tc
            cmd = "tc qdisc replace dev eth0 root tbf rate 1mbit burst 32kbit latency 400ms"
            exit_code, output = container.exec_run(cmd)
            print(f">>> PHYSICAL ASSET: Throttled to 1 Mbps, result {exit_code}")
            if output:
                print(output.decode())

            congestion_applied = True

        # Reschedule agent every 1 second (simulation time)
        ns.Simulator.Schedule(ns.Seconds(1.0), ns.pythonMakeEvent(AI_Agent))

    return AI_Agent

# ==============================
# Main Simulation
# ==============================
def run_simulation(host_ip: str = "172.29.235.20"):
    # Start Docker client container
    container = start_docker_client(host_ip)

    # ------------------------------
    # ns-3 Topology Setup
    # ------------------------------
    nodes = ns.NodeContainer()
    nodes.Create(2)

    p2p = ns.PointToPointHelper()
    p2p.SetDeviceAttribute("DataRate", ns.StringValue("5Mbps"))
    p2p.SetChannelAttribute("Delay", ns.StringValue("2ms"))
    devices = p2p.Install(nodes)

    stack = ns.InternetStackHelper()
    stack.Install(nodes)

    # ------------------------------
    # C++ Bridge: Python Event Wrapper
    # ------------------------------
    ns.cppyy.cppdef("""
    namespace ns3 {
        EventImpl* pythonMakeEvent(void (*f)()) {
            return MakeEvent(f);
        }
    }
    """)

    # ------------------------------
    # Start AI Agent Loop
    # ------------------------------
    AI_Agent = create_ai_agent(container, devices)
    initial_event = ns.pythonMakeEvent(AI_Agent)
    ns.Simulator.Schedule(ns.Seconds(1.0), initial_event)

    ns.Simulator.Stop(ns.Seconds(10.0))

    print("=== Starting Simulation ===")
    ns.GlobalValue.Bind(
        "SimulatorImplementationType",
        ns.StringValue("ns3::RealtimeSimulatorImpl")
    )

    ns.Simulator.Run()
    ns.Simulator.Destroy()
    print("=== Simulation Finished ===")

    # Cleanup Docker
    print("Stopping Docker client...")
    container.stop()
    container.remove()
    print("Docker client removed.")

# ==============================
# Command-line entry
# ==============================
if __name__ == "__main__":
    run_simulation()