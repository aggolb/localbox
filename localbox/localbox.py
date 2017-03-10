'''
## LOCALBOX 1.0: The LAN "Dropbox"
##
## WHAT:
## It is a network based P2P folder syncing client. 
## It works with any folder, just add the localbox folder, edit the hosts file and run
## It currently only works with files. Folders won't be synced. Zip a folder first to transfer it.
## 
## WHY:
## I wanted a fast way to tranfer HUGE files between two computers connected to the same wifi, but with a dropbox style UX
## i.e. a magic folder i could just put things in that syncs across all computers
##
## HOW TO USE IT: 
## Just place the "localbox" folder into any folder you want to sync..
##
## IMPORTANT: 
## I recommend using a brand new folders because in an effort to sync directories, it might end up deleting some files
## Before running the localbox.py file add the peers IP and Port to the first line,
## in the hosts.txt file in the format, HOST_IP(space)PORT e.g. 127.0.0.1 101.
## Localbox uses port 100 by default for the server thread (that others can connect to) but you can change it to whatever you want
##      
## POSSIBLE IMPROVEMENTS: 
## Add folder sync
## To get a full Dropbox experience (more than two nodes) on LAN, if you have a huge local network,
## you could spin up a separate server to handle multiple clients without a drastic change to the code              
##
## Author: Shimpano Mutangama

'''

import socket
import threading
import time
import sys
import os
import pickle
from watchbox import Watcher

class LocalBoxWatcher(Watcher):
    #Inherits Watchbox class, necessary for overrides and provide functionality

    def __init__(self,files,box):
        self.box = box
        super(LocalBoxWatcher,self).__init__(files=files)
    
    def lb_file_changed(self):
        self.box.sync_files()

    def lb_file_added(self):
        self.box.sync_files()

    def lb_file_deleted(self):
        self.box.sync_files()


