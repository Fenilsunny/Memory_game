import { useEffect, useState } from "react";
import "../css/MemoryGame.css"; // Import the CSS for styling

const MemoryGame = () => {
  const cardSymbols = ["🍎", "🍌", "🍇", "🍊", "🍓", "🍉"];
  const [cards, setCards] = useState([]);
  const [flippedCards, setFlippedCards] = useState([]);
  const [canFlip, setCanFlip] = useState(true);
  const [matchedPairs, setMatchedPairs] = useState(0);

  // Shuffle the cards
  const shuffleCards = () => {
    const shuffledCards = [...cardSymbols, ...cardSymbols]
      .map((symbol) => ({ symbol, flipped: false }))
      .sort(() => Math.random() - 0.5);
    setCards(shuffledCards);
  };

  useEffect(() => {
    shuffleCards();
  }, []);

  const flipCard = (index) => {
    if (!canFlip || cards[index].flipped) return;

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

  return (
    <div id="game-container" className="game-container">
      {cards.map((card, index) => (
        <div
          key={index}
          className={`memory-card ${!card.flipped ? "flipped" : ""}`}
          onClick={() => flipCard(index)}
        >
          <div className={`front ${!card.flipped ? "visible" : ""}`}>
            {card.symbol}
          </div>
          <div className={`back ${!card.flipped ? "hidden" : ""}`}>?</div>
        </div>
      ))}
    </div>
  );
};

export default MemoryGame;
