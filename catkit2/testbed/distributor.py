import zmq
import threading
import traceback


class ZmqDistributor:
    '''Collects messages on a port and re-publish them on another.

    This operates on a separate thread after it is started.

    Parameters
    ----------
    context : zmq.Context
        A previously-created ZMQ context. All sockets will be created on this context.
    input_port : integer
        The port number for the incoming log messages.
    output_port : integer
        The port number for the outgoing log messages.
    callback : function
        A callback to call with each message.
    '''
    def __init__(self, context, input_port, output_port, callback=None):
        self.context = context
        self.input_port = input_port
        self.output_port = output_port
        self.callback = callback

        self.shutdown_flag = threading.Event()
        self.thread = None

    def start(self):
        '''Start the proxy thread.
        '''
        self.thread = threading.Thread(target=self._forwarder)
        self.thread.start()

    def stop(self):
        '''Stop the proxy thread.

        This function waits until the thread is actually stopped.
        '''
        self.shutdown_flag.set()

        if self.thread:
            self.thread.join()

    def _forwarder(self):
        '''Create sockets and republish all received log messages.

        .. note::
            This function should not be called directly. Use
            :func:`~catkit2.testbed.ZmqDistributor.start()` to start the proxy.
        '''
        collector = self.context.socket(zmq.PULL)
        collector.RCVTIMEO = 50
        collector.bind(f'tcp://*:{self.input_port}')

        publicist = self.context.socket(zmq.PUB)
        publicist.bind(f'tcp://*:{self.output_port}')

        while not self.shutdown_flag.is_set():
            try:
                try:
                    log_message = collector.recv_multipart()
                    publicist.send_multipart(log_message)
                except zmq.ZMQError as e:
                    if e.errno == zmq.EAGAIN:
                        # Timed out.
                        continue
                    else:
                        raise RuntimeError('Error during receive') from e

                if self.callback:
                    self.callback(log_message)
            except Exception:
                # Something went wrong during handling of the log message.
                # Let's ignore this error, but still print the exception.
                print(traceback.format_exc())
