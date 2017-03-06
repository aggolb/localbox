'''
## WATCHBOX 1.0
## This contains a class that is inspired by the "pywatch" Watcher class to detect file changes
## After the file is changed, the change is detected and an appropriate action is taken
##
## AUTHOR: Shimpano Mutangama 
'''

import datetime
import os
import threading
import time

class Watcher(object):

    def __init__(self,files=None):

        self.files = []
        self.num_runs = 0
        self.mtimes = {}
        self._monitor_continuously = False
        self._monitor_thread = None

        if files:
            self.files = files

    #Override this
    def lb_file_changed(self):
        #This function should be called on a file change
        pass

    #Override this
    def lb_file_deleted(self):
        #This function should be called on a file deletion
        pass

    #Override this
    def lb_file_added(self):
        #This function should be called on a file addition 
        pass


    def execute(self):
        #It only executes when a file changes, basically the "last modified" property
        print "A file(s) has changed..."
        self.lb_file_changed()

    def monitor(self):
        #ensures only one thread runs
        self.stop_monitor()
        
        self._monitor_continously = True
        self._monitor_thread = threading.Thread(target = self._monitor_till_stopped)
        self._monitor_thread.start()

    def run_monitor(self):
        """Called by main thread methods like __main__ so Ctrl-C works"""
        self.monitor()

        try:
            while self._monitor_continously:
                time.sleep(0.02)
        except KeyboardInterrupt:
            self.stop_monitor()


    def stop_monitor(self):

        if self._monitor_thread and self._monitor_thread.isAlive():
            self._monitor_continously = False
            self._monitor_thread.join(0.05)


    def watch_directory_once(self):
        #This function is called (roughly) once a second (_monitor_till_stopped)
        #Because the execute() function handles file changes already,
        #It works on the directory level, detecting file additins and subtractions 

        directory_files = []

        #Get every path in the current directory but exclude the files.lb (stores directory files)
        dir_paths = map(lambda x: os.path.realpath("../%s"%x),os.listdir(".."))
        current_directory_paths = [os.path.realpath(obj) for obj in dir_paths if obj != "files.lb"]
        for obj in dir_paths:
            
            if os.path.isfile(obj):
                directory_files.append(obj)

        #self.files holds the files being watched,
        #directory_files holds files currently in directory at the given moment
        #Symmetric difference returns elements in both files excluding elements contained in both sets
        file_changes = list(set(self.files).symmetric_difference(set(directory_files)))
        #print"File Changes: ",file_changes
        
        if len(file_changes) > 0:
            
            for obj in file_changes:

                if obj in self.files and obj not in directory_files:
                    print "A file(s) has been deleted...",obj
                    
                    self.files.remove(obj)
                    self.lb_file_deleted()

                elif obj not in self.files and obj in directory_files:
                    print "A file(s) has been added...",obj
                    self.files.append(obj)
                    self.lb_file_added()

            
    def _monitor_till_stopped(self):
        while self._monitor_continously:
            self.watch_directory_once()
            self.monitor_once()
            time.sleep(1)


    def monitor_once(self, execute=True):
        #This detects file changes on a file level, meaning changes to the actual file
        for f in self.files:
            try:
                mtime = os.stat(f).st_mtime
            except OSError:
                #The file might be right in the middle of being written so sleep
                time.sleep(1)
                mtime = os.stat(f).st_mtime

            if f not in self.mtimes.keys():
                self.mtimes[f] = mtime
                continue

            if mtime > self.mtimes[f]:
                self.mtimes[f] = mtime
                if execute:
                    self.execute()
                    break

            
        
