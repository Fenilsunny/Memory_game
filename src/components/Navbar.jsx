import "../css/NavBar.css";
import { useState } from "react";

const NavBar = () => {
  const [menuOpen, setMenuOpen] = useState(false);

  const toggleMenu = () => {
    setMenuOpen(!menuOpen);
  };

  return (
    <header className="app-header">
      <div className="app-container">
        <div className="app-logo">
          {/* <img src="/logo.png" alt="Logo" className="app-logo-image" /> */}
          <span className="app-title">Memory Flip Game</span>
        </div>

        {/* Desktop navigation */}
        <nav className="desktop-nav md:block">
          <ul>
            <li>
              <a href="/" className="desktop-nav-link">
                Home
              </a>
            </li>
            <li>
              <a href="/leaderboard" className="desktop-nav-link">
                Leaderboard
              </a>
            </li>
            <li>
              <a href="/about" className="desktop-nav-link">
                About
              </a>
            </li>
          </ul>
        </nav>

        {/* Mobile navigation */}
        <button onClick={toggleMenu} className="mobile-menu-button md:hidden">
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M4 6h16M4 12h16M4 18h16"
            ></path>
          </svg>
        </button>
      </div>

      {/* Mobile dropdown menu */}
      <nav className={`mobile-menu ${menuOpen ? "show" : ""}`}>
        <ul>
          <li>
            <a href="/" className="mobile-menu-link">
              Home
            </a>
          </li>
          <li>
            <a href="/leaderboard" className="mobile-menu-link">
              Leaderboard
            </a>
          </li>
          <li>
            <a href="/about" className="mobile-menu-link">
              About
            </a>
          </li>
        </ul>
      </nav>
    </header>
  );
};

export default NavBar;
