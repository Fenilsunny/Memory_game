import MemoryGame from "./components/MemoryGame";
import NavBar from "./components/Navbar";
import "./css/App.css";

const App = () => {
  return (
    <div>
      <NavBar />
      <main className="main-content">
        <MemoryGame />
      </main>
    </div>
  );
};

export default App;
