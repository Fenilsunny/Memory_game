import { useState, useEffect } from "react";
import "../css/Timer.css";

const Timer = ({ time }) => {
  return (
    <div className="timer">
      <h2>Time: {time}s</h2>
    </div>
  );
};

export default Timer;
