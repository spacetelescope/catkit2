from catkit2.testbed.service import Service

import time
from pysnmp import hlapi
import numpy as np

class SnmpUps(Service):
    def __init__(self):
        super().__init__('snmp_ups')

        self.ip_address = self.config['ip_address']
        self.port = self.config['port']
        self.snmp_oid = self.config['snmp_oid']
        self.community = self.config['community']
        self.pass_status = self.config['pass_status']
        self.check_interval = self.config.get('check_interval', 30)

        self.power_ok = self.make_data_stream('power_ok', 'int8', [1], 20)

    def get_status(self):
        res = hlapi.getCmd(hlapi.SnmpEngine(),
                           hlapi.CommunityData(self.community, mpModel=0),
                           hlapi.UdpTransportTarget((self.ip_address, self.port)),
                           hlapi.ContextData(),
                           hlapi.ObjectType(hlapi.ObjectIdentity(self.snmp_oid)))

        for error_indication, error_status, error_index, var_binds in res:
            if error_indication or error_status:
                raise RuntimeError(f"Error communicating with the UPS: {error_indication}; status {error_status}.")
            else:
                return var_binds[0][1]

    def get_power_ok(self):
        try:
            status = self.get_status()
            power_ok = status == self.pass_status

            return power_ok
        except RuntimeError as e:
            self.log.error(f'Some failure occurred: {e}')
            # Failed to connect to UPS, so assume power is bad.
            return False

    def open(self):
        # Do one check on power safety during opening.
        # This is to make sure that we always have at least one power check in the datastream.
        power_ok = self.get_power_ok()
        self.power_ok.submit_data(np.array([power_ok], dtype='int8'))

    def main(self):
        while not self.should_shut_down:
            start = time.time()

            power_ok = self.get_power_ok()
            self.power_ok.submit_data(np.array([power_ok], dtype='int8'))

            time_remaining = self.check_interval - (time.time() - start)
            self.sleep(time_remaining)

if __name__ == '__main__':
    service = SnmpUps()
    service.run()
