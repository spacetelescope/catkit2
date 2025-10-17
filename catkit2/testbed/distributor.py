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

        self.is_running = threading.Event()

    def start(self):
        '''Start the proxy thread.
        '''
        self.thread = threading.Thread(target=self._forwarder)
        self.thread.start()

        self.is_running.wait()

    def stop(self):
        '''Stop the proxy thread.

        This function waits until the thread is actually stopped.
        '''
        self.shutdown_flag.set()

        if self.thread:
            self.thread.join()

        self.is_running.clear()

    def _forwarder(self):
        '''Create sockets and republish all received log messages.

        .. note::
            This function should not be called directly. Use
            :func:`~catkit2.testbed.ZmqDistributor.start()` to start the proxy.
        '''
        collector = self.context.socket(zmq.PULL)
        # Use explicit sockopt methods and set short receive timeout so the thread can exit cleanly.
        try:
            collector.setsockopt(zmq.RCVTIMEO, 50)
        except Exception:
            # ignore if option not supported in this binding
            pass

        # Retry bind a few times to avoid races / transient EADDRINUSE
        bind_ok = False
        for attempt in range(5):
            try:
                collector.bind(f'tcp://*:{self.input_port}')
                bind_ok = True
                break
            except Exception as e:
                print(f'[ZmqDistributor] Attempt {attempt+1}: Failed to bind collector to tcp://*:{self.input_port}: {e}')
                import time
                time.sleep(0.1 * (attempt + 1))

        if not bind_ok:
            try:
                collector.close()
            except Exception:
                pass
            return

        publicist = self.context.socket(zmq.PUB)
        # Retry bind for the publicist as well.
        pub_bind_ok = False
        for attempt in range(5):
            try:
                publicist.bind(f'tcp://*:{self.output_port}')
                pub_bind_ok = True
                break
            except Exception as e:
                print(f'[ZmqDistributor] Attempt {attempt+1}: Failed to bind publicist to tcp://*:{self.output_port}: {e}')
                import time
                time.sleep(0.1 * (attempt + 1))

        if not pub_bind_ok:
            try:
                collector.close()
            except Exception:
                pass
            try:
                publicist.close()
            except Exception:
                pass
            return

        self.is_running.set()

        try:
            while not self.shutdown_flag.is_set():
                try:
                    # Receive with the RCVTIMEO set above; this may raise zmq.Again
                    try:
                        log_message = collector.recv_multipart()
                    except zmq.Again:
                        # timed out, check shutdown flag again
                        continue
                    except zmq.ZMQError as e:
                        # Non-recoverable ZMQ error on recv; log and continue
                        print(f'[ZmqDistributor] recv_multipart error: {e}')
                        continue

                    try:
                        publicist.send_multipart(log_message)
                    except zmq.ZMQError as e:
                        print(f'[ZmqDistributor] send_multipart error: {e}')
                        # continue; don't let this kill the thread
                        continue

                    if self.callback:
                        try:
                            self.callback(log_message)
                        except Exception:
                            print(traceback.format_exc())

                except Exception:
                    # Catch-all around processing loop to avoid leaving thread silently
                    # and to avoid letting exceptions escape into native code.
                    print(traceback.format_exc())
                    # short sleep to avoid tight exception loop
                    import time
                    time.sleep(0.1)
        finally:
            # Ensure sockets are closed cleanly on exit.
            try:
                collector.close()
            except Exception:
                pass

            try:
                publicist.close()
            except Exception:
                pass
