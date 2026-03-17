# Dockerfile for iperf3 client with tc
FROM networkstatic/iperf3

# Install bash, sh, and iproute2 (for tc)
RUN apt-get update && apt-get install -y iproute2 bash iputils-ping && rm -rf /var/lib/apt/lists/*

# Default command to keep container alive
CMD ["sleep", "3600"]
