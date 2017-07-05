#!/usr/bin/env python
# pylint: disable=I0011,C0103,C0200

"""
Skreepy
--
Copyright (C) 2017 - Julien Blanc

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

#--------------- IMPORT MODULES
import json
import re
import argparse
import warnings
import time
from queue import Queue
import threading
import http.client
import logging
import uuid
import os
import subprocess
from pathlib import Path
import requests


#--------------- REGEX
isfilepath = re.compile(r'^\[FILE\]+([a-zA-Z0-9_\\/-]+)+\.([a-zA-Z0-9]+)$')  # Regex for FILE
issuccess = re.compile(r'^(2+[0-9]{2})$') # Regex for success rest code


#--------------- BANNER
banner = r"""
                                   
,---.|                             
`---.|__/ ,---.,---.,---.,---.,   .
    ||  \ |    |---'|---'|   ||   |
`---'`   ``    `---'`---'|---'`---|
                         |    `---'
___________________________________
Copyright 2017 - v1.1.0 - by Jbla
"""


#--------------- EXECUTE REST API COMMAND WITH MULTITHREADING
class restapicmd(threading.Thread):
    """
    EXECUTE REST API COMMAND WITH MULTITHREADING
    """
    # Get the thread queue and the completed "queue"
    def __init__(self, queue_in, completed, timeout, logpath, instance):
        threading.Thread.__init__(self)
        self.queue_in = queue_in
        self.completed = completed
        self.restcmd = None
        self.timeout = timeout
        self.logpath = logpath
        self.instance = instance

    # Get thread parameters, run the process and finish the thread
    def run(self):
        while True:
            self.restcmd = self.queue_in.get()
            self.process()
            self.queue_in.task_done()

    # Execute the thread
    def process(self):
        """
        PROCESS
        """
        # Init vars
        rid = None
        url = None
        method = None
        sslverify = None
        user = None
        password = None
        data = None
        output = None
        depon = None
        script = None
        res = None
        exportsucceded = None

        # Test if JSON segment is valid
        if checkkey(['id', \
                     'url', \
                     'method', \
                     'sslverify', \
                     'user', \
                     'password'], self.restcmd) is True:
            # Then get values (type forced)
            rid = str(self.restcmd["id"])
            url = str(self.restcmd["url"])
            method = str(self.restcmd["method"])
            sslverify = bool(self.restcmd["sslverify"])
            user = str(self.restcmd["user"])
            password = str(self.restcmd["password"])

            # If key 'data' exists, gets a value
            if checkkey(['data'], self.restcmd) is True:
                data = self.restcmd["data"]

            # If key 'output' exists, gets a value
            if checkkey(['output'], self.restcmd) is True:
                output = self.restcmd["output"]

            # If key 'script' exists, gets a value
            if checkkey(['script'], self.restcmd) is True:
                script = self.restcmd["script"]

        logging.info("%s;%s;%s", \
                     self.instance, \
                     "id=" + rid, \
                     "[" + method + "] " + url)

        # Tests the method validity
        if method in ('POST', 'PUT', 'PATCH', 'GET', 'DELETE', 'OPTIONS'):

            # Check for thread dependencies
            if checkkey(['depends_on'], self.restcmd):
                depon = str(self.restcmd["depends_on"])

                # While the completed queue does not contains the parent thread, wait
                while list(self.completed.keys()).count(depon) is 0:
                    time.sleep(0.1)

                # If the status code of request is not OK (regex at the top of the script)
                # there is an error
                if issuccess.search(self.completed[depon]) is None:
                    res = 424

            # If not dependency error, continue
            if res is not 424:

                # If datas
                d = None
                if data is not None:

                    # Regex to test if the data value is a file path
                    if isfilepath.search(data):
                        d = json.dumps(loadjson(data[6:], self.instance))
                    else:
                        d = data

                # Execute request and get a status code
                try:
                    rep = requests.request(method, \
                                            url, \
                                            data=d, \
                                            auth=(user, password), \
                                            verify=sslverify, \
                                            timeout=self.timeout, \
                                            headers={ \
                                                'Content-type': 'application/json' \
                                            })
                    res = rep.status_code

                    # If output file specified
                    if output is not None:

                        # Regex to test if the data value is a file path
                        if isfilepath.search(output):
                            try:
                                with open(output[6:], 'w') as outfile:
                                    outfile.write(json.dumps(json.loads(rep.text), \
                                                            indent=4, \
                                                            sort_keys=True))
                                exportsucceded = True
                            except FileNotFoundError:
                                exportsucceded = False
                            except PermissionError:
                                exportsucceded = False

                        else:
                            exportsucceded = False

                except requests.exceptions.ConnectionError:
                    res = 408
                except requests.exceptions.ChunkedEncodingError:
                    res = 401

        else:
            # Method not allowed
            res = 405

        # Convert status code in message
        status = http.client.responses[res]

        # Get logging attribute for set log level with http code result
        # INFO by default
        log = getattr(logging, "info")

        # If code is not 2xx, set log level to ERROR by default
        if issuccess.search(str(res)) is None:
            log = getattr(logging, "error")

        # If dependency thread error, gives the parent thread
        if res is 424:
            status += " (id " + depon + ")"
            log = getattr(logging, "error")

        # If export to file not succeded
        if exportsucceded is not True and exportsucceded is not None:
            log = getattr(logging, "warning")

        # Log to file
        log("%s;%s;%s", \
            self.instance, \
            "id=" + rid, \
            "[" + str(res) + "] " + status)

        # Script post REST API command
        if script is not None:

            status = None
            rescode = "NUL"

            if issuccess.search(str(res)) is not None:

                # Execute script
                rescode = subprocess.call(script, \
                                          stderr=subprocess.PIPE, \
                                          stdout=subprocess.PIPE)

                if rescode is not 0:
                    log = getattr(logging, "error")
                    status = "Script failed with code " + str(rescode)
                else:
                    log = getattr(logging, "info")
                    status = "Script succeeded"

            else:
                log = getattr(logging, "warning")
                status = "Script canceled"

            log("%s;%s;%s", \
                self.instance, \
                "id=" + rid, \
                status)

        # Message queue
        self.completed[rid] = str(res)


#--------------- CHECK IF KEY EXISTS
def checkkey(keytotest, keys):
    """
    TEST IF KEY EXISTS
    """
    cpt = 0

    for key in keytotest:
        if key in keys:
            cpt += 1

    if cpt is len(keytotest):
        return True
    else:
        return False


#--------------- LOAD INFRA CONFIG FILE
def loadjson(f, instance):
    """
    LOAD JSON FILE
    """
    cfg = None

    try:
        cfg = open(f, 'r')
    except FileNotFoundError:
        logging.critical("%s;%s", \
                         instance, \
                         "No such file or directory " + f)
        exit()

    try:
        return json.load(cfg)
    except json.decoder.JSONDecodeError:
        logging.critical("%s;%s", \
                         instance, \
                         f + " is not a valid JSON file.")
        exit()


#--------------- MAIN PROGRAM
def main():
    """
    MAIN
    """

    # Get arguments
    parser = argparse.ArgumentParser()

    # Help
    helptext = {
        "file":
        """
        JSON file which contains REST APIs commands to treat. There is two
        root sections : the optional 'configuration' section with 'maxthreads'
        and 'timeout' keys (which can be pass with command line) and the
        mandatory 'rest' section which contains REST APIs commands. Go to
        https://github.com/j8la/skreepy to see all the keys and the JSON structure.
        """,
        "maxthreads":
        """
        Max concurrent threads to execute. Default to 4. If the number of
        max threads is more elevated than the commands to treat, the value
        is automatically adjusted.
        """,
        "timeout":
        """
        The maximum timeout for https connection. Default to 5s.
        """,
        "logpath":
        """
        Log path (default to ./log). The log is automaticaly generated
        with 'skreepy-[instance name].log' as name. If you have specified
        --instancename option, each time than the script will run with
        the same instance name, the same log file will be used.
        """,
        "quiet":
        """
        Quiet mode with no console output. Default to 'False'. You must
        specify explicitly '--quiet True' for quiet mode.
        """,
        "instancename":
        """
        The default instance name is generated with the UUID library to a
        hexadecimal format. You can specify the instance name if you want
        to use always the same log file. A lock file is also generated
        when you specify the instance name to prevent any problem if you
        schedule Skreepy. There is no lock file when using automatic
        instance name because in this case, you can't have the same
        instance name twice.
        """
    }

    # Manage arguments
    parser.add_argument('-f', '--file', help=helptext["file"], \
                                        action='store', \
                                        required='True')

    parser.add_argument('-m', '--maxthreads', help=helptext["maxthreads"], \
                                              type=int, \
                                              default=4)

    parser.add_argument('-t', '--timeout', help=helptext["timeout"], \
                                           type=int, \
                                           default=5)

    parser.add_argument('-l', '--logpath', help=helptext["logpath"], \
                                           type=str, \
                                           default="log/")

    parser.add_argument('-q', '--quiet', help=helptext["quiet"], \
                                           type=bool, \
                                           default=False)

    parser.add_argument('-i', '--instancename', help=helptext["instancename"], \
                                                type=str, \
                                                default=None)

    # Parse arguments
    args = parser.parse_args()

    # Show banner
    if args.quiet is not True:
        print(banner)

    # Hide warnings
    warnings.filterwarnings("ignore")

    # Init max threads var
    maxthreads = None

    # Init timeout var
    timeout = None

    # Instance ID
    instance = uuid.uuid4().hex

    if args.instancename is not None:
        instance = args.instancename

    # Logging options
    try:
        logging.basicConfig(filename=args.logpath + "skreepy-" + instance + ".log", \
                            format='%(asctime)s;%(levelname)s;%(message)s', \
                            level=logging.INFO)
    except FileNotFoundError:
        print(">>> Error: Cannot create log file. Check the path or the permissions.")
        quit()

    logging.getLogger("requests").setLevel(logging.CRITICAL)

    # If not quiet mode, output to console
    if args.quiet is not True:
        logFormatter = logging.Formatter("%(asctime)s;%(levelname)s;%(message)s")
        rootLogger = logging.getLogger()
        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        rootLogger.addHandler(consoleHandler)

    # If args.instancename specified, check if an instance is running
    # else create a .lock file
    if args.instancename is not None:
        if Path(instance + ".lock").is_file():
            logging.critical("%s;%s", \
                             instance, \
                             "The instance is already running.")
            quit()
        else:
            try:
                open(instance + ".lock", 'w').close()
            except FileNotFoundError:
                logging.critical("%s;%s", \
                                instance, \
                                "Cannot create a .lock file. Check the permissions.")
                quit()

    # Load config file
    infra = loadjson(args.file, instance)

    # Check configuration
    if checkkey(['configuration'], infra):

        # Get max threads queue
        if checkkey(['maxthreads'], infra["configuration"]):
            maxthreads = infra["configuration"]["maxthreads"]
        else:
            maxthreads = args.maxthreads

        # Get timeout
        if checkkey(['timeout'], infra["configuration"]):
            timeout = infra["configuration"]["timeout"]
        else:
            timeout = args.timeout

    else:
        maxthreads = args.maxthreads
        timeout = args.timeout

    if args.quiet is not True:
        print("Instance = " + instance)
        print("Max threads = " + str(maxthreads))
        print("Timeout = " + str(timeout) + "s")

    logging.info("%s;%s", \
                 instance, \
                 "MaxThreads=" + str(maxthreads) + \
                 " Timeout=" + str(timeout) + "s")

    started = time.time()

    if args.quiet is not True:
        print("----------------------- Started threads execution @ " + \
              time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(started)))

    queue_in = Queue()
    completed = {}
    cmdid = []

    if checkkey(['rest'], infra):

        # Check if id exists
        for cmd in infra["rest"]:
            if checkkey(['id'], cmd):
                cmdid.append(cmd["id"])
            else:
                if args.quiet is not True:
                    print(">>> Error: ID is missing in 'rest' section.")
                logging.critical("%s;%s", \
                                 instance, \
                                 "ID is missing in 'rest' section.")
                exit()

        # Check for same id in rest commands
        for i in cmdid:
            if cmdid.count(i) > 1:
                logging.critical("%s;%s", \
                                 instance, \
                                 "Same ID has been found in 'rest' section.")
                exit()

        # Check if maxthreads is more elevated than rest commands
        if maxthreads > len(infra["rest"]):
            maxthreads = len(infra["rest"])

        # Create threads
        for index in range(maxthreads): #pylint: disable=I0011,W0612
            thread = restapicmd(queue_in, completed, timeout, args.logpath, instance)
            thread.setDaemon(True)
            thread.start()

        # Put threads in queue
        for cmd in infra["rest"]:
            queue_in.put(cmd)

        # Synchronize
        queue_in.join()

    # Stats
    ended = time.time()
    thsuc = len(list(filter(issuccess.match, list(completed.values()))))

    logging.info("%s;%s", \
                 instance, \
                 "ExecutionTime=" + str(round((ended - started), 4)) + \
                 " Success=" + str(thsuc) + \
                 " Failed=" + str(len(completed.values()) - thsuc))

    if args.quiet is not True:
        print("----------------------- Ended threads execution @ " + \
            time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ended)))
        print("Execution time : %ss" % round((ended - started), 4))
        print("Success : " + str(thsuc))
        print("Failed : " + str(len(completed.values()) - thsuc))

    # Delete .lock file
    if Path(instance + ".lock").is_file():
        os.remove(instance + ".lock")


#------------- Start program
if __name__ == "__main__":
    main()
