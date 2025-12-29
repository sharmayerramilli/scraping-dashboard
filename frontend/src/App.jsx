import { Routes, Route } from "react-router-dom";
import Home from "./components/Home";
import ZomatoUpload from "./components/ZomatoUpload";
import SwiggyUpload from "./components/SwiggyUpload";
import BlinkitUpload from "./components/BlinkitUpload";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/platform/zomato" element={<ZomatoUpload />} />
      <Route path="/platform/swiggy" element={<SwiggyUpload />} />
      <Route path="/platform/blinkit" element={<BlinkitUpload />} />
    </Routes>
  );
}

export default App;