from sys import stdout

from zope.interface import implements
from zope.interface.verify import verifyClass
from collections import defaultdict

from twisted.python.log import startLogging
from twisted.cred.checkers import ANONYMOUS, AllowAnonymousAccess
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse
from twisted.cred.portal import IRealm, Portal
from twisted.internet import reactor, defer
from twisted.spread.pb import Avatar, Viewable, IPerspective, PBServerFactory

from core import *
from base import *

class OptionCancelled(Exception):
    pass

class CLIUserService:
    implements(IUserService)

    def __init__(self, game, remoteUser, player):
        self.game = game
        self.remoteUser = remoteUser
        self.player = player

    def sendMessage(self, message):
        #print message
        self.remoteUser.callRemote("print", message)

    @defer.inlineCallbacks
    def chooseCardFromHand(self, klass=Card):
        validChoices = [val for val in sorted(self.player.hand) if isinstance(val, klass)]
        choice = yield self.getCardInstance(validChoices)
        defer.returnValue(choice)

    @defer.inlineCallbacks
    def chooseCardsFromHand(self, klass, number, ignore=None):
        #TODO: Replace with access to "UserService" object
        validChoices = [val for val in sorted(self.player.hand) if isinstance(val, klass) and val != ignore]
        choices = []

        while number > 0 and self.player.hand:
            cardChoice = yield self.getCardInstance(validChoices)
            if not cardChoice:
                #defer.returnValue(None)
                raise OptionCancelled()
            assert cardChoice in validChoices
            validChoices.remove(cardChoice)
            choices.append(cardChoice)
            number -= 1
        defer.returnValue(choices)

    @defer.inlineCallbacks
    def chooseCardFromSupply(self, klass, availableCoins):
        validChoices = self.game.getAvailableCardOfType(klass, availableCoins)
        choice = yield self.getCardNameByCost(validChoices)
        defer.returnValue(choice)

    @defer.inlineCallbacks
    def chooseCardForBuy(self):
        validChoices = self.game.getAvailableCardsToBuy(self.player.coins)
        choice = yield self.getCardNameByCost(validChoices)
        defer.returnValue(choice)

    @defer.inlineCallbacks
    def getCardInstance(self, validChoices):
        if not validChoices:
            defer.returnValue(None)
        prompt = ""
        for i, card in enumerate(validChoices):
            prompt += "%d: %s" % (i+1, repr(card)) + "\n"
        choice = yield self.remoteUser.callRemote("getChoice", prompt)
        if choice == "c" or int(choice)-1 < 0 or int(choice)-1 >= len(validChoices):
            #defer.returnValue(None)
            raise OptionCancelled()
        defer.returnValue(validChoices[int(choice)-1])

    @defer.inlineCallbacks
    def getCardNameByCost(self, validChoices):
        cardList = []
        for choice in validChoices:
            cardList.append(self.game.cardFactory.newCard(choice))
        cardList = sorted(cardList, key=lambda x: x.cost, reverse=True)
        prompt = ""
        for i, card in enumerate(cardList):
            prompt += "%d: (%d) %s" % (i+1, card.cost, repr(card)) + "\n"
        choice = yield self.remoteUser.callRemote("getChoice", prompt)
        if choice == "c" or int(choice)-1 < 0 or int(choice)-1 >= len(validChoices):
            raise OptionCancelled()
        defer.returnValue(cardList[int(choice)-1].__name__())

    @defer.inlineCallbacks
    def getYesNoChoice(self, question):
        prompt = question + "\n1: No\n2: Yes"
        choice = yield self.remoteUser.callRemote("getChoice", prompt)
        if choice == "2":
            defer.returnValue(True)
        else:
            defer.returnValue(False)

    @defer.inlineCallbacks
    def getChoice(self, prompt):
        choice = yield self.remoteUser.callRemote("getChoice", prompt)
        if choice == "c":
            raise OptionCancelled()
        defer.returnValue(choice)

    def noBuysRemain(self):
        self.game.endTurn()

