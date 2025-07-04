import random
import uuid # Voor het genereren van tijdelijke IDs indien nodig, al gebruiken we socket SIDs in app.py

# --- Basis Kaartdefinities ---
# Dit is de volledige set kaarten die in het spel gebruikt wordt.
BASE_CARD_TYPES = ['Koning', 'Koningin', 'Boer']
JOKER = 'Joker'

# Het volledige deck zal dynamisch gecreëerd worden om 5 kaarten per speler te garanderen.
# De verhouding van kaarten blijft: 6x Koning, 6x Koningin, 6x Boer, 2x Joker
FULL_DECK_TEMPLATE = {
    'Koning': 6,
    'Koningin': 6,
    'Boer': 6,
    'Joker': 2
}

# De gezichten van de mystieke dobbelsteen zijn nu nummers 1 t/m 6
MYSTIC_DICE_FACES = ['1', '2', '3', '4', '5', '6']


# --- Helper Functies voor Spel Logica ---

def _get_player_by_id(game_state, player_id):
    """Interne helper om een speler object op te halen via ID."""
    # Controleer of game_state bestaat en een 'players' sleutel heeft
    if not game_state or 'players' not in game_state:
        return None
    return next((p for p in game_state['players'] if p['id'] == player_id), None)

def _get_active_players(game_state):
    """Retourneert een lijst van spelers die nog in het spel zijn (alive: True)."""
    return [p for p in game_state['players'] if p['alive']]

def _get_all_players_in_lobby(game_state):
    """Retourneert een lijst van alle spelers in de lobby, ongeacht hun 'alive' status."""
    return game_state['players']


def _get_next_active_player_id(game_state, current_player_id):
    """
    Bepaalt de ID van de volgende actieve speler in de beurtvolgorde.
    Slaat spelers over die niet meer 'alive' zijn.
    """
    # Filter de turnOrder om alleen ID's van actieve spelers te bevatten
    active_turn_order_ids = [p_id for p_id in game_state['turnOrder'] if _get_player_by_id(game_state, p_id) and _get_player_by_id(game_state, p_id)['alive']]

    if not active_turn_order_ids:
        return None # Geen actieve spelers in de beurtvolgorde

    try:
        current_index = active_turn_order_ids.index(current_player_id)
        next_index = (current_index + 1) % len(active_turn_order_ids)
        return active_turn_order_ids[next_index]
    except ValueError:
        # Huidige speler niet gevonden in actieve beurtvolgorde (mogelijk net uitgeschakeld)
        # Zoek de eerste actieve speler in de volgorde
        return active_turn_order_ids[0] if active_turn_order_ids else None


def _create_and_deal_deck(players_to_deal):
    """
    Maakt een deck op basis van het aantal spelers en deelt 5 kaarten per speler uit.
    Args:
        players_to_deal (list): Lijst van speler objecten waaraan kaarten gedeeld moeten worden.
    Returns:
        list: Het geschudde deck dat gebruikt is.
    """
    num_players = len(players_to_deal)
    if num_players == 0:
        return []

    cards_needed = num_players * 5
    
    # Maak een deck dat minimaal genoeg kaarten heeft voor iedereen.
    # We houden de verhouding van de FULL_DECK_TEMPLATE aan.
    deck_builder = []
    
    # Bereken hoeveel sets van de template nodig zijn.
    # Een template set heeft 6+6+6+2 = 20 kaarten.
    # Voeg ten minste één volledige template set toe om te garanderen dat alle kaarttypen aanwezig zijn.
    total_cards_in_template_set = sum(FULL_DECK_TEMPLATE.values())
    
    sets_needed = (cards_needed + total_cards_in_template_set - 1) // total_cards_in_template_set
    if sets_needed == 0: # Zorg dat er minimaal 1 set is, zelfs als 0 kaarten nodig (geen spelers)
        sets_needed = 1 

    for card_type, count in FULL_DECK_TEMPLATE.items():
        deck_builder.extend([card_type] * (count * sets_needed))
            
    random.shuffle(deck_builder)

    # Deel precies 5 kaarten per speler uit
    current_deck_index = 0
    for player in players_to_deal:
        player['hand'] = [] # Zorg dat hand leeg is voor nieuwe deling
        for _ in range(5):
            if current_deck_index < len(deck_builder):
                player['hand'].append(deck_builder[current_deck_index])
                current_deck_index += 1
            else:
                # Dit zou niet moeten gebeuren als sets_needed correct is berekend
                print("Waarschuwing: Onvoldoende kaarten in het gedeelde deck voor 5 kaarten per speler.")
                break
        player['hand'].sort() # Sorteer de hand van de speler voor gemak
    
    # Retourneer het deel van het deck dat daadwerkelijk is gebruikt, of het hele deck
    return deck_builder[:current_deck_index]


