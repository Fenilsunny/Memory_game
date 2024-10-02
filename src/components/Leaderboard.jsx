const Leaderboard = () => {
  const dummyScores = [
    { name: "Player1", score: 20 },
    { name: "Player2", score: 25 },
    { name: "Player3", score: 30 },
  ];

  return (
    <div className="leaderboard">
      <h3>Leaderboard</h3>
      <ul>
        {dummyScores.map((player, index) => (
          <li key={index}>
            {player.name}: {player.score} seconds
          </li>
        ))}
      </ul>
    </div>
  );
};

export default Leaderboard;
