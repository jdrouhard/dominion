from core import *
from twisted.internet import defer
from collections import defaultdict

class Adventurer(Action):
    cost = 6

    def doAction(self):
        revealedCards = []
        treasureCards = []
        discardedCards = []
        while len(treasureCards) < 2 and (self.owner.drawdeck or self.owner.discard):
            revealedCard = self.owner.draw(1, False)
            if revealedCard:
                revealedCard = revealedCard[0]
                if isinstance(revealedCard, Treasure):
                    treasureCards.append(revealedCard)
                else:
                    discardedCards.append(revealedCard)
                revealedCards.append(revealedCard)

        #TODO: discarding can trigger a reaction
        self.owner.discard.extend(discardedCards)
        self.owner.hand.extend(treasureCards)
        self.owner.addToLog("revealing %s." % (', '.join([repr(x) for x in revealedCards])))
        if discardedCards:
            self.owner.addToLog("discarding %s." % (', '.join([repr(x) for x in discardedCards])))
        self.owner.addToLog("putting %s into the hand." % (', '.join([repr(x) for x in treasureCards])))

class Bureaucrat(Attack):
    cost = 4

    @defer.inlineCallbacks
    def doAction(self):
        silver = self.owner.game.getCardFromSupply("Silver")
        if silver:
            self.owner.gainToDiscard(silver)
        self.owner.addToLog("gaining a Silver.")
        #for player in self.owner.game.players:
            #playerReactions = [x for x in player.hand if isinstance(x, Reaction)]
        playersAffected = yield self.owner.game.doAttack(self.owner)
        deferreds = []
        for player in playersAffected:
            player.userService.sendMessage("(Bureaucrat attack) Choose a Victory card to put back on your deck:")
            d = player.userService.chooseCardFromHand(Victory)
            deferreds.append(d)
        results = yield defer.gatherResults(deferreds)
        for i, player in enumerate(playersAffected):
            card = results[i]
            if card:
                player.drawdeck.insert(0, card)
                player.hand.remove(card)
                self.owner.addToLog("%s reveals a %s and puts it back on their deck." % (player, repr(card)))
            else:
                cardCount = defaultdict(int)
                for card in player.hand:
                    cardCount[repr(card)] += 1
                handStr = ', '.join(["%s: %d" % (name, count) for name, count in cardCount.iteritems()])
                self.owner.addToLog("%s reveals their hand: %s" % (player, handStr))


class Cellar(Action):
    cost = 2

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.actions += 1
        self.owner.addToLog("getting +1 action")
        numDiscard = -1
        while numDiscard < 0 or numDiscard > len(self.owner.hand):
            numDiscard = yield self.owner.userService.getChoice("How many cards would you like to discard? (min 0, max %s)" % len(self.owner.hand))
            numDiscard = int(numDiscard)
        cards = yield self.owner.userService.chooseCardsFromHand(Card, numDiscard)
        for card in cards:
            #TODO: discarding can trigger a reaction
            self.owner.hand.remove(card)
            self.owner.discard.append(card)

        drawnCards = self.owner.draw(numDiscard)

        self.owner.addToLog("discarding %d cards and drawing %d cards" % (numDiscard, len(drawnCards)))

class Chancellor(Action):
    cost = 3

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.coins += 2
        self.owner.addToLog("getting +$2.")
        choice = yield self.owner.userService.getYesNoChoice("Put deck in discard pile?")
        if choice:
            self.owner.discard += self.owner.drawdeck
            self.owner.drawdeck = []
            self.owner.addToLog("discarding the deck.")
        else:
            self.owner.addToLog("not discarding the deck.")

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
        self.owner.addToLog("trashing %d cards." % numTrash)

class CouncilRoom(Action):
    cost = 5

    def __repr__(self):
        return "Council Room"

    def doAction(self):
        drawnCards = self.owner.draw(4)
        self.owner.buys += 1
        self.owner.addToLog("getting +1 buy and drawing %d cards" % len(drawnCards))
        for player in self.owner.game.players:
            if player != self.owner:
                drawnCards = player.draw(1)
                if drawnCards:
                    self.owner.addToLog("%s draws 1 card" % player.name)
                else:
                    self.owner.addtoLog("%s draws no cards" % player.name)

class Feast(Action):
    cost = 4

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.userService.sendMessage("Choose a card to gain:")
        cardToGainName = yield self.owner.userService.chooseCardFromSupply(Card, 5)
        cardToGain = self.owner.game.getCardFromSupply(cardToGainName)
        self.owner.gainToDiscard(cardToGain)
        self.markedForTrash = True
        self.owner.addToLog("trashing the Feast and gaining a %s." % repr(cardToGain))

class Festival(Action):
    cost = 5

    def doAction(self):
        self.owner.actions += 2
        self.owner.buys += 1
        self.owner.coins += 2
        self.owner.addToLog("getting +2 actions, +1 buy, and +$2.")

class Gardens(Victory):
    cost = 4

    def getScore(self):
        return len(self.owner.deck) / 10

class Laboratory(Action):
    cost = 5

    def doAction(self):
        self.owner.actions += 1
        drawnCards = self.owner.draw(2)
        self.owner.addToLog("getting +1 action and drawing %d cards." % len(drawnCards))

