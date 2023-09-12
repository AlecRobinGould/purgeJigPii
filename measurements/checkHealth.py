import psutil

class healthyPi(object):
    def __init__(self):
        pass

    def checkPi(self):
        memoryUsage = psutil.virtual_memory()
        diskUsage = psutil.disk_usage("/root")
        networkConnection = psutil.net_if_stats()

        memFlag = ''
        diskFlag = ''
        netFlag = ''

        if memoryUsage.percent <= 90:
            memFlag = True
        else:
            memFlag = False

        if diskUsage.percent <= 90:
            diskFlag = True
        else:
            diskFlag = False
            
        st = None
        for nic, addrs in networkConnection.items():
                if nic in networkConnection:
                    st = networkConnection[nic]
                    
        if st.isup:
            netFlag = True
        else:
            netFlag = False

        return {"Memory":memFlag, "Disk":diskFlag, "Network":netFlag}