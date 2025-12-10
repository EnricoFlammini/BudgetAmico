import threading
import time

class AsyncTask:
    """
    Helper per eseguire task bloccanti in un thread separato 
    e aggiornare la UI al termine.
    """
    def __init__(self, target, args=(), kwargs=None, callback=None, error_callback=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.callback = callback
        self.error_callback = error_callback
        self.result = None
        self.error = None

    def start(self):
        """Avvia il task in un thread separato."""
        thread = threading.Thread(target=self._run)
        thread.daemon = True # Il thread si chiude se il programma principale si chiude
        thread.start()

    def _run(self):
        try:
            self.result = self.target(*self.args, **self.kwargs)
            if self.callback:
                self.callback(self.result)
        except Exception as e:
            self.error = e
            print(f"[AsyncTask Error] {e}")
            if self.error_callback:
                self.error_callback(e)
