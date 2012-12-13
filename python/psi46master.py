from sclient import *
from decode import *
from colorprinter import printer
from threading import Thread
import subprocess
from BetterConfigParser import BetterConfigParser
import sys
import argparse

#------------some configuration--------------
parser = argparse.ArgumentParser()

parser.add_argument("-c", "--config", dest="configDir",
                       help="specify directory containing config files e.g. ../config/",
                       default="../config/")
parser.add_argument("-dir","--directory", dest="loggingDir",
                        help="specify directory containing all logging files e.g. ../DATA/logfiles/",
                        default="../DATA/logfiles")
#parse args and setup logdir
args = parser.parse_args()
Logger = printer()
Logger.set_prefix('')
Logger.set_logfile('%s/psi46Handler.log'%(args.loggingDir))
Logger <<'ConfigDir: "%s"'%args.configDir
configDir= args.configDir
#load config
config = BetterConfigParser()
config.read(configDir+'/elComandante.conf')
#config
serverZiel=config.get('subsystem','Ziel')
Port = int(config.get('subsystem','Port'))
serverPort = int(config.get('subsystem','serverPort'))
psiSubscription = config.get('subsystem','psiSubscription')
#construct
client = sClient(serverZiel,serverPort,"psi46")
#subscribe
client.subscribe(psiSubscription)
#----------------------------------------------------


#handler
def handler(signum, frame):
    Logger << 'Close Connection'
    client.closeConnection()
    Logger << 'Signal handler called with signal', signum
signal.signal(signal.SIGINT, handler)

#color gadget
def colorGenerator():
    list=['green','red','blue','magenta']
    i=0
    while True:
        yield list[i]
        i = (i+1)%len(list)

class TBmaster(object):
    def __init__(self, TB, client, psiSubscription, Logger, color='black'):
        self.TB = TB
        self.client = client
        self.psiSubscription = psiSubscription
        self.color = color
        self.Logger = Logger
        self.TBSubscription=self.client.subscribe('/TB%s'%TB)

    def _spawn(self):
        #self.proc = subprocess.Popen([executestr,''], shell = True, stdout=subprocess.PIPE)
        self.proc = subprocess.Popen([executestr,''], shell = True, stdout = subprocess.PIPE, stdin = subprocess.PIPE)
        busy[TB] = True

    def _kill(self):
        try:
            self.proc.kill()
            self.Logger.warning("--> PSI%s KILLED"%TB)
        except:
            self.Logger.warning("--> nothing to be killed")

    def _abort(self):
        self.Logger.warning('ABORT!')
        self._kill()
        Abort[TB] = False
        return True

    def _resteVariables(self):
        busy[self.TB] = False
        failed[self.TB] = False
        TestEnd[self.TB] = False
        DoTest[self.TB] = False
        ClosePSI[self.TB] = False
        Abort[self.TB] = False

    def _readAllSoFar(self, retVal = ''): 
        while (select.select([self.proc.stdout], [], [], 0)[0] != []) and self.proc.poll() is None:   
            retVal += self.proc.stdout.read(1)
        return retVal

    @staticmethod
    def findError(stat):
        return any([Error in stat for Error in ['error','Error','anyOtherString']])

    def _readout(self):
        failed = False
        self.Logger << 'HERE i am'
        while self.proc.poll() is None and ClosePSI[TB]==False:
            if Abort[TB]:
                failed = self._abort()
        lines = ['']
        lines = self.readAllSoFar(lines[-1]).split('\n')
        for a in range(len(lines)-1):
            line=lines[a]
                hesays=line.rstrip()
                self.client.send(self.TBSubscription,hesays+'\n')        
                self.Logger.printcolor("PSI%s stdout: %s"%(TB,hesays),self.color)
                if self.findError(line.rstrip()):
                    failed=True
                    self._kill()
                if 'command not found' in line.strip():
                    self.Logger.warning("--> psi46expert for TB%s not found"%TB)
                if Abort[TB]: 
                    failed = self._abort()
        self.Logger << 'I am done'
        TestEnd[TB] = True
        busy[TB] = False
        return failed

    def _answer(self):
        if failed[TB]:
            self.client.send(self.psiSubscription,':STAT:TB%s! test:failed\n'%self.TB)
            self.Logger << ':STAT:TB%s! test:failed'%self.TB
        else:
            self.client.send(self.psiSubscription,':STAT:TB%s! test:finished\n'%self.TB)
            self.Logger << ':STAT:TB%s! test:finished'%self.TB

    def executeTest(self,whichTest,dir,fname):
        self._resetVariables()
        self.Logger << 'psi46 %s in TB%s'%(whichTest,self.TB)
        executestr='psi46expert -dir %s -f %s -r %s.root -log %s.log'%(dir,whichTest,fname,fname)
        self._spawn(executestr)
        failed[TB]=self._readout()
        self._answer()

    def openTB(self,dir,fname):
        self._resetVariables()
        Logger << 'open TB%s'%(self.TB)
        executestr='psi46expert -dir %s -r %s.root -log %s.log'%(dir,fname,fname)
        self._spawn(executestr)
        failed[TB]=self._readout()
        while not ClosePSI[TB]:
            pass
        self.Logger << 'CLOSE TB %s HERE'%(TB)
        self.proc.communicate(input='exit\n')[0] 
        self.proc.poll()
        if (None == self.proc.returncode):
            try:
                self.proc.send_signal(signal.SIGINT)
            except:
                slef.Logger << 'Process already killed'
        self._answer()


