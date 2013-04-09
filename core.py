from zope.interface import Interface
from collections import Counter
from itertools import cycle
from twisted.internet import defer
import random

_cardLookup = {}
_kingdomCardList = []

class CardFactory:
    def newCard(self, cardType):
        if cardType in _cardLookup.keys():
            return _cardLookup[cardType]()

class CardType(type):
    def __new__(cls, name, bases, attrs):
        new = super(CardType, cls).__new__
        klass = new(cls, name,  bases, attrs)
        if not attrs.pop("abstract", None):
            _cardLookup[name] = klass
        if 'cost' in attrs and attrs['__module__'] != 'core':
            _kingdomCardList.append(name)
        return klass

class Card:
    __metaclass__ = CardType

    cost = 0
    abstract = True

    def discard(self):
        return True

    def getCost(self):
        return self.cost

    def onGain(self):
        """Called when card is being gained. Returns whether the card
        should be gained"""
        return True

    def onTrash(self):
        """Called when card is being trashed. Returns whether it should
        actually be trashed"""
        return True

    def __repr__(self):
        return self.__class__.__name__

    def __lt__(self, other):
        return self.__repr__() < other.__repr__()

    def __name__(self):
        return self.__class__.__name__

class Treasure(Card):
    treasure = 0
    abstract = True

    def getTreasure(self):
        return self.treasure
    pass

class Victory(Card):
    victory = 0
    abstract = True

class Action(Card):
    abstract = True

class Attack(Action):
    abstract = True

class Reaction(Card):
    abstract = True

class AttackReaction(Reaction):
    abstract = True

class Curse(Card):
    """Curse"""
    kingdom = False
    cost = 0
    victory = -1

class Estate(Victory):
    """Estate"""
    kingdom = False
    cost = 2
    victory = 1

class Duchy(Victory):
    """Duchy"""
    kingdom = False
    cost = 5
    victory = 3

class Province(Victory):
    """Province"""
    kingdom = False
    cost = 8
    victory = 6

class Colony(Victory):
    """Colony"""
    kingdom = False
    cost = 11
    victory = 10

class Copper(Treasure):
    """Copper"""
    kingdom = False
    cost = 0
    treasure = 1

class Silver(Treasure):
    """Silver"""
    kingdom = False
    cost = 3
    treasure = 2

class Gold(Treasure):
    """Gold"""
    kingdom = False
    cost = 6
    treasure = 3

class Platinum(Treasure):
    """Platinum"""
    kingdom = False
    cost = 9
    treasure = 5

class IUserService(Interface):
    def sendMessage(message):
        """Send a message to the user"""

    def chooseCardFromHand(klass):
        """Ask the user to choose one card from their hand of type klass"""

    def chooseCardsFromHand(klass, number, ignore):
        """Ask the user to choose number of cards from their hand of type klass except for ignore"""

    def chooseCardFromSupply(klass, availableCoins):
        """Ask the user to choose a card from the supply of type klass costing no more than availableCoins"""

    def chooseCardForBuy():
        """Ask the user to choose a card to buy"""

    def getCardInstance(validChoices):
        """Ask the user to choose a card from their hand of specified type"""

    def getCardNameByCost(validChoices):
        """Ask the user for what they want to buy given the valid choices"""

    def getYesNoChoice(question):
        """Ask the user to respond to a yes or no question"""

    def getChoice(prompt):
        """Ask the user for input after printing the prompt"""

    def noBuysRemain():
        """Notifies the user service object that the user is unable to do anything else"""

class IllegalAction(Exception):
    pass

