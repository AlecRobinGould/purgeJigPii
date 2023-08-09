import multiprocessing
import traceback

# Pretty much an overload of the process module
class Process(multiprocessing.Process):
    """
    Class which returns child Exceptions to Parent.
    """

    def __init__(self, *args, **kwargs):

        # super.__init__(...)
        multiprocessing.Process.__init__(self, *args, **kwargs)
        # Can be used for pipe comms betweeen processes - NOTE: not thread or process safe like a Queue, use locks
        self._parent_conn, self._child_conn = multiprocessing.Pipe()
        self._exception = None

    
    def run(self):
        try:
            multiprocessing.Process.run(self)
            self._child_conn.send(None)
        except Exception as e:
            tb = traceback.format_exc()
            self._child_conn.send((e, tb))
            # raise e  # You can still rise this exception if you need to

    @property
    def exception(self):
        if self._parent_conn.poll():
            self._exception = self._parent_conn.recv()
        return self._exception