verifyClass(IUserService, CLIUserService)

class DominionServer:
    def __init__(self):
        self.games = {}

    def joinGame(self, gameId, user):
        if not self.games.has_key(gameId):
            self.games[gameId] = Game(gameId)
        self.games[gameId].addUser(user)
        return self.games[gameId]


class DominionRealm(object):
    implements(IRealm)

    def __init__(self):
        self.anoncount = 0
        self.avatars = {}

    def requestAvatar(self, avatarId, mind, *interfaces):
        assert IPerspective in interfaces
        if avatarId is ANONYMOUS:
            avatarId = "Anonymous%s" % str(self.anoncount)
            self.anoncount +=1 
        if not self.avatars.has_key(avatarId):
            avatar = User(avatarId)
            self.avatars[avatarId] = avatar
            avatar.server = self.server
        else:
            avatar = self.avatars[avatarId]
        avatar.attached(mind)
        return IPerspective, avatar, lambda a=avatar:a.detached(mind)

class User(Avatar):
    """
    User avatar. Persistent on server and keeps tracks of connected clients

    @type name: C{str}
    @ivar name: The username which was used during login or C{"Anonymous"}
    """
    def __init__(self, name):
        self.name = name
    def attached(self, mind):
        self.remote = mind
    def detached(self, mind):
        self.remote = None
    def perspective_joinGame(self, gameId):
        return self.server.joinGame(gameId, self)

class Game(Viewable):
    def __init__(self, gameId):
        self.name = gameId
        self.users = {}
        self.players = []
        self.inProgress = False

    def addUser(self, user):
        if user not in self.users and not self.inProgress:
            player = Player(user.name)
            user.player = player
            self.users[user] = player
            self.players.append(player)

        if len(self.users) == 2 and not self.inProgress:
            self.startGame()
            self.inProgress = True

    #def view_send(self, from_user, message):
        #for user in self.users:
            #user.send("<%s> %s" % (from_user.name, message))

    def view_hand(self, from_user):
        pass

    def startGame(self):
        self.gameManager = GameManager(self.players)

        for user, player in self.users.iteritems():
            player.userService = CLIUserService(self.gameManager, user.remote, player)

        self.gameManager.setup()

        self.menu = Menu(self)

        turnOrder = "Turn order will be "
        turnOrder += ' then '.join(["%s" % x for x in self.players]) + "\n"
        turnOrder += "Game: %s" % ', '.join(sorted([x for x in self.gameManager.supplyPile.keys() if self.gameManager.cardFactory.newCard(x).__module__ != 'core']))
        self.sendToAll(turnOrder)

        self.gameLoop()

    @defer.inlineCallbacks
    def gameLoop(self):
        prevPlayer = None
        while not self.gameManager.end():
            player = self.gameManager.currentPlayer
            if prevPlayer != player:
                self.sendToAll("\n------------------\n\n%s's turn!\nTurn: %d" % (player, player.turn))
                prevPlayer = player

            self.menu.showHand(player)
            yield self.menu.handle_options(player)

        self.menu.showSummary()

    def sendToAll(self, message):
        for player in self.players:
            player.userService.sendMessage(message)

