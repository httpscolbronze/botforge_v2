import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { api } from '../services/api.js';
import HostLogin from '../components/HostDashboard/HostLogin.jsx';
import HostDashboard from '../components/HostDashboard/HostDashboard.jsx';

export default function HostMode({ onSwitchMode }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    if (!api.getAdminToken()) {
      setChecking(false);
      return undefined;
    }
    api
      .session()
      .then((data) => {
        if (!active) return;
        if (data.authenticated) {
          setAuthenticated(true);
        } else {
          api.clearAdminToken();
          setAuthenticated(false);
        }
      })
      .catch((err) => {
        if (!active) return;
        api.clearAdminToken();
        setAuthenticated(false);
        setError(err.message);
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const logout = (message = '') => {
    api.clearAdminToken();
    setAuthenticated(false);
    setError(message);
  };

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 size={16} className="animate-spin text-electric-400" />
          Verifying administrator session…
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <HostLogin
        initialError={error}
        onSwitchMode={onSwitchMode}
        onSuccess={() => {
          setError('');
          setAuthenticated(true);
        }}
      />
    );
  }

  return <HostDashboard onLogout={logout} onSwitchMode={onSwitchMode} />;
}
