import PropTypes from "prop-types";
import "../css/Scoreboard.css";

const Scoreboard = ({ score }) => {
  return (
    <div className="scoreboard">
      <h2>Scoreboard</h2>
      <p>Score: {score}</p>
    </div>
  );
};

// Define prop-types for Scoreboard
Scoreboard.propTypes = {
  score: PropTypes.number.isRequired, // Ensures 'score' is a required number
};

export default Scoreboard;
