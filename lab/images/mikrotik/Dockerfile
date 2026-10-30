ARG BASE=vrnetlab/mikrotik_routeros:7.16.2
FROM ${BASE}
COPY bootstrap.py /lab_bootstrap.py
RUN sed -i '/^if __name__ == "__main__":/i from lab_bootstrap import bootstrap_spin\nROS_vm.bootstrap_spin = bootstrap_spin\n' /launch.py
