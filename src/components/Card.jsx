import "../css/Card.css";

const Card = ({ card, handleClick }) => {
  return (
    <div
      className={`card ${card.flipped ? "flipped" : ""}`}
      onClick={() => handleClick(card)}
    >
      <div className="card-inner">
        <div className="card-front">?</div>
        <div className="card-back">{card.content}</div>
      </div>
    </div>
  );
};

export default Card;