def _reset_revealed_cards_info(game_state):
    """Helper functie om revealedCardsInfo te resetten."""
    game_state['revealedCardsInfo'] = {
        "isRevealed": False,
        "claimerId": None,
        "claimerName": None,
        "actualCards": [],
        "claimWasTrue": None,
        "playerToRollDice": None,
        "outcomeMessage": None,
        "diceRollOutcome": None # Nieuw veld voor dobbelsteen resultaat
    }


# --- Kern Spel Logica Functies ---

def create_new_game(lobby_code, player_data_list):
    """
    Initialiseert een compleet nieuwe GameState voor een lobby.
    Args:
        lobby_code (str): De unieke code van de lobby.
        player_data_list (list): Een lijst van tuples (player_id, player_name) voor elke speler.
    Returns:
        dict: De volledig geïnitialiseerde GameState.
    """
    players = []
    for player_id, player_name in player_data_list:
        players.append({
            "id": player_id,
            "name": player_name,
            "hand": [], # Hand wordt later gevuld door _create_and_deal_deck
            "alive": True,
            "mysticDice": {
                "totalSides": 6,
                "remainingSafeSides": 6, 
                "rolledNumbers": [] # NIEUW: Houdt bij welke nummers al gerold zijn door deze speler
            },
            "diceRollAttempts": 0 
        })

    # Bepaal de willekeurige beurtvolgorde van de initieel verbonden spelers
    turn_order = [p["id"] for p in players]
    random.shuffle(turn_order)

    # Kies de startspeler willekeurig voor de eerste ronde
    start_player_id = random.choice(turn_order)
    start_player_name = _get_player_by_id({"players": players}, start_player_id)['name'] # Gebruik temp dict voor naam

    # Initialiseer de game state
    initial_game_state = {
        "lobbyCode": lobby_code,
        "deckType": [random.choice(BASE_CARD_TYPES)], # De kaarten in het midden (nu slechts 1)
        "players": players,
        "turnOrder": turn_order, # Bevat alleen alive spelers ID's in de juiste volgorde
        "currentTurn": start_player_id,
        "pile": [],
        "actualPileCards": [],
        "lastClaimDetails": {
            "player": None, "playerName": None, "claimedCardType": None,
            "claimedAmount": None, "actualCardsPlayed": []
        },
        "revealedCardsInfo": {
            "isRevealed": False, "claimerId": None, "claimerName": None,
            "actualCards": [], "claimWasTrue": None, "playerToRollDice": None,
            "outcomeMessage": None,
            "diceRollOutcome": None # Nieuw veld
        },
        "phase": "awaitingPlay",
        "log": [f"Spel gestart in lobby {lobby_code}!", f"{start_player_name} is aan de beurt."]
    }
    
    # Deel kaarten uit voor de eerste ronde
    _create_and_deal_deck(initial_game_state['players'])

    return initial_game_state

def is_valid_claim(game_state, player_id, cards_played):
    """
    Valideert of een claim geldig is.
    - Kaarttype moet in deckType zitten (nu met slechts 1 toegestaan type).
    - Aantal kaarten minimaal 1.
    - De geclaimde kaarten moeten in de hand van de speler zijn.
    - Joker kan voor alles staan.
    """
    player = _get_player_by_id(game_state, player_id)
    if not player or not player['alive']:
        return False, "Speler is niet actief of bestaat niet."

    if not (1 <= len(cards_played) <= 5):
        return False, "Je moet tussen 1 en 5 kaarten leggen."

    # Het geclaimde type is nu ALTIJD de middenkaart, dus we halen die hier op.
    allowed_claimed_type = game_state['deckType'][0] 

    # Controleer of de speler de opgegeven kaarten daadwerkelijk in zijn hand heeft
    player_hand_copy = list(player['hand'])
    for card in cards_played:
        if card in player_hand_copy:
            player_hand_copy.remove(card)
        else:
            return False, f"De kaart '{card}' is niet in je hand."

    return True, "Claim is geldig."


