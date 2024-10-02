import { useEffect, useState } from "react";
import Leaderboard from "./Leaderboard";
import "../css/MemoryGame.css"; // Import the CSS for styling

const MemoryGame = () => {
  const cardSymbols = ["🍎", "🍌", "🍇", "🍊", "🍓", "🍉"];
  const [cards, setCards] = useState([]);
  const [flippedCards, setFlippedCards] = useState([]);
  const [canFlip, setCanFlip] = useState(false);
  const [matchedPairs, setMatchedPairs] = useState(0);
  const [timer, setTimer] = useState(0);
  const [clicks, setClicks] = useState(0);
  const [isGameStarted, setIsGameStarted] = useState(false);
  const [gameLevel, setGameLevel] = useState("easy");

  const levelDurations = {
    easy: 3000, // 3 seconds
    medium: 2000, // 2 seconds
    hard: 1000, // 1 second
  };

  // Shuffle the cards
  const shuffleCards = () => {
    const shuffledCards = [...cardSymbols, ...cardSymbols]
      .map((symbol) => ({ symbol, flipped: true })) // Show all cards initially
      .sort(() => Math.random() - 0.5);
    setCards(shuffledCards);
  };

  useEffect(() => {
    shuffleCards();
  }, []);

  const startGame = () => {
    shuffleCards();
    setIsGameStarted(true);
    setMatchedPairs(0);
    setClicks(0);
    setTimer(0);
    setFlippedCards([]);
    setCanFlip(false); // Disable flipping during the initial reveal

    // Set timer for flipping the cards back based on difficulty level
    setTimeout(() => {
      setCards((prevCards) =>
        prevCards.map((card) => ({ ...card, flipped: false }))
      );
      setCanFlip(true); // Enable flipping after reveal
    }, levelDurations[gameLevel]); // Adjust timer based on the selected level
  };

  useEffect(() => {
    let interval;
    if (isGameStarted && canFlip) {
      interval = setInterval(() => setTimer((prev) => prev + 1), 1000);
    }
    return () => clearInterval(interval);
  }, [isGameStarted, canFlip]);

  const flipCard = (index) => {
    if (!canFlip || cards[index].flipped) return;

    setClicks((prev) => prev + 1); // Increment click counter
    const newCards = [...cards];
    newCards[index].flipped = true;
    setFlippedCards((prev) => [...prev, index]);
    setCards(newCards);

    if (flippedCards.length === 1) {
      setCanFlip(false);
      checkForMatch(index);
    }
  };

  const checkForMatch = (index) => {
    const [card1] = flippedCards;
    const symbol1 = cards[card1].symbol;
    const symbol2 = cards[index].symbol;

    if (symbol1 === symbol2) {
      setMatchedPairs((prev) => prev + 1);
      setFlippedCards([]);
      setCanFlip(true);

      if (matchedPairs + 1 === cardSymbols.length) {
        setTimeout(() => alert("Congratulations! You won!"), 500);
        setClicks(0);
        setTimer(0);
        setIsGameStarted(false);
      }
    } else {
      setTimeout(() => {
        const newCards = [...cards];
        newCards[card1].flipped = false;
        newCards[index].flipped = false;
        setCards(newCards);
        setFlippedCards([]);
        setCanFlip(true);
      }, 1000);
    }
  };

  const resetGame = () => {
    setIsGameStarted(false);
    shuffleCards();
    setMatchedPairs(0);
    setTimer(0);
    setClicks(0);
    setFlippedCards([]);
  };

  return (
    <div>
      <div className="game-controls">
        {!isGameStarted ? (
          <button className="start" onClick={startGame}>
            Start Game
          </button>
        ) : (
          <button className="disabled-custom" onClick={startGame} disabled>
            Start Game
          </button>
        )}

        <button className="reset" onClick={resetGame}>
          Reset Game
        </button>
        {!isGameStarted ? (
          <div className="level-select">
            <select
              value={gameLevel}
              onChange={(e) => setGameLevel(e.target.value)}
            >
              <option value="easy">Easy</option>
              <option value="medium">Medium</option>
              <option value="hard">Hard</option>
            </select>
          </div>
        ) : (
          <></>
        )}
      </div>

      {isGameStarted ? (
        <>
          {" "}
          {/* Game board only becomes visible after the game starts */}
          <div className="timer">Timer: {timer} seconds</div>
          <div className="click-counter">Clicks: {clicks}</div>
          <div
            id="game-container"
            className="game-container"
            style={{ visibility: isGameStarted ? "visible" : "hidden" }}
          >
            {cards.map((card, index) => (
              <div
                key={index}
                className={`memory-card ${card.flipped ? "flipped" : ""}`}
                onClick={() => flipCard(index)}
              >
                <div className="front">?</div>
                <div className="back">{card.symbol}</div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div id="leaderboard">
          <Leaderboard />
        </div>
      )}
    </div>
  );
};

export default MemoryGame;
