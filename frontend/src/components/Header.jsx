import { useAuth } from '../context/AuthContext';
import { LogOut, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="h-14 bg-dark-800 border-b border-dark-700 flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm">
          <User className="w-4 h-4 text-gray-400" />
          <span className="text-gray-300">{user?.full_name || user?.username}</span>
          <span className="badge badge-info capitalize">{user?.role}</span>
        </div>
        <button onClick={handleLogout} className="btn-secondary flex items-center gap-2 text-sm">
          <LogOut className="w-4 h-4" />
          Salir
        </button>
      </div>
    </header>
  );
}