class Library(Action):
    cost = 5

    @defer.inlineCallbacks
    def doAction(self):
        sidePile = []
        while len(self.owner.hand) < 7 and (self.owner.drawdeck or self.owner.discard):
            revealedCards = self.owner.draw(1, False)
            if revealedCards:
                revealedCard = revealedCards[0]
                if isinstance(revealedCard, Action):
                    setAside = yield self.owner.userService.getYesNoChoice("Set aside %s?" % revealedCard)
                    if setAside:
                        sidePile.append(revealedCard)
                        self.owner.addToLog("setting aside an action card.")
                        continue
                self.owner.addToLog("drawing 1 card.")
                self.owner.hand.append(revealedCard)

        if sidePile:
            self.owner.addToLog("discarding a %s." % (', '.join([repr(x) for x in sidePile])))
            self.owner.discard.extend(sidePile)

class Market(Action):
    cost = 5

    def doAction(self):
        drawnCards = self.owner.draw(1)
        self.owner.actions += 1
        self.owner.buys += 1
        self.owner.coins += 1
        self.owner.addToLog("drawing %d card and getting +1 action, +1 buy, +$1." % len(drawnCards))

class Militia(Attack):
    pass

class Mine(Action):
    cost = 5

    @defer.inlineCallbacks
    def doAction(self):
        #TODO: utilize the userservice object here for interaction
        self.owner.userService.sendMessage("Choose a treasure to upgrade:")
        cardToUpgrade = yield self.owner.userService.chooseCardFromHand(Treasure)
        if cardToUpgrade:
            #self.owner.userService.sendMessage("Upgrading " + repr(cardToUpgrade))
            availableCoins = cardToUpgrade.getCost() + 3
            self.owner.trashFromHand(cardToUpgrade)
            self.owner.addToLog("trashing a %s." % repr(cardToUpgrade))
            self.owner.userService.sendMessage("Choose a treasure to upgrade to:")
            cardToGainName = yield self.owner.userService.chooseCardFromSupply(Treasure, availableCoins)
            cardToGain = self.owner.game.getCardFromSupply(cardToGainName)
            self.owner.gainInHand(cardToGain)
            self.owner.addToLog("gaining a %s in hand." % repr(cardToGain))

class Moat(Action, AttackReaction):
    cost = 2

    def doAction(self):
        drawnCards = self.owner.draw(2)
        self.owner.addToLog("drawing %d cards." % len(drawnCards))

    @defer.inlineCallbacks
    def doReaction(self, player):
        """Return true if reaction makes this player immune to attack.
        player argument is the player initiating the attack"""
        choice = yield self.owner.userService.getYesNoChoice("Reveal moat?")
        if choice:
            player.addToLog("%s reveals a Moat and is immune to the attack." % self.owner.name)
        defer.returnValue(choice)

class Moneylender(Action):
    cost = 4

    def doAction(self):
        coppers = [x for x in self.owner.hand if isinstance(x, Copper)]
        if coppers:
            self.owner.trashFromHand(coppers[0])
            self.owner.coins += 3
            self.owner.addToLog("trashing a Copper and getting +$3.")

class Remodel(Action):
    cost = 4

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.userService.sendMessage("Choose a card to trash:")
        cardToRemodel = yield self.owner.userService.chooseCardFromHand(Card)
        if cardToRemodel:
            costOfCard = cardToRemodel.cost
            self.owner.trashFromHand(cardToRemodel)
            self.owner.addToLog("trashing a %s." % repr(cardToRemodel))
            self.owner.userService.sendMessage("Choose a card to gain:")
            cardToGainName = yield self.owner.userService.chooseCardFromSupply(Card, costOfCard+2)
            cardToGain = self.owner.game.getCardFromSupply(cardToGainName)
            self.owner.gainToDiscard(cardToGain)
            self.owner.addToLog("gaining a %s." % repr(cardToGain))

class Smithy(Action):
    cost = 4

    def doAction(self):
        drawnCards = self.owner.draw(3)
        self.owner.addToLog("drawing %d cards." % len(drawnCards))

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
            if card:
                self.owner.addToLog("and plays a %s." % repr(card))
                self.owner.pushLogLevel()
                yield card.doAction()
                self.owner.popLogLevel()
                self.owner.addToLog("and plays the %s again." % repr(card))
                self.owner.pushLogLevel()
                yield card.doAction()
                self.owner.popLogLevel()

                #TODO: do this through methods on the Player object
                # (Feast doesn't work yet)
                self.owner.hand.remove(card)
                self.owner.played.append(card)

class Village(Action):
    cost = 3

    def doAction(self):
        self.owner.actions += 2
        drawnCards = self.owner.draw(1)
        self.owner.addToLog("getting +2 actions and drawing %d card." % len(drawnCards))

class Witch(Attack):
    def doAction(self):
        # For each player, check attack rules and give curse if it's possible
        pass

class Woodcutter(Action):
    cost = 3

    def doAction(self):
        self.owner.buys += 1
        self.owner.coins += 2
        self.owner.addToLog("getting +1 buy and +$2.")

class Workshop(Action):
    cost = 3

    @defer.inlineCallbacks
    def doAction(self):
        self.owner.userService.sendMessage("Choose card to gain:")
        cardToGainName = yield self.owner.userService.chooseCardFromSupply(Card, 4)
        cardToGain = self.owner.game.getCardFromSupply(cardToGainName)
        self.owner.gainToDiscard(cardToGain)
        self.owner.addToLog("gaining a %s." % repr(cardToGain))
