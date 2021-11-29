from catkit2.simulator import Simulator
from catkit2.protocol.service import parse_service_args

class HicatSimulator(Simulator):
    def __init__(self, service_name, testbed_port):
        Simulator.__init__(service_name, 'hicat_simulator', testbed_port)



if __name__ == '__main__':
    service_name, testbed_port = parse_service_args()

    service = HicatSimulator(service_name, testbed_port)
    service.run()