def make_play(game_state, player_id, cards_played):
    """
    Verwerkt een speler die kaarten neerlegt en een claim doet.
    Het geclaimde kaarttype wordt automatisch bepaald door de middenkaart (deckType).
    Args:
        game_state (dict): De huidige GameState.
        player_id (str): De ID van de speler die de zet doet.
        cards_played (list): De werkelijke kaarten die de speler neerlegt.
    Returns:
        tuple: (bool success, str message)
    """
    player = _get_player_by_id(game_state, player_id)

    # Reset de revealedCardsInfo wanneer een nieuwe zet wordt gedaan
    _reset_revealed_cards_info(game_state)

    # Validatie die al deels in app.py zit, maar hier voor robuustheid herhalen
    if game_state['currentTurn'] != player_id:
        return False, "Niet jouw beurt."
    if game_state['phase'] != 'awaitingPlay':
        return False, "Kan nu geen kaarten leggen."
    if not player or not player['alive']:
        return False, "Speler is niet actief of bestaat niet."

    # Het geclaimde kaarttype is nu ALTIJD de middenkaart
    claimed_card_type = game_state['deckType'][0]

    # Uitgebreide validatie van de claim
    valid, message = is_valid_claim(game_state, player_id, cards_played)
    if not valid:
        return False, message

    # Update de hand van de speler
    for card in cards_played:
        player['hand'].remove(card)

    # Voeg de claim toe aan de stapel (publiek zichtbaar)
    game_state['pile'].append({
        "player": player_id,
        "claimedCardType": claimed_card_type, # Gebruik de automatisch bepaalde claim
        "claimedAmount": len(cards_played)
    })
    
    # Voeg de werkelijke kaarten toe aan de interne stapel
    game_state['actualPileCards'].extend(cards_played)

    # Update de details van de laatste claim
    game_state['lastClaimDetails'] = {
        "player": player_id,
        "playerName": player['name'], # Naam van de speler die de claim deed
        "claimedCardType": claimed_card_type, # Gebruik de automatisch bepaalde claim
        "claimedAmount": len(cards_played),
        "actualCardsPlayed": cards_played # Deze info is nodig voor de Liar! check
    }

    # Ga naar de volgende actieve speler
    game_state['currentTurn'] = _get_next_active_player_id(game_state, player_id)
    game_state['phase'] = 'awaitingLiarCall' # Na een zet kan er 'LIAR!' geroepen worden of geloofd worden

    # NIEUWE LOGICA: Controleer hier direct of een verplichte LIAR! call nodig is
    win_check_result = check_win_condition(game_state)
    if win_check_result['forced_liar_call']:
        forced_calling_player_id = win_check_result['calling_player_id']
        forced_calling_player_name = _get_player_by_id(game_state, forced_calling_player_id)['name']
        game_state['log'].append(f"Regel geactiveerd: {forced_calling_player_name} wordt gedwongen 'LIAR!' te roepen.")
        # Roep call_liar aan met de speler die gedwongen wordt te liegen
        success, msg = call_liar(game_state, forced_calling_player_id)
        if not success:
            game_state['log'].append(f"Fout bij automatische LIAR! call: {msg}")
        return True, "Zet succesvol uitgevoerd en verplichte LIAR! call verwerkt."
    
    # Als geen verplichte LIAR! call, dan de normale flow:
    # Controleer of de toegewezen speler kan reageren (heeft kaarten).
    # Zo niet, schuif de beurt automatisch door.
    current_responder_id = game_state['currentTurn']
    first_candidate_id = current_responder_id
    looper_count = 0 
    max_loops = len(game_state['players']) * 2 # Veiligheidslimiet

    while True:
        responder_player = _get_player_by_id(game_state, current_responder_id)

        if not responder_player or not responder_player['alive']:
            # Dit zou normaal gesproken betekenen dat er geen actieve spelers meer zijn
            # en het spel ten einde zou moeten zijn.
            game_state['log'].append("Geen actieve spelers gevonden om te reageren op de claim.")
            game_state['phase'] = 'gameOver' 
            break

        # Controleer of de speler 'alive' is EN kaarten in de hand heeft
        if responder_player['alive'] and len(responder_player['hand']) > 0:
            game_state['currentTurn'] = current_responder_id # Deze speler is de juiste responder
            game_state['log'].append(f"{responder_player['name']} is aan de beurt om te reageren op de claim.")
            break # Geschikte responder gevonden, stop de loop
        else:
            # Deze speler is levend maar heeft geen kaarten, dus kan niet reageren.
            game_state['log'].append(f"{responder_player['name']} heeft geen kaarten en kan niet reageren op de claim. Beurt gaat door.")
            
            # Ga naar de volgende actieve speler in de beurtvolgorde
            next_potential_responder_id = _get_next_active_player_id(game_state, current_responder_id)

            if next_potential_responder_id is None or next_potential_responder_id == first_candidate_id:
                # We zijn rond geweest of er is niemand meer gevonden die kan reageren
                game_state['log'].append("Geen speler gevonden met kaarten om te reageren. Spel is mogelijk geblokkeerd of afgelopen.")
                game_state['phase'] = 'gameOver' # Forceer game over of een 'vastgelopen' fase
                break
            
            current_responder_id = next_potential_responder_id # Test de volgende kandidaat
            looper_count += 1
            if looper_count > max_loops:
                   game_state['log'].append("ERROR: Loop voor het vinden van de volgende reageerder lijkt vast te zitten.")
                   game_state['phase'] = 'gameOver'
                   break

    game_state['log'].append(f"{player['name']} claimt {len(cards_played)} {claimed_card_type}(s) te hebben gelegd.")

    return True, "Zet succesvol uitgevoerd."


