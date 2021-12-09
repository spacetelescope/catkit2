from catkit2.protocol.service import Service, parse_service_args

import time
from pysnmp import hlapi
import numpy as np

class SnmpUps(Service):
    def __init__(self, service_name, testbed_port):
        Service.__init__(self, service_name, 'snmp_ups', testbed_port)

        config = self.configuration

        self.ip_address = config['ip_address']
        self.port = config['port']
        self.snmp_oid = config['snmp_oid']
        self.community = config['community']
        self.pass_status = config['pass_status']
        self.check_interval = config.get('check_interval', 30)

        self.power_ok = self.make_data_stream('power_ok', 'int8', [1], 20)

        self.shutdown_flag = False

    def get_status(self):
        res = hlapi.getCmd(hlapi.SnmpEngine(),
                           hlapi.CommunityData(self.community, mpModel=0),
                           hlapi.UdpTransportTarget((self.ip_address, self.port)),
                           hlapi.ContextData(),
                           hlapi.ObjectType(hlapi.ObjectIdentity(self.snmp_oid)))

        for error_indication, error_status, error_index, var_binds in res:
            if error_indication or error_status:
                raise RuntimeError(f"Error communicating with the UPS: '{self.name}'.\n" +
                                   f"Error Indication: {str(error_indication)}\n" +
                                   f"Error Status: {str(error_status)}")
            else:
                return var_binds[0][1]

    def get_power_ok(self):
        try:
            status = self.get_status()
            power_ok = status == self.pass_status

            return power_ok
        except RuntimeError:
            # Failed to connect to UPS, so assume power is bad.
            return False

    def main(self):
        while not self.shutdown_flag:
            start = time.time()

            power_ok = self.get_power_ok()
            frame = self.power_ok.submit_data(np.array([power_ok], dtype='int8'))

            while not self.shutdown_flag and time.time() < (start + self.check_interval):
                time.sleep(0.05)

    def shut_down(self):
        self.shutdown_flag = True

if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = SnmpUps(service_name, testbed_port)
    service.run()