class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.played = []
        self.drawdeck = []
        self.discard = []
        self.deck = []
        self.score = 0
        self.turn = 1

        self.turnphase = "IDLE"
        self.actions = 1
        self.buys = 1
        self.coins = 0

        self.logBuffer = []
        self.logLevel = ""

    def __repr__(self):
        return self.name

    def draw(self, number, placeInHand=True):
        if not self.drawdeck and not self.discard:
            return []
        if len(self.drawdeck) < number:
            drawnCards = self.drawdeck[:]
            remaining = number - len(self.drawdeck)
            if placeInHand:
                self.hand.extend(drawnCards)
            self.drawdeck[:] = self.discard[:]
            self.discard[:] = []
            random.shuffle(self.drawdeck)
            self.addToLog("(%s reshuffles.)" % self.name)
            drawnCards.extend(self.draw(remaining, placeInHand))
            return drawnCards
        else:
            drawnCards = self.drawdeck[:number]
            if placeInHand:
                self.hand.extend(drawnCards)
            self.drawdeck[:] = self.drawdeck[number:]
            return drawnCards

    @defer.inlineCallbacks
    def play(self, card):
        assert card in self.hand
        if self.turnphase == "ACTION" and isinstance(card, Action) and self.actions > 0:
            self.played.append(card)
            self.hand.remove(card)
            self.pushLogLevel()
            yield card.doAction()
            self.popLogLevel()
            shouldTrash = False
            try:
                shouldTrash = card.markedForTrash
            except AttributeError:
                pass
            if shouldTrash:
                self.trashFromPlay(card)
            self.actions -= 1
            defer.returnValue(True)
        elif self.turnphase == "ACTION" and isinstance(card, Treasure):
            self.turnphase = "BUY"

        if self.turnphase == "BUY" and isinstance(card, Treasure):
            self.coins += card.getTreasure()
            self.played.append(card)
            self.hand.remove(card)
            defer.returnValue(True)

        defer.returnValue(False)

    @defer.inlineCallbacks
    def buy(self, cardName):
        #assert card.getCost() <= self.coins
        self.turnphase = "BUY"
        if self.buys > 0:
            card = self.game.getCardFromSupply(cardName)
            yield self.gainToDiscard(card)
            self.coins -= card.getCost()
            self.buys -= 1
            self.addToLog("%s buys a %s" % (self.name, repr(card)))
            if self.buys == 0:
                self.userService.noBuysRemain()
            defer.returnValue(True)
        defer.returnValue(False)

    def cleanup(self):
        cardsToDiscard = [x for x in self.played if x.discard()]
        self.played[:] = [x for x in self.played if x not in cardsToDiscard]
        self.discard += cardsToDiscard
        self.discard += self.hand
        self.hand = []
        self.turnphase = "IDLE"
        self.actions = 1
        self.buys = 1
        self.coins = 0
        self.draw(5)

        self.logLevel = ''
        #self.logBuffer = ''

    def updateScore(self):
        self.score = 0
        for card in self.deck:
            if isinstance(card, Victory) or isinstance(card, Curse):
                self.score += card.victory

    @defer.inlineCallbacks
    def gainInHand(self, card):
        shouldGain = yield self._gain(card)
        if shouldGain:
            self.hand.append(card)
        defer.returnValue(shouldGain)

    @defer.inlineCallbacks
    def gainToDiscard(self, card):
        shouldGain = yield self._gain(card)
        if shouldGain:
            self.discard.append(card)
        defer.returnValue(shouldGain)

    @defer.inlineCallbacks
    def _gain(self, card):
        shouldGain = yield card.onGain()
        if shouldGain:
            card.owner = self
            self.deck.append(card)
            self.updateScore()
        defer.returnValue(shouldGain)

    @defer.inlineCallbacks
    def trashFromHand(self, card):
        assert card in self.hand
        shouldTrash = yield self._trash(card)
        if shouldTrash:
            self.hand.remove(card)

    @defer.inlineCallbacks
    def trashFromPlay(self, card):
        assert card in self.played
        shouldTrash = yield card.onTrash()
        if shouldTrash:
            self.played.remove(card)

    @defer.inlineCallbacks
    def _trash(self, card):
        shouldTrash = yield card.onTrash()
        if shouldTrash:
            card.owner = None
            self.deck.remove(card)
            self.game.trash.append(card)
        defer.returnValue(shouldTrash)

    def addToLog(self, message):
        self.logBuffer.append(self.logLevel + message)

    def flushLog(self):
        temp = self.logBuffer
        self.logBuffer = []
        self.logLevel = ""
        return '\n'.join(temp)

    def pushLogLevel(self):
        self.logLevel += "... "

    def popLogLevel(self):
        self.logLevel = self.logLevel[:-4]