def believe_claim(game_state, believing_player_id):
    """
    Verwerkt een speler die besluit de claim van de vorige speler te geloven.
    De beurt gaat naar de gelovende speler en de stapel wordt NIET gereset.
    Args:
        game_state (dict): De huidige GameState.
        believing_player_id (str): De ID van de speler die de claim gelooft.
    Returns:
        tuple: (bool success, str message)
    """
    believing_player = _get_player_by_id(game_state, believing_player_id)

    if not believing_player or not believing_player['alive']:
        return False, "Speler die de claim wil geloven is niet actief of bestaat niet."

    if game_state['currentTurn'] != believing_player_id:
        return False, "Niet jouw beurt om een claim te geloven."
    
    if game_state['phase'] != 'awaitingLiarCall':
        return False, "Er is momenteel geen claim om te geloven."
    
    last_claim = game_state['lastClaimDetails']
    if not last_claim or not last_claim['player']:
        return False, "Er is geen claim om te geloven."
    
    claiming_player_id = last_claim['player']
    claiming_player_name = last_claim['playerName'] # Haal de naam op uit lastClaimDetails
    believing_player_name = believing_player['name']

    # Controleer de werkelijke waarheid van de claim (voor logging, maar niet voor UI weergave)
    is_claim_true = True
    actual_cards_played_in_claim = last_claim['actualCardsPlayed']
    claimed_type = last_claim['claimedCardType']
    claimed_amount = last_claim['claimedAmount']

    matched_cards_count = 0
    for card in actual_cards_played_in_claim:
        if card == claimed_type or card == JOKER:
            matched_cards_count += 1
    
    if matched_cards_count != claimed_amount:
        is_claim_true = False # De claim was onwaar

    # Stel revealedCardsInfo in, maar zorg dat 'isRevealed' FALSE blijft.
    # Dit zorgt ervoor dat de kaarten niet getoond worden op de UI.
    game_state['revealedCardsInfo'] = {
        "isRevealed": False, # BELANGRIJKE WIJZIGING: kaarten niet tonen!
        "claimerId": None,
        "claimerName": None,
        "actualCards": [], # Geen kaarten om te tonen
        "claimWasTrue": None, # Niet visueel bepaald in deze fase, maar wel logisch bepaald.
        "playerToRollDice": None,
        "outcomeMessage": f"{believing_player_name} gelooft de claim van {claiming_player_name}."
    }

    # Voeg gedetailleerde logberichten toe over het resultaat (zonder de 'waarheid' te vermelden in de log)
    game_state['log'].append(f"{believing_player_name} gelooft de claim van {claiming_player_name}.")

    # De beurt blijft bij de `believing_player_id`
    game_state['currentTurn'] = believing_player_id # BELANGRIJKE WIJZIGING: beurt blijft bij de gelovende speler
    game_state['phase'] = 'awaitingPlay' # De speler kan nu zijn eigen kaarten leggen

    # NIEUWE LOGICA: Controleer of de toegewezen speler kan spelen (heeft kaarten).
    # Zo niet, schuif de beurt automatisch door.
    current_player_for_play_id = game_state['currentTurn']
    first_play_candidate_id = current_player_for_play_id
    play_looper_count = 0
    max_loops = len(game_state['players']) * 2 # Veiligheidslimiet

    while True:
        player_for_play = _get_player_by_id(game_state, current_player_for_play_id)

        if not player_for_play or not player_for_play['alive']:
            game_state['log'].append("Geen actieve spelers gevonden om de volgende zet te doen.")
            game_state['phase'] = 'gameOver'
            break
        
        if player_for_play['alive'] and len(player_for_play['hand']) > 0:
            game_state['currentTurn'] = current_player_for_play_id
            game_state['log'].append(f"{player_for_play['name']} is aan de beurt om kaarten te leggen.")
            break
        else:
            game_state['log'].append(f"{player_for_play['name']} heeft geen kaarten en kan niet spelen. Beurt gaat door.")
            next_potential_player_for_play_id = _get_next_active_player_id(game_state, current_player_for_play_id)

            if next_potential_player_for_play_id is None or next_potential_player_for_play_id == first_play_candidate_id:
                game_state['log'].append("Geen speler gevonden met kaarten om te spelen. Spel is mogelijk geblokkeerd of afgelopen.")
                game_state['phase'] = 'gameOver'
                break
            
            current_player_for_play_id = next_potential_player_for_play_id
            play_looper_count += 1
            if play_looper_count > max_loops:
                game_state['log'].append("ERROR: Speelbeurt loop lijkt vast te zitten.")
                game_state['phase'] = 'gameOver'
                break

    return True, "Claim succesvol geloofd. Je bent aan de beurt."