def initGlobals(numTB): 
    busy = [False]*numTB
    failed = [False]*numTB
    TestEnd = [False]*numTB
    DoTest=[False]*numTB
    ClosePSI=[False]*numTB
    Abort=[False]*numTB



#Globals
global busy
global failed
global TestEnd
global DoTest
global ClosePSI
global Abort

End=False
#MAINLOOP
numTB = 4

color = colorGenerator()

Logger << 'Hello\n'

#ToDo:
initGlobals(numTB)
#init TBmasters:
TBmasters=[]
for i in range(numTB):
    TBmasters.append(TBmaster(i, client, psiSubscription, Logger, next(color)))



#RECEIVE COMMANDS (mainloop)
while client.anzahl_threads > 0 and not End:
    sleep(.5)
    packet = client.getFirstPacket(psiSubscription)
    if not packet.isEmpty() and not "pong" in packet.data.lower():
        time,coms,typ,msg,cmd = decode(packet.data)
        Logger << time,coms,typ,msg
        Logger << cmd
        if coms[0].find('PROG')==0 and coms[1].find('TB')==0 and coms[2].find('OPEN')==0 and typ == 'c':
	        Logger << msg
            dir,fname=msg.split(',')
            TB=int(coms[1][2])
            if not busy[TB]:
                DoTest[TB] = Thread(target=TBmasters[TB].openTB, args=(dir,fname,))
                DoTest[TB].start()

        elif coms[0].find('PROG')==0 and coms[1].find('TB')==0 and coms[2][0:5] == 'CLOSE' and typ == 'c':
            if len(coms[1])>=3:
		        TB=int(coms[1][2])
	    	    Logger << 'trying to close TB...'
            	ClosePSI[TB]=True

        elif coms[0].find('PROG')==0 and coms[1][0:2] == 'TB' and coms[2][0:5] == 'START' and typ == 'c':
            whichTest,dir,fname=msg.split(',')
            TB=int(coms[1][2])
            if not busy[TB]:
		        Logger << whichTest
                Logger << '\t--> psi46 execute %s in TB%s'%(whichTest,TB)
                DoTest[TB] = Thread(target=TBmasters[TB].executeTest, args=(whichTest,dir,fname,))
                DoTest[TB].start()
                client.send(psiSubscription,':STAT:TB%s! %s:started\n'%(TB,whichTest))
                busy[TB]=True
            else:
                client.send(psiSubscription,':STAT:TB%s! busy\n'%TB)

        elif coms[0][0:4] == 'PROG' and coms[1][0:2] == 'TB' and coms[2][0:4] == 'KILL' and typ == 'c':
            TB=int(coms[1][2])
            if not DoTest[TB]:
                Logger << 'nothing to be killed!'
            else:
                failed[TB]=True
                busy[TB]=False
                Abort[TB]=True
                Logger << 'killing TB%s...'%TB
                
        elif coms[0].find('PROG')==0 and coms[1].find('EXIT')==0 and typ == 'c':
            Logger << 'exit'
            if not reduce(lambda x,y: x or y, busy):
                End = True
            else:
                for i in range(0,numTB):
                    if busy[i]: client.send(psiSubscription,':STAT:TB%s! busy\n'%i)

        elif coms[0][0:4] == 'STAT' and coms[1][0:2] == 'TB' and typ == 'q':
            TB=int(coms[1][2])
            if busy[TB]:
                client.send(psiSubscription,':STAT:TB%s! busy\n'%TB)
            elif failed[TB]:
                client.send(psiSubscription,':STAT:TB%s! test:failed\n'%TB)
            elif TestEnd[TB]:
                client.send(psiSubscription,':STAT:TB%s! test:finished\n'%TB)
            else:
                client.send(psiSubscription,':STAT:TB%s! status:unknown\n'%TB)
        else:
            Logger << 'unknown command: ', coms, msg
    else:
        pass
        #Logger << 'waiting for answer...\n'

for i in range(0,numTB):
    if failed[i]: client.send(psiSubscription,':STAT:TB%s! test:failed\n'%i)
    elif TestEnd[i]: client.send(psiSubscription,':STAT:TB%s! test:finished\n'%i)

client.send(psiSubscription,':prog:stat! exit\n')    
Logger << 'exiting...'
client.closeConnection()

#END
while client.anzahl_threads > 0: 
    Logger << 'waiting for client to be closed...'
    client.closeConnection()
    sleep(0.5)
    pass    		
Logger << 'ciao!'