class GameManager:
    def __init__(self, players):
        self.players = players
        self.playerCycle = cycle(players)
        self.currentPlayer = self.playerCycle.next()
        self.cardFactory = CardFactory()
        self.trash = []

    def setup(self, cards = None):
        for player in self.players:
            player.game = self
            player.deck = [self.cardFactory.newCard(x) for x in Counter({"Estate" : 3, "Copper" : 7}).elements()]
            #player.deck = [self.cardFactory.newCard(x) for x in ["Estate", "Copper", "Moat", "Witch", "Copper", "Gold", "Silver", "Militia"]]
            for card in player.deck:
                card.owner = player
            player.drawdeck[:] = player.deck[:]
            random.shuffle(player.drawdeck)
            player.draw(5)

        provinces = None
        if len(self.players) == 5:
            provinces = 15
        if len(self.players) == 6:
            provinces = 18

        if len(self.players) > 2:
            vpcards = 12
            if not provinces:
                provinces = vpcards
        else:
            vpcards = provinces = 8

        supplyPile = {
                "Estate": vpcards,
                "Duchy": vpcards,
                "Province": provinces,
                "Copper": 44, #TODO check this number
                "Silver": 30, #TODO check this number
                "Gold": 30, #TODO check this number
                "Curse": max((len(self.players)-1) * 10, 10)
                }

        if not cards:
            cards = random.sample(_kingdomCardList, 10)
        nonVictoryCardPiles = {key: 10 for key in [card for card in cards if not isinstance(self.cardFactory.newCard(card), Victory)]}
        victoryCardPiles = {key: vpcards for key in [card for card in cards if isinstance(self.cardFactory.newCard(card), Victory)]}
        self.supplyPile = dict(supplyPile.items() + nonVictoryCardPiles.items() + victoryCardPiles.items())

        self.currentPlayer.turnphase = "ACTION"

    def getCardFromSupply(self, cardName):
        assert cardName in self.supplyPile.keys() and self.supplyPile[cardName] > 0
        card = self.cardFactory.newCard(cardName)
        self.supplyPile[cardName] -= 1
        return card

    def getAvailableCardsToBuy(self, availableCoin):
        cards = []
        for cardName, remaining in self.supplyPile.iteritems():
            if remaining > 0:
                card = self.cardFactory.newCard(cardName)
                if card.getCost() <= availableCoin:
                    cards.append(cardName)
        return cards

    def getAvailableCardOfType(self, klass, availableCoins):
        cards = []
        for cardName, remaining in self.supplyPile.iteritems():
            if remaining > 0:
                card = self.cardFactory.newCard(cardName)
                if isinstance(card, klass) and card.getCost() <= availableCoins:
                    cards.append(cardName)
        return cards

    def endTurn(self):
        self.currentPlayer.cleanup()
        self.currentPlayer = self.playerCycle.next()
        self.currentPlayer.turnphase = "ACTION"
        self.currentPlayer.turn += 1

    @defer.inlineCallbacks
    def doAttack(self, player):
        """Lets users perform reactions to attacks. Returns list of players who should
        be affected by the attack."""
        deferreds = []
        potentialImmunePlayers = []
        for otherPlayer in self.players:
            if otherPlayer != player:
                for card in otherPlayer.hand:
                    if isinstance(card, AttackReaction):
                        d = card.doReaction(player)
                        deferreds.append(d)
                        potentialImmunePlayers.append(otherPlayer)
        result = yield defer.gatherResults(deferreds)
        playersAffected = []
        for i, otherPlayer in enumerate(potentialImmunePlayers):
            if not result[i]:
                playersAffected.append(otherPlayer)
        for otherPlayer in self.players:
            if otherPlayer not in potentialImmunePlayers and otherPlayer != player:
                playersAffected.append(otherPlayer)
        defer.returnValue(playersAffected)


    def end(self):
        if self.supplyPile["Province"] == 0:
            return True
        threePileEnding = 0
        for remaining in self.supplyPile.itervalues():
            if remaining == 0:
                threePileEnding += 1
                if threePileEnding >= 3:
                    return True
        return False

    def getWinners(self):
        winners = []
        highScore = None
        lowestTurns = None
        for player in self.players:
            if player.score > highScore:
                winners[:] = []
                winners.append(player)
                highScore = player.score
                lowerTurns = player.turn
            elif player.score == highScore and player.turn < lowestTurns:
                winners[:] = []
                winners.append(player)
                highScore = player.score
                lowerTurns = player.turn
            elif player.score == highScore and player.turn == lowestTurns:
                winners.append(player)

        return winners