def call_liar(game_state, calling_player_id):
    """
    Verwerkt een speler die 'LIAR!' roept.
    Bepaalt wie moet dobbelen en triggert de dobbelsteenworp-fase.
    Args:
        game_state (dict): De huidige GameState.
        calling_player_id (str): De ID van de speler die 'LIAR!' roept.
    Returns:
        tuple: (bool success, str message)
    """
    calling_player = _get_player_by_id(game_state, calling_player_id)

    if not calling_player or not calling_player['alive']:
        return False, "Speler die 'LIAR!' roept is niet actief of bestaat niet."

    # De speler die aan de beurt is om te spelen, kan LIAR! geroepen worden door een ander.
    # Maar de speler die de claim deed, kan niet zichzelf van liegen beschuldigen.
    if game_state['lastClaimDetails'] and game_state['lastClaimDetails']['player'] == calling_player_id:
        return False, "Je kunt jezelf niet van liegen beschuldigen."
    
    if game_state['phase'] != 'awaitingLiarCall':
        return False, "Kan nu geen LIAR! roepen."

    last_claim = game_state['lastClaimDetails']
    if not last_claim or not last_claim['player']:
        return False, "Niemand heeft nog een claim gemaakt om 'LIAR!' te roepen."

    claiming_player_id = last_claim['player']
    claiming_player_name = last_claim['playerName']
    calling_player_name = calling_player['name']
    
    # Controleer of de claim waar was
    is_claim_true = True
    actual_cards_played_in_claim = last_claim['actualCardsPlayed']
    claimed_type = last_claim['claimedCardType']
    claimed_amount = last_claim['claimedAmount']

    matched_cards_count = 0
    for card in actual_cards_played_in_claim:
        if card == claimed_type or card == JOKER: # Gebruik JOKER constante
            matched_cards_count += 1
    
    if matched_cards_count != claimed_amount:
        is_claim_true = False # De claim was onwaar

    player_who_must_roll_sid = None
    outcome_message = ""
    if not is_claim_true:
        # De speler loog, hij moet dobbelen
        player_who_must_roll_sid = claiming_player_id
        outcome_message = f"De claim van {claiming_player_name} was een leugen! {claiming_player_name} moet de dobbelsteen werpen."
        game_state['log'].append(f"{calling_player_name} roept LIAR! De claim van {claiming_player_name} was onwaar.")
    else:
        # De speler loog niet, de roeper moet dobbelen
        player_who_must_roll_sid = calling_player_id
        outcome_message = f"De claim van {claiming_player_name} was waar! {calling_player_name} moet de dobbelsteen werpen."
        game_state['log'].append(f"{calling_player_name} roept LIAR! De claim van {claiming_player_name} was waar.")

    # Vul de revealedCardsInfo
    game_state['revealedCardsInfo'] = {
        "isRevealed": True,
        "claimerId": claiming_player_id, # Speler die de claim deed
        "claimerName": claiming_player_name,
        "actualCards": actual_cards_played_in_claim, # De werkelijke kaarten die waren gelegd
        "claimWasTrue": is_claim_true,
        "playerToRollDice": player_who_must_roll_sid, # ID van de speler die nu moet dobbelen
        "outcomeMessage": outcome_message,
        "diceRollOutcome": None # Dit wordt pas na de worp gevuld
    }

    # Reset de stapel na een LIAR call. De kaarten verdwijnen uit het spel.
    game_state['pile'] = []
    game_state['actualPileCards'] = []
    game_state['lastClaimDetails'] = {
        "player": None,
        "playerName": None, # Reset ook de naam
        "claimedCardType": None,
        "claimedAmount": None,
        "actualCardsPlayed": []
    }

    game_state['currentTurn'] = player_who_must_roll_sid # Degene die moet dobbelen, is nu aan de beurt
    game_state['phase'] = 'resolvingDiceRoll' # Ga naar de fase van dobbelsteenworp

    return True, "LIAR! call verwerkt."