class LocalBox:

    def __init__(self):
        
        print "\nIniltializing LocalBox..."
        
        self._directory_files = {}
        self._file_queue = []
        self._client_socket = None
        self._server_socket = None

        self.BUFFER_SIZE = 1024
        self._friend_host_saved = False
        self._friend_port_saved = False
        self._client_connected = False

        #Files used to help the program function
        self._ignore_list = ["files.lb","localbox.py","localbox.pyc","watchbox.py","watchbox.pyc","server.py","hosts.txt"]

        #When files are being sent from the peer to the user, they trigger a transfer
        #back to the user, the temp ignore list allows you to ignore the files currently being transfered
    
        self._temp_ignore_list = []

    def _accept_connections(self):

        while True:
            connection,address = self._server_socket.accept()
            print "\nReceived connection from: ",address
            connection.send("\nSuccessfully Connected")

            self._handle_file_receive(connection)

    def server_thread(self):

        #The server thread deals exclusively with receiving files

        host = '0.0.0.0'
        port  = 101

        server_tuple = (host,port)
        self._server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self._server_socket.bind(server_tuple)
        self._server_socket.listen(5)

        print "\nWaiting for a connection....."

        self._accept_connections()
        self._server_socket.close()


    def _execute_directory_sync_command(self,c,message):
        #command to sync, usually happens if a file is deleted or the directory changes
        #we receive a directory list from the peer
        c.send(message)

        directory_data = ''
        chunk = c.recv(self.BUFFER_SIZE)

        while chunk:
            
            directory_data+=chunk

            if directory_data[-2:] == "/0":
                break

            chunk = c.recv(self.BUFFER_SIZE)

        #print "\nDirectory: %s\n"%directory_data

        directory_list = pickle.loads(directory_data[:-2])
        directory_list = {os.path.realpath("../%s"%os.path.basename(key)):directory_list[key] for key in directory_list}
        current_directory = map(lambda x: os.path.realpath("../%s"%x),os.listdir(".."))

        for file_object in current_directory:
            
            if os.path.isfile(file_object):
                #if file is being ignored or is already in the directory list, do nothing
                #otherwise remove it because the remote peer doesn't have it

                if file_object in directory_list or file_object in self._ignore_list: 
                    pass
                else:
                    os.remove(file_object)
                    
            else:

                pass
        
    def _handle_file_receive(self,c):
        
        while True:
                
            #Add recently received file to the _directory_files dictionary
            for current_object in self._temp_ignore_list:

                if os.path.exists(current_object):
                    last_modified_epoch = os.path.getmtime(current_object)
                    last_modified = time.strftime('%Y/%m/%d %H:%M:%S',time.localtime(last_modified_epoch))
                    self._directory_files[current_object] = last_modified
                    
            #If the temp ignore list has files, update files.lb
            if len(self._temp_ignore_list) > 0:
                with open("files.lb","wb") as f:
                    pickle.dump(self._directory_files,f)

            #Empty the list
            self._temp_ignore_list = []

            print "\nWaiting for file..."

            #A message is the first thing sent by the peer, could be file details, a sync command or a break
            message = c.recv(self.BUFFER_SIZE)

            print "\nMessage: %s"%message

            if message == '':
                c.close()
                break

            elif message[:3] == 'cmd':
                m = "\nSynced Remote Directory"
                self._execute_directory_sync_command(c,m)
                
            else:

                file_array = message.split(",")
                filename = file_array[0]
                file_size = int(file_array[1])

                #avoid sync loops, ignore files you're currently receiving
                file_str = "../%s"%filename
                filename = os.path.realpath(file_str)
                self._temp_ignore_list.append(filename)

                c.send("OK TO SEND")

                with open(filename,"wb") as f:

                    chunk = c.recv(self.BUFFER_SIZE)
                    total = len(chunk)

                    while chunk:

                        f.write(chunk)

                        if total < file_size:
                            chunk = c.recv(self.BUFFER_SIZE)
                            total = total + len(chunk)
                        else:
                            break

                #c.send("Successfully uploaded")
                print "\nSuccessfully downloaded %s!"%filename
                m = "\n Successfully Uploaded!"
                self._execute_directory_sync_command(c,m)


             


    def client_thread(self):

        #The client thread dealse exclusively with detecting changes and sending files

        with open("hosts.txt","rb") as f:
            remote_server_string = f.readline()

        remote_server_array = remote_server_string.split(" ")

        host = remote_server_array[0]
        port = remote_server_array[1]
        
        self._friend_port_saved = True
        self._friend_host_saved = True

        port = int(port)

        client_data = (host,port)

        print "\nConnecting to: ",client_data

        #This continously checks if the client successfully connects. If the remote peer
        #isn't ready wait 10 seconds and try to reconnect
        while self._client_connected == False:
            
            try:
                self._client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._client_socket.connect(client_data)
                self._client_connected = True
            except:
                time.sleep(10)
                continue

        data = self._client_socket.recv(self.BUFFER_SIZE)
        print data

        self.sync_files()

        #This finds the full path of the objects in the folder one level up
        #These will be watched
        files = map(lambda x: os.path.realpath("../%s"%x),os.listdir(".."))
        

        watcher = LocalBoxWatcher(files=files,box=self)
        watcher.monitor()
        

        
    def _sync_directory(self,args=None):
        #This sends the "cmd:..." message to the remote host to sync itself
        if args is not None:
            
            self._client_socket.sendall(args)
            response = self._client_socket.recv(self.BUFFER_SIZE)
            print response

        
        directory_table = pickle.dumps(self._directory_files)
        self._client_socket.sendall(directory_table+"/0")


    def _flush_queue(self):

        #This gets the file queue (which contains files recently changed, added or deleted)
        #and acts on them
        for i in range(0,len(self._file_queue)):

            filename = self._file_queue.pop(0)

            if os.stat(filename).st_size != 0:

                self._send_file(filename)
                self._sync_directory()

    def _send_file(self,filename):

        if filename == 'q' or filename == 'Q':
            self._client_socket.send(filename)
            self._client_socket.close()
        else:
            file_size = os.stat(filename).st_size
            file_stats = "%s,%s"%(os.path.basename(filename),file_size)

            print "Filename: ",filename
            print "File Stats: ",file_stats

            #Gets file stats i.e. name and size and sends them to the remote peer before sending
            #the file itself
            self._client_socket.send(file_stats)
            self._client_socket.recv(self.BUFFER_SIZE)

            while True:

                #Read file data and send it in chunks.
                try:
                    with open(filename,"rb") as f:
                        
                        file_data = f.read(self.BUFFER_SIZE)

                        while file_data:
                            self._client_socket.send(file_data)
                            file_data = f.read(self.BUFFER_SIZE)

                            if file_data == '':
                                break

                        response = self._client_socket.recv(self.BUFFER_SIZE)
                        print response
                        break
                except IOError:
                    #This is triggered if the file is still being copied to the folder and can't be read
                    #It waits 10 seconds for a reasonable amount of data and tries again
                    time.sleep(10)
                    continue
                except:
                    break
    
        
    def _load_file_list(self):

        #The files.lb file holds the current directories file list.
        #This function reads it if it already exists, creates it if it doesn't
        #and re-creates it if it is corrupt and can't be loaded by pickle module

        if os.path.exists("files.lb"):

            try:
                with open("files.lb","rb") as f:
                    self._directory_files = pickle.load(f)
            except:
                open("files.lb").close()

        else:
            with open("files.lb","wb") as f:
                self._directory_files = {}

    def sync_files(self):
        
        #Don't sync anything until the files being received are added
        while True:
            if len(self._temp_ignore_list) == 0:
                break
            time.sleep(5)

        self._load_file_list()
        current_directory = map(lambda x: os.path.realpath("../%s"%x),os.listdir(".."))

        for current_object in current_directory:

            if os.path.isfile(current_object):

                if current_object in self._ignore_list:
                    pass
                else:

                    #If file is deleted before this block of code is reached an error is thrown
                    #so check if file exists and get its modified time if it does
                    if os.path.exists(current_object):
                        last_modified_epoch = os.path.getmtime(current_object)
                        last_modified = time.strftime('%Y/%m/%d %H:%M:%S',time.localtime(last_modified_epoch))
                    else:
                        #file doesn't exist, was likely deleted
                        last_modified = ""

                    if current_object in self._directory_files:
                        #if file hasn't changed since last sync leave it alone
                        if self._directory_files[current_object] == last_modified:
                            pass
                        #file was deleted, do nothing
                        elif last_modified == "":
                            pass
                        
                        else:
                            #file changed, update the directory file table and add it to the sync queue
                            self._directory_files[current_object] = last_modified
                            self._file_queue.append(current_object)
                            
                    else:
                        #file is new and was just added, add it to directory file table and add it to sync queue
                        self._directory_files[current_object] = last_modified
                        self._file_queue.append(current_object)

        print "\nFile Queue: %s"%map(os.path.basename,self._file_queue)

        #Now we reconstruct the self._directory_files and files.lb file
        #We do this so in case any files are deleted, the reconstructed file will omit them

        self._directory_files = {}
        current_directory = map(lambda x: os.path.realpath("../%s"%x),os.listdir(".."))
        
        for current_object in current_directory:
            if os.path.isfile(current_object):
                if current_object in self._ignore_list or current_object in self._temp_ignore_list:
                    pass
                else:
                    last_modified_epoch = os.path.getmtime(current_object)
                    last_modified = time.strftime('%Y/%m/%d %H:%M:%S',time.localtime(last_modified_epoch))
                    
                    self._directory_files[current_object] = last_modified


        if len(self._file_queue)==0:
            #no files were in the queue to send so files were deleted, so send sync command
            #so files on the remote computer are removed as well
            self._sync_directory(args="cmd:sync_directory")
        else:
            #send newly as=dded and modified files
            self._flush_queue()

        with open("files.lb","wb") as f:
            pickle.dump(self._directory_files,f)
                    
        print""
        for filename in self._directory_files:
            print "\nFile: %s Last Modified: %s"%(os.path.basename(filename),self._directory_files[filename])

            
    def start_server(self):

        print "\n Starting Server... "

        t = threading.Thread(target = self.server_thread)
        t.daemon = True
        t.start()

    def start_client(self):

        print "\n Starting Client... "

        t = threading.Thread(target = self.client_thread)
        t.daemon = True
        t.start()
        

    
        
            

def main():
    
    box = LocalBox()
    box.start_server()
    box.start_client()

    #Quit the program at any time by typing q or Q

    choice = raw_input(">")
    while True:
        if choice == "q" or choice == "Q":
            break
        time.sleep(5)
        


if __name__ == "__main__":
    main()
        
