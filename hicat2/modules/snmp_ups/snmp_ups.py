from hicat2.bindings import Module, DataStream, Command, Property
from hicat2.testbed import parse_module_args

import time
import pysnmp

class SnmpUpsodule(Module):
    def __init__(self):
        args = parse_module_args()
        Module.__init__(self, args.module_name, args.module_port)

        testbed = Testbed(args.testbed_server_port)
        config = testbed.config['modules'][args.module_name]

        self.ip_address = config['ip_address']
        self.port = config['port']
        self.snmp_oid = config['snmp_oid']
        self.community = config['community']
        self.pass_status = config['pass_status']

        self.power_ok = DataStream.create('power_ok', self.name, 'int8', [1], 20)
        self.register_data_stream(self.power_ok)

    def get_status(self):
        res = pysnmp.getCmd(pysnmp.SnmpEngine(),
                            pysnmp.CommunityData(self.community, mpModel=0),
                            pysnmp.UdpTransportTarget((self.ip_address, self.port)),
                            pysnmp.ContextData(),
                            pysnmp.ObjectType(pysnmp.ObjectIdentity(self.snmp_oid)))

        for error_indication, error_status, error_index, var_binds in res:
            if error_indication or error_status:
                raise RuntimeError(f"Error communicating with the UPS: '{self.config_id}'.\n" +
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

            frame = self.power_ok.request_new_frame()
            frame.data[0] = self.get_power_ok()
            self.power_ok.submit_frame(frame.id)

            while not self.shutdown_flag and time.time() < (start + self.check_interval):
                time.sleep(0.05)

    def shut_down(self):
        self.shutdown_flag = True