def roll_mystic_dice(game_state, player_id):
    """
    Verwerkt het werpen van de mystieke dobbelsteen.
    Args:
        game_state (dict): De huidige GameState.
        player_id (str): De ID van de speler die werpt.
    Returns:
        tuple: (bool success, str message)
    """
    player_to_roll = _get_player_by_id(game_state, player_id)

    if not player_to_roll or not player_to_roll['alive']:
        return False, "Speler is niet actief of bestaat niet."

    if game_state['currentTurn'] != player_id:
        return False, "Niet jouw beurt om te dobbelen."

    if game_state['phase'] != 'resolvingDiceRoll':
        return False, "Kan nu geen dobbelsteen werpen."

    player_to_roll['diceRollAttempts'] += 1
    attempts = player_to_roll['diceRollAttempts']

    # Bepaal de mogelijke dobbelsteengezichten op basis van het aantal pogingen
    # en filter EERST de al gerolde nummers uit.
    available_dice_pool = [str(i) for i in range(1, 7)] # Alle 6 gezichten als strings
    
    # Filter nummers die de speler al heeft gerold in deze game
    available_dice_pool = [
        face for face in available_dice_pool 
        if face not in player_to_roll['mysticDice']['rolledNumbers']
    ]

    # Filter nummers lager dan 'attempts' (voor de progressieve moeilijkheid)
    # Zorg dat 'attempts' niet groter is dan 6, anders blijft er niets over
    current_attempt_filter = min(attempts, 6) # max 6, zelfs als attempts hoger is
    
    # We filteren nu op de face waarde als getal, niet de string vergelijking
    current_dice_pool = [
        face for face in available_dice_pool 
        if int(face) >= current_attempt_filter
    ]
    
    if not current_dice_pool:
        # Dit betekent dat alle mogelijke nummers al gerold zijn, of gefilterd
        # door attempts. In dit scenario moet de speler automatisch een '6' verliezen.
        game_state['log'].append(f"{player_to_roll['name']} heeft alle dobbelsteengezichten al gerold, of de moeilijkheid is te hoog. Automatisch een 6.")
        dice_face_rolled = '6'
        roll_result_is_loss = True
    else:
        dice_face_rolled = random.choice(current_dice_pool) # Kies een getal uit de gereduceerde pool
        roll_result_is_loss = (dice_face_rolled == '6') # Verlies als een 6 wordt gerold
    
    # Voeg het gerolde nummer toe aan de lijst van gerolde nummers voor deze speler
    player_to_roll['mysticDice']['rolledNumbers'].append(dice_face_rolled)
    # Sorteer de lijst om consistentie te bewaren (optioneel, maar netjes)
    player_to_roll['mysticDice']['rolledNumbers'].sort()


    player_name = player_to_roll['name']

    # Vul de diceRollOutcome in revealedCardsInfo
    game_state['revealedCardsInfo']['diceRollOutcome'] = {
        "face": dice_face_rolled,
        "isLoss": roll_result_is_loss
    }
    
    if roll_result_is_loss:
        # Speler verliest opnieuw een leven (eindigt het spel voor deze speler)
        game_state['log'].append(f"{player_name} wierp de mystieke dobbelsteen en rolde een {dice_face_rolled}! Hij is uit het spel!")
        player_to_roll['alive'] = False
        
        # Verwijder de speler uit de turnOrder als deze definitief uitgeschakeld is
        game_state['turnOrder'] = [p_id for p_id in game_state['turnOrder'] if p_id != player_id]
        
        # Controleer de winconditie direct na uitschakeling
        win_check_result = check_win_condition(game_state)
        if win_check_result['game_over']:
            game_state['phase'] = 'gameOver'
            # app.py zal de 'game_over' event broadcasten
        else:
            # Als het spel niet voorbij is, geef de beurt door aan de volgende actieve speler
            next_turn_player_id = _get_next_active_player_id(game_state, player_id)
            game_state['currentTurn'] = next_turn_player_id
            game_state['phase'] = 'awaitingPlay'
            # Start een nieuwe ronde: deel kaarten opnieuw uit, kies nieuw deckType
            # Belangrijk: rolledDiceNumbers NIET resetten hier
            _start_new_round(game_state, game_state['currentTurn'])

    else:
        # Speler overleeft de dobbelsteenworp, mag doorgaan met spelen
        game_state['log'].append(f"{player_name} wierp de mystieke dobbelsteen en rolde een {dice_face_rolled}! Hij blijft in het spel!")
        # BELANGRIJK: Na een succesvolle worp, is het nog steeds de beurt van deze speler
        # om een zet te doen (kaarten te leggen)
        game_state['phase'] = 'awaitingPlay'
        game_state['currentTurn'] = player_id # Beurt blijft bij dezelfde speler (die net gedobbeld heeft)
        # Start een nieuwe ronde: deel kaarten opnieuw uit, kies nieuw deckType
        # Belangrijk: rolledDiceNumbers NIET resetten hier
        _start_new_round(game_state, player_id) # De speler die de beurt krijgt is degene die de dobbelsteen succesvol wierp

    # Reset de onthulde kaarten info na de dobbelsteenworp (of herverdeling)
    # Behalve de dobbelsteen informatie zelf, die willen we nog even tonen
    game_state['revealedCardsInfo']['isRevealed'] = True # Zorg dat de sectie zichtbaar blijft voor dobbelsteen info
    game_state['revealedCardsInfo']['outcomeMessage'] = f"Dobbelsteen resultaat voor {player_name}:"


    return True, "Dobbelsteen geworpen."

