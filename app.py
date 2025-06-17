import random
import string
import uuid
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room

# Importeer de kern spelregels en logica vanuit game_logic.py
from game_logic import (
    create_new_game,
    make_play,
    call_liar,
    roll_mystic_dice,
    believe_claim, # NIEUW: Importeer de believe_claim functie
    check_win_condition,
    _get_player_by_id # Deze is handig voor logging en namen
)

app = Flask(__name__)
# De secret key is nodig voor sessies in Flask, inclusief voor SocketIO.
# In een productomgeving zou dit een complexe, willekeurige string moeten zijn
# en op een veilige manier geladen moeten worden (bijv. uit een omgevingsvariabele).
app.config['SECRET_KEY'] = 'een_zeer_geheime_sleutel_voor_liars_bar'
socketio = SocketIO(app, cors_allowed_origins="*")

# Globale variabele om alle actieve lobbies en hun GameState op te slaan.
# Elke entry in 'lobbies' is: { "lobby_code": GameState_object }
lobbies = {}


# --- Helper functies voor SocketIO en communicatie ---

def generate_lobby_code():
    """Genereert een unieke 4-letterige lobbycode."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in lobbies:
            return code

def get_public_game_state(game_state, current_player_id=None):
    """
    Filtert de GameState om alleen publiek zichtbare informatie te retourneren.
    De handkaarten van de huidige speler worden wel meegegeven, maar niet die van anderen.
    """
    public_state = game_state.copy()
    public_players = []

    for player in public_state['players']:
        player_copy = player.copy()
        if player_copy['id'] != current_player_id:
            # Verberg de hand van andere spelers
            player_copy['hand'] = []
        public_players.append(player_copy)

    public_state['players'] = public_players
    return public_state

def broadcast_game_state(lobby_code):
    """Verstuurt de bijgewerkte publieke GameState naar alle spelers in een lobby."""
    game_state = lobbies.get(lobby_code)
    if game_state:
        # Loop door alle spelers in de lobby en stuur hen hun specifieke (gefilterde) state
        for player in game_state['players']:
            if player['alive']: # Stuur alleen naar actieve spelers
                player_id = player['id']
                # Gebruik de helper functie om de publieke staat te krijgen,
                # maar met de hand van de specifieke speler zichtbaar.
                public_state = get_public_game_state(game_state, player_id)
                socketio.emit('game_state_update', public_state, room=player_id) # Emit naar de individuele speler_id (wat hun sid is)
    else:
        print(f"Waarschuwing: Geen GameState gevonden voor lobby {lobby_code} bij broadcast.")


# --- Flask Routes ---

@app.route('/')
def index():
    """Rendert de hoofd HTML pagina."""
    return render_template('index.html')


# --- SocketIO Event Handlers ---

@socketio.on('connect')
def handle_connect():
    """Behandelt nieuwe client verbindingen."""
    # Gebruik request.sid als een unieke ID voor de socket.
    # We slaan de speler naam tijdelijk in de sessie op.
    print(f"Client {request.sid} verbonden.")

@socketio.on('disconnect')
def handle_disconnect():
    """Behandelt client ontkoppelingen."""
    player_sid = request.sid
    # Probeer de naam op te halen, standaard naar 'Onbekende speler'
    player_name = session.get(player_sid, 'Onbekende speler') 

    print(f"Client {player_sid} ({player_name}) ontkoppeld.")

    # Zoek en verwijder de speler uit zijn lobby
    # Loop over een kopie van de items om wijzigingen tijdens iteratie toe te staan
    for lobby_code, game_state in list(lobbies.items()): 
        player_found_in_lobby = False
        for player in game_state['players']:
            if player['id'] == player_sid:
                game_state['players'].remove(player)
                game_state['log'].append(f"{player_name} heeft de lobby verlaten.")
                print(f"{player_name} verwijderd uit lobby {lobby_code}.")
                player_found_in_lobby = True
                break
        
        if player_found_in_lobby:
            # Als de lobby leeg is, verwijder deze volledig
            if not game_state['players']:
                del lobbies[lobby_code]
                print(f"Lobby {lobby_code} is leeg en verwijderd.")
            else:
                # Als het spel al gestart was, controleer de winconditie na een disconnect
                if "turnOrder" in game_state: # Dit betekent dat initialize_game_state al is aangeroepen
                    # Verwijder de speler ook uit turnOrder als deze daar nog in zit
                    game_state['turnOrder'] = [p_id for p_id in game_state['turnOrder'] if p_id != player_sid]
                    
                    # Als het zijn beurt was, zet de beurt op de volgende actieve speler
                    if game_state['currentTurn'] == player_sid:
                        game_state['currentTurn'] = _get_next_active_player_id(game_state, player_sid)
                        if not game_state['currentTurn'] and len([p for p in game_state['players'] if p['alive']]) > 1:
                            # Dit kan gebeuren als de laatste in de turnOrder disconnected en er nog meer spelers zijn,
                            # dan moet de beurt naar de eerste in de turnOrder
                            game_state['currentTurn'] = game_state['turnOrder'][0] if game_state['turnOrder'] else None

                    # Controleer de winconditie als een speler disconnect
                    win_check_result = check_win_condition(game_state)
                    if win_check_result['game_over']:
                        game_state['phase'] = 'gameOver'
                        if win_check_result['winner']:
                            game_state['log'].append(f"{win_check_result['winner_name']} heeft het spel gewonnen!")
                            socketio.emit('game_over', {'winner': win_check_result['winner_name']}, room=lobby_code)
                        else:
                            game_state['log'].append("Alle spelers zijn uitgeschakeld. Geen winnaar.")
                            socketio.emit('game_over', {'winner': 'geen'}, room=lobby_code)

                # Stuur update naar de overgebleven spelers
                broadcast_game_state(lobby_code)
            return


@socketio.on('set_player_name')
def handle_set_player_name(data):
    """Slaat de spelernaam op in de sessie voor deze client."""
    player_name = data.get('name')
    if player_name:
        session[request.sid] = player_name
        print(f"Speler {request.sid} naam ingesteld op: {player_name}")
        emit('name_set', {'name': player_name})
    else:
        emit('error_message', {'message': 'Naam is verplicht.'})


@socketio.on('create_lobby')
def handle_create_lobby():
    """Behandelt de aanvraag om een nieuwe lobby aan te maken."""
    player_sid = request.sid
    player_name = session.get(player_sid)
    if not player_name:
        emit('error_message', {'message': 'Stel eerst je naam in.'})
        return

    lobby_code = generate_lobby_code()
    
    # Initialiseer een basis lobby met de aanmaker als eerste speler
    # De volledige game state wordt geïnitialiseerd bij 'start_game_request'
    lobbies[lobby_code] = {
        "lobbyCode": lobby_code,
        "players": [
            { "id": player_sid, "name": player_name, "alive": True }
        ],
        "log": [f"{player_name} heeft lobby {lobby_code} aangemaakt."]
    }
    join_room(lobby_code) # Voeg de speler toe aan de SocketIO room
    print(f"{player_name} heeft lobby {lobby_code} aangemaakt.")
    emit('lobby_created', {'lobbyCode': lobby_code, 'players': [p['name'] for p in lobbies[lobby_code]['players']]})
    
    # Stuur een update naar de aanmaker over de spelers in de lobby
    emit('lobby_update', {'players': [p['name'] for p in lobbies[lobby_code]['players']]}, room=lobby_code)


@socketio.on('join_lobby')
def handle_join_lobby(data):
    """Behandelt de aanvraag om een bestaande lobby te joinen."""
    lobby_code = data.get('lobbyCode', '').upper()
    player_sid = request.sid
    player_name = session.get(player_sid)

    if not player_name:
        emit('error_message', {'message': 'Stel eerst je naam in.'})
        return

    if lobby_code not in lobbies:
        emit('error_message', {'message': 'Lobby bestaat niet.'})
        return

    game_state = lobbies[lobby_code]

    # Voorkom dat dezelfde speler meerdere keren joined
    if any(p['id'] == player_sid for p in game_state['players']):
        emit('error_message', {'message': 'Je bent al in deze lobby.'})
        return

    if len(game_state['players']) >= 4:
        emit('error_message', {'message': 'Lobby is vol.'})
        return
    
    if "turnOrder" in game_state: # Spel is al gestart, geen nieuwe spelers meer
        emit('error_message', {'message': 'Het spel in deze lobby is al gestart. Je kunt niet meer meedoen.'})
        return

    game_state['players'].append({"id": player_sid, "name": player_name, "alive": True})
    join_room(lobby_code)
    game_state['log'].append(f"{player_name} is de lobby binnengekomen.")
    print(f"{player_name} joined lobby {lobby_code}. Huidige spelers: {[p['name'] for p in game_state['players']]}")

    emit('lobby_joined', {'lobbyCode': lobby_code, 'players': [p['name'] for p in game_state['players']]})
    # Stuur update naar alle spelers in de lobby
    socketio.emit('lobby_update', {'players': [p['name'] for p in lobbies[lobby_code]['players']]}, room=lobby_code)


@socketio.on('start_game_request')
def handle_start_game_request(data):
    """
    Behandelt de aanvraag om het spel te starten.
    Alleen de lobby maker kan starten. Minimaal 2 spelers nodig.
    """
    lobby_code = data.get('lobbyCode')
    player_sid = request.sid

    game_state = lobbies.get(lobby_code)
    if not game_state:
        emit('error_message', {'message': 'Lobby niet gevonden.'})
        return

    # Controleer of de aanvrager de maker van de lobby is
    if player_sid != game_state['players'][0]['id']:
        emit('error_message', {'message': 'Alleen de maker van de lobby kan het spel starten.'})
        return

    if len(game_state['players']) < 2:
        emit('error_message', {'message': 'Minimaal 2 spelers nodig om te starten.'})
        return

    if "turnOrder" in game_state: # Spel is al gestart
        emit('error_message', {'message': 'Spel is al gestart.'})
        return

    # Initialiseer de volledige GameState via game_logic.py
    player_ids_and_names = [(p['id'], p['name']) for p in game_state['players']]
    new_game_state = create_new_game(lobby_code, player_ids_and_names)
    lobbies[lobby_code] = new_game_state # Overwrite de basis lobby state met de volledige game state

    print(f"Spel gestart in lobby {lobby_code}.")
    broadcast_game_state(lobby_code) # Verstuurt de eerste GameState naar alle clients
    socketio.emit('game_started', {'lobbyCode': lobby_code}, room=lobby_code)


@socketio.on('make_play')
def handle_make_play(data):
    """Behandelt een speler die kaarten neerlegt en een claim doet."""
    lobby_code = data.get('lobbyCode')
    player_sid = request.sid
    cards_played = data.get('cardsPlayed') # Lijst van kaarten die de speler zegt neer te leggen
    
    game_state = lobbies.get(lobby_code)
    if not game_state:
        emit('error_message', {'message': 'Lobby of spel niet gevonden.'})
        return
    
    # Roep de game_logic functie aan om de zet te verwerken
    # Verwijder claimed_card_type uit de argumenten, omdat game_logic.make_play het niet meer verwacht
    success, message = make_play(game_state, player_sid, cards_played) 

    if not success:
        emit('error_message', {'message': message})
        return

    # Na een succesvolle zet, controleer op speciale 2-spelers regel
    win_check_result = check_win_condition(game_state)
    if win_check_result['forced_liar_call']:
        # Als een automatische LIAR! call nodig is
        calling_player_id = win_check_result['calling_player_id']
        call_liar(game_state, calling_player_id) # De game_logic.call_liar zal de fase aanpassen
        game_state['log'].append(f"Automatische 'LIAR!' call door {_get_player_by_id(game_state, calling_player_id)['name']} (speciale 2-spelers regel).")
        # De fase is nu 'resolvingDiceRoll', de beurt is bij de roepende speler

    broadcast_game_state(lobby_code) # Verstuurt de bijgewerkte GameState


@socketio.on('call_liar')
def handle_call_liar(data):
    """Behandelt een speler die 'LIAR!' roept."""
    lobby_code = data.get('lobbyCode')
    calling_player_sid = request.sid

    game_state = lobbies.get(lobby_code)
    if not game_state:
        emit('error_message', {'message': 'Lobby of spel niet gevonden.'})
        return
    
    # Roep de game_logic functie aan om de LIAR! call te verwerken
    success, message = call_liar(game_state, calling_player_sid)

    if not success:
        emit('error_message', {'message': message})
        return

    broadcast_game_state(lobby_code)


@socketio.on('believe_claim') # NIEUW: Nieuwe event handler voor 'believe_claim'
def handle_believe_claim(data):
    """Behandelt een speler die besluit de claim van de vorige speler te geloven."""
    lobby_code = data.get('lobbyCode')
    believing_player_sid = request.sid

    game_state = lobbies.get(lobby_code)
    if not game_state:
        emit('error_message', {'message': 'Lobby of spel niet gevonden.'})
        return

    # Roep de game_logic functie aan om de 'believe' actie te verwerken
    success, message = believe_claim(game_state, believing_player_sid)

    if not success:
        emit('error_message', {'message': message})
        return

    broadcast_game_state(lobby_code)


@socketio.on('roll_dice')
def handle_roll_dice(data):
    """Behandelt het werpen van de mystieke dobbelsteen."""
    lobby_code = data.get('lobbyCode')
    player_sid = request.sid

    game_state = lobbies.get(lobby_code)
    if not game_state:
        emit('error_message', {'message': 'Lobby of spel niet gevonden.'})
        return
    
    # Roep de game_logic functie aan om de dobbelsteenworp te verwerken
    success, message = roll_mystic_dice(game_state, player_sid)

    if not success:
        emit('error_message', {'message': message})
        return

    # Controleer de winconditie direct na de dobbelsteenworp
    win_check_result = check_win_condition(game_state)
    if win_check_result['game_over']:
        game_state['phase'] = 'gameOver' # Zorg dat de fase als 'gameOver' wordt gezet
        if win_check_result['winner']:
            game_state['log'].append(f"{win_check_result['winner_name']} heeft het spel gewonnen!")
            socketio.emit('game_over', {'winner': win_check_result['winner_name']}, room=lobby_code)
        else:
            game_state['log'].append("Alle spelers zijn uitgeschakeld. Geen winnaar.")
            socketio.emit('game_over', {'winner': 'geen'}, room=lobby_code)
        
    # Na een succesvolle dobbelsteenworp, of als het spel voorbij is
    # broadcast de geüpdatete state
    broadcast_game_state(lobby_code)


@socketio.on('chat_message')
def handle_chat_message(data):
    """Behandelt chatberichten."""
    lobby_code = data.get('lobbyCode')
    message = data.get('message')
    player_name = session.get(request.sid) # Gebruik de opgeslagen naam

    if lobby_code not in lobbies:
        emit('error_message', {'message': 'Lobby niet gevonden voor chat.'})
        return

    if player_name and message:
        full_message = f"{player_name}: {message}"
        lobbies[lobby_code]['log'].append(f"CHAT: {full_message}")
        # Verstuur het chatbericht alleen als 'chat_message' event
        socketio.emit('chat_message', {'message': full_message}, room=lobby_code)
        # We hoeven niet de volledige game state te broadcasten voor alleen een chatbericht,
        # tenzij we willen dat de chat log in de game_state.log verschijnt en direct wordt weergegeven via broadcast_game_state.
        # Voor nu alleen de chat_message event. Als de log zichtbaar moet zijn, dan broadcast_game_state uncommenten.
        # broadcast_game_state(lobby_code)
    else:
        emit('error_message', {'message': 'Bericht of naam ontbreekt.'})


if __name__ == '__main__':
    # Start de Flask-SocketIO server
    socketio.run(app, debug=True, port=5000)
