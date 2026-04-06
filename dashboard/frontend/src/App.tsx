import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Portfolio from './pages/Portfolio';
import Trades from './pages/Trades';
import Agents from './pages/Agents';
import Research from './pages/Research';
import Control from './pages/Control';
import NewsMonitor from './pages/NewsMonitor';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Portfolio />} />
          <Route path="/trades" element={<Trades />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/agents/:ticker/:date" element={<Agents />} />
          <Route path="/research" element={<Research />} />
          <Route path="/news-monitor" element={<NewsMonitor />} />
          <Route path="/control" element={<Control />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
