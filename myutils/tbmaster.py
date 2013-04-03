
from myutils import sClient, printer, decode, BetterConfigParser, colorgenerator
from threading import Thread
import subprocess
import sys
import select
from time import sleep
class TBmaster(object):
    def __init__(self, TB, client, psiSubscription, Logger, color='black', psiVersion='psi46expert'):
        self.TB = TB
        self.client = client
        self.psiSubscription = psiSubscription
        self.color = color
        self.Logger = Logger
        self.TBSubscription = '/TB%s'%self.TB
        self.client.subscribe(self.TBSubscription)
        self.dir = ''
        self.psiVersion = psiVersion

        self.failed = False
        self.busy = False
        self.testName ='unkown'
        self.testNo = -1
        self.TestEnd = False
        self.DoTest= False
        self.ClosePSI= False
        self.Abort = False

    def _spawn(self,executestr):
        self.proc = subprocess.Popen([executestr,''], shell = True, stdout = subprocess.PIPE, stdin = subprocess.PIPE)
        self.busy = True

    def _kill(self):
        try:
            self.proc.kill()
            self.Logger.warning("PSI%s KILLED"%self.TB)
        except:
            self.Logger.warning("nothing to be killed")

    def _abort(self):
        self.Logger.warning('ABORT!')
        self._kill()
        self.Abort = False
        return True

    def _resetVariables(self):
        self.busy = False
        self.failed = False
        self.TestEnd = False
        self.DoTest = False
        self.ClosePSI = False
        self.Abort = False

    def _readAllSoFar(self, retVal = ''): 
        while (select.select([self.proc.stdout],[],[],0)[0]!=[]) and self.proc.poll() is None:   
            retVal += self.proc.stdout.read(1)
        return retVal

    @staticmethod
    def findError(stat):
        return any([Error in stat for Error in ['error','Error','anyOtherString','command not found']])

    def _readout(self):
        internalFailed = False
        self.Logger << '>>> Aquire Testboard %s <<<'%self.TB
#        self._answer(self)
        while self.proc.poll() is None and self.ClosePSI==False:
            if self.Abort:
                internalFailed = self._abort()
            lines = ['']
            lines = self._readAllSoFar(lines[-1]).split('\n')
            for a in range(len(lines)-1):
                line=lines[a]
                hesays=line.rstrip()
                self.client.send(self.TBSubscription,'%s\n'%hesays)
                self.Logger.printcolor("psi46@TB%s >> %s"%(self.TB,hesays),self.color)
                if self.findError(line.rstrip()):
                    self.Logger << 'The following error triggered the exception:'
                    self.Logger.warning(line.rstrip())
                    self.client.send(self.psiSubscription, 'psi46@TB%s - Error >> %s\n'%(self.TB,line.rstrip()))
                    self.client.send(self.TBSubscription, 'Error >> %s\n'%(line.rstrip()))
                    internalFailed = True
                    self.failed = True
                    self._kill()
                if 'command not found' in line.strip():
                    self.Logger.warning("psi46expert for TB%s not found"%self.TB)
                if self.Abort:
                    internalFailed = self._abort()
                    self.failed = internalFailed or self.failed
        self.Logger << '>>> Release Testboard %s <<<'%self.TB
        self.TestEnd = True
        self.busy = False
        return internalFailed

    def _answer(self):
        name = self.get_directory_name()
        if self.failed:
            self.client.send(self.psiSubscription,':STAT:TB%s! %s:failed\n'%(self.TB,name))
            self.Logger.warning(':Test %s failed in TB%s'%(name,self.TB))
            self.client.send(self.psiSubscription,':STAT:TB%s! %s:failed\n'%(self.TB,name))
        elif self.busy:
            self.client.send(self.psiSubscription,':STAT:TB%s! %s:busy\n'%(self.TB,name))
            #self.Logger << ':Test %s busy in TB%s'%(name,self.TB)
        else:
            self.client.send(self.psiSubscription,':STAT:TB%s! %s:finished\n'%(self.TB,name))
            self.Logger << ':Test %s finished in TB%s'%(name,self.TB)
            
            
    def get_directory_name(self):
        dir = self.dir.rstrip('/')
        name = dir.split('/')[-1]
        return name

    def executeTest(self,whichTest,dir,fname):
        self._resetVariables()
        self.dir = dir
        self.Logger << 'executing psi46 %s in TB%s'%(whichTest,self.TB)
        executestr='%s -dir %s -f %s -r %s.root -log %s.log'%(self.psiVersion,dir,whichTest,fname,fname)
        self._spawn(executestr)
        self.failed=self._readout()
        self._answer()

    def openTB(self,dir,fname):
        self._resetVariables()
        self.dir = dir
        self.Logger << 'open TB%s'%(self.TB)
        executestr='%s -dir %s -r %s.root -log %s.log'%(self.psiVersion,dir,fname,fname)
        self._spawn(executestr)
        self.failed=self._readout()
        self._answer()
        while not self.ClosePSI:
            pass
        self.Logger << 'CLOSE TB %s HERE'%(self.TB)
        self.proc.communicate(input='exit\n')[0] 
        self.proc.poll()
        if (None == self.proc.returncode):
            try:
                self.proc.send_signal(signal.SIGINT)
            except:
                self.Logger << 'Process already killed'
        self._answer()
        
    def sendTBStatus(self):
        self._answer()
        