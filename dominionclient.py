import sys

from twisted.spread import pb
from twisted.internet import reactor, stdio, defer
from twisted.protocols import basic
from twisted.cred import credentials
from twisted.python import log

from zope.interface import implements

from core import *

class DominionClient(basic.LineReceiver):

    delimiter = '\n'

    def __init__(self, perspective):
        self.perspective = perspective
        self.captureNextLine = None

    def connectionMade(self):
        self.sendLine("Welcome to Dominion!")

    def lineReceived(self, line):
        if not line: return

        if self.perspective.captureNextLine:
            self.perspective.captureNextLine.callback(line)
            self.perspective.captureNextLine = None
            return

        self.perspective.sendLine(line)
        #commandParts = line.split()
        #command = commandParts[0].lower()
        #args = commandParts[1:]

        #try:
            #method = getattr(self, 'do_' + command)
        #except AttributeError, e:
            #self.sendLine('Error: no such command.')
            #return

        #try:
            #method(*args)
        #except Exception, e:
            #self.sendLine('Error: ' + str(e))

class DominionClientPerspective(pb.Referenceable):

    def __init__(self):
        self.captureNextLine = None

    def remote_print(self, message):
        #self.service.sendMessage(message)
        print message

    def remote_getChoice(self, message):
        #self.service.sendMessage(message)
        print message
        d = defer.Deferred()
        self.captureNextLine = d
        return d

    def connect(self, user, password):
        factory = pb.PBClientFactory()
        reactor.connectTCP("localhost", 8800, factory)
        def1 = factory.login(credentials.UsernamePassword(user, password), client=self)
        def1.addCallback(self.connected)
        reactor.run()

    def connected(self, perspective):
        print "connected, joining game #EA"
        self.perspective = perspective
        d = perspective.callRemote("joinGame", "#EA")
        d.addCallback(self.gotgame)

    def gotgame(self, game):
        print "joined game"
        self.game = game

    def sendLine(self, message):
        d = self.game.callRemote("send", message)

    def shutdown(self, result):
        reactor.stop()

def main():
    argv = sys.argv

    clientPerspective = DominionClientPerspective()
    client = DominionClient(clientPerspective)
    stdio.StandardIO(client)
    clientPerspective.connect(argv[1], argv[2])

if __name__ == '__main__':
    main()
