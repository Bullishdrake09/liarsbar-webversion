document.addEventListener('DOMContentLoaded', () => {
    // Initialiseer Socket.IO connectie
    const socket = io();

    // --- UI Elementen ---
    const lobbySection = document.getElementById('lobby-section');
    const gameSection = document.getElementById('game-section');
    const playerNameInput = document.getElementById('playerNameInput');
    const setPlayerNameBtn = document.getElementById('setPlayerNameBtn');
    const nameStatus = document.getElementById('nameStatus');
    const currentPlayerNameSpan = document.getElementById('currentPlayerName');
    const lobbyControls = document.getElementById('lobby-controls');
    const lobbyCodeInput = document.getElementById('lobbyCodeInput');
    const createLobbyBtn = document.getElementById('createLobbyBtn'); 
    const joinLobbyBtn = document.getElementById('joinLobbyBtn');
    const lobbyInfo = document.getElementById('lobby-info');
    const currentLobbyCodeSpan = document.getElementById('currentLobbyCode');
    const playersInLobbyUl = document.getElementById('playersInLobby');
    const startGameBtn = document.getElementById('startGameBtn');
    const playerListDiv = document.getElementById('player-list');
    const deckTypeCardsDiv = document.getElementById('deck-type-cards');
    const pileDisplayP = document.getElementById('currentClaim');
    const revealedCardsSection = document.getElementById('revealed-cards-section');
    const revealedMessageP = document.getElementById('revealedMessage');
    const revealedCardsDisplayDiv = document.getElementById('revealedCardsDisplay');
    const playerHandDiv = document.getElementById('player-hand');
    const gameLogDiv = document.getElementById('game-log');
    const makePlayBtn = document.getElementById('makePlayBtn');
    const believeClaimBtn = document.getElementById('believeClaimBtn'); 
    const callLiarBtn = document.getElementById('callLiarBtn'); 
    const rollDiceBtn = document.getElementById('rollDiceBtn');
    const chatInput = document.getElementById('chatInput');
    const sendChatBtn = document.getElementById('sendChatBtn');
    const messageBox = document.getElementById('messageBox');
    const messageText = document.getElementById('messageText');
    const messageBoxCloseBtn = document.getElementById('messageBoxCloseBtn');
    const playerDiceStatusContainer = document.getElementById('dice-status-container'); 
    const restartGameBtn = document.getElementById('restartGameBtn'); // NIEUW: Restart game knop

    // Elementen voor eliminatie animatie
    const eliminationOverlay = document.getElementById('elimination-animation-overlay');
    const eliminatedPlayerNameDisplay = document.getElementById('eliminatedPlayerName');

    let selectedCards = []; // Houdt de geselecteerde kaarten in de hand van de speler bij
    let currentLobbyCode = null; // Houdt de huidige lobbycode bij
    let myPlayerId = null; // Houdt de socket ID van de huidige speler bij

    // Houdt de alive status van spelers bij tussen updates
    let lastKnownPlayerStates = {};

    // --- Message Box Functie ---
    function showMessageBox(message) {
        messageText.textContent = message;
        messageBox.classList.remove('hidden');
    }

    messageBoxCloseBtn.addEventListener('click', () => {
        messageBox.classList.add('hidden');
    });

    // --- Socket.IO Event Handlers ---

    socket.on('connect', () => {
        console.log('Verbonden met server!');
        myPlayerId = socket.id; // Sla de eigen socket ID op
    });

    socket.on('disconnect', () => {
        console.log('Verbinding verbroken met server.');
        showMessageBox('Verbinding met de server verbroken. Probeer de pagina opnieuw te laden.');
    });

    socket.on('name_set', (data) => {
        currentPlayerNameSpan.textContent = data.name;
        nameStatus.classList.remove('hidden');
        playerNameInput.disabled = true; // Naam kan niet meer gewijzigd worden
        setPlayerNameBtn.disabled = true;
        lobbyControls.classList.remove('hidden'); // Toon de lobby controls
    });

    socket.on('error_message', (data) => {
        showMessageBox(data.message);
    });

    socket.on('lobby_created', (data) => {
        currentLobbyCode = data.lobbyCode;
        currentLobbyCodeSpan.textContent = data.lobbyCode;
        lobbyInfo.classList.remove('hidden');
        createLobbyBtn.disabled = true;
        joinLobbyBtn.disabled = true;
        lobbyCodeInput.disabled = true;
        startGameBtn.classList.remove('hidden'); // Toon start game knop voor maker
        console.log(`Lobby ${data.lobbyCode} aangemaakt.`);
    });

    socket.on('lobby_joined', (data) => {
        currentLobbyCode = data.lobbyCode;
        currentLobbyCodeSpan.textContent = data.lobbyCode;
        lobbyInfo.classList.remove('hidden');
        createLobbyBtn.disabled = true;
        joinLobbyBtn.disabled = true;
        lobbyCodeInput.disabled = true;
        startGameBtn.classList.add('hidden'); // Verberg start game knop voor joiner
        console.log(`Lobby ${data.lobbyCode} gejoined.`);
    });

    socket.on('lobby_update', (data) => {
        // Update de lijst van spelers in de lobby
        playersInLobbyUl.innerHTML = '';
        data.players.forEach(player_name => {
            const li = document.createElement('li');
            li.textContent = player_name;
            playersInLobbyUl.appendChild(li);
        });
    });

    socket.on('game_started', (data) => {
        console.log('Spel gestart!');
        lobbySection.classList.add('hidden'); // Verberg lobby UI
        gameSection.classList.remove('hidden'); // Toon spel UI
        showMessageBox(`Het spel is begonnen in lobby ${data.lobbyCode}!`);

        // Verberg de restart knop als een nieuw spel start
        restartGameBtn.classList.add('hidden');

        // Initialiseer lastKnownPlayerStates bij start van het spel
        // De volledige player data komt nu via game_state_update, dus deze init is hier niet strikt nodig,
        // maar kan helpen bij een race condition. Voor de zekerheid laten we hem staan.
        // Let op: 'data' van game_started bevat niet de 'alive' status, dus we resetten 'lastKnownPlayerStates'
        // en laten de eerste game_state_update dit correct opvullen.
        lastKnownPlayerStates = {};
    });

    socket.on('game_state_update', (gameState) => {
        console.log('Game State Update:', gameState);
        
        // Initialiseer lastKnownPlayerStates als het nog leeg is (eerste game_state_update)
        if (Object.keys(lastKnownPlayerStates).length === 0 && gameState.players.length > 0) {
            gameState.players.forEach(player => {
                lastKnownPlayerStates[player.id] = player.alive;
            });
        }

        gameState.players.forEach(player => {
            if (lastKnownPlayerStates[player.id] !== undefined && lastKnownPlayerStates[player.id] && !player.alive) {
                // Speler was alive en is nu dood -> Toon animatie!
                showPlayerEliminationAnimation(player.name);
            }
            // Update de laatst bekende status
            lastKnownPlayerStates[player.id] = player.alive;
        });

        // Render spelerslijst
        renderPlayerList(gameState);

        // Render dobbelsteen status
        renderPlayerDiceStatus(gameState); 

        // Render middenkaarten (deck type)
        renderDeckTypeCards(gameState);

        // Render stapel display
        renderPileDisplay(gameState);

        // Render speler's hand
        renderPlayerHand(gameState);

        // Render spel log
        renderGameLog(gameState);

        // Update knop statussen gebaseerd op beurt en fase
        updateActionButtons(gameState);

        // Render onthulde kaarten sectie
        renderRevealedCardsInfo(gameState);
    });

    socket.on('chat_message', (data) => {
        // Voeg chatbericht toe aan de spel log
        const logItem = document.createElement('p');
        logItem.textContent = data.message;
        gameLogDiv.appendChild(logItem);
        gameLogDiv.scrollTop = gameLogDiv.scrollHeight; // Scroll naar beneden
    });

    socket.on('game_over', (data) => {
        if (data.winner && data.winner !== 'geen') {
            showMessageBox(`Spel afgelopen! De winnaar is: ${data.winner}!`);
        } else {
            showMessageBox('Spel afgelopen! Geen winnaar (mogelijk alle spelers uitgeschakeld).');
        }
        // Uitschakelen van actieknoppen
        makePlayBtn.disabled = true;
        callLiarBtn.disabled = true;
        rollDiceBtn.disabled = true;
        believeClaimBtn.disabled = true; 
        revealedCardsSection.classList.add('hidden'); // Verberg ook de onthulde kaarten
        lastKnownPlayerStates = {}; // Reset staten bij game over

        // Toon de restart game knop
        restartGameBtn.classList.remove('hidden');
    });

    socket.on('game_restarted', (data) => {
        // Hoewel game_state_update de UI al zal bijwerken,
        // kunnen we hier een bevestiging tonen of extra logica uitvoeren
        console.log(`Spel opnieuw gestart in lobby ${data.lobbyCode}`);
        showMessageBox(`Nieuw spel gestart in lobby ${data.lobbyCode}!`);
        // Verberg de restart knop na het starten van een nieuw spel
        restartGameBtn.classList.add('hidden');
    });

    // --- Render Functies ---

    function renderPlayerList(gameState) {
        playerListDiv.innerHTML = '';
        gameState.players.forEach(player => {
            const playerStatusDiv = document.createElement('div');
            playerStatusDiv.classList.add('player-status');
            playerStatusDiv.classList.add(player.alive ? 'alive' : 'dead');
            if (player.id === gameState.currentTurn) {
                playerStatusDiv.classList.add('current-turn');
            }

            const dotSpan = document.createElement('span');
            dotSpan.classList.add('dot');
            playerStatusDiv.appendChild(dotSpan);

            const nameSpan = document.createElement('span');
            nameSpan.classList.add('name', 'text-lg');
            nameSpan.textContent = player.name;
            playerStatusDiv.appendChild(nameSpan);

            // Voeg aantal dobbelsteen pogingen toe indien van toepassing
            // Update: toon "Dood" als speler niet meer alive is
            if (!player.alive) {
                    const statusSpan = document.createElement('span');
                    statusSpan.classList.add('ml-2', 'text-sm', 'text-red-400', 'font-bold');
                    statusSpan.textContent = '(Dood)';
                    playerStatusDiv.appendChild(statusSpan);
            } else if (player.diceRollAttempts > 0) {
                    const diceAttemptsSpan = document.createElement('span');
                    diceAttemptsSpan.classList.add('ml-2', 'text-sm', 'text-gray-400');
                    diceAttemptsSpan.textContent = `(Dobbelen: ${player.diceRollAttempts}x)`;
                    playerStatusDiv.appendChild(diceAttemptsSpan);
            }

            // Toon "Jij" label voor de huidige speler
            if (player.id === myPlayerId) {
                const youSpan = document.createElement('span');
                youSpan.classList.add('ml-2', 'text-sm', 'text-blue-300', 'font-bold');
                youSpan.textContent = '(Jij)';
                playerStatusDiv.appendChild(youSpan);
            }

            playerListDiv.appendChild(playerStatusDiv);
        });
    }

    // Functie om de dobbelsteenstatus per speler te renderen
    function renderPlayerDiceStatus(gameState) {
        playerDiceStatusContainer.innerHTML = ''; // Leeg de container

        gameState.players.forEach(player => {
            const playerDiceDiv = document.createElement('div');
            playerDiceDiv.classList.add('flex', 'items-center', 'justify-between', 'p-2', 'bg-gray-800', 'rounded-lg', 'shadow-md', 'mb-2');

            const playerNameSpan = document.createElement('span');
            playerNameSpan.classList.add('font-semibold', 'text-lg');
            playerNameSpan.textContent = player.name;
            playerDiceDiv.appendChild(playerNameSpan);

            const diceNumbersDiv = document.createElement('div');
            diceNumbersDiv.classList.add('flex', 'space-x-2');

            // Itereer over alle mogelijke dobbelsteengezichten (1 t/m 6)
            for (let i = 1; i <= 6; i++) {
                const diceFaceSpan = document.createElement('span');
                diceFaceSpan.classList.add('dice-face', 'text-xl', 'font-bold', 'py-1', 'px-2', 'rounded-md');
                diceFaceSpan.textContent = i;

                // Controleer of dit nummer al is gerold door de speler
                if (player.mysticDice && player.mysticDice.rolledNumbers && player.mysticDice.rolledNumbers.includes(String(i))) {
                    diceFaceSpan.classList.add('rolled'); // Voeg 'rolled' class toe voor doorstrepen
                }
                diceNumbersDiv.appendChild(diceFaceSpan);
            }
            playerDiceDiv.appendChild(diceNumbersDiv);
            playerDiceStatusContainer.appendChild(playerDiceDiv);
        });
    }


    function renderDeckTypeCards(gameState) {
        deckTypeCardsDiv.innerHTML = '';
        // Er is nu slechts EEN middenkaart (deckType[0])
        const cardType = gameState.deckType[0];
        const cardElement = document.createElement('div');
        cardElement.classList.add('card');
        cardElement.textContent = cardType;
        
        let icon = '';
        if (cardType === 'Koning') icon = '👑';
        else if (cardType === 'Koningin') icon = '👸';
        else if (cardType === 'Boer') icon = '🤵';
        
        if (icon) {
            const iconSpan = document.createElement('span');
            iconSpan.classList.add('card-icon');
            iconSpan.textContent = icon;
            cardElement.innerHTML = ''; // Leeg de textContent
            cardElement.appendChild(iconSpan);
            const typeSpan = document.createElement('span');
            typeSpan.textContent = cardType;
            cardElement.appendChild(typeSpan);
        }

        deckTypeCardsDiv.appendChild(cardElement);
    }

    function renderPileDisplay(gameState) {
        // BELANGRIJKE WIJZIGING: Gebruik lastClaimDetails voor de display tekst
        if (gameState.lastClaimDetails && gameState.lastClaimDetails.player) {
            const lastClaim = gameState.lastClaimDetails;
            const playerName = lastClaim.playerName || "Onbekende speler"; 
            pileDisplayP.textContent = `${playerName} claimde: ${lastClaim.claimedAmount} ${lastClaim.claimedCardType}(s)`;
        } else {
            pileDisplayP.textContent = 'Geen claims nog.';
        }
    }

    function renderPlayerHand(gameState) {
        playerHandDiv.innerHTML = '';
        const myPlayer = gameState.players.find(p => p.id === myPlayerId);

        if (myPlayer && myPlayer.hand) {
            myPlayer.hand.forEach(card => {
                const cardElement = document.createElement('div');
                cardElement.classList.add('card', 'cursor-pointer');
                cardElement.textContent = card;
                cardElement.dataset.card = card; // Sla de kaartwaarde op

                // Optioneel: voeg een icoon toe voor Koning, Koningin, Boer, Joker
                let icon = '';
                if (card === 'Koning') icon = '👑';
                else if (card === 'Koningin') icon = '👸';
                else if (card === 'Boer') icon = '🤵';
                else if (card === 'Joker') icon = '🃏';
                
                if (icon) {
                    const iconSpan = document.createElement('span');
                    iconSpan.classList.add('card-icon');
                    iconSpan.textContent = icon;
                    cardElement.innerHTML = ''; // Leeg de textContent
                    cardElement.appendChild(iconSpan);
                    const typeSpan = document.createElement('span');
                    typeSpan.textContent = card;
                    cardElement.appendChild(typeSpan);
                }

                // Voeg 'selected' class toe als de kaart al geselecteerd was
                if (selectedCards.includes(card)) {
                    cardElement.classList.add('selected');
                }

                // Voeg click listener toe voor kaartselectie
                cardElement.addEventListener('click', () => {
                    // Alleen selecteer/deselecteer als het mijn beurt is en in de juiste fase
                    const currentGameState = socket.currentGameState; // Pak de laatste game state op de client
                    const myPlayerInState = currentGameState.players.find(p => p.id === myPlayerId);

                    if (currentGameState.currentTurn === myPlayerId && currentGameState.phase === 'awaitingPlay' && myPlayerInState.alive) {
                        cardElement.classList.toggle('selected');
                        if (cardElement.classList.contains('selected')) {
                            selectedCards.push(card);
                        } else {
                            selectedCards = selectedCards.filter(c => c !== card);
                        }
                        updateMakePlayButtonState(currentGameState); // Gebruik de actuele gameState
                    } else {
                        showMessageBox("Je kunt nu geen kaarten selecteren.");
                    }
                });
                playerHandDiv.appendChild(cardElement);
            });
        }
    }

    function renderGameLog(gameState) {
        gameLogDiv.innerHTML = ''; // Leeg de log voor de zekerheid
        gameState.log.forEach(logItem => {
            const p = document.createElement('p');
            p.textContent = logItem;
            gameLogDiv.appendChild(p);
        });
        gameLogDiv.scrollTop = gameLogDiv.scrollHeight; // Scroll naar beneden
    }

    // Functie om onthulde kaarten te renderen
    function renderRevealedCardsInfo(gameState) {
        const revealedInfo = gameState.revealedCardsInfo;
        revealedCardsDisplayDiv.innerHTML = ''; // Leeg de vorige onthulde kaarten

        if (revealedInfo && revealedInfo.isRevealed) {
            revealedCardsSection.classList.remove('hidden'); // Toon de sectie
            revealedMessageP.textContent = revealedInfo.outcomeMessage; // Toon het resultaatbericht

            // Als er dobbelsteen resultaat is, toon dat
            if (revealedInfo.diceRollOutcome) {
                const diceOutcomeDiv = document.createElement('div');
                diceOutcomeDiv.classList.add('dice-outcome');
                diceOutcomeDiv.textContent = `🎲 ${revealedInfo.diceRollOutcome.face}`; // Toon dobbelsteen icoon + nummer
                // Voeg een specifieke stijl toe voor verlies
                if (revealedInfo.diceRollOutcome.isLoss) {
                    diceOutcomeDiv.classList.add('dice-loss');
                }
                revealedCardsDisplayDiv.appendChild(diceOutcomeDiv);
            }
            
            // Toon de werkelijke kaarten (indien van toepassing)
            if (revealedInfo.actualCards && revealedInfo.actualCards.length > 0) {
                revealedInfo.actualCards.forEach((card, index) => {
                    const cardElement = document.createElement('div');
                    cardElement.classList.add('card', 'revealed-card'); // Voeg 'revealed-card' class toe voor animatie
                    // Pas de animationDelay aan naar 0.5s per kaart
                    cardElement.style.animationDelay = `${index * 0.5}s`; 

                    let icon = '';
                    if (card === 'Koning') icon = '👑';
                    else if (card === 'Koningin') icon = '👸';
                    else if (card === 'Boer') icon = '🤵';
                    else if (card === 'Joker') icon = '🃏';
                    
                    if (icon) {
                        const iconSpan = document.createElement('span');
                        iconSpan.classList.add('card-icon');
                        iconSpan.textContent = icon;
                        cardElement.appendChild(iconSpan);
                        const typeSpan = document.createElement('span');
                        typeSpan.textContent = card;
                        cardElement.appendChild(typeSpan);
                    } else {
                        cardElement.textContent = card;
                    }
                    revealedCardsDisplayDiv.appendChild(cardElement);
                });
            }
        } else {
            revealedCardsSection.classList.add('hidden'); // Verberg de sectie
            revealedCardsDisplayDiv.innerHTML = '';
            revealedMessageP.textContent = '';
        }
    }

    // Functie voor eliminatie animatie
    function showPlayerEliminationAnimation(playerName) {
        eliminatedPlayerNameDisplay.textContent = playerName;
        eliminationOverlay.classList.remove('hidden');
        eliminationOverlay.classList.add('active'); // Voor animatie trigger

        setTimeout(() => {
            eliminationOverlay.classList.remove('active');
            eliminationOverlay.classList.add('hidden');
        }, 2500); // Duur van de animatie (2.5 seconden)
    }


    function updateMakePlayButtonState(gameState) {
        // Helper functie om de Leg Kaarten knop te updaten
        const myPlayer = gameState.players.find(p => p.id === myPlayerId);
        const hasCards = myPlayer && myPlayer.hand && myPlayer.hand.length > 0;
        makePlayBtn.disabled = selectedCards.length === 0 || gameState.currentTurn !== myPlayerId || gameState.phase !== 'awaitingPlay' || !hasCards;
    }


    function updateActionButtons(gameState) {
        const isMyTurn = (gameState.currentTurn === myPlayerId);
        const isAwaitingPlay = (gameState.phase === 'awaitingPlay');
        const isAwaitingLiarCall = (gameState.phase === 'awaitingLiarCall');
        const isResolvingDiceRoll = (gameState.phase === 'resolvingDiceRoll');
        const isGameOver = (gameState.phase === 'gameOver');

        // Get my player object to check hand size
        const myPlayer = gameState.players.find(p => p.id === myPlayerId);
        // Spelers die niet 'alive' zijn kunnen geen acties meer uitvoeren.
        const canAct = myPlayer && myPlayer.alive;


        // Reset alle knoppen zichtbaarheid en disabled state
        makePlayBtn.disabled = true;
        believeClaimBtn.classList.add('hidden'); 
        believeClaimBtn.disabled = true;
        callLiarBtn.disabled = true;
        callLiarBtn.classList.add('hidden'); 
        rollDiceBtn.classList.add('hidden'); 
        rollDiceBtn.disabled = true;
        restartGameBtn.classList.add('hidden'); // Verberg restart knop standaard

        if (isGameOver) {
            restartGameBtn.classList.remove('hidden'); // Toon de restart knop als het spel voorbij is
            return;
        }

        if (isMyTurn && canAct) { // Alleen acties als het mijn beurt is EN ik actief ben
            if (isAwaitingPlay) {
                // Mijn beurt om kaarten te leggen
                // Enable if I have selected cards AND I have cards in hand.
                makePlayBtn.disabled = selectedCards.length === 0 || myPlayer.hand.length === 0; 
            } else if (isAwaitingLiarCall) {
                // Mijn beurt om te reageren op een claim van een ANDERE speler
                makePlayBtn.disabled = true; // Kan geen kaarten leggen in deze fase

                const lastClaimerName = gameState.lastClaimDetails ? gameState.lastClaimDetails.playerName : null;
                // Enable LIAR/BELIEVE only if it's not my own claim AND I have cards
                // (Omdat je anders niet kunt geloven/liar roepen als je geen kaarten meer hebt)
                if (lastClaimerName && gameState.lastClaimDetails.player !== myPlayerId && myPlayer.hand.length > 0) { 
                    believeClaimBtn.classList.remove('hidden'); 
                    believeClaimBtn.disabled = false;
                    believeClaimBtn.textContent = `Ik denk dat ${lastClaimerName} de waarheid spreekt`;

                    callLiarBtn.classList.remove('hidden'); 
                    callLiarBtn.disabled = false; 
                    callLiarBtn.textContent = `Ik denk dat ${lastClaimerName} liegt`;
                } else {
                    // Verberg knoppen als het mijn eigen claim is of als ik geen kaarten heb
                    believeClaimBtn.classList.add('hidden');
                    callLiarBtn.classList.add('hidden');
                }

            } else if (isResolvingDiceRoll) {
                // Mijn beurt om dobbelsteen te werpen
                // Deze actie hangt niet af van het hebben van kaarten in de hand.
                // Controleren of de huidige speler de speler is die de dobbelsteen moet werpen
                if (gameState.revealedCardsInfo.playerToRollDice === myPlayerId) {
                    rollDiceBtn.classList.remove('hidden');
                    rollDiceBtn.disabled = false;
                } else {
                    // Niet mijn beurt om te dobbelen
                    rollDiceBtn.classList.add('hidden');
                    rollDiceBtn.disabled = true;
                }
            }
        } else {
            // Niet mijn beurt of ik ben uitgeschakeld, alle actieknoppen zijn disabled/verborgen voor mij.
            // (al afgehandeld door standaard reset)
        }

        // Sla de actuele gameState op de socket op, zodat we deze in de click listener kunnen gebruiken
        socket.currentGameState = gameState;
    }


    // --- Event Listeners voor Knoppen en Input ---

    setPlayerNameBtn.addEventListener('click', () => {
        const playerName = playerNameInput.value.trim();
        console.log("Poging om naam in te stellen:", playerName);
        if (playerName) {
            socket.emit('set_player_name', { name: playerName });
        } else {
            showMessageBox('Voer een geldige naam in.');
        }
    });

    createLobbyBtn.addEventListener('click', () => {
        socket.emit('create_lobby');
    });

    joinLobbyBtn.addEventListener('click', () => {
        const lobbyCode = lobbyCodeInput.value.trim();
        if (lobbyCode) {
            socket.emit('join_lobby', { lobbyCode: lobbyCode });
        } else {
            showMessageBox('Voer een lobby code in.');
        }
    });

    startGameBtn.addEventListener('click', () => {
        console.log("Start Spel knop geklikt.");
        if (currentLobbyCode) {
            socket.emit('start_game_request', { lobbyCode: currentLobbyCode });
        } else {
            showMessageBox('Geen actieve lobby om te starten.');
        }
    });

    makePlayBtn.addEventListener('click', () => {
        if (selectedCards.length === 0) {
            showMessageBox('Selecteer minimaal 1 kaart om te leggen.');
            return;
        }

        if (currentLobbyCode) {
            socket.emit('make_play', {
                lobbyCode: currentLobbyCode,
                cardsPlayed: selectedCards
            });
            selectedCards = []; // Reset selectie na zet
            // Deselecteer alle kaarten visueel na de zet
            document.querySelectorAll('#player-hand .card.selected').forEach(card => {
                card.classList.remove('selected');
            });
        }
    });

    believeClaimBtn.addEventListener('click', () => { 
        if (currentLobbyCode) {
            socket.emit('believe_claim', { lobbyCode: currentLobbyCode });
        }
    });

    callLiarBtn.addEventListener('click', () => {
        if (currentLobbyCode) {
            socket.emit('call_liar', { lobbyCode: currentLobbyCode });
        }
    });

    rollDiceBtn.addEventListener('click', () => {
        if (currentLobbyCode && myPlayerId) { 
            socket.emit('roll_dice', { lobbyCode: currentLobbyCode, playerId: myPlayerId });
        } else {
            showMessageBox('Fout: Kan dobbelsteen niet werpen zonder lobby of speler ID.');
        }
    });

    // NIEUW: Event Listener voor de restartGameBtn
    restartGameBtn.addEventListener('click', () => {
        if (currentLobbyCode) {
            socket.emit('restart_game_request', { lobbyCode: currentLobbyCode });
        } else {
            showMessageBox('Kan spel niet herstarten, geen actieve lobby.');
        }
    });

    sendChatBtn.addEventListener('click', () => {
        const message = chatInput.value.trim();
        if (message) {
            socket.emit('chat_message', { lobbyCode: currentLobbyCode, message: message });
            chatInput.value = ''; // Leeg het chat input veld
        }
    });

    // Enter-toets voor chat
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendChatBtn.click();
        }
    });
});