def _start_new_round(game_state, starting_player_id):
    """
    Start een nieuwe ronde: deelt kaarten opnieuw uit, kiest een nieuw deckType,
    en reset de stapel en dobbelsteenpogingen.
    Belangrijk: De lijst van gerolde dobbelsteennummers per speler wordt NIET gereset in een nieuwe ronde.
    Args:
        game_state (dict): De huidige GameState.
        starting_player_id (str): De ID van de speler die de eerste beurt van de nieuwe ronde krijgt.
    """
    game_state['log'].append("Een nieuwe ronde begint!")

    # Maak alle spelers die in de lobby zitten weer 'alive'
    for player in game_state['players']:
        player['alive'] = True # Zet alle spelers weer levend
        player['diceRollAttempts'] = 0 # Reset dobbelsteenpogingen voor iedereen
        # BELANGRIJK: player['mysticDice']['rolledNumbers'] wordt HIER NIET gereset
        # Deze wordt alleen gereset wanneer een HELE NIEUWE GAME begint (create_new_game)
        
    # Deel kaarten opnieuw uit aan ALLE spelers die nu 'alive' zijn (dus iedereen in de lobby)
    all_players_in_lobby = _get_all_players_in_lobby(game_state)
    _create_and_deal_deck(all_players_in_lobby) # Gebruik de nieuwe deal functie

    # Regenereer de turnOrder om alle spelers weer op te nemen
    game_state['turnOrder'] = [p["id"] for p in game_state['players']]
    random.shuffle(game_state['turnOrder']) # Schud de beurtvolgorde opnieuw

    # Kies een nieuw deckType
    game_state['deckType'] = [random.choice(BASE_CARD_TYPES)] # Gebruik BASE_CARD_TYPES
    game_state['log'].append(f"De nieuwe middenkaart is {game_state['deckType'][0]}.")

    # Reset de stapel en laatste claim details
    game_state['pile'] = []
    game_state['actualPileCards'] = []
    game_state['lastClaimDetails'] = {
        "player": None, "playerName": None, "claimedCardType": None,
        "claimedAmount": None, "actualCardsPlayed": []
    }

    # Zorg dat de beurt bij de juiste speler ligt.
    # Als de oorspronkelijke starting_player_id nog bestaat, gebruik die.
    # Anders, pak de eerste speler uit de nieuw geschudde turnOrder.
    if starting_player_id in game_state['turnOrder']:
        game_state['currentTurn'] = starting_player_id
    else:
        game_state['currentTurn'] = game_state['turnOrder'][0] if game_state['turnOrder'] else None

    game_state['phase'] = 'awaitingPlay' # Begin nieuwe ronde in speelfase
    current_turn_player_name = _get_player_by_id(game_state, game_state['currentTurn'])['name'] if game_state['currentTurn'] else "Onbekende speler"
    game_state['log'].append(f"{current_turn_player_name} is aan de beurt.")


