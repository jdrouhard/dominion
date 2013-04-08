from core import *
from twisted.internet import defer

class Adventurer(Action):
    pass

class Bureaucrat(Attack):
    pass

class Cellar(Action):
    cost = 2

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.addActions(1)
        numDiscard = -1
        while numDiscard < 0 or numDiscard > len(self.owner.hand):
            numDiscard = yield self.owner.userService.getChoice("How many cards would you like to discard? (min 0, max %s)" % len(self.owner.hand))
            numDiscard = int(numDiscard)
        cards = yield self.owner.userService.chooseCardsFromHand(Card, numDiscard)
        for card in cards:
            self.owner.hand.remove(card)
            self.owner.discard.append(card)

        self.owner.draw(numDiscard)

class Chancellor(Action):
    cost = 3

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.coins += 2
        choice = yield self.owner.userService.getYesNoChoice("Put deck in discard pile?")
        if choice:
            self.owner.discard += self.owner.drawdeck
            self.owner.drawdeck = []

class Chapel(Action):
    cost = 2

    @defer.inlineCallbacks
    def doAction(self):
        numTrash = -1
        while numTrash < 0 or numTrash > 4:
            numTrash = yield self.owner.userService.getChoice("How many cards would you like to trash? (min 0, max 4)")
            numTrash = int(numTrash)
        cards = yield self.owner.userService.chooseCardsFromHand(Card, numTrash)
        for card in cards:
            self.owner.trashFromHand(card)

class CouncilRoom(Action):
    cost = 5

    def __repr__(self):
        return "Council Room"

    def doAction(self):
        self.owner.draw(4)
        self.owner.buys += 1
        for player in self.owner.game.players:
            player.draw(1)

class Feast(Action):
    cost = 4

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.userService.sendMessage("Choose a card to gain:")
        cardToGainName = yield self.owner.userService.chooseCardFromSupply(Card, 5)
        cardToGain = self.owner.game.getCardFromSupply(cardToGainName)
        self.owner.gainToDiscard(cardToGain)
        self.markedForTrash = True

class Festival(Action):
    cost = 5

    def doAction(self):
        self.owner.actions += 2
        self.owner.buys += 1
        self.owner.coins += 2

class Gardens(Victory):
    cost = 4

    def getScore(self):
        return len(self.owner.deck) / 10

class Laboratory(Action):
    cost = 5

    def doAction(self):
        self.owner.actions += 1
        self.owner.draw(2)

class Library(Action):
    cost = 5

    @defer.inlineCallbacks
    def doAction(self):
        sidePile = []
        while len(self.owner.hand) < 7 and (self.owner.drawdeck or self.owner.discard):
            revealedCards = self.owner.draw(1, False)
            if revealedCards:
                revealedCard = revealedCard[0]
                if isinstance(revealedCard, Action):
                    setAside = yield self.owner.userService.getYesNoChoice("Set aside %s?" % revealedCard)
                    if setAside:
                        sidePile.append(revealedCard)
                        continue
                self.owner.hand.append(revealedCard)

        if sidePile:
            self.owner.discard.extend(sidePile)

class Market(Action):
    cost = 5

    def doAction(self):
        self.owner.draw(1)
        self.owner.actions += 1
        self.owner.buys += 1
        self.owner.coins += 1

class Militia(Attack):
    pass

class Mine(Action):
    cost = 5

    @defer.inlineCallbacks
    def doAction(self):
        #TODO: utilize the userservice object here for interaction
        self.owner.userService.sendMessage("Choose a treasure to upgrade:")
        cardToUpgrade = yield self.owner.userService.chooseCardFromHand(Treasure)
        self.owner.userService.sendMessage("Upgrading " + repr(cardToUpgrade))
        availableCoins = cardToUpgrade.getCost() + 3
        self.owner.trashFromHand(cardToUpgrade)
        self.owner.userService.sendMessage("Choose a treasure to upgrade to:")
        cardToGainName = yield self.owner.userService.chooseCardFromSupply(Treasure, availableCoins)
        cardToGain = self.owner.game.getCardFromSupply(cardToGainName)
        self.owner.gainInHand(cardToGain)

class Moat(Action, Reaction):
    cost = 2

    def doAction(self):
        self.owner.draw(2)

    @defer.inlineCallbacks
    def doReaction(self):
        """Return true if reaction makes player immune to attack"""
        choice = yield self.owner.userService.getYesNoChoice("Reveal moat?")
        defer.returnValue(choice)

class Moneylender(Action):
    cost = 4

    def doAction(self):
        coppers = [x for x in self.owner.hand if isinstance(x, Copper)]
        if coppers:
            self.owner.trashFromHand(coppers[0])
            self.owner.coins += 3

class Remodel(Action):
    cost = 4

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.userService.sendMessage("Choose a card to trash:")
        cardToRemodel = yield self.owner.userService.chooseCardFromHand(Card)
        costOfCard = cardToRemodel.cost
        self.owner.trashFromHand(cardToRemodel)
        self.owner.userService.sendMessage("Choose a card to gain:")
        cardToGainName = yield self.owner.userService.chooseCardFromSupply(Card, costOfCard+2)
        cardToGain = self.owner.game.getCardFromSupply(cardToGainName)
        self.owner.gainToDiscard(cardToGain)

class Smithy(Action):
    cost = 4

    def doAction(self):
        self.owner.draw(3)

class Spy(Attack):
    pass

class Thief(Attack):
    pass

class ThroneRoom(Action):
    cost = 4

    def __repr__(self):
        return "Throne Room"

    @defer.inlineCallbacks
    def doAction(self):
        if (len([x for x in self.owner.hand if isinstance(x, Action)]) > 0):
            self.owner.userService.sendMessage("Choose an action card to play twice:")
            card = yield self.owner.userService.chooseCardFromHand(Action)
            yield self.owner.play(card)
            yield self.owner.play(card)

class Village(Action):
    cost = 3

    def doAction(self):
        self.owner.actions += 2
        self.owner.draw(1)

class Witch(Attack):
    def doAction(self):
        # For each player, check attack rules and give curse if it's possible
        pass

class Woodcutter(Action):
    cost = 3

    def doAction(self):
        self.owner.buys += 1
        self.owner.coins += 2

class Workshop(Action):
    cost = 3

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.userService.sendMessage("Choose card to gain:")
        cardToGainName = yield self.owner.chooseCardFromSupply(Card, 4)
        cardToGain = self.owner.game.getCardFromSupply(cardToGainName)
        self.owner.gainToDiscard(cardToGain)
