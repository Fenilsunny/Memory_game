import Board from "./components/Board";
import Scoreboard from "./components/ScoreBoard";
import MemoryGame from "./components/MemoryGame";
import Timer from "./components/Timer";
import NavBar from "./components/Navbar";
import "./css/App.css";

import { useState, useEffect } from "react";

const App = () => {
  const [time, setTime] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setTime((prevTime) => prevTime + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <NavBar />
      <main className="main-content">
        <h1>Memory Flip Game</h1>
        <Timer time={time} />
        <MemoryGame />
      </main>
    </div>
  );
};

export default App;
