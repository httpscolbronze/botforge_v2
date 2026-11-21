import { useEffect, useState } from 'react';
import ClientMode from './pages/ClientMode.jsx';
import HostMode from './pages/HostMode.jsx';

const MODE_KEY = 'botforge.mode';

export default function App() {
  const [mode, setMode] = useState(() => {
    const stored = localStorage.getItem(MODE_KEY);
    return stored === 'host' ? 'host' : 'client';
  });

  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode);
  }, [mode]);

  if (mode === 'host') return <HostMode onSwitchMode={() => setMode('client')} />;
  return <ClientMode onSwitchMode={() => setMode('host')} />;
}