def check_win_condition(game_state):
    """
    Controleert of aan de winconditie is voldaan (slechts één speler over).
    Retourneert een dict { 'game_over': bool, 'winner': id_of_winner_or_None, 'winner_name': name_or_None, 'forced_liar_call': bool, 'calling_player_id': id_or_None }
    """
    alive_players = _get_active_players(game_state) # Players who are alive (not out by dice roll)
    
    # NIEUW: Identificeer spelers die nog levend zijn EN nog kaarten hebben
    players_with_cards = [p for p in alive_players if len(p['hand']) > 0]

    if len(alive_players) == 1:
        winner = alive_players[0]
        game_state['log'].append(f"{winner['name']} heeft het spel gewonnen!")
        return {'game_over': True, 'winner': winner['id'], 'winner_name': winner['name'], 'forced_liar_call': False, 'calling_player_id': None}
    elif len(alive_players) == 0:
        return {
            'game_over': True,
            'winner': None,
            'winner_name': None,
            'forced_liar_call': False
        }
    
    # NIEUW: Speciale regel: Verplichte 'LIAR!'-roep wanneer er nog maar 2 spelers kaarten hebben,
    # en de ene speler zojuist al zijn kaarten heeft gespeeld.
    # Deze regel wordt alleen geactiveerd als we in de 'awaitingLiarCall' fase zijn.
    if game_state['phase'] == 'awaitingLiarCall' and game_state['lastClaimDetails']:
        last_claimer_id = game_state['lastClaimDetails']['player']
        claimer_player = _get_player_by_id(game_state, last_claimer_id)

        # De speler die aan de beurt is om te reageren op de claim.
        current_responder = _get_player_by_id(game_state, game_state['currentTurn'])

        # De voorwaarden voor de verplichte LIAR! call zijn:
        # 1. Er is precies 1 speler met kaarten over.
        # 2. De speler die zojuist de claim deed (claimer_player) is levend en heeft NU 0 kaarten.
        # 3. De speler die aan de beurt is om te reageren (current_responder) is levend en heeft NOG WEL kaarten.
        if len(players_with_cards) == 1 and \
           claimer_player and claimer_player['alive'] and len(claimer_player['hand']) == 0 and \
           current_responder and current_responder['alive'] and len(current_responder['hand']) > 0:
            
            # De speler die nog kaarten heeft (current_responder) wordt gedwongen 'LIAR!' te roepen.
            return {
                'game_over': False,
                'winner': None,
                'winner_name': None,
                'forced_liar_call': True,
                'calling_player_id': current_responder['id']
            }

    # Geen game over of speciale 2-speler regel actief
    return {'game_over': False, 'winner': None, 'winner_name': None, 'forced_liar_call': False, 'calling_player_id': None}
