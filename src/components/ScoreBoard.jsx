import "../css/Scoreboard.css";

const Scoreboard = ({ score }) => {
  return (
    <div className="scoreboard">
      <h2>Score: {score}</h2>
    </div>
  );
};

export default Scoreboard;
