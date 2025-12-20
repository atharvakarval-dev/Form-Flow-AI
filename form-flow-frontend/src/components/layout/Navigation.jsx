import { Link, useLocation } from 'react-router-dom';
import { ROUTES } from '@/constants';

/**
 * Navigation - Global navigation bar component
 */
const Navigation = () => {
    const location = useLocation();

    return (
        <nav className="fixed top-6 right-8 z-[100] flex items-center gap-2 bg-white/40 backdrop-blur-xl px-2 py-2 rounded-full border border-white/20 shadow-lg shadow-black/5">
            <a href={ROUTES.HOME} className="px-4 py-2 rounded-full text-gray-600 hover:text-black hover:bg-white/50 transition-all font-medium text-sm tracking-wide">Home</a>

            {localStorage.getItem('token') ? (
                <>
                    <Link to={ROUTES.DASHBOARD} className="px-4 py-2 rounded-full text-gray-600 hover:text-black hover:bg-white/50 transition-all font-medium text-sm tracking-wide">Dashboard</Link>
                    <div className="w-px h-4 bg-gray-300 mx-1"></div>
                    <button
                        onClick={() => {
                            localStorage.removeItem('token');
                            window.location.href = ROUTES.LOGIN;
                        }}
                        className="flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 hover:bg-red-500/20 text-red-600 border border-red-500/10 text-sm font-medium transition-all ml-1"
                    >
                        Sign Out
                    </button>
                </>
            ) : (
                <>
                    {/* Hide "Login" link if on /login */}
                    {location.pathname !== ROUTES.LOGIN && (
                        <Link to={ROUTES.LOGIN} className="px-4 py-2 rounded-full text-gray-600 hover:text-black hover:bg-white/50 transition-all font-medium text-sm tracking-wide">Login</Link>
                    )}

                    {/* Hide "Sign Up" button if on /register */}
                    {location.pathname !== ROUTES.REGISTER && (
                        <Link to={ROUTES.REGISTER} className="px-5 py-2.5 rounded-full bg-black hover:bg-gray-900 text-white text-sm font-medium transition-all shadow-lg shadow-black/20 ml-1">
                            Sign Up
                        </Link>
                    )}
                </>
            )}
        </nav>
    );
};

export default Navigation;
