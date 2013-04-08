import sys
from collections import defaultdict
from zope.interface import implements
from zope.interface.verify import verifyClass
from core import *
from base import *

class SimpleUserService:
    implements(IUserService)

    def __init__(self, game, player):
        self.game = game
        self.player = player

    def sendMessage(self, message):
        print message

    def chooseCardFromHand(self, klass):
        #TODO: Replace with access to "UserService" object
        validChoices = [val for val in sorted(self.player.hand) if isinstance(val, klass)]

        cardChoice = self.getCardInstance(validChoices)
        if not cardChoice:
            return None
        assert cardChoice in validChoices

        return cardChoice

    def chooseCardsFromHand(self, klass, number, ignore=None):
        #TODO: Replace with access to "UserService" object
        validChoices = [val for val in sorted(self.player.hand) if isinstance(val, klass) and val != ignore]
        choices = []

        while number > 0 and self.player.hand:
            cardChoice = self.getCardInstance(validChoices)
            if not cardChoice:
                return None
            assert cardChoice in validChoices
            validChoices.remove(cardChoice)
            choices.append(cardChoice)
            number -= 1
        return choices

    def chooseCardFromSupply(self, klass, availableCoins):
        validChoices = self.game.getAvailableCardOfType(klass, availableCoins)
        return self.getCardNameByCost(validChoices)

    def chooseCardForBuy(self):
        validChoices = self.game.getAvailableCardsToBuy(self.player.coins)
        return self.getCardNameByCost(validChoices)

    def getCardInstance(self, validChoices):
        for i, card in enumerate(validChoices):
            print "%d: %s" % (i+1, repr(card))
        choice = raw_input("Enter choice: ")
        if choice == "c" or choice == "" or int(choice)-1 < 0 or int(choice)-1 >= len(validChoices):
            return None
        return validChoices[int(choice)-1]

    def getCardNameByCost(self, validChoices):
        cardList = []
        for choice in validChoices:
            cardList.append(self.game.cardFactory.newCard(choice))
        cardList = sorted(cardList, key=lambda x: x.cost, reverse=True)
        for i, card in enumerate(cardList):
            print "%d: (%d) %s" % (i+1, card.cost, repr(card))
        choice = raw_input("Enter choice: ")
        if choice == "c" or choice == "" or int(choice)-1 < 0 or int(choice)-1 >= len(validChoices):
            return None
        return cardList[int(choice)-1].__name__()

    def getYesNoChoice(self, question):
        print question
        print "1: No"
        print "2: Yes"
        choice = raw_input("Enter choice: ")
        if choice == "2":
            return True
        else:
            return False

    def getChoice(self, prompt):
        print prompt
        choice = raw_input("Enter choice: ")
        if choice == "c" or choice == "":
            return None
        return choice

    def noBuysRemain(self):
        self.game.endTurn()

verifyClass(IUserService, SimpleUserService)

class Menu:
    def __init__(self, game):
        self._options = {'1': self.playCard,
                         '2': self.playTreasures,
                         '3': self.buyCard,
                         '4': self.showHand,
                         '5': self.showGameArea,
                         '6': self.endTurn}
        self.game = game

    def handle_options(self, player):
        option = "-1"
        while option not in self._options:
            for key in sorted(self._options.iterkeys()):
                print "%s: %s" % (key, self._options[key].__doc__)
            option = raw_input("Enter choice: ")
            if option == "c":
                return

        self._options[option](player)

    #def playCard(self, player):
        #"""Play card"""
        #cardToPlay = player.userService.chooseCardFromHand((Action, Treasure))
        #if cardToPlay:
            #player.play(cardToPlay)

    @defer.inlineCallbacks
    def playCard(self, player):
        """Play card"""
        card = yield player.userService.chooseCardFromHand((Action, Treasure))
        if card:
            played = yield player.play(card)
            if played:
                print "%s played %s" % (player, repr(card))

    def playTreasures(self, player):
        """Play all treasure cards"""
        hand = player.hand[:]
        for card in hand:
            if isinstance(card, Treasure):
                player.play(card)

    #def buyCard(self, player):
        #"""Buy card"""
        #cardToBuy = player.userService.chooseCardForBuy()
        #if cardToBuy:
            #player.buy(cardToBuy)

    @defer.inlineCallbacks
    def buyCard(self, player):
        """Buy card"""
        cardName = yield player.userService.chooseCardForBuy()
        if cardName:
            bought = yield player.buy(cardName)
            if bought:
                print "%s bought %s" % (player, cardName)

    def showHand(self, player):
        """Show hand"""
        cardCount = defaultdict(int)
        for card in player.hand:
            cardCount[card.__repr__()] += 1
        handStr = ', '.join(["%s: %d" % (name, count) for name, count in cardCount.iteritems()])
        #print "\nHand:      " + repr(Counter(player.hand))
        print "\nHand:     " + handStr + "\n"
        print "Actions:  " + repr(player.actions) + "\t\tDraw: %d" % len(player.drawdeck)
        print "Buys:     " + repr(player.buys) + "\t\tDiscard: %d" % len(player.discard)
        print "Treasure: " + repr(player.coins)

    def showGameArea(self, player):
        """Show game area"""
        print ""
        for card, remaining in self.game.supplyPile.iteritems():
            print "%s: %d" % (card, remaining)
        for player in self.game.players:
            if player.played and player is not self.game.currentPlayer:
                print "%s duration: %s" % (player, repr(player.played))
        print "Cards played so far:"
        for card in self.game.currentPlayer.played:
            print card
        print ""

    def endTurn(self, player):
        """End turn"""
        self.game.endTurn()

    def showSummary(self):
        winners = self.game.getWinners()
        if len(winners) > 1:
            print "Game is a tie between %s!" % (' and '.join([x for x in winners]))
        else:
            print "%s wins!" % winners[0] + "\n"
        print ""
        print "%s wins!" % winner
        for player in self.game.players:
            print "%s: %d points" % (player, player.score)
            #print "%s's deck: %s" % (player, repr(player.deck))
            print "%s's deck: [%s]" % (player, ', '.join(["%s: %d" % (name, count) for name, count in cardCount.iteritems()]))
            print ""


def main():
    print "Welcome to Dominion!"
    #user1 = raw_input("Enter username 1: ")
    #user2 = raw_input("Enter username 2: ")
    user1 = "azadin"
    user2 = "john"

    player1 = Player(user1)
    #player2 = Player(user2)

    #players = [player1, player2]

    #game = GameManager(players)
    game = GameManager([player1])

    player1.userService = SimpleUserService(game, player1)
    #player2.userService = SimpleUserService(game, player2)

    #cards = {
            #"Mine": 10,
            #"Village": 10,
            #"Smithy": 10,
            #"Market": 10,
            #"Festival": 10,
            #"Feast": 10,
            #"Chancellor": 10,
            #"Laboratory": 10,
            #"Gardens": 8,
            #"CouncilRoom": 10
            #}
    game.setup()

    menu = Menu(game)
    #print "Turn order will be %s then %s" % (user1, user2)
    print "Game: %s" % ', '.join(sorted([x for x in game.supplyPile.keys() if game.cardFactory.newCard(x).__module__ != 'core']))

    while not game.end():
        player = game.currentPlayer
        #print "\n\n%s's turn!" % player
        print "\n------------------\n\n%s's turn!\nTurn: %d" % (player, player.turn)

        #showHand(player)
        menu.showHand(player)
        print ""
        menu.handle_options(player)

    menu.showSummary()

if __name__ == '__main__':
    main()

