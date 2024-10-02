import { useState, useEffect } from "react";
import Card from "./Card";
import "../css/Board.css";

const Board = ({ cards, handleMatch }) => {
  return (
    <div id="game-board">
      {cards.map((card) => (
        <Card key={card.id} card={card} handleClick={handleMatch} />
      ))}
    </div>
  );
};
export default Board;
