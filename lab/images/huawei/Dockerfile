FROM vrnetlab/huawei_vrp:ce12800-V200R005C10SPC607B607
COPY patch-launcher.py repair-nics.sh /lab/
RUN python3 /lab/patch-launcher.py /launch.py
