const Leaderboard = () => {
  const dummyScores = [
    { name: "Player1", score: 20 },
    { name: "Player2", score: 25 },
    { name: "Player3", score: 30 },
  ];

  return (
    <div id="leaderboard">
      <h3 className="leaderboard-title">Leaderboard</h3>
      <table>
        <thead>
          <tr>
            <th>Player</th>
            <th>Score (seconds)</th>
          </tr>
        </thead>
        <tbody className="leaderboard-list">
          {dummyScores.map((player, index) => (
            <tr key={index}>
              <td>{player.name}</td>
              <td>{player.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Leaderboard;