class Menu:
    def __init__(self, game):
        self._options = {'1': self.playCard,
                         '2': self.playTreasures,
                         '3': self.buyCard,
                         '4': self.showHand,
                         '5': self.showGameArea,
                         '6': self.endTurn}
        self.game = game

    @defer.inlineCallbacks
    def handle_options(self, player):
        option = "-1"
        while option not in self._options:
            prompt = ""
            for key in sorted(self._options.iterkeys()):
                prompt += "%s: %s" % (key, self._options[key].__doc__) + "\n"
            option = yield player.userService.getChoice(prompt)

        try:
            yield self._options[option](player)
        except OptionCancelled:
            pass
        except Exception as e:
            print e

    @defer.inlineCallbacks
    def playCard(self, player):
        """Play card"""
        card = yield player.userService.chooseCardFromHand((Action, Treasure))
        self.game.sendToAll("%s plays a %s." % (player, repr(card)))
        played = yield player.play(card)
        if played:
            #self.game.sendToAll("%s played %s" % (player, repr(card)))
            self.game.sendToAll(player.flushLog())
        else:
            player.flushLog()

    def playTreasures(self, player):
        """Play all treasure cards"""
        cardsPlayed = defaultdict(int)
        hand = player.hand[:]
        for card in hand:
            if isinstance(card, Treasure):
                cardsPlayed[repr(card)] += 1
                player.play(card)
        message = "%s plays %s." % (player, ', '.join(["%d %ss" % (x, y) for y, x in cardsPlayed.iteritems()]))
        self.game.sendToAll(message)
        #self.game.sendToAll(player.flushLog())
        player.flushLog()

    @defer.inlineCallbacks
    def buyCard(self, player):
        """Buy card"""
        cardName = yield player.userService.chooseCardForBuy()
        bought = yield player.buy(cardName)
        self.game.sendToAll(player.flushLog())
        #if bought:
            #self.game.sendToAll("%s buys a %s" % (player, repr(self.game.gameManager.cardFactory.newCard(cardName))))

    def showHand(self, player):
        """Show hand"""
        cardCount = defaultdict(int)
        for card in player.hand:
            cardCount[repr(card)] += 1
        handStr = ', '.join(["%s: %d" % (name, count) for name, count in cardCount.iteritems()])
        message = "\n"
        message += "Hand:     " + handStr + "\n\n"
        message += "Actions:  " + repr(player.actions) + "\t\tDraw: %d" % len(player.drawdeck) + "\n"
        message += "Buys:     " + repr(player.buys) + "\t\tDiscard: %d" % len(player.discard) + "\n"
        message += "Treasure: " + repr(player.coins) + "\n"
        player.userService.sendMessage(message)

    def showGameArea(self, player):
        """Show game area"""
        message = ""
        for card, remaining in self.game.gameManager.supplyPile.iteritems():
            message += "%s: %d" % (card, remaining) + "\n"
        for playerIter in self.game.gameManager.players:
            if playerIter.played and playerIter is not self.game.gameManager.currentPlayer:
                message += "%s duration: %s" % (playerIter, repr(player.played)) + "\n"
        message += "Cards played so far:\n"
        for card in self.game.gameManager.currentPlayer.played:
            message += repr(card) + "\n"
        message += "\n"
        player.userService.sendMessage(message)

    def endTurn(self, player):
        """End turn"""
        self.game.gameManager.endTurn()
        self.game.sendToAll(player.flushLog())

    def showSummary(self):
        winners = self.game.gameManager.getWinners()
        message = "\n"
        if len(winners) > 1:
            message += "Game is a tie between %s!" % (' and '.join([x for x in winners]))
        else:
            message += "%s wins!" % winners[0] + "\n"
        for player in self.game.gameManager.players:
            message += "%s: %d points" % (player, player.score) + "\n"
            #message += "%s's deck: %s" % (player, repr(player.deck)) + "\n"
            cardCount = defaultdict(int)
            for card in player.deck:
                cardCount[repr(card)] += 1
            message += "%s's deck: [%s]" % (player, ', '.join(["%s: %d" % (name, count) for name, count in cardCount.iteritems()])) + "\n"
            message += "\n"
        self.game.sendToAll(message)

def main():
    startLogging(stdout)

    realm = DominionRealm()
    realm.server = DominionServer()
    c1 = InMemoryUsernamePasswordDatabaseDontUse()
    c1.addUser("john", "1234")
    c1.addUser("bo", "9876")
    c1.addUser("adam", "3456")
    c1.addUser("derek", "7654")
    c2 = AllowAnonymousAccess()
    p = Portal(realm, [c1, c2])

    reactor.listenTCP(8800, PBServerFactory(p))
    reactor.run()

if __name__ == '__main__':
    main()
